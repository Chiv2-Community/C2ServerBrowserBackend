use server_browser_client::apis::{api_v1_api, configuration::Configuration, Error};
use std::time::Duration;
use wiremock::{
    matchers::{any, header, method, path},
    Mock, MockServer, ResponseTemplate,
};

fn configuration(server: &MockServer) -> Configuration {
    Configuration {
        base_path: server.uri(),
        ..Configuration::default()
    }
}

#[tokio::test]
async fn client_uses_injected_transport_and_encodes_path_parameter() {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(header("user-agent", "server-browser-client/1.0.0"))
        .respond_with(
            ResponseTemplate::new(200).set_body_json(serde_json::json!({"banned": false})),
        )
        .expect(1)
        .mount(&server)
        .await;
    let config = Configuration {
        base_path: server.uri(),
        ..Configuration::with_client(
            reqwest::Client::builder()
                .no_proxy()
                .timeout(Duration::from_secs(5))
                .build()
                .unwrap(),
        )
    };
    assert!(
        !api_v1_api::check_banned(&config, "2001:db8::1")
            .await
            .unwrap()
            .banned
    );
    let requests = server.received_requests().await.unwrap();
    assert_eq!(
        requests[0].url.path(),
        "/api/v1/check-banned/2001%3Adb8%3A%3A1"
    );
}

async fn check_redirect_policy(injected: bool) {
    let origin = MockServer::start().await;
    let target = MockServer::start().await;
    Mock::given(any())
        .respond_with(
            ResponseTemplate::new(200).set_body_json(serde_json::json!({"banned_ips": []})),
        )
        .expect(u64::from(injected))
        .mount(&target)
        .await;
    Mock::given(method("GET"))
        .and(path("/api/v1/admin/ban-list"))
        .and(header(
            "X-CHIV2-SERVER-BROWSER-ADMIN-KEY",
            "redirect-secret",
        ))
        .respond_with(
            ResponseTemplate::new(302)
                .insert_header("Location", format!("{}/capture", target.uri())),
        )
        .expect(1)
        .mount(&origin)
        .await;
    let config = if injected {
        Configuration {
            base_path: origin.uri(),
            ..Configuration::with_client(
                reqwest::Client::builder()
                    .no_proxy()
                    .timeout(Duration::from_secs(5))
                    .redirect(reqwest::redirect::Policy::limited(1))
                    .build()
                    .unwrap(),
            )
        }
    } else {
        configuration(&origin)
    };
    let result = api_v1_api::get_ban_list(&config, "redirect-secret").await;
    let requests = target.received_requests().await.unwrap();
    if injected {
        assert!(result.unwrap().banned_ips.is_empty());
        assert_eq!(requests[0].url.path(), "/capture");
        assert_eq!(
            requests[0].headers["X-CHIV2-SERVER-BROWSER-ADMIN-KEY"],
            "redirect-secret"
        );
    } else {
        assert!(requests.is_empty(), "default client forwarded credentials");
        assert!(result.is_err());
    }
}

#[tokio::test]
async fn default_client_does_not_redirect_credentials() {
    check_redirect_policy(false).await;
}

#[tokio::test]
async fn injected_client_preserves_explicit_redirect_policy() {
    check_redirect_policy(true).await;
}

#[tokio::test]
async fn heartbeat_errors_decode_by_status_and_preserve_fallbacks() {
    use api_v1_api::HeartbeatError;

    let status_body = r#"{"status":"not_found","message":"Missing registration"}"#;
    for (status, body) in [
        (404, status_body),
        (401, status_body),
        (400, status_body),
        (403, status_body),
        (503, status_body),
        (404, "{}"),
        (404, "not json"),
        (503, "not json"),
        (503, r#"{"unknown":true}"#),
    ] {
        let server = MockServer::start().await;
        Mock::given(method("POST"))
            .and(path("/api/v1/servers/id/heartbeat"))
            .respond_with(ResponseTemplate::new(status).set_body_raw(body, "application/json"))
            .expect(1)
            .mount(&server)
            .await;
        match api_v1_api::heartbeat(&configuration(&server), "key", "id").await {
            Err(Error::ResponseError(response)) => {
                assert_eq!(response.status.as_u16(), status);
                assert_eq!(response.content, body);
                match (status, body, response.entity) {
                    (401, _, Some(HeartbeatError::Status401(_)))
                    | (400, _, Some(HeartbeatError::Status400(_)))
                    | (403, _, Some(HeartbeatError::Status403(_)))
                    | (404, "{}" | "not json", None)
                    | (503, "not json", None) => {}
                    (404, body, Some(HeartbeatError::Status404(entity))) if body == status_body => {
                        assert_eq!(entity.status, "not_found");
                        assert_eq!(entity.message, "Missing registration");
                    }
                    (503, body, Some(HeartbeatError::DefaultResponse(_)))
                        if body == status_body => {}
                    (503, _, Some(HeartbeatError::UnknownValue(value))) => {
                        assert_eq!(value, serde_json::json!({"unknown": true}));
                    }
                    unexpected => panic!("wrong status-directed entity: {unexpected:?}"),
                }
            }
            unexpected => panic!("expected HTTP error: {unexpected:?}"),
        }
    }
}

#[tokio::test]
async fn registration_rate_limit_decodes_exact_variant() {
    let body = r#"{"status":"error","message":"Registration limit reached"}"#;
    let server = MockServer::start().await;
    Mock::given(method("POST"))
        .and(path("/api/v1/servers"))
        .respond_with(ResponseTemplate::new(429).set_body_raw(body, "application/json"))
        .expect(1)
        .mount(&server)
        .await;
    let request = server_browser_client::models::ServerRegistrationRequest::default();
    match api_v1_api::register(&configuration(&server), request).await {
        Err(Error::ResponseError(response)) => {
            assert_eq!(response.status.as_u16(), 429);
            assert_eq!(response.content, body);
            assert!(matches!(
                response.entity,
                Some(api_v1_api::RegisterError::Status429(_))
            ));
        }
        unexpected => panic!("expected HTTP error: {unexpected:?}"),
    }
}

#[test]
fn injected_configuration_preserves_default_metadata() {
    let default = Configuration::default();
    let injected = Configuration::with_client(default.client.clone());
    assert_eq!(injected.base_path, default.base_path);
    assert_eq!(injected.user_agent, default.user_agent);
}

#[test]
fn configuration_debug_redacts_urls_and_headers() {
    let config = Configuration {
        base_path: "https://user:password@example.invalid/?token=secret".into(),
        user_agent: Some("private-agent".into()),
        ..Configuration::default()
    };
    assert_eq!(format!("{config:?}"), "Configuration([REDACTED])");
}

#[test]
fn protocol_errors_keep_response_bodies_off_the_stack() {
    assert!(size_of::<Error<api_v1_api::RegisterError>>() <= 32);
}
