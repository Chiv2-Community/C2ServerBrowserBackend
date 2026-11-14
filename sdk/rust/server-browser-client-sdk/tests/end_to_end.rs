//! The Python test harness owns the isolated backend and loopback listener.
use server_browser_client::apis::{api_v1_api as api, configuration::Configuration};
use server_browser_client_sdk::{
    models::{Chivalry2Ports, ServerRegistrationRequest, UpdateRegisteredServer},
    Clock, Event, HttpTransport, Policy, Registration, RegistrationControl,
};
use std::{
    cell::Cell,
    time::{Duration, Instant},
};

struct TestClock(Cell<Instant>);
impl Clock for &TestClock {
    fn now(&self) -> Instant {
        self.0.get()
    }
}

#[test]
#[ignore = "run uv run pytest -q src/test/server_browser_backend/test_sdk_e2e.py"]
fn registration_sdk_against_python_backend() {
    let url = std::env::var("SDK_E2E_URL").expect("Python harness URL required");
    let configuration = Configuration {
        base_path: url,
        client: reqwest::blocking::Client::builder()
            .no_proxy()
            .timeout(Duration::from_secs(5))
            .redirect(reqwest::redirect::Policy::none())
            .build()
            .unwrap(),
        ..Configuration::default()
    };
    let request = ServerRegistrationRequest::new(
        Chivalry2Ports::new(7777, 7778, 7779),
        "SDK lifecycle".into(),
        "test".into(),
        "map".into(),
        0,
        32,
    );
    let transport = HttpTransport::from_configuration(configuration.clone());
    let clock = TestClock(Cell::new(Instant::now()));
    let mut registration = Registration::with_clock(
        transport.clone(),
        request.clone(),
        Policy::default(),
        &clock,
    )
    .unwrap();
    assert!(matches!(
        registration.poll().unwrap(),
        Event::Registered { .. }
    ));
    let id = registration.server_id().unwrap().to_owned();
    registration
        .set_update(UpdateRegisteredServer::new(2, 32, "next".into()))
        .unwrap();
    assert_eq!(registration.poll(), Ok(Event::Updated));
    let listing = api::get_servers(&configuration).unwrap();
    let value = serde_json::to_value(&listing.servers[0]).unwrap();
    assert_eq!(value["unique_id"], id);
    assert_eq!(value["player_count"], 2);
    assert_eq!(value["current_map"], "next");
    clock.0.set(clock.0.get() + Duration::from_secs(31));
    assert_eq!(registration.poll(), Ok(Event::Heartbeat));

    registration.stop().unwrap();
    assert!(api::get_servers(&configuration).unwrap().servers.is_empty());

    // The blocking driver coalesces updates and cancels without waiting a lease.
    let mut registration = Registration::new(transport, request, Policy::default()).unwrap();
    let control = RegistrationControl::default();
    let mut events = Vec::new();
    registration
        .run(&control, |event| {
            events.push(event.clone());
            match event {
                Event::Registered { .. } => {
                    control.publish(UpdateRegisteredServer::new(3, 32, "driver".into()));
                }
                Event::Updated => control.cancel(),
                _ => panic!("unexpected lifecycle event"),
            }
        })
        .unwrap();
    assert_eq!(events.len(), 2);
    assert!(api::get_servers(&configuration).unwrap().servers.is_empty());
}
