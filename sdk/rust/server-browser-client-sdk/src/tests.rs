use super::*;
use models::{RegistrationResponse, ServerResponse, UpdateResponse};
use std::{
    cell::{Cell, RefCell},
    collections::VecDeque,
    rc::Rc,
};

#[derive(Clone)]
struct TestClock {
    now: Rc<Cell<Instant>>,
}
impl Clock for TestClock {
    fn now(&self) -> Instant {
        self.now.get()
    }
}
impl TestClock {
    fn advance(&self, seconds: u64) {
        self.now.set(self.now() + Duration::from_secs(seconds));
    }
}

#[derive(Default)]
struct Fake {
    calls: RefCell<Vec<&'static str>>,
    failures: RefCell<VecDeque<RequestFailure>>,
    sequence: Cell<u32>,
    lifetime: Cell<f64>,
    heartbeat: Cell<f64>,
}
impl Fake {
    fn call(&self, name: &'static str) -> Result<(), RequestFailure> {
        self.calls.borrow_mut().push(name);
        self.failures.borrow_mut().pop_front().map_or(Ok(()), Err)
    }
    fn server(&self) -> ServerResponse {
        ServerResponse {
            unique_id: self.sequence.get().to_string(),
            last_heartbeat: self.heartbeat.get(),
            ..Default::default()
        }
    }
}
impl RegistrationTransport for Rc<Fake> {
    fn register(
        &self,
        _: ServerRegistrationRequest,
    ) -> Result<RegistrationResponse, RequestFailure> {
        self.call("register")?;
        self.sequence.set(self.sequence.get() + 1);
        self.heartbeat.set(2_000_000_000.0);
        Ok(RegistrationResponse::new(
            "secret-test-key".into(),
            self.server().last_heartbeat + self.lifetime.get(),
            self.server(),
        ))
    }
    fn heartbeat(&self, _: &str, key: &str) -> Result<UpdateResponse, RequestFailure> {
        assert_eq!(key, "secret-test-key");
        self.call("heartbeat")?;
        self.heartbeat.set(self.heartbeat.get() + 30.0);
        Ok(UpdateResponse::new(
            self.server().last_heartbeat + self.lifetime.get(),
            self.server(),
        ))
    }
    fn update(
        &self,
        _: &str,
        _: &str,
        _: UpdateRegisteredServer,
    ) -> Result<UpdateResponse, RequestFailure> {
        self.call("update")?;
        self.heartbeat.set(self.heartbeat.get() + 1.0);
        Ok(UpdateResponse::new(
            self.server().last_heartbeat + self.lifetime.get(),
            self.server(),
        ))
    }
    fn delete(&self, _: &str, _: &str) -> Result<(), RequestFailure> {
        self.call("delete")
    }
}

struct Fixture {
    registration: Registration<Rc<Fake>, TestClock>,
    transport: Rc<Fake>,
    clock: TestClock,
}

fn fixture() -> Fixture {
    let transport = Rc::new(Fake::default());
    transport.lifetime.set(65.0);
    let clock = TestClock {
        now: Rc::new(Cell::new(Instant::now())),
    };
    let registration = Registration::with_clock(
        transport.clone(),
        ServerRegistrationRequest::default(),
        Policy::default(),
        clock.clone(),
    )
    .unwrap();
    Fixture {
        registration,
        transport,
        clock,
    }
}

#[test]
fn lifecycle_coalesces_updates_schedules_heartbeats_and_deletes_once() {
    let Fixture {
        mut registration,
        transport,
        clock,
    } = fixture();
    assert_eq!(
        registration.poll(),
        Ok(Event::Registered {
            server_id: "1".into()
        })
    );
    assert_eq!(registration.next_delay(), Some(Duration::from_secs(30)));
    assert_eq!(
        registration.poll(),
        Ok(Event::Waiting(Duration::from_secs(30)))
    );
    registration
        .set_update(UpdateRegisteredServer::new(1, 32, "first".into()))
        .unwrap();
    registration
        .set_update(UpdateRegisteredServer::new(2, 32, "second".into()))
        .unwrap();
    assert_eq!(registration.poll(), Ok(Event::Updated));
    clock.advance(30);
    assert_eq!(registration.poll(), Ok(Event::Heartbeat));
    registration.stop().unwrap();
    registration.stop().unwrap();
    assert_eq!(registration.poll(), Err(SdkError::Stopped));
    assert_eq!(
        *transport.calls.borrow(),
        ["register", "update", "heartbeat", "delete"]
    );
    assert!(!format!("{registration:?}").contains("secret-test-key"));
}

#[test]
fn retries_keep_identity_and_do_not_let_updates_bypass_backoff() {
    let Fixture {
        mut registration,
        transport,
        clock,
    } = fixture();
    registration.poll().unwrap();
    clock.advance(30);
    transport
        .failures
        .borrow_mut()
        .extend([RequestFailure::Transport, RequestFailure::Http(503)]);
    assert_eq!(
        registration.poll(),
        Ok(Event::RetryScheduled(Duration::from_secs(10)))
    );
    registration
        .set_update(UpdateRegisteredServer::new(1, 32, "next".into()))
        .unwrap();
    assert_eq!(registration.next_delay(), Some(Duration::from_secs(10)));
    clock.advance(10);
    assert_eq!(
        registration.poll(),
        Ok(Event::RetryScheduled(Duration::from_secs(20)))
    );
    clock.advance(20);
    assert_eq!(registration.poll(), Ok(Event::Updated));
    assert_eq!(registration.server_id(), Some("1"));
    assert_eq!(transport.sequence.get(), 1);
}

#[test]
fn continuous_metadata_updates_renew_without_separate_heartbeats() {
    let Fixture {
        mut registration,
        transport,
        clock,
    } = fixture();
    registration.poll().unwrap();
    let original_heartbeat = transport.server().last_heartbeat;
    for second in 1..=60 {
        clock.advance(1);
        registration
            .set_update(UpdateRegisteredServer::new(second, 64, "next".into()))
            .unwrap();
        let before = transport.calls.borrow().len();
        assert_eq!(registration.poll(), Ok(Event::Updated));
        assert_eq!(transport.calls.borrow().len(), before + 1);
        assert_eq!(registration.next_delay(), Some(Duration::from_secs(30)));
        assert!(transport.server().last_heartbeat > original_heartbeat);
    }
    assert_eq!(
        transport
            .calls
            .borrow()
            .iter()
            .filter(|call| **call == "heartbeat")
            .count(),
        0
    );
    assert_eq!(registration.server_id(), Some("1"));
}

#[test]
fn metadata_renewal_respects_backoff() {
    let Fixture {
        mut registration,
        transport,
        clock,
    } = fixture();
    registration.poll().unwrap();
    clock.advance(25);
    registration
        .set_update(UpdateRegisteredServer::new(1, 32, "first".into()))
        .unwrap();
    transport
        .failures
        .borrow_mut()
        .push_back(RequestFailure::Http(503));
    assert_eq!(
        registration.poll(),
        Ok(Event::RetryScheduled(Duration::from_secs(10)))
    );
    clock.advance(5);
    registration
        .set_update(UpdateRegisteredServer::new(2, 32, "latest".into()))
        .unwrap();
    assert_eq!(
        registration.poll(),
        Ok(Event::Waiting(Duration::from_secs(5)))
    );
    assert_eq!(*transport.calls.borrow(), ["register", "update"]);
    clock.advance(5);
    assert_eq!(registration.poll(), Ok(Event::Updated));
    assert_eq!(
        registration.poll(),
        Ok(Event::Waiting(Duration::from_secs(30)))
    );
    assert_eq!(*transport.calls.borrow(), ["register", "update", "update"]);
}

#[test]
fn expired_registration_recovers_but_rejected_credentials_halt() {
    let Fixture {
        mut registration,
        transport,
        clock,
    } = fixture();
    registration.poll().unwrap();
    clock.advance(30);
    transport
        .failures
        .borrow_mut()
        .push_back(RequestFailure::Http(404));
    assert_eq!(registration.poll(), Ok(Event::RegistrationLost));
    assert_eq!(registration.server_id(), None);
    assert_eq!(
        registration.poll(),
        Ok(Event::Registered {
            server_id: "2".into()
        })
    );
    clock.advance(30);
    transport
        .failures
        .borrow_mut()
        .push_back(RequestFailure::Http(403));
    assert_eq!(registration.poll(), Err(SdkError::Rejected(403)));
    assert_eq!(registration.poll(), Err(SdkError::Rejected(403)));
    assert_eq!(registration.server_id(), Some("2"));
    registration.stop().unwrap();
}

#[test]
fn ambiguous_registration_is_never_retried() {
    for failure in [
        RequestFailure::Transport,
        RequestFailure::InvalidResponse,
        RequestFailure::Http(500),
    ] {
        let Fixture {
            mut registration,
            transport,
            ..
        } = fixture();
        transport.failures.borrow_mut().push_back(failure);
        assert_eq!(registration.poll(), Err(SdkError::RegistrationUncertain));
        assert_eq!(registration.poll(), Err(SdkError::RegistrationUncertain));
        registration.stop().unwrap();
        assert_eq!(*transport.calls.borrow(), ["register"]);
    }
}

#[test]
fn throttled_registration_retries_with_a_bound() {
    let Fixture {
        mut registration,
        transport,
        clock,
    } = fixture();
    registration.policy.maximum_failures = 3;
    registration.policy.maximum_backoff = Duration::from_secs(15);
    transport
        .failures
        .borrow_mut()
        .extend([RequestFailure::Http(429); 3]);
    assert_eq!(
        registration.poll(),
        Ok(Event::RetryScheduled(Duration::from_secs(10)))
    );
    clock.advance(10);
    assert_eq!(
        registration.poll(),
        Ok(Event::RetryScheduled(Duration::from_secs(15)))
    );
    clock.advance(15);
    assert_eq!(registration.poll(), Err(SdkError::RetriesExhausted));
    assert_eq!(registration.next_delay(), None);
}

#[test]
fn short_leases_use_server_time_and_invalid_leases_halt() {
    let Fixture {
        mut registration,
        transport,
        ..
    } = fixture();
    transport.lifetime.set(4.0);
    registration.poll().unwrap();
    assert_eq!(registration.next_delay(), Some(Duration::from_secs(2)));
    for lifetime in [0.0, -1.0, f64::NAN, f64::INFINITY] {
        let Fixture {
            mut registration,
            transport,
            ..
        } = fixture();
        transport.lifetime.set(lifetime);
        assert_eq!(registration.poll(), Err(SdkError::InvalidLease));
        registration.stop().unwrap();
        assert_eq!(*transport.calls.borrow(), ["register", "delete"]);
    }
}

#[test]
fn cancellation_cleans_up_and_control_is_single_run() {
    let Fixture {
        mut registration,
        transport,
        ..
    } = fixture();
    let control = RegistrationControl::default();
    registration.run(&control, |_| control.cancel()).unwrap();
    assert_eq!(*transport.calls.borrow(), ["register", "delete"]);
    assert!(!control.publish(UpdateRegisteredServer::default()));
    let Fixture {
        mut registration,
        transport,
        ..
    } = fixture();
    registration
        .run(&control, |_| panic!("cancelled before start"))
        .unwrap();
    assert!(transport.calls.borrow().is_empty());
}

#[test]
fn cleanup_reports_failure_without_logging_secrets_or_retrying() {
    let Fixture {
        mut registration,
        transport,
        ..
    } = fixture();
    registration.poll().unwrap();
    transport
        .failures
        .borrow_mut()
        .push_back(RequestFailure::Transport);
    assert_eq!(
        registration.stop(),
        Err(SdkError::CleanupFailed(RequestFailure::Transport))
    );
    assert_eq!(registration.poll(), Err(SdkError::Stopped));
    assert_eq!(registration.next_delay(), None);
    registration.stop().unwrap();
    assert_eq!(*transport.calls.borrow(), ["register", "delete"]);
}

#[test]
fn stopping_overrides_terminal_failure_and_blocks_future_work() {
    let Fixture {
        mut registration,
        transport,
        clock,
    } = fixture();
    registration.poll().unwrap();
    clock.advance(30);
    transport
        .failures
        .borrow_mut()
        .push_back(RequestFailure::Http(403));
    assert_eq!(registration.poll(), Err(SdkError::Rejected(403)));
    assert_eq!(registration.next_delay(), None);
    assert_eq!(
        registration.set_update(UpdateRegisteredServer::default()),
        Err(SdkError::Rejected(403))
    );
    registration.stop().unwrap();
    assert_eq!(registration.server_id(), None);
    assert_eq!(registration.next_delay(), None);
    assert_eq!(registration.poll(), Err(SdkError::Stopped));
    assert_eq!(
        registration.set_update(UpdateRegisteredServer::default()),
        Err(SdkError::Stopped)
    );
    registration.stop().unwrap();
    assert_eq!(
        *transport.calls.borrow(),
        ["register", "heartbeat", "delete"]
    );
}

#[test]
fn stopping_before_registration_never_performs_network_io() {
    let Fixture {
        mut registration,
        transport,
        ..
    } = fixture();
    registration.stop().unwrap();
    assert_eq!(registration.next_delay(), None);
    assert_eq!(registration.poll(), Err(SdkError::Stopped));
    assert_eq!(
        registration.set_update(UpdateRegisteredServer::default()),
        Err(SdkError::Stopped)
    );
    assert!(transport.calls.borrow().is_empty());
}

#[test]
fn control_coalescing_preserves_omitted_mod_updates() {
    let control = RegistrationControl::default();
    let mut update = UpdateRegisteredServer::new(1, 32, "first".into());
    update.mods = Some(vec![models::Mod::new(
        "mod".into(),
        "org".into(),
        "1".into(),
    )]);
    assert!(control.publish(update));
    assert!(control.publish(UpdateRegisteredServer::new(2, 32, "next".into())));
    let pending = control.inner.pending.lock().unwrap();
    let update = pending.update.as_ref().unwrap();
    assert_eq!(update.player_count, 2);
    assert_eq!(update.mods.as_ref().unwrap()[0].name, "mod");
    drop(pending);
}

#[test]
fn invalid_policy_fails_before_network_io() {
    for policy in [
        Policy {
            heartbeat_interval: Duration::ZERO,
            ..Policy::default()
        },
        Policy {
            initial_backoff: Duration::ZERO,
            ..Policy::default()
        },
        Policy {
            maximum_backoff: Duration::from_secs(1),
            ..Policy::default()
        },
        Policy {
            maximum_failures: 0,
            ..Policy::default()
        },
    ] {
        let transport = Rc::new(Fake::default());
        assert!(matches!(
            Registration::new(
                transport.clone(),
                ServerRegistrationRequest::default(),
                policy
            ),
            Err(SdkError::InvalidPolicy)
        ));
        assert!(transport.calls.borrow().is_empty());
    }
}
