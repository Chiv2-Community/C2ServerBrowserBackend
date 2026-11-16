use super::*;
use crate::models::Jwk;
use jsonwebtoken::{encode, EncodingKey, Header};
use rsa::{pkcs1::EncodeRsaPrivateKey, traits::PublicKeyParts, RsaPrivateKey};
use serde_json::{json, Value};
use std::sync::{Arc, Barrier, OnceLock};

const SERVER: &str = "18e532b1-6733-4b5a-9ffb-1cd7838bc7e4";
const ISSUER: &str = "https://browser.example";
const NOW: i64 = 2_000_000_000;

fn keys() -> &'static (EncodingKey, Jwk) {
    static KEYS: OnceLock<(EncodingKey, Jwk)> = OnceLock::new();
    KEYS.get_or_init(|| {
        let key = RsaPrivateKey::new(&mut rand::thread_rng(), 2048).unwrap();
        let der = key.to_pkcs1_der().unwrap();
        let encode = |bytes: &[u8]| base64::engine::general_purpose::URL_SAFE_NO_PAD.encode(bytes);
        (
            EncodingKey::from_rsa_der(der.as_bytes()),
            Jwk::new(
                "RSA".into(),
                "RS256".into(),
                "sig".into(),
                "key".into(),
                encode(&key.n().to_bytes_be()),
                encode(&key.e().to_bytes_be()),
            ),
        )
    })
}

fn claims() -> Value {
    json!({"iss": ISSUER, "aud": format!("urn:unchained:server:{SERVER}"),
        "sub": "ABC123", "purpose": "unchained.game-join", "version": 1,
        "iat": NOW, "nbf": NOW, "exp": NOW + 60,
        "jti": "18e532b1-6733-4b5a-9ffb-1cd7838bc7e5",
        "identities": {"playfab": "ABC123", "eos_product_user_id": "a".repeat(32),
            "platform": {"provider": "steam", "id": "76561198000000001"}}})
}

fn token(claims: &Value) -> String {
    let mut header = Header::new(Algorithm::RS256);
    header.kid = Some("key".into());
    header.typ = Some("unchained-game-join+jwt".into());
    encode(&header, claims, &keys().0).unwrap()
}

fn verifier() -> AdmissionVerifier {
    let verifier = AdmissionVerifier::new(ISSUER, SERVER).unwrap();
    verifier
        .replace_keys(JwksResponse::new(vec![keys().1.clone()]))
        .unwrap();
    verifier
}

#[test]
fn consumes_once_and_keeps_replay_state_across_key_refresh() {
    let verifier = verifier();
    let token = token(&claims());
    assert_eq!(verifier.consume_at(&token, NOW).unwrap().sub, "ABC123");
    verifier
        .replace_keys(JwksResponse::new(vec![keys().1.clone()]))
        .unwrap();
    assert_eq!(
        verifier.consume_at(&token, NOW),
        Err(AdmissionError::Replay)
    );
}

#[test]
fn rejects_invalid_claims_without_consuming_valid_token() {
    for (field, value) in [
        ("iss", json!("https://other.example")),
        ("aud", json!("other")),
        ("purpose", json!("discord")),
        ("version", json!(2)),
        ("version", json!("1")),
        ("sub", json!("DEF")),
        ("exp", json!(NOW)),
        ("exp", json!(NOW + 61)),
        ("iat", json!(NOW + 1)),
        ("nbf", json!(NOW + 1)),
        ("iat", json!(-1)),
        ("jti", json!("bad")),
        ("aud", json!([format!("urn:unchained:server:{SERVER}")])),
    ] {
        let verifier = verifier();
        let mut bad = claims();
        bad[field] = value;
        assert_eq!(
            verifier.consume_at(&token(&bad), NOW),
            Err(AdmissionError::Rejected),
            "{field}"
        );
        assert!(verifier.consume_at(&token(&claims()), NOW).is_ok());
    }
}

#[test]
fn rejects_invalid_identity_claims() {
    for (field, value) in [
        ("playfab", json!("abc123")),
        ("eos_product_user_id", json!("bad")),
        ("platform", json!({"provider":"steam", "id":"0"})),
        (
            "platform",
            json!({"provider":"steam", "id":"076561198000000001"}),
        ),
        (
            "platform",
            json!({"provider":"steam", "id":"18446744073709551616"}),
        ),
        ("platform", json!({"provider":"eos", "id":"b".repeat(32)})),
    ] {
        let mut bad = claims();
        bad["identities"][field] = value;
        assert_eq!(
            verifier().consume_at(&token(&bad), NOW),
            Err(AdmissionError::Rejected)
        );
    }
    let mut epic = claims();
    epic["identities"]["platform"] = json!({"provider":"eos", "id":"a".repeat(32)});
    assert!(verifier().consume_at(&token(&epic), NOW).is_ok());
}

#[test]
fn unknown_revoked_stale_and_missing_keys_fail_closed() {
    let verifier = AdmissionVerifier::new(ISSUER, SERVER).unwrap();
    let token = token(&claims());
    assert_eq!(
        verifier.consume_at(&token, NOW),
        Err(AdmissionError::KeysUnavailable)
    );
    let mut unknown = keys().1.clone();
    unknown.kid = "other".into();
    verifier
        .replace_keys(JwksResponse::new(vec![unknown]))
        .unwrap();
    assert_eq!(
        verifier.consume_at(&token, NOW),
        Err(AdmissionError::KeysUnavailable)
    );
    verifier
        .replace_keys(JwksResponse::new(vec![keys().1.clone()]))
        .unwrap();
    verifier.state.lock().unwrap().refreshed =
        std::time::Instant::now().checked_sub(std::time::Duration::from_secs(MAX_KEY_AGE));
    assert_eq!(
        verifier.consume_at(&token, NOW),
        Err(AdmissionError::KeysUnavailable)
    );
    verifier.replace_keys(JwksResponse::new(vec![])).unwrap();
    assert_eq!(
        verifier.consume_at(&token, NOW),
        Err(AdmissionError::KeysUnavailable)
    );
}

#[test]
fn concurrent_replay_has_exactly_one_winner() {
    let verifier = Arc::new(verifier());
    let token = token(&claims());
    let barrier = Arc::new(Barrier::new(8));
    let mut threads = Vec::new();
    for _ in 0..8 {
        let verifier = Arc::clone(&verifier);
        let token = token.clone();
        let barrier = Arc::clone(&barrier);
        threads.push(std::thread::spawn(move || {
            barrier.wait();
            verifier.consume_at(&token, NOW)
        }));
    }
    let results: Vec<_> = threads
        .into_iter()
        .map(|thread| thread.join().unwrap())
        .collect();
    assert_eq!(results.iter().filter(|result| result.is_ok()).count(), 1);
    assert_eq!(
        results
            .iter()
            .filter(|result| **result == Err(AdmissionError::Replay))
            .count(),
        7
    );
}

#[test]
fn full_cache_rejects_without_evicting_unexpired_entries() {
    let verifier = verifier();
    {
        let mut state = verifier.state.lock().unwrap();
        state.consumed = (0..MAX_REPLAYS)
            .map(|i| (i.to_string(), NOW + 30))
            .collect();
    }
    let token = token(&claims());
    assert_eq!(
        verifier.consume_at(&token, NOW),
        Err(AdmissionError::Capacity)
    );
    assert!(verifier.consume_at(&token, NOW + 30).is_ok());
}

#[test]
fn malformed_snapshots_do_not_replace_working_keys() {
    let verifier = verifier();
    assert_eq!(
        verifier.replace_keys(JwksResponse::new(vec![keys().1.clone(); 2])),
        Err(AdmissionError::Configuration)
    );
    let mut invalid = keys().1.clone();
    invalid.alg = "HS256".into();
    assert_eq!(
        verifier.replace_keys(JwksResponse::new(vec![invalid])),
        Err(AdmissionError::Configuration)
    );
    assert!(verifier.consume_at(&token(&claims()), NOW).is_ok());
}
