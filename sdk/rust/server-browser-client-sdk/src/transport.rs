//! Bounded default transport and a typed injection boundary for lifecycle tests.
use server_browser_client::apis::{api_v1_api as api, configuration::Configuration, Error};
use server_browser_models::{
    RegistrationResponse, ServerRegistrationRequest, UpdateRegisteredServer, UpdateResponse,
};
use std::{net::IpAddr, time::Duration};

/// Credential-safe failure reported by a registration transport.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RequestFailure {
    /// HTTP rejection with its status code only.
    Http(u16),
    /// Connection, timeout, or I/O failure.
    Transport,
    /// A response could not be decoded.
    InvalidResponse,
}

/// Injected protocol operations; implementations must keep credentials out of errors.
pub trait RegistrationTransport {
    /// Submit one non-idempotent registration attempt.
    ///
    /// # Errors
    /// Returns a transport, HTTP, or decoding failure without credential details.
    fn register(
        &self,
        request: ServerRegistrationRequest,
    ) -> Result<RegistrationResponse, RequestFailure>;
    /// Publish metadata for a known identity.
    ///
    /// # Errors
    /// Returns a transport, HTTP, or decoding failure without credential details.
    fn update(
        &self,
        id: &str,
        key: &str,
        update: UpdateRegisteredServer,
    ) -> Result<UpdateResponse, RequestFailure>;
    /// Renew the lease of a known identity.
    ///
    /// # Errors
    /// Returns a transport, HTTP, or decoding failure without credential details.
    fn heartbeat(&self, id: &str, key: &str) -> Result<UpdateResponse, RequestFailure>;
    /// Delete a known identity once.
    ///
    /// # Errors
    /// Returns a transport, HTTP, or decoding failure without credential details.
    fn delete(&self, id: &str, key: &str) -> Result<(), RequestFailure>;
}

/// Bounded blocking HTTP transport with redacted diagnostic output.
#[derive(Clone)]
pub struct HttpTransport {
    configuration: Configuration,
}

impl std::fmt::Debug for HttpTransport {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str("HttpTransport([REDACTED])")
    }
}

impl HttpTransport {
    /// Build a bounded client with redirects disabled.
    ///
    /// # Errors
    /// Returns the HTTP client initialization error.
    pub fn new(base_url: &str, source_ip: Option<IpAddr>) -> Result<Self, reqwest::Error> {
        let mut builder = reqwest::blocking::Client::builder()
            .timeout(Duration::from_secs(10))
            .connect_timeout(Duration::from_secs(5))
            .redirect(reqwest::redirect::Policy::none());
        if let Some(ip) = source_ip {
            builder = builder.local_address(ip);
        }
        Ok(Self::from_configuration(Configuration {
            base_path: base_url.trim_end_matches('/').into(),
            ..Configuration::with_client(builder.build()?)
        }))
    }

    /// Callers supplying a transport own its timeout, redirect and proxy policy.
    #[must_use]
    pub const fn from_configuration(configuration: Configuration) -> Self {
        Self { configuration }
    }

    /// Borrow the generated client's configuration for other protocol operations.
    #[must_use]
    pub const fn configuration(&self) -> &Configuration {
        &self.configuration
    }
}

fn safe_failure<E>(error: Error<E>) -> RequestFailure {
    match error {
        Error::ResponseError(response) => RequestFailure::Http(response.status.as_u16()),
        Error::Serde(_) => RequestFailure::InvalidResponse,
        _ => RequestFailure::Transport,
    }
}

impl RegistrationTransport for HttpTransport {
    fn register(
        &self,
        request: ServerRegistrationRequest,
    ) -> Result<RegistrationResponse, RequestFailure> {
        api::register(&self.configuration, request).map_err(safe_failure)
    }

    fn update(
        &self,
        id: &str,
        key: &str,
        update: UpdateRegisteredServer,
    ) -> Result<UpdateResponse, RequestFailure> {
        api::update(&self.configuration, key, id, update).map_err(safe_failure)
    }

    fn heartbeat(&self, id: &str, key: &str) -> Result<UpdateResponse, RequestFailure> {
        api::heartbeat(&self.configuration, key, id).map_err(safe_failure)
    }

    fn delete(&self, id: &str, key: &str) -> Result<(), RequestFailure> {
        api::delete_server(&self.configuration, key, id)
            .map(|_| ())
            .map_err(safe_failure)
    }
}
