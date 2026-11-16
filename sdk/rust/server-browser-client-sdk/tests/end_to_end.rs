//! The Python test harness owns the isolated backend and loopback listener.
use server_browser_client::apis::{api_v1_api as api, configuration::Configuration};
use server_browser_client_sdk::{
    models::{Chivalry2Ports, ServerRegistrationRequest, UpdateRegisteredServer},
    Clock, Event, HttpTransport, Policy, Registration, SdkError,
};
use std::{
    cell::Cell,
    time::{Duration, Instant},
};

struct TestClock {
    now: Cell<Instant>,
}
impl Clock for &TestClock {
    fn now(&self) -> Instant {
        self.now.get()
    }
}

fn configuration() -> Configuration {
    let url = std::env::var("SDK_E2E_URL").expect("Python harness URL required");
    Configuration {
        base_path: url,
        ..Configuration::with_client(
            reqwest::Client::builder()
                .no_proxy()
                .timeout(Duration::from_secs(5))
                .redirect(reqwest::redirect::Policy::none())
                .build()
                .unwrap(),
        )
    }
}

fn request() -> ServerRegistrationRequest {
    ServerRegistrationRequest::new(
        Chivalry2Ports::new(7777, 7778, 7779),
        "SDK lifecycle".into(),
        "test".into(),
        "map".into(),
        0,
        32,
    )
}

#[tokio::test]
#[ignore = "run uv run pytest -q src/test/server_browser_backend/test_sdk_e2e.py"]
async fn registration_sdk_against_python_backend() {
    let configuration = configuration();
    let request = request();
    let transport = HttpTransport::from_configuration(configuration.clone());
    let clock = TestClock {
        now: Cell::new(Instant::now()),
    };
    let mut registration = Registration::with_clock(
        transport.clone(),
        request.clone(),
        Policy::default(),
        &clock,
    )
    .unwrap();
    assert!(matches!(
        registration.poll().await.unwrap(),
        Event::Registered { .. }
    ));
    let id = registration.server_id().unwrap().to_owned();
    registration
        .set_update(UpdateRegisteredServer::new(2, 32, "next".into()))
        .unwrap();
    assert_eq!(registration.poll().await, Ok(Event::Updated));
    let listing = api::get_servers(&configuration).await.unwrap();
    let value = serde_json::to_value(&listing.servers[0]).unwrap();
    assert_eq!(value["unique_id"], id);
    assert_eq!(value["player_count"], 2);
    assert_eq!(value["current_map"], "next");
    clock.now.set(clock.now.get() + Duration::from_secs(31));
    assert_eq!(registration.poll().await, Ok(Event::Heartbeat));

    registration.stop().await.unwrap();
    assert!(api::get_servers(&configuration)
        .await
        .unwrap()
        .servers
        .is_empty());

    // The async driver coalesces updates and cancels without waiting a lease.
    let registration = Registration::new(transport.clone(), request.clone(), Policy::default())
        .unwrap()
        .into_worker();
    let mut events = Vec::new();
    registration
        .run(|event| {
            events.push(event.clone());
            match event {
                Event::Registered { .. } => {
                    assert!(registration.set_update(UpdateRegisteredServer::new(
                        3,
                        32,
                        "driver".into()
                    )));
                }
                Event::Updated => registration.cancel(),
                _ => panic!("unexpected lifecycle event"),
            }
        })
        .await
        .unwrap();
    assert_eq!(events.len(), 2);
    let mut rejected = Registration::new(transport, request, Policy::default()).unwrap();
    rejected.add_registration_response_listener(|_| Err("listener rejected registration".into()));
    assert_eq!(
        rejected
            .into_worker()
            .run(|_| panic!("listener failure must halt the driver"))
            .await,
        Err(SdkError::ListenerFailed)
    );
    assert!(api::get_servers(&configuration)
        .await
        .unwrap()
        .servers
        .is_empty());
}

#[tokio::test]
#[ignore = "run uv run pytest -q src/test/server_browser_backend/test_sdk_e2e.py"]
async fn metadata_updates_renew_lease_without_heartbeats() {
    let configuration = configuration();
    let mut registration = Registration::new(
        HttpTransport::from_configuration(configuration.clone()),
        request(),
        Policy {
            heartbeat_interval: Duration::from_millis(100),
            safety_margin: Duration::from_millis(100),
            ..Policy::default()
        },
    )
    .unwrap();
    assert!(matches!(
        registration.poll().await.unwrap(),
        Event::Registered { .. }
    ));
    let id = registration.server_id().unwrap().to_owned();
    let started = Instant::now();
    let mut updates = 0;
    // The harness gives this registration a one-second lease. Metadata changes
    // arrive faster than heartbeats for longer than that original lease.
    while started.elapsed() < Duration::from_millis(1300) {
        registration
            .set_update(UpdateRegisteredServer::new(
                updates + 1,
                64,
                "changing".into(),
            ))
            .unwrap();
        match registration.poll().await.unwrap() {
            Event::Updated => updates += 1,
            event => panic!("unexpected event: {event:?}"),
        }
        assert_eq!(registration.server_id(), Some(id.as_str()));
        tokio::time::sleep(Duration::from_millis(40)).await;
    }
    assert!(updates >= 5);
    let listing = api::get_servers(&configuration).await.unwrap();
    assert_eq!(listing.servers.len(), 1);
    let server = serde_json::to_value(&listing.servers[0]).unwrap();
    assert_eq!(server["unique_id"], id);
    assert_eq!(server["player_count"], updates);
    assert_eq!(server["max_players"], 64);
    assert_eq!(server["current_map"], "changing");
    registration.stop().await.unwrap();
    assert!(api::get_servers(&configuration)
        .await
        .unwrap()
        .servers
        .is_empty());
}
