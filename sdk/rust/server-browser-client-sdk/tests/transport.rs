use server_browser_client_sdk::{
    models::{Chivalry2Ports, ServerRegistrationRequest, UpdateRegisteredServer},
    DeleteServerError, Event, HeartbeatError, HttpError, HttpEvent, HttpTransport, Policy,
    RegisterError, Registration, RegistrationTransport, RequestFailure, SdkError, UpdateError,
};
use wiremock::{
    matchers::{any, header, method, path},
    Mock, MockServer, ResponseTemplate,
};

#[test]
fn transport_debug_redacts_configuration() {
    let transport = HttpTransport::new("http://user:secret@127.0.0.1/private", None).unwrap();
    assert_eq!(format!("{transport:?}"), "HttpTransport([REDACTED])");
}

#[test]
fn user_agent_customization_preserves_base_path_and_redaction() {
    let transport = HttpTransport::new("http://user:secret@127.0.0.1/private///", None)
        .unwrap()
        .with_user_agent(String::from("private-user-agent"));
    assert_eq!(
        transport.configuration().base_path,
        "http://user:secret@127.0.0.1/private"
    );
    assert_eq!(
        transport.configuration().user_agent.as_deref(),
        Some("private-user-agent")
    );
    assert_eq!(format!("{transport:?}"), "HttpTransport([REDACTED])");
}

#[tokio::test]
async fn route_errors_preserve_typed_responses_bodies_and_summaries() {
    let server = MockServer::start().await;
    let body = r#"{"status":"error","message":"response-sentinel"}"#;
    for (verb, route) in [
        ("POST", "/api/v1/servers"),
        ("POST", "/api/v1/servers/id/heartbeat"),
        ("PUT", "/api/v1/servers/id"),
        ("DELETE", "/api/v1/servers/id"),
    ] {
        Mock::given(method(verb))
            .and(path(route))
            .respond_with(ResponseTemplate::new(403).set_body_raw(body, "application/json"))
            .expect(1)
            .mount(&server)
            .await;
    }
    let transport = HttpTransport::new(&server.uri(), None).unwrap();
    let register = transport
        .register(ServerRegistrationRequest::default())
        .await
        .unwrap_err();
    let heartbeat = transport.heartbeat("id", "key").await.unwrap_err();
    let update = transport
        .update("id", "key", UpdateRegisteredServer::default())
        .await
        .unwrap_err();
    let delete = transport.delete("id", "key").await.unwrap_err();
    assert_eq!(register.to_string(), "HTTP status 403 Forbidden");
    let HttpError::ResponseError(register) = register else {
        panic!("expected register HTTP error")
    };
    assert_eq!(register.content, body);
    let Some(RegisterError::DefaultResponse(response)) = register.entity else {
        panic!("expected typed register error")
    };
    assert_eq!(response.message, "response-sentinel");
    let HttpError::ResponseError(heartbeat) = heartbeat else {
        panic!("expected heartbeat HTTP error")
    };
    assert_eq!(heartbeat.content, body);
    assert!(matches!(
        heartbeat.entity,
        Some(HeartbeatError::Status403(_))
    ));
    let HttpError::ResponseError(update) = update else {
        panic!("expected update HTTP error")
    };
    assert_eq!(update.content, body);
    assert!(matches!(update.entity, Some(UpdateError::Status403(_))));
    let HttpError::ResponseError(delete) = delete else {
        panic!("expected delete HTTP error")
    };
    assert_eq!(delete.content, body);
    assert!(matches!(
        delete.entity,
        Some(DeleteServerError::Status403(_))
    ));
}

#[tokio::test]
async fn http_observer_receives_typed_errors_without_leaking_them_in_debug() {
    let server = MockServer::start().await;
    Mock::given(method("POST"))
        .and(path("/api/v1/servers"))
        .respond_with(ResponseTemplate::new(429).set_body_json(serde_json::json!({
            "status": "error", "message": "private-response-sentinel"
        })))
        .expect(1)
        .mount(&server)
        .await;
    let worker = Registration::new(
        HttpTransport::new(&server.uri(), None).unwrap(),
        ServerRegistrationRequest::default(),
        Policy::default(),
    )
    .unwrap()
    .into_worker();
    let mut observed = false;
    assert_eq!(
        worker
            .run(|event| {
                assert!(!format!("{event:?}").contains("private-response-sentinel"));
                let Event::Http(HttpEvent::Register(Err(error))) = event else {
                    panic!("unexpected event")
                };
                assert_eq!(error.to_string(), "HTTP status 429 Too Many Requests");
                let HttpError::ResponseError(response) = error else {
                    panic!("expected HTTP error")
                };
                let Some(RegisterError::Status429(entity)) = &response.entity else {
                    panic!("expected typed response")
                };
                assert_eq!(entity.message, "private-response-sentinel");
                observed = true;
                Err("private-observer-sentinel".into())
            })
            .await,
        Err(SdkError::ObserverFailed)
    );
    assert!(observed);
    assert_eq!(
        worker.set_update(UpdateRegisteredServer::default()),
        Err(SdkError::Stopped)
    );
}

#[tokio::test]
async fn default_transport_does_not_forward_registration_credentials() {
    let origin = MockServer::start().await;
    let target = MockServer::start().await;
    Mock::given(any())
        .respond_with(ResponseTemplate::new(200))
        .expect(0)
        .mount(&target)
        .await;
    Mock::given(method("DELETE"))
        .and(path("/api/v1/servers/id"))
        .and(header("User-Agent", "sdk-test/1.0"))
        .and(header("X-CHIV2-SERVER-BROWSER-KEY", "credential-sentinel"))
        .respond_with(ResponseTemplate::new(302).insert_header("Location", target.uri()))
        .expect(1)
        .mount(&origin)
        .await;
    let transport = HttpTransport::new(&origin.uri(), None)
        .unwrap()
        .with_user_agent("sdk-test/1.0");
    assert_eq!(
        transport
            .delete("id", "credential-sentinel")
            .await
            .map_err(|error| RequestFailure::from_error(&error)),
        Err(RequestFailure::InvalidResponse)
    );
}

#[tokio::test]
async fn registration_redirect_preserves_uncertainty_without_retrying() {
    let origin = MockServer::start().await;
    let target = MockServer::start().await;
    Mock::given(any())
        .respond_with(ResponseTemplate::new(200))
        .expect(0)
        .mount(&target)
        .await;
    Mock::given(method("POST"))
        .and(path("/api/v1/servers"))
        .respond_with(ResponseTemplate::new(302).insert_header("Location", target.uri()))
        .expect(1)
        .mount(&origin)
        .await;
    let request = ServerRegistrationRequest::new(
        Chivalry2Ports::new(7777, 7778, 7779),
        "server".into(),
        "test".into(),
        "map".into(),
        0,
        32,
    );
    let transport = HttpTransport::new(&origin.uri(), None).unwrap();
    let mut registration =
        Registration::new(transport, request.clone(), Policy::default()).unwrap();
    for _ in 0..2 {
        assert_eq!(
            registration.poll().await,
            Err(SdkError::RegistrationUncertain)
        );
    }
    let requests = origin.received_requests().await.unwrap();
    assert_eq!(requests.len(), 1);
    let body: ServerRegistrationRequest = requests[0].body_json().unwrap();
    assert_eq!(body, request);
}
