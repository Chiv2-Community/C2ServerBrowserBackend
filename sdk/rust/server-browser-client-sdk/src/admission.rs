//! Offline game admission with bounded keys and atomic, process-local replay state.
//!
//! Fetch JWKS outside login and pass snapshots to [`AdmissionVerifier::replace_keys`].
//! Unknown keys never trigger network work. Create a verifier for each fresh live
//! registration; never restore registration UUIDs or clear replay state mid-lease.

use crate::models::{game_platform_identity::Provider, GameAdmissionClaims, JwksResponse};
use base64::Engine;
use jsonwebtoken::{decode, decode_header, Algorithm, DecodingKey, Validation};
use std::{
    collections::HashMap,
    fmt,
    sync::Mutex,
    time::{SystemTime, UNIX_EPOCH},
};

const MAX_TOKEN_BYTES: usize = 16384;
const MAX_KEYS: usize = 8;
const MAX_REPLAYS: usize = 4096;
const MAX_KEY_AGE: u64 = 300;

/// Credential-safe rejection; no token or provider claims are retained in errors.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum AdmissionError {
    /// Invalid pinned issuer, registration UUID, or key snapshot.
    Configuration,
    /// No fresh verification key is available.
    KeysUnavailable,
    /// Invalid signature, header, claims, or identity.
    Rejected,
    /// This admission has already been consumed.
    Replay,
    /// Replay protection is full; admission fails closed.
    Capacity,
}

impl fmt::Display for AdmissionError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{self:?}")
    }
}
impl std::error::Error for AdmissionError {}

struct State {
    keys: HashMap<String, DecodingKey>,
    refreshed: Option<std::time::Instant>,
    consumed: HashMap<String, i64>,
}

/// Signature validation and replay consumption happen synchronously without I/O.
///
/// Share one instance across all login paths for a registration. Key refreshes
/// replace the entire snapshot atomically without clearing consumed admissions.
pub struct AdmissionVerifier {
    issuer: String,
    audience: String,
    state: Mutex<State>,
}

impl fmt::Debug for AdmissionVerifier {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("AdmissionVerifier").finish_non_exhaustive()
    }
}

fn canonical_uuid(value: &str) -> bool {
    value.len() == 36
        && value.bytes().enumerate().all(|(index, byte)| {
            if matches!(index, 8 | 13 | 18 | 23) {
                byte == b'-'
            } else {
                byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte)
            }
        })
}

impl AdmissionVerifier {
    /// Pin the configured backend issuer and this process's fresh registration.
    ///
    /// # Errors
    /// Rejects non-HTTPS issuers (except loopback HTTP) or malformed UUIDs.
    pub fn new(issuer: &str, server_id: &str) -> Result<Self, AdmissionError> {
        let url = reqwest::Url::parse(issuer).map_err(|_| AdmissionError::Configuration)?;
        let loopback = url.host_str().is_some_and(|host| {
            host.trim_matches(['[', ']'])
                .parse::<std::net::IpAddr>()
                .is_ok_and(|ip| ip.is_loopback())
        });
        if !(url.scheme() == "https" || url.scheme() == "http" && loopback)
            || url.host_str().is_none()
            || !url.username().is_empty()
            || url.password().is_some()
            || url.query().is_some()
            || url.fragment().is_some()
            || issuer.ends_with('/')
            || issuer.len() > 2048
            || !canonical_uuid(server_id)
        {
            return Err(AdmissionError::Configuration);
        }
        Ok(Self {
            issuer: issuer.to_owned(),
            audience: format!("urn:unchained:server:{server_id}"),
            state: Mutex::new(State {
                keys: HashMap::new(),
                refreshed: None,
                consumed: HashMap::new(),
            }),
        })
    }

    /// Install a successfully fetched JWKS snapshot, retaining replay state.
    ///
    /// Empty snapshots revoke all keys. Retained rotation keys must be included
    /// by the backend; removed keys cannot verify even unexpired admissions.
    ///
    /// # Errors
    /// Rejects duplicate IDs, unsupported keys, oversized snapshots, or bad RSA.
    pub fn replace_keys(&self, jwks: JwksResponse) -> Result<(), AdmissionError> {
        if jwks.keys.len() > MAX_KEYS {
            return Err(AdmissionError::Configuration);
        }
        let mut keys = HashMap::new();
        for jwk in jwks.keys {
            if jwk.kty != "RSA"
                || jwk.alg != "RS256"
                || jwk.r#use != "sig"
                || jwk.kid.is_empty()
                || jwk.kid.len() > 128
                || keys.contains_key(&jwk.kid)
                || !(342..=1366).contains(&jwk.n.len())
                || jwk.e != "AQAB"
            {
                return Err(AdmissionError::Configuration);
            }
            let key = DecodingKey::from_rsa_components(&jwk.n, &jwk.e)
                .map_err(|_| AdmissionError::Configuration)?;
            keys.insert(jwk.kid, key);
        }
        let mut state = self
            .state
            .lock()
            .map_err(|_| AdmissionError::KeysUnavailable)?;
        state.keys = keys;
        state.refreshed = Some(std::time::Instant::now());
        drop(state);
        Ok(())
    }

    /// Authenticate and atomically consume one admission JWT.
    ///
    /// Only the returned claims may supply native identity fields. Call this
    /// before native completion, including restored-player reconnect paths.
    ///
    /// # Errors
    /// Rejects invalid, expired, replayed tokens, stale keys, and exhausted bounds.
    pub fn consume(&self, token: &str) -> Result<GameAdmissionClaims, AdmissionError> {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map_err(|_| AdmissionError::Rejected)?
            .as_secs();
        let now = i64::try_from(now).map_err(|_| AdmissionError::Rejected)?;
        self.consume_at(token, now)
    }

    fn consume_at(&self, token: &str, now: i64) -> Result<GameAdmissionClaims, AdmissionError> {
        if token.is_empty() || token.len() > MAX_TOKEN_BYTES {
            return Err(AdmissionError::Rejected);
        }
        // Check unsupported JOSE extensions rather than silently ignoring them.
        let raw_header = base64::engine::general_purpose::URL_SAFE_NO_PAD
            .decode(token.split('.').next().ok_or(AdmissionError::Rejected)?)
            .map_err(|_| AdmissionError::Rejected)?;
        let raw_header: serde_json::Value =
            serde_json::from_slice(&raw_header).map_err(|_| AdmissionError::Rejected)?;
        if !raw_header.as_object().is_some_and(|fields| {
            fields
                .keys()
                .all(|name| matches!(name.as_str(), "alg" | "kid" | "typ"))
        }) {
            return Err(AdmissionError::Rejected);
        }
        let header = decode_header(token).map_err(|_| AdmissionError::Rejected)?;
        if header.alg != Algorithm::RS256
            || header.typ.as_deref() != Some("unchained-game-join+jwt")
            || header.jku.is_some()
            || header.jwk.is_some()
            || header.x5u.is_some()
        {
            return Err(AdmissionError::Rejected);
        }
        let kid = header
            .kid
            .filter(|kid| !kid.is_empty() && kid.len() <= 128)
            .ok_or(AdmissionError::Rejected)?;
        let mut validation = Validation::new(Algorithm::RS256);
        validation.set_issuer(&[&self.issuer]);
        validation.set_audience(&[&self.audience]);
        validation.set_required_spec_claims(&["iss", "aud", "sub", "exp", "nbf", "iat"]);
        // Validate all times below, together with the maximum admission lifetime.
        validation.validate_exp = false;
        validation.validate_nbf = false;
        let mut state = self
            .state
            .lock()
            .map_err(|_| AdmissionError::KeysUnavailable)?;
        if state
            .refreshed
            .is_none_or(|at| at.elapsed().as_secs() >= MAX_KEY_AGE)
        {
            return Err(AdmissionError::KeysUnavailable);
        }
        let key = state
            .keys
            .get(&kid)
            .ok_or(AdmissionError::KeysUnavailable)?;
        let claims = decode::<GameAdmissionClaims>(token, key, &validation)
            .map_err(|_| AdmissionError::Rejected)?
            .claims;
        let ids = &claims.identities;
        let playfab = !ids.playfab.is_empty()
            && ids.playfab.len() <= 64
            && ids
                .playfab
                .bytes()
                .all(|b| b.is_ascii_digit() || (b'A'..=b'F').contains(&b));
        let eos = ids.eos_product_user_id.len() == 32
            && ids
                .eos_product_user_id
                .bytes()
                .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b));
        let platform = match ids.platform.provider {
            Provider::Eos => ids.platform.id == ids.eos_product_user_id,
            Provider::Steam => ids
                .platform
                .id
                .parse::<u64>()
                .is_ok_and(|id| id > 0 && id.to_string() == ids.platform.id),
        };
        if claims.version != 1
            || claims.sub != ids.playfab
            || !playfab
            || !eos
            || !platform
            || claims.iat < 0
            || claims.iat > now
            || claims.nbf != claims.iat
            || claims.exp <= now
            || claims.exp <= claims.iat
            || claims.exp.saturating_sub(claims.iat) > 60
            || !canonical_uuid(&claims.jti)
        {
            return Err(AdmissionError::Rejected);
        }
        state.consumed.retain(|_, expires| *expires > now);
        if state.consumed.contains_key(&claims.jti) {
            return Err(AdmissionError::Replay);
        }
        if state.consumed.len() >= MAX_REPLAYS {
            return Err(AdmissionError::Capacity);
        }
        state.consumed.insert(claims.jti.clone(), claims.exp);
        drop(state);
        Ok(claims)
    }
}

#[cfg(test)]
#[path = "admission_tests.rs"]
mod tests;
