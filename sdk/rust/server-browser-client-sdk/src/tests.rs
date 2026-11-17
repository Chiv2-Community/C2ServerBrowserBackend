use super::LifecycleEvent as Event;
use super::*;
use models::{RegistrationResponse, ServerResponse, UpdateResponse};
use std::collections::VecDeque;

fn http_failure<E>(failure: RequestFailure) -> HttpError<E> {
    match failure {
        RequestFailure::Http(status) => HttpError::ResponseError(Box::new(ResponseContent {
            status: reqwest::StatusCode::from_u16(status).unwrap(),
            content: "private-response-body".into(),
            entity: None,
        })),
        RequestFailure::InvalidResponse => {
            HttpError::Serde(serde_json::from_str::<serde_json::Value>("invalid").unwrap_err())
        }
        RequestFailure::Transport => HttpError::Reqwest(
            reqwest::Client::new()
                .get("invalid://")
                .build()
                .unwrap_err(),
        ),
    }
}

fn lifecycle_only(
    mut observe: impl FnMut(&LifecycleEvent),
) -> impl FnMut(&super::Event<'_>) -> ObserverResult {
    move |event| {
        if let super::Event::Lifecycle(event) = event {
            observe(event);
        }
        Ok(())
    }
}

impl<T: RegistrationTransport, C: Clock> Registration<T, C> {
    async fn run_lifecycle(
        &mut self,
        control: &RegistrationControl,
        observe: impl FnMut(&LifecycleEvent),
    ) -> Result<(), SdkError> {
        self.run(control, lifecycle_only(observe)).await
    }
}

impl<T: RegistrationTransport, C: Clock> RegistrationWorker<T, C> {
    async fn run_lifecycle(&self, observe: impl FnMut(&LifecycleEvent)) -> Result<(), SdkError> {
        self.run(lifecycle_only(observe)).await
    }
}

#[derive(Default)]
struct Value<T>(Mutex<T>);
impl<T: Copy> Value<T> {
    fn get(&self) -> T {
        *self.0.lock().unwrap()
    }
    fn set(&self, value: T) {
        *self.0.lock().unwrap() = value;
    }
}

#[derive(Clone)]
struct TestClock {
    now: Arc<Value<Instant>>,
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
    calls: Mutex<Vec<&'static str>>,
    failures: Mutex<VecDeque<RequestFailure>>,
    sequence: Value<u32>,
    lifetime: Value<f64>,
    heartbeat: Value<f64>,
    blocked: Mutex<Option<&'static str>>,
    entered: Notify,
    release: Notify,
}
impl Fake {
    async fn call(&self, name: &'static str) -> Result<(), RequestFailure> {
        self.calls.lock().unwrap().push(name);
        let blocked = *self.blocked.lock().unwrap() == Some(name);
        if blocked {
            self.entered.notify_one();
            self.release.notified().await;
        }
        self.failures
            .lock()
            .unwrap()
            .pop_front()
            .map_or(Ok(()), Err)
    }
    fn server(&self) -> ServerResponse {
        ServerResponse {
            unique_id: self.sequence.get().to_string(),
            last_heartbeat: self.heartbeat.get(),
            ..Default::default()
        }
    }
}
impl RegistrationTransport for Arc<Fake> {
    async fn register(
        &self,
        _: ServerRegistrationRequest,
    ) -> Result<RegistrationResponse, HttpError<RegisterError>> {
        self.call("register").await.map_err(http_failure)?;
        self.sequence.set(self.sequence.get() + 1);
        self.heartbeat.set(2_000_000_000.0);
        Ok(RegistrationResponse::new(
            "secret-test-key".into(),
            self.server().last_heartbeat + self.lifetime.get(),
            self.server(),
        ))
    }
    async fn heartbeat(
        &self,
        _: &str,
        key: &str,
    ) -> Result<UpdateResponse, HttpError<HeartbeatError>> {
        assert_eq!(key, "secret-test-key");
        self.call("heartbeat").await.map_err(http_failure)?;
        self.heartbeat.set(self.heartbeat.get() + 30.0);
        Ok(UpdateResponse::new(
            self.server().last_heartbeat + self.lifetime.get(),
            self.server(),
        ))
    }
    async fn update(
        &self,
        _: &str,
        _: &str,
        _: UpdateRegisteredServer,
    ) -> Result<UpdateResponse, HttpError<UpdateError>> {
        self.call("update").await.map_err(http_failure)?;
        self.heartbeat.set(self.heartbeat.get() + 1.0);
        Ok(UpdateResponse::new(
            self.server().last_heartbeat + self.lifetime.get(),
            self.server(),
        ))
    }
    async fn delete(
        &self,
        _: &str,
        _: &str,
    ) -> Result<StatusResponse, HttpError<DeleteServerError>> {
        self.call("delete").await.map_err(http_failure)?;
        Ok(StatusResponse::default())
    }
}

struct Fixture {
    registration: Registration<Arc<Fake>, TestClock>,
    transport: Arc<Fake>,
    clock: TestClock,
}

fn fixture() -> Fixture {
    let transport = Arc::new(Fake::default());
    transport.lifetime.set(65.0);
    let clock = TestClock {
        now: Arc::new(Value(Mutex::new(Instant::now()))),
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

#[tokio::test]
async fn lifecycle_coalesces_updates_schedules_heartbeats_and_deletes_once() {
    let Fixture {
        mut registration,
        transport,
        clock,
    } = fixture();
    assert_eq!(
        registration.poll().await,
        Ok(Event::Registered {
            server_id: "1".into()
        })
    );
    assert_eq!(registration.next_delay(), Some(Duration::from_secs(30)));
    assert_eq!(
        registration.poll().await,
        Ok(Event::Waiting(Duration::from_secs(30)))
    );
    registration
        .set_update(UpdateRegisteredServer::new(1, 32, "first".into()))
        .unwrap();
    registration
        .set_update(UpdateRegisteredServer::new(2, 32, "second".into()))
        .unwrap();
    assert_eq!(registration.poll().await, Ok(Event::Updated));
    clock.advance(30);
    assert_eq!(registration.poll().await, Ok(Event::Heartbeat));
    registration.stop().await.unwrap();
    registration.stop().await.unwrap();
    assert_eq!(registration.poll().await, Err(SdkError::Stopped));
    assert_eq!(
        *transport.calls.lock().unwrap(),
        ["register", "update", "heartbeat", "delete"]
    );
    assert!(!format!("{registration:?}").contains("secret-test-key"));
}

#[tokio::test]
async fn identical_metadata_does_not_send_updates_or_postpone_heartbeats() {
    let Fixture {
        mut registration,
        transport,
        clock,
    } = fixture();
    registration.poll().await.unwrap();
    let mut metadata = UpdateRegisteredServer::new(2, 32, "map".into());
    metadata.mods = Some(vec![models::Mod::new(
        "mod".into(),
        "org".into(),
        "1".into(),
    )]);
    registration.set_update(metadata.clone()).unwrap();
    assert_eq!(registration.poll().await, Ok(Event::Updated));
    for _ in 0..2 {
        let deadline = registration.next_attempt;
        for step in 1..=6 {
            clock.advance(5);
            let mut duplicate = metadata.clone();
            if step % 2 == 0 {
                duplicate.mods = None;
            }
            registration.set_update(duplicate).unwrap();
            assert_eq!(registration.next_attempt, deadline);
            assert_eq!(
                registration.poll().await,
                Ok(if step == 6 {
                    Event::Heartbeat
                } else {
                    Event::Waiting(Duration::from_secs(30 - step * 5))
                })
            );
        }
    }
    assert_eq!(
        *transport.calls.lock().unwrap(),
        ["register", "update", "heartbeat", "heartbeat"]
    );
    metadata.mods = Some(Vec::new());
    registration.set_update(metadata).unwrap();
    assert_eq!(registration.poll().await, Ok(Event::Updated));
}

#[tokio::test]
async fn worker_ignores_duplicate_metadata_and_uses_heartbeat() {
    let Fixture {
        registration,
        transport,
        clock,
    } = fixture();
    let worker = registration.into_worker();
    worker
        .run_lifecycle(|event| match event {
            Event::Registered { .. } => {
                let metadata = UpdateRegisteredServer::default();
                assert!(worker.set_update(metadata.clone()));
                assert!(worker.set_update(metadata));
                clock.advance(30);
            }
            Event::Heartbeat => worker.cancel(),
            event => panic!("unexpected event: {event:?}"),
        })
        .await
        .unwrap();
    assert_eq!(
        *transport.calls.lock().unwrap(),
        ["register", "heartbeat", "delete"]
    );
}

#[tokio::test]
async fn retries_keep_identity_and_do_not_let_updates_bypass_backoff() {
    let Fixture {
        mut registration,
        transport,
        clock,
    } = fixture();
    registration.poll().await.unwrap();
    clock.advance(30);
    transport
        .failures
        .lock()
        .unwrap()
        .extend([RequestFailure::Transport, RequestFailure::Http(503)]);
    assert_eq!(
        registration.poll().await,
        Ok(Event::RetryScheduled(Duration::from_secs(10)))
    );
    registration
        .set_update(UpdateRegisteredServer::new(1, 32, "next".into()))
        .unwrap();
    assert_eq!(registration.next_delay(), Some(Duration::from_secs(10)));
    clock.advance(10);
    assert_eq!(
        registration.poll().await,
        Ok(Event::RetryScheduled(Duration::from_secs(20)))
    );
    clock.advance(20);
    assert_eq!(registration.poll().await, Ok(Event::Updated));
    assert_eq!(registration.server_id(), Some("1"));
    assert_eq!(transport.sequence.get(), 1);
}

#[tokio::test]
async fn continuous_metadata_updates_renew_without_separate_heartbeats() {
    let Fixture {
        mut registration,
        transport,
        clock,
    } = fixture();
    registration.poll().await.unwrap();
    let original_heartbeat = transport.server().last_heartbeat;
    for second in 1..=60 {
        clock.advance(1);
        registration
            .set_update(UpdateRegisteredServer::new(second, 64, "next".into()))
            .unwrap();
        let before = transport.calls.lock().unwrap().len();
        assert_eq!(registration.poll().await, Ok(Event::Updated));
        assert_eq!(transport.calls.lock().unwrap().len(), before + 1);
        assert_eq!(registration.next_delay(), Some(Duration::from_secs(30)));
        assert!(transport.server().last_heartbeat > original_heartbeat);
    }
    assert_eq!(
        transport
            .calls
            .lock()
            .unwrap()
            .iter()
            .filter(|call| **call == "heartbeat")
            .count(),
        0
    );
    assert_eq!(registration.server_id(), Some("1"));
}

#[tokio::test]
async fn metadata_renewal_respects_backoff() {
    let Fixture {
        mut registration,
        transport,
        clock,
    } = fixture();
    registration.poll().await.unwrap();
    clock.advance(25);
    registration
        .set_update(UpdateRegisteredServer::new(1, 32, "first".into()))
        .unwrap();
    transport
        .failures
        .lock()
        .unwrap()
        .push_back(RequestFailure::Http(503));
    assert_eq!(
        registration.poll().await,
        Ok(Event::RetryScheduled(Duration::from_secs(10)))
    );
    clock.advance(5);
    registration
        .set_update(UpdateRegisteredServer::new(2, 32, "latest".into()))
        .unwrap();
    assert_eq!(
        registration.poll().await,
        Ok(Event::Waiting(Duration::from_secs(5)))
    );
    assert_eq!(*transport.calls.lock().unwrap(), ["register", "update"]);
    clock.advance(5);
    assert_eq!(registration.poll().await, Ok(Event::Updated));
    assert_eq!(
        registration.poll().await,
        Ok(Event::Waiting(Duration::from_secs(30)))
    );
    assert_eq!(
        *transport.calls.lock().unwrap(),
        ["register", "update", "update"]
    );
}

#[tokio::test]
async fn expired_registration_recovers_but_rejected_credentials_halt() {
    let Fixture {
        mut registration,
        transport,
        clock,
    } = fixture();
    registration.poll().await.unwrap();
    clock.advance(30);
    transport
        .failures
        .lock()
        .unwrap()
        .push_back(RequestFailure::Http(404));
    assert_eq!(registration.poll().await, Ok(Event::RegistrationLost));
    assert_eq!(registration.server_id(), None);
    assert_eq!(
        registration.poll().await,
        Ok(Event::Registered {
            server_id: "2".into()
        })
    );
    clock.advance(30);
    transport
        .failures
        .lock()
        .unwrap()
        .push_back(RequestFailure::Http(403));
    assert_eq!(registration.poll().await, Err(SdkError::Rejected(403)));
    assert_eq!(registration.poll().await, Err(SdkError::Rejected(403)));
    assert_eq!(registration.server_id(), Some("2"));
    registration.stop().await.unwrap();
}

#[tokio::test]
async fn ambiguous_registration_is_never_retried() {
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
        transport.failures.lock().unwrap().push_back(failure);
        assert_eq!(
            registration.poll().await,
            Err(SdkError::RegistrationUncertain)
        );
        assert_eq!(
            registration.poll().await,
            Err(SdkError::RegistrationUncertain)
        );
        registration.stop().await.unwrap();
        assert_eq!(*transport.calls.lock().unwrap(), ["register"]);
    }
}

#[tokio::test]
async fn throttled_registration_retries_with_a_bound() {
    let Fixture {
        mut registration,
        transport,
        clock,
    } = fixture();
    registration.policy.maximum_failures = 3;
    registration.policy.maximum_backoff = Duration::from_secs(15);
    transport
        .failures
        .lock()
        .unwrap()
        .extend([RequestFailure::Http(429); 3]);
    assert_eq!(
        registration.poll().await,
        Ok(Event::RetryScheduled(Duration::from_secs(10)))
    );
    clock.advance(10);
    assert_eq!(
        registration.poll().await,
        Ok(Event::RetryScheduled(Duration::from_secs(15)))
    );
    clock.advance(15);
    assert_eq!(registration.poll().await, Err(SdkError::RetriesExhausted));
    assert_eq!(registration.next_delay(), None);
}

#[tokio::test]
async fn short_leases_use_server_time_and_invalid_leases_halt() {
    let Fixture {
        mut registration,
        transport,
        ..
    } = fixture();
    transport.lifetime.set(4.0);
    registration.poll().await.unwrap();
    assert_eq!(registration.next_delay(), Some(Duration::from_secs(2)));
    for lifetime in [0.0, -1.0, f64::NAN, f64::INFINITY] {
        let Fixture {
            mut registration,
            transport,
            ..
        } = fixture();
        transport.lifetime.set(lifetime);
        assert_eq!(registration.poll().await, Err(SdkError::InvalidLease));
        registration.stop().await.unwrap();
        assert_eq!(*transport.calls.lock().unwrap(), ["register", "delete"]);
    }
}

#[tokio::test]
async fn cancellation_cleans_up_and_control_is_single_run() {
    let Fixture {
        mut registration,
        transport,
        ..
    } = fixture();
    let control = RegistrationControl::default();
    registration
        .run_lifecycle(&control, |_| control.cancel())
        .await
        .unwrap();
    assert_eq!(*transport.calls.lock().unwrap(), ["register", "delete"]);
    assert!(!control.publish(UpdateRegisteredServer::default()));
    let Fixture {
        mut registration,
        transport,
        ..
    } = fixture();
    registration
        .run_lifecycle(&control, |_| panic!("cancelled before start"))
        .await
        .unwrap();
    assert!(transport.calls.lock().unwrap().is_empty());
}

#[tokio::test]
async fn worker_accepts_updates_and_owns_cleanup() {
    let Fixture {
        registration,
        transport,
        ..
    } = fixture();
    let worker = registration.into_worker();
    worker
        .run_lifecycle(|event| match event {
            Event::Registered { .. } => {
                assert!(worker.set_update(UpdateRegisteredServer::new(1, 32, "next".into())));
            }
            Event::Updated => worker.cancel(),
            event => panic!("unexpected event: {event:?}"),
        })
        .await
        .unwrap();
    assert_eq!(
        *transport.calls.lock().unwrap(),
        ["register", "update", "delete"]
    );
    assert!(!worker.set_update(UpdateRegisteredServer::default()));
    assert_eq!(
        worker.run_lifecycle(|_| panic!("second run")).await,
        Err(SdkError::Stopped)
    );
}

#[tokio::test]
async fn worker_renews_without_metadata_and_cleans_up_terminal_errors() {
    let Fixture {
        registration,
        transport,
        clock,
    } = fixture();
    let worker = registration.into_worker();
    assert_eq!(
        worker
            .run_lifecycle(|event| match event {
                Event::Registered { .. } => clock.advance(30),
                Event::Heartbeat => {
                    transport
                        .failures
                        .lock()
                        .unwrap()
                        .push_back(RequestFailure::Http(403));
                    clock.advance(30);
                }
                event => panic!("unexpected event: {event:?}"),
            })
            .await,
        Err(SdkError::Rejected(403))
    );
    assert_eq!(
        *transport.calls.lock().unwrap(),
        ["register", "heartbeat", "heartbeat", "delete"]
    );
    assert!(!worker.set_update(UpdateRegisteredServer::default()));
}

#[tokio::test]
async fn worker_shutdown_finishes_registration_before_deleting() {
    let Fixture {
        registration,
        transport,
        ..
    } = fixture();
    *transport.blocked.lock().unwrap() = Some("register");
    let worker = registration.into_worker();
    let shutdown = async {
        transport.entered.notified().await;
        assert_eq!(
            worker.run_lifecycle(|_| panic!("concurrent run")).await,
            Err(SdkError::Stopped)
        );
        worker.cancel();
        assert_eq!(*transport.calls.lock().unwrap(), ["register"]);
        transport.release.notify_one();
    };
    let (result, ()) = tokio::join!(worker.run_lifecycle(|_| {}), shutdown);
    assert_eq!(result, Ok(()));
    assert_eq!(*transport.calls.lock().unwrap(), ["register", "delete"]);
}

#[tokio::test]
async fn aborted_worker_never_restarts_an_uncertain_registration() {
    let Fixture {
        registration,
        transport,
        ..
    } = fixture();
    *transport.blocked.lock().unwrap() = Some("register");
    let worker = registration.into_worker();
    interrupt(worker.run_lifecycle(|_| {}), &transport.entered).await;
    assert!(!worker.set_update(UpdateRegisteredServer::default()));
    assert_eq!(
        worker.run_lifecycle(|_| panic!("restarted")).await,
        Err(SdkError::Stopped)
    );
    assert_eq!(*transport.calls.lock().unwrap(), ["register"]);
}

#[tokio::test]
async fn observer_covers_each_http_operation_before_lifecycle_events() {
    let Fixture {
        registration,
        transport,
        clock,
    } = fixture();
    let mut observed = Vec::new();
    let worker = registration.into_worker();
    worker
        .run(|event| {
            match event {
                super::Event::Http(http) => {
                    assert!(!format!("{event:?}").contains("secret-test-key"));
                    observed.push(match http {
                        HttpEvent::Register(response) => {
                            assert_eq!(response.as_ref().unwrap().server.unique_id, "1");
                            "register"
                        }
                        HttpEvent::Update(response) => {
                            assert!(response.is_ok());
                            "update"
                        }
                        HttpEvent::Heartbeat(response) => {
                            assert!(response.is_ok());
                            "heartbeat"
                        }
                        HttpEvent::Delete(response) => {
                            assert!(response.is_ok());
                            "delete"
                        }
                    });
                }
                super::Event::Lifecycle(Event::Registered { .. }) => {
                    assert_eq!(observed.last(), Some(&"register"));
                    assert!(worker.set_update(UpdateRegisteredServer::new(1, 32, "map".into())));
                }
                super::Event::Lifecycle(Event::Updated) => {
                    assert_eq!(observed.last(), Some(&"update"));
                    clock.advance(30);
                }
                super::Event::Lifecycle(Event::Heartbeat) => {
                    assert_eq!(observed.last(), Some(&"heartbeat"));
                    worker.cancel();
                }
                event @ super::Event::Lifecycle(_) => panic!("unexpected event: {event:?}"),
            }
            Ok(())
        })
        .await
        .unwrap();
    assert_eq!(observed, *transport.calls.lock().unwrap());
    assert_eq!(observed, ["register", "update", "heartbeat", "delete"]);
}

#[tokio::test]
async fn observer_errors_halt_the_worker_and_cleanup_remains_single_shot() {
    for operation in ["register", "update", "heartbeat", "delete", "lifecycle"] {
        let Fixture {
            registration,
            transport,
            clock,
        } = fixture();
        let worker = registration.into_worker();
        let result = worker
            .run(|event| {
                let reject = matches!(
                    (operation, event),
                    ("register", super::Event::Http(HttpEvent::Register(_)))
                        | ("update", super::Event::Http(HttpEvent::Update(_)))
                        | ("heartbeat", super::Event::Http(HttpEvent::Heartbeat(_)))
                        | ("delete", super::Event::Http(HttpEvent::Delete(_)))
                        | ("lifecycle", super::Event::Lifecycle(_))
                );
                if reject {
                    return Err("private-observer-error".into());
                }
                if let super::Event::Lifecycle(Event::Registered { .. }) = event {
                    match operation {
                        "update" => {
                            assert!(worker.set_update(UpdateRegisteredServer::new(
                                1,
                                32,
                                "map".into()
                            )));
                        }
                        "heartbeat" => clock.advance(30),
                        "delete" => worker.cancel(),
                        _ => panic!("event after observer failure"),
                    }
                }
                Ok(())
            })
            .await;
        assert_eq!(result, Err(SdkError::ObserverFailed));
        assert_eq!(transport.calls.lock().unwrap().last(), Some(&"delete"));
        assert_eq!(
            transport
                .calls
                .lock()
                .unwrap()
                .iter()
                .filter(|call| **call == "delete")
                .count(),
            1
        );
        assert_eq!(
            worker.run(|_| panic!("restarted")).await,
            Err(SdkError::Stopped)
        );
        assert!(!format!("{worker:?} {result:?}").contains("private-observer-error"));
    }
}

#[tokio::test]
async fn observers_receive_http_failures_before_retry_events() {
    let Fixture {
        registration,
        transport,
        clock,
    } = fixture();
    transport
        .failures
        .lock()
        .unwrap()
        .push_back(RequestFailure::Http(429));
    let mut observed = Vec::new();
    let worker = registration.into_worker();
    worker
        .run(|event| {
            match event {
                super::Event::Http(HttpEvent::Register(response)) => {
                    observed.push(
                        response
                            .as_ref()
                            .map(|_| ())
                            .map_err(|error| RequestFailure::from_error(error)),
                    );
                }
                super::Event::Http(HttpEvent::Delete(_)) => {}
                super::Event::Lifecycle(Event::RetryScheduled(_)) => {
                    assert_eq!(observed, [Err(RequestFailure::Http(429))]);
                    clock.advance(10);
                }
                super::Event::Lifecycle(Event::Registered { .. }) => worker.cancel(),
                event => panic!("unexpected event: {event:?}"),
            }
            Ok(())
        })
        .await
        .unwrap();
    assert_eq!(observed, [Err(RequestFailure::Http(429)), Ok(())]);
}

#[tokio::test]
async fn cleanup_reports_failure_without_logging_secrets_or_retrying() {
    let Fixture {
        mut registration,
        transport,
        ..
    } = fixture();
    registration.poll().await.unwrap();
    transport
        .failures
        .lock()
        .unwrap()
        .push_back(RequestFailure::Transport);
    assert_eq!(
        registration.stop().await,
        Err(SdkError::CleanupFailed(RequestFailure::Transport))
    );
    assert_eq!(registration.poll().await, Err(SdkError::Stopped));
    assert_eq!(registration.next_delay(), None);
    registration.stop().await.unwrap();
    assert_eq!(*transport.calls.lock().unwrap(), ["register", "delete"]);
}

#[tokio::test]
async fn stopping_overrides_terminal_failure_and_blocks_future_work() {
    let Fixture {
        mut registration,
        transport,
        clock,
    } = fixture();
    registration.poll().await.unwrap();
    clock.advance(30);
    transport
        .failures
        .lock()
        .unwrap()
        .push_back(RequestFailure::Http(403));
    assert_eq!(registration.poll().await, Err(SdkError::Rejected(403)));
    assert_eq!(registration.next_delay(), None);
    assert_eq!(
        registration.set_update(UpdateRegisteredServer::default()),
        Err(SdkError::Rejected(403))
    );
    registration.stop().await.unwrap();
    assert_eq!(registration.server_id(), None);
    assert_eq!(registration.next_delay(), None);
    assert_eq!(registration.poll().await, Err(SdkError::Stopped));
    assert_eq!(
        registration.set_update(UpdateRegisteredServer::default()),
        Err(SdkError::Stopped)
    );
    registration.stop().await.unwrap();
    assert_eq!(
        *transport.calls.lock().unwrap(),
        ["register", "heartbeat", "delete"]
    );
}

#[tokio::test]
async fn stopping_before_registration_never_performs_network_io() {
    let Fixture {
        mut registration,
        transport,
        ..
    } = fixture();
    registration.stop().await.unwrap();
    assert_eq!(registration.next_delay(), None);
    assert_eq!(registration.poll().await, Err(SdkError::Stopped));
    assert_eq!(
        registration.set_update(UpdateRegisteredServer::default()),
        Err(SdkError::Stopped)
    );
    assert!(transport.calls.lock().unwrap().is_empty());
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
        let transport = Arc::new(Fake::default());
        assert!(matches!(
            Registration::new(
                transport.clone(),
                ServerRegistrationRequest::default(),
                policy
            ),
            Err(SdkError::InvalidPolicy)
        ));
        assert!(transport.calls.lock().unwrap().is_empty());
    }
}

async fn interrupt(future: impl std::future::Future, entered: &Notify) {
    tokio::select! {
        biased;
        _ = future => panic!("request unexpectedly completed"),
        () = entered.notified() => {},
    }
}

#[tokio::test]
async fn dropping_unpolled_registration_has_no_side_effect() {
    let Fixture {
        mut registration,
        transport,
        ..
    } = fixture();
    drop(registration.poll());
    assert!(transport.calls.lock().unwrap().is_empty());
    assert!(registration.terminal_error.is_none());
    registration.poll().await.unwrap();
}

#[tokio::test]
async fn interrupted_registration_never_blindly_registers_again() {
    let Fixture {
        mut registration,
        transport,
        ..
    } = fixture();
    *transport.blocked.lock().unwrap() = Some("register");
    interrupt(registration.poll(), &transport.entered).await;
    assert_eq!(
        registration.poll().await,
        Err(SdkError::RegistrationUncertain)
    );
    assert_eq!(registration.next_delay(), None);
    registration.stop().await.unwrap();
    assert_eq!(*transport.calls.lock().unwrap(), ["register"]);
}

#[tokio::test]
async fn interrupted_renewals_keep_identity_and_unpublished_metadata() {
    for operation in ["heartbeat", "update"] {
        let Fixture {
            mut registration,
            transport,
            clock,
        } = fixture();
        registration.poll().await.unwrap();
        clock.advance(30);
        if operation == "update" {
            registration
                .set_update(UpdateRegisteredServer::new(1, 32, "new".into()))
                .unwrap();
        }
        let published = registration.published.clone();
        let deadline = registration.next_attempt;
        *transport.blocked.lock().unwrap() = Some(operation);
        interrupt(registration.poll(), &transport.entered).await;
        assert_eq!(registration.server_id(), Some("1"));
        assert_eq!(registration.published, published);
        assert_eq!(registration.next_attempt, deadline);
        *transport.blocked.lock().unwrap() = None;
        let event = registration.poll().await.unwrap();
        assert_eq!(
            event,
            if operation == "update" {
                Event::Updated
            } else {
                Event::Heartbeat
            }
        );
        assert_eq!(transport.sequence.get(), 1);
    }
}

#[tokio::test]
async fn interrupted_cleanup_is_still_single_shot() {
    let Fixture {
        mut registration,
        transport,
        ..
    } = fixture();
    registration.poll().await.unwrap();
    *transport.blocked.lock().unwrap() = Some("delete");
    interrupt(registration.stop(), &transport.entered).await;
    assert_eq!(registration.server_id(), None);
    assert_eq!(registration.poll().await, Err(SdkError::Stopped));
    registration.stop().await.unwrap();
    assert_eq!(*transport.calls.lock().unwrap(), ["register", "delete"]);
}

#[tokio::test]
async fn spawned_driver_waits_without_blocking_and_observes_notifications() {
    let Fixture {
        mut registration,
        transport,
        ..
    } = fixture();
    let control = RegistrationControl::default();
    let worker_control = control.clone();
    let (events, mut received) = tokio::sync::mpsc::unbounded_channel();
    let worker = tokio::spawn(async move {
        registration
            .run_lifecycle(&worker_control, |event| events.send(event.clone()).unwrap())
            .await
    });
    tokio::time::timeout(Duration::from_secs(1), async {
        assert!(matches!(
            received.recv().await,
            Some(Event::Registered { .. })
        ));
        assert!(control.publish(UpdateRegisteredServer::new(1, 32, "notified".into())));
        assert_eq!(received.recv().await, Some(Event::Updated));
        control.cancel();
        worker.await.unwrap().unwrap();
    })
    .await
    .unwrap();
    assert_eq!(
        *transport.calls.lock().unwrap(),
        ["register", "update", "delete"]
    );
}

#[tokio::test]
async fn cancellation_finishes_in_flight_requests_and_cleans_up_once() {
    for operation in ["register", "heartbeat", "update", "delete"] {
        let Fixture {
            mut registration,
            transport,
            clock,
        } = fixture();
        let control = RegistrationControl::default();
        if operation != "register" {
            registration.poll().await.unwrap();
            clock.advance(30);
            if operation == "update" {
                registration
                    .set_update(UpdateRegisteredServer::new(1, 32, "pending".into()))
                    .unwrap();
            } else if operation == "delete" {
                control.cancel();
            }
        }
        *transport.blocked.lock().unwrap() = Some(operation);
        let worker_control = control.clone();
        let worker =
            tokio::spawn(async move { registration.run_lifecycle(&worker_control, |_| {}).await });
        tokio::time::timeout(Duration::from_secs(1), async {
            transport.entered.notified().await;
            control.cancel();
            tokio::task::yield_now().await;
            assert!(!worker.is_finished());
            transport.release.notify_one();
            worker.await.unwrap().unwrap();
        })
        .await
        .unwrap();
        let expected = match operation {
            "register" | "delete" => vec!["register", "delete"],
            _ => vec!["register", operation, "delete"],
        };
        assert_eq!(*transport.calls.lock().unwrap(), expected);
    }
}
