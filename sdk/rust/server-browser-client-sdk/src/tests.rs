use super::*;
use models::{RegistrationResponse, ServerResponse, UpdateResponse};
use std::{
    cell::{Cell, RefCell},
    collections::VecDeque,
    rc::Rc,
};

#[derive(Clone)]
struct TestClock(Rc<Cell<Instant>>);
impl Clock for TestClock {
    fn now(&self) -> Instant {
        self.0.get()
    }
}
impl TestClock {
    fn advance(&self, seconds: u64) {
        self.0.set(self.now() + Duration::from_secs(seconds));
    }
}

#[derive(Default)]
struct Fake {
    calls: RefCell<Vec<&'static str>>,
    failures: RefCell<VecDeque<RequestFailure>>,
    sequence: Cell<u32>,
    lifetime: Cell<f64>,
}
impl Fake {
    fn call(&self, name: &'static str) -> Result<(), RequestFailure> {
        self.calls.borrow_mut().push(name);
        self.failures.borrow_mut().pop_front().map_or(Ok(()), Err)
    }
    fn server(&self) -> ServerResponse {
        ServerResponse {
            unique_id: self.sequence.get().to_string(),
            last_heartbeat: 2_000_000_000.0,
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
        Ok(RegistrationResponse::new(
            "secret-test-key".into(),
            self.server().last_heartbeat + self.lifetime.get(),
            self.server(),
        ))
    }
    fn heartbeat(&self, _: &str, key: &str) -> Result<UpdateResponse, RequestFailure> {
        assert_eq!(key, "secret-test-key");
        self.call("heartbeat")?;
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
        Ok(UpdateResponse::new(
            self.server().last_heartbeat + self.lifetime.get(),
            self.server(),
        ))
    }
    fn delete(&self, _: &str, _: &str) -> Result<(), RequestFailure> {
        self.call("delete")
    }
}

fn fixture() -> (Registration<Rc<Fake>, TestClock>, Rc<Fake>, TestClock) {
    let transport = Rc::new(Fake::default());
    transport.lifetime.set(65.0);
    let clock = TestClock(Rc::new(Cell::new(Instant::now())));
    let registration = Registration::with_clock(
        transport.clone(),
        ServerRegistrationRequest::default(),
        Policy::default(),
        clock.clone(),
    )
    .unwrap();
    (registration, transport, clock)
}

#[test]
fn lifecycle_coalesces_updates_schedules_heartbeats_and_deletes_once() {
    let (mut registration, transport, clock) = fixture();
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
    let (mut registration, transport, clock) = fixture();
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
fn expired_registration_recovers_but_rejected_credentials_halt() {
    let (mut registration, transport, clock) = fixture();
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
        let (mut registration, transport, _) = fixture();
        transport.failures.borrow_mut().push_back(failure);
        assert_eq!(registration.poll(), Err(SdkError::RegistrationUncertain));
        assert_eq!(registration.poll(), Err(SdkError::RegistrationUncertain));
        registration.stop().unwrap();
        assert_eq!(*transport.calls.borrow(), ["register"]);
    }
}

#[test]
fn throttled_registration_retries_with_a_bound() {
    let (mut registration, transport, clock) = fixture();
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
    let (mut registration, transport, _) = fixture();
    transport.lifetime.set(4.0);
    registration.poll().unwrap();
    assert_eq!(registration.next_delay(), Some(Duration::from_secs(2)));
    for lifetime in [0.0, -1.0, f64::NAN, f64::INFINITY] {
        let (mut registration, transport, _) = fixture();
        transport.lifetime.set(lifetime);
        assert_eq!(registration.poll(), Err(SdkError::InvalidLease));
        registration.stop().unwrap();
        assert_eq!(*transport.calls.borrow(), ["register", "delete"]);
    }
}

#[test]
fn cancellation_cleans_up_and_control_is_single_run() {
    let (mut registration, transport, _) = fixture();
    let control = RegistrationControl::default();
    registration.run(&control, |_| control.cancel()).unwrap();
    assert_eq!(*transport.calls.borrow(), ["register", "delete"]);
    assert!(!control.publish(UpdateRegisteredServer::default()));
    let (mut registration, transport, _) = fixture();
    registration
        .run(&control, |_| panic!("cancelled before start"))
        .unwrap();
    assert!(transport.calls.borrow().is_empty());
}

#[test]
fn cleanup_reports_failure_without_logging_secrets_or_retrying() {
    let (mut registration, transport, _) = fixture();
    registration.poll().unwrap();
    transport
        .failures
        .borrow_mut()
        .push_back(RequestFailure::Transport);
    assert_eq!(
        registration.stop(),
        Err(SdkError::CleanupFailed(RequestFailure::Transport))
    );
    registration.stop().unwrap();
    assert_eq!(*transport.calls.borrow(), ["register", "delete"]);
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
    let pending = control.inner.0.lock().unwrap();
    let update = pending.update.as_ref().unwrap();
    assert_eq!(update.player_count, 2);
    assert_eq!(update.mods.as_ref().unwrap()[0].name, "mod");
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
