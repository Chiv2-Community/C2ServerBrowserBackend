//! Verify tickets issued by the real backend without exporting its private key.
mod support;
use server_browser_client::{
    apis::api_v1_api as api,
    models::{Chivalry2Ports, ServerRegistrationRequest},
};
use server_browser_client_sdk::{HttpTransport, Policy, Registration};

#[test]
#[ignore = "requires Docker and the published backend image"]
fn backend_signed_ticket_verifies_once_for_live_registration() {
    use server_browser_auth_sdk::{AuthError, TicketVerifier};
    use testcontainers::core::ExecCommand;

    let (container, url) = support::backend();
    let runtime = tokio::runtime::Runtime::new().unwrap();
    let (mut registration, id, jwks) = runtime.block_on(async {
        let client = HttpTransport::new(&url, None).unwrap();
        let request = ServerRegistrationRequest::new(
            Chivalry2Ports::new(7777, 7778, 7779),
            "ticket-test".into(),
            String::new(),
            "map".into(),
            0,
            32,
        );
        let mut registration =
            Registration::new(client.clone(), request, Policy::default()).unwrap();
        registration.poll().await.unwrap();
        let id = registration.server_id().unwrap().to_owned();
        let jwks = api::jwks(client.configuration())
            .await
            .unwrap_or_else(|_| panic!("JWKS retrieval failed"));
        (registration, id, serde_json::to_vec(&jwks).unwrap())
    });
    // Exercise the backend's internal signing boundary inside its container.
    // No test-only HTTP endpoint or private key crosses into the verifier.
    let mut issued = container
        .exec(ExecCommand::new([
            "python",
            "-c",
            r"
import json
import sys
import time
from pathlib import Path
from server_browser_backend.auth.signing import SigningKeys

now = int(time.time())
ticket = SigningKeys(Path('/tmp/browser-test/signing.json')).issue_join_ticket(
    issuer='https://local-auth.test',
    discord_id='123456789012345678',
    server_id=sys.argv[1],
    auth_time=now,
)
print(json.dumps({'ticket': ticket, 'now': now}))
",
            id.as_str(),
        ]))
        .expect("issue ticket inside backend container");
    let output = issued.stdout_to_vec().unwrap();
    assert_eq!(issued.exit_code().unwrap(), Some(0));
    let bundle: serde_json::Value = serde_json::from_slice(&output).expect("decode signing result");
    let ticket = bundle["ticket"].as_str().unwrap();
    let now = bundle["now"].as_u64().unwrap();
    let mut verifier = TicketVerifier::new("https://local-auth.test", &id, &jwks, 32).unwrap();
    let identity = verifier.verify_and_consume(ticket, now).unwrap();
    assert_eq!(identity.discord_id(), "123456789012345678");
    assert_eq!(identity.server_id().to_string(), id);
    assert_eq!(
        verifier.verify_and_consume(ticket, now),
        Err(AuthError::Replay)
    );
    let mut wrong_server = TicketVerifier::new(
        "https://local-auth.test",
        "00000000-0000-0000-0000-000000000001",
        &jwks,
        32,
    )
    .unwrap();
    assert!(wrong_server.verify_and_consume(ticket, now).is_err());
    let mut logs = container.stdout_to_vec().unwrap();
    logs.extend(container.stderr_to_vec().unwrap());
    assert!(
        !logs
            .windows(ticket.len())
            .any(|window| window == ticket.as_bytes()),
        "ticket leaked to backend logs"
    );
    runtime.block_on(async { registration.stop().await.unwrap() });
}
