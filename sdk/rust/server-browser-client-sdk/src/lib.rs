//! Handwritten registration lifecycle on top of generated protocol bindings.
#![doc = include_str!("../README.md")]
#![deny(missing_docs, missing_debug_implementations)]
pub mod compatibility;
pub mod transport;
pub use server_browser_models as models;
pub use transport::{
    DeleteServerError, HeartbeatError, HttpError, HttpTransport, RegisterError,
    RegistrationTransport, RequestFailure, ResponseContent, UpdateError,
};

use models::{
    RegistrationResponse, ServerRegistrationRequest, StatusResponse, UpdateRegisteredServer,
    UpdateResponse,
};
use std::{
    sync::{Arc, Mutex},
    time::{Duration, Instant},
};
use tokio::sync::Notify;

/// Supplies monotonic time for lifecycle scheduling.
pub trait Clock {
    /// Return the current monotonic instant.
    fn now(&self) -> Instant;
}

/// Uses the host's monotonic clock.
#[derive(Clone, Copy, Debug, Default)]
pub struct SystemClock;
impl Clock for SystemClock {
    fn now(&self) -> Instant {
        Instant::now()
    }
}

/// Scheduling and bounded-retry configuration.
#[derive(Clone, Debug)]
pub struct Policy {
    /// Maximum interval between successful lease renewals.
    pub heartbeat_interval: Duration,
    /// Time reserved before the server's lease deadline.
    pub safety_margin: Duration,
    /// Delay after the first retryable failure.
    pub initial_backoff: Duration,
    /// Upper bound for exponential retry delays.
    pub maximum_backoff: Duration,
    /// Number of consecutive failures that halts the lifecycle.
    pub maximum_failures: u32,
}

impl Default for Policy {
    fn default() -> Self {
        Self {
            heartbeat_interval: Duration::from_secs(30),
            safety_margin: Duration::from_secs(5),
            initial_backoff: Duration::from_secs(10),
            maximum_backoff: Duration::from_secs(300),
            maximum_failures: 8,
        }
    }
}

/// Credential-safe terminal lifecycle failures.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SdkError {
    /// Scheduling or retry bounds are invalid.
    InvalidPolicy,
    /// A lease is invalid or identifies another registration.
    InvalidLease,
    /// The backend rejected the request with this HTTP status.
    Rejected(u16),
    /// Registration may have succeeded without returning a usable identity.
    RegistrationUncertain,
    /// Consecutive failures reached the policy limit.
    RetriesExhausted,
    /// The single best-effort deletion failed.
    CleanupFailed(RequestFailure),
    /// An observer rejected an event; its error details are not logged.
    ObserverFailed,
    /// The manager has been stopped.
    Stopped,
}

impl std::fmt::Display for SdkError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{self:?}")
    }
}
impl std::error::Error for SdkError {}

/// Outcome of one lifecycle poll.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum LifecycleEvent {
    /// A new registration was established.
    Registered {
        /// Identifier assigned by the backend; never a credential.
        server_id: String,
    },
    /// Changed metadata was published and the lease renewed.
    Updated,
    /// Unchanged metadata's lease was renewed.
    Heartbeat,
    /// The backend no longer knows the identity; a later poll may register again.
    RegistrationLost,
    /// A retryable failure scheduled this delay.
    RetryScheduled(Duration),
    /// No request is due until this delay elapses.
    Waiting(Duration),
}

struct Identity {
    id: String,
    key: String,
}

/// HTTP completion by route, before lifecycle processing.
/// Payloads and generated errors may contain credentials; Debug output is redacted.
pub enum HttpEvent<'a> {
    /// POST /api/v1/servers.
    Register(Result<&'a RegistrationResponse, &'a HttpError<RegisterError>>),
    /// POST /api/v1/servers/{id}/heartbeat.
    Heartbeat(Result<&'a UpdateResponse, &'a HttpError<HeartbeatError>>),
    /// PUT /api/v1/servers/{id}.
    Update(Result<&'a UpdateResponse, &'a HttpError<UpdateError>>),
    /// DELETE /api/v1/servers/{id}, including an already-absent registration.
    Delete(Result<&'a StatusResponse, &'a HttpError<DeleteServerError>>),
}

impl std::fmt::Debug for HttpEvent<'_> {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let route = match self {
            Self::Register(_) => "Register",
            Self::Heartbeat(_) => "Heartbeat",
            Self::Update(_) => "Update",
            Self::Delete(_) => "Delete",
        };
        write!(formatter, "{route}([REDACTED])")
    }
}

/// Observer notifications; match only the categories and routes you need.
#[derive(Debug)]
pub enum Event<'a> {
    /// Credential-safe lifecycle outcome.
    Lifecycle(LifecycleEvent),
    /// Route-specific HTTP response or generated error.
    Http(HttpEvent<'a>),
}

/// Observers can halt the driver without exposing their error details.
pub type ObserverResult = Result<(), Box<dyn std::error::Error + Send + Sync>>;

/// One owner serializes registration, updates, heartbeat and cleanup.
pub struct Registration<T, C = SystemClock> {
    transport: T,
    clock: C,
    policy: Policy,
    request: ServerRegistrationRequest,
    identity: Option<Identity>,
    published: Option<UpdateRegisteredServer>,
    next_attempt: Instant,
    failures: u32,
    terminal_error: Option<SdkError>,
}

impl<T, C> std::fmt::Debug for Registration<T, C> {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Registration")
            .field("registered", &self.identity.is_some())
            .field("terminal_error", &self.terminal_error)
            .finish_non_exhaustive()
    }
}

impl<T: RegistrationTransport> Registration<T> {
    /// Construct a lifecycle manager using the system monotonic clock.
    ///
    /// # Errors
    /// Returns [`SdkError::InvalidPolicy`] for invalid scheduling or retry bounds.
    pub fn new(
        transport: T,
        request: ServerRegistrationRequest,
        policy: Policy,
    ) -> Result<Self, SdkError> {
        Self::with_clock(transport, request, policy, SystemClock)
    }
}

impl<T: RegistrationTransport, C: Clock> Registration<T, C> {
    /// Convert this manager into a single-run worker with concurrent metadata updates.
    /// The application owns the task and runtime that drive [`RegistrationWorker::run`].
    #[must_use]
    pub fn into_worker(self) -> RegistrationWorker<T, C> {
        RegistrationWorker {
            registration: Mutex::new(Some(self)),
            control: RegistrationControl::default(),
        }
    }

    /// Construct a lifecycle manager using an injected monotonic clock.
    ///
    /// # Errors
    /// Returns [`SdkError::InvalidPolicy`] for invalid scheduling or retry bounds.
    pub fn with_clock(
        transport: T,
        request: ServerRegistrationRequest,
        policy: Policy,
        clock: C,
    ) -> Result<Self, SdkError> {
        if policy.heartbeat_interval < Duration::from_millis(100)
            || policy.initial_backoff.is_zero()
            || policy.maximum_backoff < policy.initial_backoff
            || policy.maximum_failures == 0
        {
            return Err(SdkError::InvalidPolicy);
        }
        let next_attempt = clock.now();
        Ok(Self {
            transport,
            clock,
            policy,
            request,
            identity: None,
            published: None,
            next_attempt,
            failures: 0,
            terminal_error: None,
        })
    }

    /// Return the current backend identity, if one is known.
    pub fn server_id(&self) -> Option<&str> {
        self.identity.as_ref().map(|identity| identity.id.as_str())
    }

    /// Return the delay until another poll, or none after a terminal outcome.
    pub fn next_delay(&self) -> Option<Duration> {
        if self.terminal_error.is_some() {
            None
        } else {
            Some(
                self.next_attempt
                    .saturating_duration_since(self.clock.now()),
            )
        }
    }

    fn snapshot(&self) -> UpdateRegisteredServer {
        UpdateRegisteredServer {
            player_count: self.request.player_count,
            max_players: self.request.max_players,
            current_map: self.request.current_map.clone(),
            mods: self.request.mods.clone(),
        }
    }

    fn metadata_changed(&self) -> bool {
        self.published.as_ref().is_none_or(|published| {
            published.player_count != self.request.player_count
                || published.max_players != self.request.max_players
                || published.current_map != self.request.current_map
                || published.mods != self.request.mods
        })
    }

    /// Coalesce metadata changes without bypassing an active retry backoff.
    /// Identical effective metadata is ignored without changing the heartbeat deadline.
    ///
    /// # Errors
    /// Returns the terminal lifecycle error if halted or stopped.
    pub fn set_update(&mut self, update: UpdateRegisteredServer) -> Result<(), SdkError> {
        self.check_running()?;
        if update.player_count == self.request.player_count
            && update.max_players == self.request.max_players
            && update.current_map == self.request.current_map
            && update
                .mods
                .as_ref()
                .is_none_or(|mods| self.request.mods.as_ref() == Some(mods))
        {
            return Ok(());
        }
        self.request.player_count = update.player_count;
        self.request.max_players = update.max_players;
        self.request.current_map = update.current_map;
        if update.mods.is_some() {
            self.request.mods = update.mods;
        }
        if self.identity.is_some() && self.failures == 0 && self.metadata_changed() {
            self.next_attempt = self.clock.now();
        }
        Ok(())
    }

    const fn check_running(&self) -> Result<(), SdkError> {
        match self.terminal_error {
            Some(error) => Err(error),
            None => Ok(()),
        }
    }

    const fn halt(&mut self, error: SdkError) -> SdkError {
        self.terminal_error = Some(error);
        error
    }

    fn renew(
        &mut self,
        started: Instant,
        refresh_before: f64,
        heartbeat: f64,
    ) -> Result<(), SdkError> {
        // Subtract server timestamps, then use monotonic time: client/server wall
        // clock skew cannot move the schedule. Request start is conservative.
        let lifetime = Duration::try_from_secs_f64(refresh_before - heartbeat)
            .map_err(|_| self.halt(SdkError::InvalidLease))?;
        if lifetime < Duration::from_millis(200) {
            return Err(self.halt(SdkError::InvalidLease));
        }
        let remaining = lifetime.saturating_sub(self.policy.safety_margin);
        let interval = if remaining.is_zero() {
            lifetime / 2
        } else {
            remaining
        };
        self.next_attempt = started
            .checked_add(interval.min(self.policy.heartbeat_interval))
            .ok_or_else(|| self.halt(SdkError::InvalidLease))?;
        self.failures = 0;
        if self.metadata_changed() {
            self.published = Some(self.snapshot());
        }
        Ok(())
    }

    fn retry(&mut self) -> Result<LifecycleEvent, SdkError> {
        self.failures += 1;
        if self.failures >= self.policy.maximum_failures {
            return Err(self.halt(SdkError::RetriesExhausted));
        }
        let factor = 1_u32
            .checked_shl((self.failures - 1).min(31))
            .unwrap_or(u32::MAX);
        let delay = self
            .policy
            .initial_backoff
            .checked_mul(factor)
            .unwrap_or(self.policy.maximum_backoff)
            .min(self.policy.maximum_backoff);
        self.next_attempt = self
            .clock
            .now()
            .checked_add(delay)
            .ok_or_else(|| self.halt(SdkError::InvalidPolicy))?;
        Ok(LifecycleEvent::RetryScheduled(delay))
    }

    /// Make at most one request. Waiting never sleeps or performs network I/O.
    ///
    /// # Errors
    /// Returns a terminal lifecycle error for rejection, uncertain registration,
    /// invalid leases, exhausted retries, or polling after shutdown.
    ///
    /// # Cancellation
    /// Dropping an in-flight first registration halts with uncertainty. Dropping
    /// a renewal retains the known identity and previous publication schedule.
    pub async fn poll(&mut self) -> Result<LifecycleEvent, SdkError> {
        self.poll_observed(&mut |_| Ok(())).await
    }

    fn observe_http(
        &mut self,
        event: HttpEvent<'_>,
        observe: &mut impl FnMut(&Event<'_>) -> ObserverResult,
    ) -> Result<(), SdkError> {
        observe(&Event::Http(event)).map_err(|_| self.halt(SdkError::ObserverFailed))
    }

    async fn poll_observed(
        &mut self,
        observe: &mut impl FnMut(&Event<'_>) -> ObserverResult,
    ) -> Result<LifecycleEvent, SdkError> {
        self.check_running()?;
        let started = self.clock.now();
        if started < self.next_attempt {
            return Ok(LifecycleEvent::Waiting(
                self.next_attempt.duration_since(started),
            ));
        }
        let Some(identity) = self.identity.as_ref() else {
            // Persist uncertainty before suspension: dropping this future must
            // not permit another non-idempotent registration attempt.
            self.terminal_error = Some(SdkError::RegistrationUncertain);
            let response = self.transport.register(self.request.clone()).await;
            self.terminal_error = None;
            if let Ok(response) = &response {
                if !response.server.unique_id.is_empty()
                    && !response.key.is_empty()
                    && response
                        .key
                        .bytes()
                        .all(|byte| (0x21..=0x7e).contains(&byte))
                {
                    self.identity = Some(Identity {
                        id: response.server.unique_id.clone(),
                        key: response.key.clone(),
                    });
                }
            }
            self.observe_http(HttpEvent::Register(response.as_ref()), observe)?;
            return match response.map_err(|error| RequestFailure::from_error(&error)) {
                Ok(response) => {
                    if self.identity.is_none() {
                        return Err(self.halt(SdkError::RegistrationUncertain));
                    }
                    self.renew(
                        started,
                        response.refresh_before,
                        response.server.last_heartbeat,
                    )?;
                    Ok(LifecycleEvent::Registered {
                        server_id: response.server.unique_id,
                    })
                }
                Err(RequestFailure::Http(429)) => self.retry(),
                Err(RequestFailure::Http(status)) if (400..500).contains(&status) => {
                    Err(self.halt(SdkError::Rejected(status)))
                }
                // Registration is not idempotent. A lost response may strand a
                // live server whose key we never received; never blindly retry.
                Err(_) => Err(self.halt(SdkError::RegistrationUncertain)),
            };
        };
        let changed = self.metadata_changed();
        let response = if changed {
            let response = self
                .transport
                .update(&identity.id, &identity.key, self.snapshot())
                .await;
            self.observe_http(HttpEvent::Update(response.as_ref()), observe)?;
            response.map_err(|error| RequestFailure::from_error(&error))
        } else {
            let response = self.transport.heartbeat(&identity.id, &identity.key).await;
            self.observe_http(HttpEvent::Heartbeat(response.as_ref()), observe)?;
            response.map_err(|error| RequestFailure::from_error(&error))
        };
        match response {
            Ok(response) => {
                if self
                    .identity
                    .as_ref()
                    .is_none_or(|identity| response.server.unique_id != identity.id)
                {
                    return Err(self.halt(SdkError::InvalidLease));
                }
                self.renew(
                    started,
                    response.refresh_before,
                    response.server.last_heartbeat,
                )?;
                Ok(if changed {
                    LifecycleEvent::Updated
                } else {
                    LifecycleEvent::Heartbeat
                })
            }
            Err(RequestFailure::Http(404)) => {
                self.identity = None;
                self.published = None;
                self.failures = 0;
                self.next_attempt = self.clock.now();
                Ok(LifecycleEvent::RegistrationLost)
            }
            Err(RequestFailure::Http(status)) if (400..500).contains(&status) && status != 429 => {
                Err(self.halt(SdkError::Rejected(status)))
            }
            // Keep the known ID after a timeout, even beyond the last known
            // lease: the server may have renewed it before the response was lost.
            Err(_) => self.retry(),
        }
    }

    /// Exactly one best-effort deletion; no network I/O is hidden in Drop.
    ///
    /// # Errors
    /// Returns [`SdkError::CleanupFailed`] if deletion fails, except HTTP 404.
    ///
    /// # Cancellation
    /// Dropping this future after deletion starts never permits a second attempt.
    pub async fn stop(&mut self) -> Result<(), SdkError> {
        self.stop_observed(&mut |_| Ok(())).await
    }

    async fn stop_observed(
        &mut self,
        observe: &mut impl FnMut(&Event<'_>) -> ObserverResult,
    ) -> Result<(), SdkError> {
        self.terminal_error = Some(SdkError::Stopped);
        match self.identity.take() {
            Some(identity) => {
                let response = self.transport.delete(&identity.id, &identity.key).await;
                self.observe_http(HttpEvent::Delete(response.as_ref()), observe)?;
                match response.map_err(|error| RequestFailure::from_error(&error)) {
                    Ok(_) | Err(RequestFailure::Http(404)) => Ok(()),
                    Err(error) => Err(SdkError::CleanupFailed(error)),
                }
            }
            None => Ok(()),
        }
    }

    /// Drive the lifecycle in the caller's Tokio task and runtime.
    /// The observer receives HTTP completions and non-waiting lifecycle events.
    /// Cancellation wakes waits promptly but lets an in-flight request finish;
    /// injected transports must bound request duration. No runtime is created.
    /// On error, call `stop` explicitly to attempt cleanup of a known registration.
    ///
    /// # Errors
    /// Returns lifecycle, observer or cleanup failures from polling, updates, or shutdown.
    ///
    /// # Panics
    /// Panics if the control mutex was poisoned or the observer panics.
    pub async fn run(
        &mut self,
        control: &RegistrationControl,
        mut observe: impl FnMut(&Event<'_>) -> ObserverResult,
    ) -> Result<(), SdkError> {
        loop {
            // Register before checking shared state. A publication between the
            // check and await leaves a permit, so notifications cannot be lost.
            let notified = control.inner.wake.notified();
            tokio::pin!(notified);
            notified.as_mut().enable();
            let (cancelled, update) = {
                let mut pending = control.inner.pending.lock().unwrap();
                (pending.cancelled, pending.update.take())
            };
            if cancelled {
                return self.stop_observed(&mut observe).await;
            }
            if let Some(update) = update {
                self.set_update(update)?;
            }
            let event = self.poll_observed(&mut observe).await?;
            if !matches!(event, LifecycleEvent::Waiting(_)) {
                observe(&Event::Lifecycle(event))
                    .map_err(|_| self.halt(SdkError::ObserverFailed))?;
            }
            let delay = self.next_delay().ok_or(SdkError::Stopped)?;
            tokio::select! {
                () = &mut notified => {},
                () = tokio::time::sleep(delay) => {},
            }
        }
    }
}

#[cfg(test)]
mod tests;

/// SDK-owned lifecycle driver; callers publish metadata independently of HTTP work.
/// No tasks or runtimes are started implicitly.
pub struct RegistrationWorker<T, C = SystemClock> {
    registration: Mutex<Option<Registration<T, C>>>,
    control: RegistrationControl,
}

impl<T, C> std::fmt::Debug for RegistrationWorker<T, C> {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter.write_str("RegistrationWorker([REDACTED])")
    }
}

struct CloseOnDrop(RegistrationControl);

impl Drop for CloseOnDrop {
    fn drop(&mut self) {
        self.0.cancel();
    }
}

impl<T: RegistrationTransport, C: Clock> RegistrationWorker<T, C> {
    /// Publish the latest metadata without waiting for an in-flight HTTP request.
    /// Updates are coalesced and never bypass retry backoff.
    /// Returns false after cancellation or worker completion.
    ///
    /// # Panics
    /// Panics if the control mutex was poisoned.
    #[must_use]
    pub fn set_update(&self, update: UpdateRegisteredServer) -> bool {
        self.control.publish(update)
    }

    /// Request shutdown after any in-flight request finishes, then delete once.
    /// Await [`Self::run`] to complete graceful shutdown.
    ///
    /// # Panics
    /// Panics if the control mutex was poisoned.
    pub fn cancel(&self) {
        self.control.cancel();
    }

    /// Drive scheduling, retries and cleanup in the caller's task, once only.
    /// Cleanup is attempted on cancellation and terminal lifecycle errors.
    /// Aborting this future closes the worker; unknown or stranded identities
    /// are left to expire. Injected transports must bound request duration.
    ///
    /// # Errors
    /// Returns the lifecycle error, otherwise any cleanup failure. A second run
    /// returns [`SdkError::Stopped`] without touching the active worker.
    ///
    /// # Panics
    /// Panics if a mutex was poisoned or the observer panics.
    pub async fn run(
        &self,
        mut observe: impl FnMut(&Event<'_>) -> ObserverResult,
    ) -> Result<(), SdkError> {
        let mut registration = self
            .registration
            .lock()
            .unwrap()
            .take()
            .ok_or(SdkError::Stopped)?;
        let _close = CloseOnDrop(self.control.clone());
        let result = registration.run(&self.control, &mut observe).await;
        let cleanup = registration.stop_observed(&mut observe).await;
        result.and(cleanup)
    }
}

#[derive(Default)]
struct Pending {
    cancelled: bool,
    update: Option<UpdateRegisteredServer>,
}

/// Cloneable, single-run cancellation/update handle. Only the latest update waits.
#[derive(Clone, Default)]
pub struct RegistrationControl {
    inner: Arc<ControlState>,
}

impl std::fmt::Debug for RegistrationControl {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter.write_str("RegistrationControl([REDACTED])")
    }
}

#[derive(Default)]
struct ControlState {
    pending: Mutex<Pending>,
    wake: Notify,
}

impl RegistrationControl {
    /// Queue the latest update; return false after cancellation.
    ///
    /// # Panics
    /// Panics if the control mutex was poisoned.
    #[must_use]
    pub fn publish(&self, mut update: UpdateRegisteredServer) -> bool {
        let mut pending = self.inner.pending.lock().unwrap();
        if pending.cancelled {
            return false;
        }
        if let Some(queued) = pending.update.as_mut() {
            if *queued == update {
                return true;
            }
            if update.mods.is_none() {
                if queued.player_count == update.player_count
                    && queued.max_players == update.max_players
                    && queued.current_map == update.current_map
                {
                    return true;
                }
                update.mods = queued.mods.take();
            }
        }
        pending.update = Some(update);
        drop(pending);
        self.inner.wake.notify_one();
        true
    }

    /// Discard queued metadata, wake the driver and request one cleanup attempt.
    ///
    /// # Panics
    /// Panics if the control mutex was poisoned.
    pub fn cancel(&self) {
        let mut pending = self.inner.pending.lock().unwrap();
        pending.cancelled = true;
        pending.update = None;
        drop(pending);
        self.inner.wake.notify_one();
    }
}
