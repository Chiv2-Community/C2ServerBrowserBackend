//! Handwritten registration lifecycle on top of generated protocol bindings.
#![doc = include_str!("../README.md")]
#![deny(missing_docs, missing_debug_implementations)]
pub mod transport;
pub use server_browser_models as models;
pub use transport::{HttpTransport, RegistrationTransport, RequestFailure};

use models::{
    RegistrationResponse, ServerRegistrationRequest, UpdateRegisteredServer, UpdateResponse,
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
    /// A response listener rejected a response; its error details are not logged.
    ListenerFailed,
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
pub enum Event {
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

/// Response callbacks can halt the driver without exposing their error details.
pub type ListenerResult = Result<(), Box<dyn std::error::Error + Send + Sync>>;

type ResponseListener<R> = Box<dyn FnMut(Result<&R, RequestFailure>) -> ListenerResult + Send>;
type DeletionListener = Box<dyn FnMut(Result<(), RequestFailure>) -> ListenerResult + Send>;

#[derive(Default)]
struct ResponseListeners {
    registration: Vec<ResponseListener<RegistrationResponse>>,
    heartbeat: Vec<ResponseListener<UpdateResponse>>,
    update: Vec<ResponseListener<UpdateResponse>>,
    deletion: Vec<DeletionListener>,
}

fn notify<R>(
    listeners: &mut [ResponseListener<R>],
    response: Result<&R, RequestFailure>,
) -> Result<(), SdkError> {
    for listener in listeners {
        listener(response).map_err(|_| SdkError::ListenerFailed)?;
    }
    Ok(())
}

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
    listeners: ResponseListeners,
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
    /// Add a listener for each registration HTTP result, including failed attempts.
    /// Success responses contain a secret key: never log the complete response.
    /// Listeners run synchronously in insertion order; an error halts the lifecycle.
    pub fn add_registration_response_listener(
        &mut self,
        listener: impl FnMut(Result<&RegistrationResponse, RequestFailure>) -> ListenerResult
            + Send
            + 'static,
    ) {
        self.listeners.registration.push(Box::new(listener));
    }

    /// Add a listener for each heartbeat HTTP result; errors halt the lifecycle.
    pub fn add_heartbeat_response_listener(
        &mut self,
        listener: impl FnMut(Result<&UpdateResponse, RequestFailure>) -> ListenerResult + Send + 'static,
    ) {
        self.listeners.heartbeat.push(Box::new(listener));
    }

    /// Add a listener for each metadata-update HTTP result; errors halt the lifecycle.
    pub fn add_update_response_listener(
        &mut self,
        listener: impl FnMut(Result<&UpdateResponse, RequestFailure>) -> ListenerResult + Send + 'static,
    ) {
        self.listeners.update.push(Box::new(listener));
    }

    /// Add a listener for the single deletion HTTP result, including failure or 404.
    /// A listener error is returned to the driver; deletion is never repeated.
    pub fn add_deletion_response_listener(
        &mut self,
        listener: impl FnMut(Result<(), RequestFailure>) -> ListenerResult + Send + 'static,
    ) {
        self.listeners.deletion.push(Box::new(listener));
    }

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
            listeners: ResponseListeners::default(),
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

    /// Coalesce metadata changes without bypassing an active retry backoff.
    ///
    /// # Errors
    /// Returns the terminal lifecycle error if halted or stopped.
    pub fn set_update(&mut self, update: UpdateRegisteredServer) -> Result<(), SdkError> {
        self.check_running()?;
        self.request.player_count = update.player_count;
        self.request.max_players = update.max_players;
        self.request.current_map = update.current_map;
        if update.mods.is_some() {
            self.request.mods = update.mods;
        }
        if self.identity.is_some()
            && self.failures == 0
            && self.published.as_ref() != Some(&self.snapshot())
        {
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
        self.published = Some(self.snapshot());
        Ok(())
    }

    fn retry(&mut self) -> Result<Event, SdkError> {
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
        Ok(Event::RetryScheduled(delay))
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
    pub async fn poll(&mut self) -> Result<Event, SdkError> {
        self.check_running()?;
        let started = self.clock.now();
        if started < self.next_attempt {
            return Ok(Event::Waiting(self.next_attempt.duration_since(started)));
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
            notify(
                &mut self.listeners.registration,
                response.as_ref().map_err(|error| *error),
            )
            .map_err(|error| self.halt(error))?;
            return match response {
                Ok(response) => {
                    if self.identity.is_none() {
                        return Err(self.halt(SdkError::RegistrationUncertain));
                    }
                    self.renew(
                        started,
                        response.refresh_before,
                        response.server.last_heartbeat,
                    )?;
                    Ok(Event::Registered {
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
        let snapshot = self.snapshot();
        let changed = self.published.as_ref() != Some(&snapshot);
        let response = if changed {
            self.transport
                .update(&identity.id, &identity.key, snapshot)
                .await
        } else {
            self.transport.heartbeat(&identity.id, &identity.key).await
        };
        let listeners = if changed {
            &mut self.listeners.update
        } else {
            &mut self.listeners.heartbeat
        };
        if let Err(error) = notify(listeners, response.as_ref().map_err(|error| *error)) {
            return Err(self.halt(error));
        }
        match response {
            Ok(response) => {
                if response.server.unique_id != identity.id {
                    return Err(self.halt(SdkError::InvalidLease));
                }
                self.renew(
                    started,
                    response.refresh_before,
                    response.server.last_heartbeat,
                )?;
                Ok(if changed {
                    Event::Updated
                } else {
                    Event::Heartbeat
                })
            }
            Err(RequestFailure::Http(404)) => {
                self.identity = None;
                self.published = None;
                self.failures = 0;
                self.next_attempt = self.clock.now();
                Ok(Event::RegistrationLost)
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
        self.terminal_error = Some(SdkError::Stopped);
        match self.identity.take() {
            Some(identity) => {
                let response = self.transport.delete(&identity.id, &identity.key).await;
                for listener in &mut self.listeners.deletion {
                    listener(response).map_err(|_| SdkError::ListenerFailed)?;
                }
                match response {
                    Ok(()) | Err(RequestFailure::Http(404)) => Ok(()),
                    Err(error) => Err(SdkError::CleanupFailed(error)),
                }
            }
            None => Ok(()),
        }
    }

    /// Drive the lifecycle in the caller's Tokio task and runtime.
    /// Cancellation wakes waits promptly but lets an in-flight request finish;
    /// injected transports must bound request duration. No runtime is created.
    /// On error, call `stop` explicitly to attempt cleanup of a known registration.
    ///
    /// # Errors
    /// Returns lifecycle or cleanup failures from polling, updates, or shutdown.
    ///
    /// # Panics
    /// Panics if the control mutex was poisoned or the observer panics.
    pub async fn run(
        &mut self,
        control: &RegistrationControl,
        mut observe: impl FnMut(&Event),
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
                return self.stop().await;
            }
            if let Some(update) = update {
                self.set_update(update)?;
            }
            let event = self.poll().await?;
            if !matches!(event, Event::Waiting(_)) {
                observe(&event);
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
    pub async fn run(&self, observe: impl FnMut(&Event)) -> Result<(), SdkError> {
        let mut registration = self
            .registration
            .lock()
            .unwrap()
            .take()
            .ok_or(SdkError::Stopped)?;
        let _close = CloseOnDrop(self.control.clone());
        let result = registration.run(&self.control, observe).await;
        let cleanup = registration.stop().await;
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
        if update.mods.is_none() {
            update.mods = pending
                .update
                .as_ref()
                .and_then(|update| update.mods.clone());
        }
        pending.update = Some(update);
        drop(pending);
        self.inner.wake.notify_one();
        true
    }

    /// Wake the driver and request one cleanup attempt.
    ///
    /// # Panics
    /// Panics if the control mutex was poisoned.
    pub fn cancel(&self) {
        self.inner.pending.lock().unwrap().cancelled = true;
        self.inner.wake.notify_one();
    }
}
