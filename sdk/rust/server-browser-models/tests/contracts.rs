use serde_json::json;
use server_browser_models::{
    BanStatusResponse, ServerListResponse, ServerListingItem, ServerResponse,
};

#[test]
fn ban_status_decodes_boolean_not_text() {
    let result: BanStatusResponse = serde_json::from_value(json!({"banned": false})).unwrap();
    assert!(!result.banned);
    assert!(serde_json::from_value::<BanStatusResponse>(json!({"banned": "true"})).is_err());
}

#[test]
fn join_claims_accept_timestamps_after_2038() {
    let mut value =
        serde_json::to_value(server_browser_models::JoinTicketClaims::default()).unwrap();
    for field in ["auth_time", "iat", "nbf", "exp"] {
        value[field] = json!(2_200_000_000_i64);
    }
    let claims: server_browser_models::JoinTicketClaims = serde_json::from_value(value).unwrap();
    assert_eq!(claims.auth_time, 2_200_000_000);
    assert_eq!(claims.iat, 2_200_000_000);
    assert_eq!(claims.nbf, 2_200_000_000);
    assert_eq!(claims.exp, 2_200_000_000);
}

#[test]
fn listings_preserve_plain_and_diagnostic_variants() {
    let plain = serde_json::to_value(ServerResponse::default()).unwrap();
    let mut diagnostic = plain.clone();
    diagnostic["ip_address"] = json!("2001:db8::1");
    diagnostic["public_ip_address"] = json!("2001:db8::1");
    diagnostic["local_ip_address"] = json!("fd00::1");
    let listing: ServerListResponse =
        serde_json::from_value(json!({"servers":[plain, diagnostic]})).unwrap();
    assert!(matches!(
        listing.servers[0],
        ServerListingItem::ServerResponse(_)
    ));
    match &listing.servers[1] {
        ServerListingItem::ServerResponseWithIp(server) => {
            assert_eq!(server.ip_address, "2001:db8::1")
        }
        _ => panic!("diagnostic IP fields lost"),
    }
}
