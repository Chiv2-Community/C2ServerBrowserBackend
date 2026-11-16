use server_browser_client_sdk::{
    models::{Chivalry2Ports, ServerRegistrationRequest},
    HttpTransport, Policy, Registration, RegistrationTransport, RequestFailure, SdkError,
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
        .and(header("X-CHIV2-SERVER-BROWSER-KEY", "credential-sentinel"))
        .respond_with(ResponseTemplate::new(302).insert_header("Location", target.uri()))
        .expect(1)
        .mount(&origin)
        .await;
    let transport = HttpTransport::new(&origin.uri(), None).unwrap();
    assert_eq!(
        transport.delete("id", "credential-sentinel").await,
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
