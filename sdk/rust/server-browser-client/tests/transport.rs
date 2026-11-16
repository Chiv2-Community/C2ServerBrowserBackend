use server_browser_client::apis::{api_v1_api, configuration::Configuration, Error};
use std::time::Duration;
use tokio::{
    io::{AsyncReadExt, AsyncWriteExt},
    net::{TcpListener, TcpStream},
    sync::oneshot,
    task::JoinHandle,
};

async fn read_request(stream: &mut TcpStream) -> String {
    let mut request = Vec::new();
    while !request.ends_with(b"\r\n\r\n") {
        let mut byte = [0];
        stream.read_exact(&mut byte).await.unwrap();
        request.push(byte[0]);
    }
    let headers = String::from_utf8(request).unwrap();
    // Drain bodies before closing the socket to avoid a TCP reset.
    for line in headers.lines() {
        if let Some(length) = line.to_ascii_lowercase().strip_prefix("content-length:") {
            let mut body = vec![0; length.trim().parse().unwrap()];
            stream.read_exact(&mut body).await.unwrap();
        }
    }
    headers
}

async fn write_response(stream: &mut TcpStream, status: u16, headers: &str, body: &str) {
    let response = format!(
        "HTTP/1.1 {status} Test\r\n{headers}Content-Length: {}\r\nConnection: close\r\n\r\n{body}",
        body.len(),
    );
    stream.write_all(response.as_bytes()).await.unwrap();
}

struct TestServer {
    base_path: String,
    worker: JoinHandle<String>,
}

impl TestServer {
    async fn new(status: u16, headers: String, body: String) -> Self {
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let base_path = format!("http://{}", listener.local_addr().unwrap());
        let worker = tokio::spawn(async move {
            tokio::time::timeout(Duration::from_secs(5), async {
                let (mut stream, _) = listener.accept().await.unwrap();
                let request = read_request(&mut stream).await;
                write_response(&mut stream, status, &headers, &body).await;
                request
            })
            .await
            .unwrap()
        });
        Self { base_path, worker }
    }

    fn configuration(&self) -> Configuration {
        Configuration {
            base_path: self.base_path.clone(),
            ..Configuration::default()
        }
    }
}

#[tokio::test]
async fn client_uses_injected_transport_and_encodes_path_parameter() {
    let server = TestServer::new(
        200,
        "Content-Type: application/json\r\n".into(),
        r#"{"banned":false}"#.into(),
    )
    .await;
    let config = Configuration {
        base_path: server.base_path,
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
    let request = server.worker.await.unwrap();
    assert!(request.starts_with("GET /api/v1/check-banned/2001%3Adb8%3A%3A1 "));
    assert!(request
        .to_ascii_lowercase()
        .contains("user-agent: server-browser-client/1.0.0\r\n"));
}

async fn check_redirect_policy(injected: bool) {
    let target = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let location = format!("http://{}/capture", target.local_addr().unwrap());
    let origin = TestServer::new(302, format!("Location: {location}\r\n"), String::new()).await;
    let (stop, stopped) = oneshot::channel();
    let target_worker = tokio::spawn(async move {
        tokio::select! {
            accepted = target.accept() => {
                let (mut stream, _) = accepted.unwrap();
                let request = read_request(&mut stream).await;
                write_response(&mut stream, 200, "Content-Type: application/json\r\n", r#"{"banned_ips":[]}"#).await;
                Some(request)
            },
            _ = stopped => None,
            () = tokio::time::sleep(Duration::from_secs(5)) => panic!("redirect request timed out"),
        }
    });
    let config = if injected {
        Configuration {
            base_path: origin.base_path.clone(),
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
        origin.configuration()
    };
    let result = api_v1_api::get_ban_list(&config, "redirect-secret").await;
    let _ = stop.send(());
    let captured = target_worker.await.unwrap();
    let request = origin.worker.await.unwrap().to_ascii_lowercase();
    assert!(request.contains("x-chiv2-server-browser-admin-key: redirect-secret\r\n"));
    if injected {
        assert!(result.unwrap().banned_ips.is_empty());
        let request = captured.expect("injected redirect policy was changed");
        assert!(request.starts_with("GET /capture "));
        assert!(request
            .to_ascii_lowercase()
            .contains("x-chiv2-server-browser-admin-key: redirect-secret\r\n"));
    } else {
        assert!(captured.is_none(), "default client forwarded credentials");
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
        let server = TestServer::new(
            status,
            "Content-Type: application/json\r\n".into(),
            body.into(),
        )
        .await;
        match api_v1_api::heartbeat(&server.configuration(), "key", "id").await {
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
        server.worker.await.unwrap();
    }
}

#[tokio::test]
async fn registration_rate_limit_decodes_exact_variant() {
    let body = r#"{"status":"error","message":"Registration limit reached"}"#;
    let server = TestServer::new(
        429,
        "Content-Type: application/json\r\n".into(),
        body.into(),
    )
    .await;
    let request = server_browser_client::models::ServerRegistrationRequest::default();
    match api_v1_api::register(&server.configuration(), request).await {
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
    assert!(server
        .worker
        .await
        .unwrap()
        .starts_with("POST /api/v1/servers "));
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
