//! Handwritten registration lifecycle on top of generated protocol bindings.
#![doc = include_str!("../README.md")]
pub mod transport;
pub use server_browser_models as models;
pub use transport::{HttpTransport, RegistrationTransport, RequestFailure};

use models::{ServerRegistrationRequest, UpdateRegisteredServer};
use std::{
    sync::{Arc, Condvar, Mutex},
    time::{Duration, Instant},
};

pub trait Clock {
    fn now(&self) -> Instant;
}

pub struct SystemClock;
impl Clock for SystemClock {
    fn now(&self) -> Instant {
        Instant::now()
    }
}

#[derive(Clone, Debug)]
pub struct Policy {
    pub heartbeat_interval: Duration,
    pub safety_margin: Duration,
    pub initial_backoff: Duration,
    pub maximum_backoff: Duration,
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

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SdkError {
    InvalidPolicy,
    InvalidLease,
    Rejected(u16),
    RegistrationUncertain,
    RetriesExhausted,
    CleanupFailed(RequestFailure),
    Stopped,
}

impl std::fmt::Display for SdkError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{self:?}")
    }
}
impl std::error::Error for SdkError {}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Event {
    Registered { server_id: String },
    Updated,
    Heartbeat,
    RegistrationLost,
    RetryScheduled(Duration),
    Waiting(Duration),
}

struct Identity {
    id: String,
    key: String,
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
    failure: Option<SdkError>,
    stopped: bool,
}

impl<T, C> std::fmt::Debug for Registration<T, C> {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Registration")
            .field("registered", &self.identity.is_some())
            .field("failure", &self.failure)
            .field("stopped", &self.stopped)
            .finish_non_exhaustive()
    }
}

impl<T: RegistrationTransport> Registration<T> {
    pub fn new(
        transport: T,
        request: ServerRegistrationRequest,
        policy: Policy,
    ) -> Result<Self, SdkError> {
        Self::with_clock(transport, request, policy, SystemClock)
    }
}

impl<T: RegistrationTransport, C: Clock> Registration<T, C> {
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
            failure: None,
            stopped: false,
        })
    }

    pub fn server_id(&self) -> Option<&str> {
        self.identity.as_ref().map(|identity| identity.id.as_str())
    }

    pub fn next_delay(&self) -> Option<Duration> {
        if self.stopped || self.failure.is_some() {
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

    fn check_running(&self) -> Result<(), SdkError> {
        if self.stopped {
            Err(SdkError::Stopped)
        } else if let Some(error) = self.failure {
            Err(error)
        } else {
            Ok(())
        }
    }

    fn halt(&mut self, error: SdkError) -> SdkError {
        self.failure = Some(error);
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
    pub fn poll(&mut self) -> Result<Event, SdkError> {
        self.check_running()?;
        let started = self.clock.now();
        if started < self.next_attempt {
            return Ok(Event::Waiting(self.next_attempt.duration_since(started)));
        }
        let Some(identity) = self.identity.as_ref() else {
            return match self.transport.register(self.request.clone()) {
                Ok(response) => {
                    if response.server.unique_id.is_empty()
                        || response.key.is_empty()
                        || !response
                            .key
                            .bytes()
                            .all(|byte| (0x21..=0x7e).contains(&byte))
                    {
                        return Err(self.halt(SdkError::RegistrationUncertain));
                    }
                    self.identity = Some(Identity {
                        id: response.server.unique_id.clone(),
                        key: response.key,
                    });
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
            self.transport.update(&identity.id, &identity.key, snapshot)
        } else {
            self.transport.heartbeat(&identity.id, &identity.key)
        };
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
    pub fn stop(&mut self) -> Result<(), SdkError> {
        self.stopped = true;
        match self.identity.take() {
            Some(identity) => match self.transport.delete(&identity.id, &identity.key) {
                Ok(()) | Err(RequestFailure::Http(404)) => Ok(()),
                Err(error) => Err(SdkError::CleanupFailed(error)),
            },
            None => Ok(()),
        }
    }

    /// Drive the lifecycle on the calling thread; callers may spawn that thread.
    /// Cancellation wakes waits but cannot interrupt an in-flight HTTP request.
    /// On error, call `stop` explicitly to attempt cleanup of a known registration.
    pub fn run(
        &mut self,
        control: &RegistrationControl,
        mut observe: impl FnMut(&Event),
    ) -> Result<(), SdkError> {
        loop {
            let mut pending = control.inner.0.lock().unwrap();
            if pending.cancelled {
                drop(pending);
                return self.stop();
            }
            let update = pending.update.take();
            drop(pending);
            if let Some(update) = update {
                self.set_update(update)?;
            }
            let event = self.poll()?;
            if !matches!(event, Event::Waiting(_)) {
                observe(&event);
            }
            let delay = self.next_delay().ok_or(SdkError::Stopped)?;
            let pending = control.inner.0.lock().unwrap();
            drop(
                control
                    .inner
                    .1
                    .wait_timeout_while(pending, delay, |pending| {
                        !pending.cancelled && pending.update.is_none()
                    })
                    .unwrap(),
            );
        }
    }
}

#[cfg(test)]
mod tests;

#[derive(Default)]
struct Pending {
    cancelled: bool,
    update: Option<UpdateRegisteredServer>,
}

/// Cloneable, single-run cancellation/update handle. Only the latest update waits.
#[derive(Clone, Default)]
pub struct RegistrationControl {
    inner: Arc<(Mutex<Pending>, Condvar)>,
}

impl RegistrationControl {
    pub fn publish(&self, mut update: UpdateRegisteredServer) -> bool {
        let mut pending = self.inner.0.lock().unwrap();
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
        self.inner.1.notify_all();
        true
    }

    pub fn cancel(&self) {
        self.inner.0.lock().unwrap().cancelled = true;
        self.inner.1.notify_all();
    }
}
