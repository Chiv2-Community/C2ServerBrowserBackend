use server_browser_client::apis::{api_v1_api, configuration::Configuration};
use std::{
    io::{Read, Write},
    net::TcpListener,
    thread,
    time::Duration,
};

#[test]
fn client_uses_injected_transport_and_encodes_path_parameter() {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let base_path = format!("http://{}", listener.local_addr().unwrap());
    let worker = thread::spawn(move || {
        let (mut stream, _) = listener.accept().unwrap();
        stream
            .set_read_timeout(Some(Duration::from_secs(5)))
            .unwrap();
        let mut request = Vec::new();
        while !request.ends_with(b"\r\n\r\n") {
            let mut byte = [0];
            stream.read_exact(&mut byte).unwrap();
            request.push(byte[0]);
        }
        let body = r#"{"banned":false}"#;
        write!(
            stream,
            "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
            body.len(),
            body
        )
        .unwrap();
        String::from_utf8(request).unwrap()
    });
    let config = Configuration {
        base_path,
        client: reqwest::blocking::Client::builder()
            .no_proxy()
            .timeout(Duration::from_secs(5))
            .build()
            .unwrap(),
        ..Configuration::default()
    };
    assert!(
        !api_v1_api::check_banned(&config, "2001:db8::1")
            .unwrap()
            .banned
    );
    let request = worker.join().unwrap();
    assert!(request.starts_with("GET /api/v1/check-banned/2001%3Adb8%3A%3A1 "));
}
