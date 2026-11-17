//! Bounded default transport and a typed injection boundary for lifecycle tests.
use server_browser_client::apis::{api_v1_api as api, configuration::Configuration};
pub use server_browser_client::apis::{
    api_v1_api::{DeleteServerError, HeartbeatError, RegisterError, UpdateError},
    Error as HttpError, ResponseContent,
};
use server_browser_models::{
    RegistrationResponse, ServerRegistrationRequest, StatusResponse, UpdateRegisteredServer,
    UpdateResponse,
};
use std::{future::Future, net::IpAddr, time::Duration};

/// Credential-safe classification for lifecycle failures and application logs.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RequestFailure {
    /// HTTP rejection with its status code only.
    Http(u16),
    /// Connection, timeout, or I/O failure.
    Transport,
    /// A response could not be decoded.
    InvalidResponse,
}

impl RequestFailure {
    /// Classify an HTTP error without exposing its response body or request URL.
    #[must_use]
    pub const fn from_error<E>(error: &HttpError<E>) -> Self {
        match error {
            HttpError::ResponseError(response) => Self::Http(response.status.as_u16()),
            HttpError::Serde(_) => Self::InvalidResponse,
            HttpError::Reqwest(_) => Self::Transport,
        }
    }
}

/// Injected protocol operations with generated route-specific errors.
/// Errors retain response bodies and request details: never log them wholesale.
pub trait RegistrationTransport: Sync {
    /// Submit one non-idempotent registration attempt.
    ///
    /// # Errors
    /// Returns a generated transport, HTTP, or decoding error; details may be sensitive.
    fn register(
        &self,
        request: ServerRegistrationRequest,
    ) -> impl Future<Output = Result<RegistrationResponse, HttpError<RegisterError>>> + Send;
    /// Publish metadata for a known identity.
    ///
    /// # Errors
    /// Returns a generated transport, HTTP, or decoding error; details may be sensitive.
    fn update(
        &self,
        id: &str,
        key: &str,
        update: UpdateRegisteredServer,
    ) -> impl Future<Output = Result<UpdateResponse, HttpError<UpdateError>>> + Send;
    /// Renew the lease of a known identity.
    ///
    /// # Errors
    /// Returns a generated transport, HTTP, or decoding error; details may be sensitive.
    fn heartbeat(
        &self,
        id: &str,
        key: &str,
    ) -> impl Future<Output = Result<UpdateResponse, HttpError<HeartbeatError>>> + Send;
    /// Delete a known identity once.
    ///
    /// # Errors
    /// Returns a generated transport, HTTP, or decoding error; details may be sensitive.
    fn delete(
        &self,
        id: &str,
        key: &str,
    ) -> impl Future<Output = Result<StatusResponse, HttpError<DeleteServerError>>> + Send;
}

/// Bounded async HTTP transport with redacted diagnostic output.
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
        let mut builder = reqwest::Client::builder()
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

    /// Set the application user-agent without changing the HTTP client or its policy.
    #[must_use]
    pub fn with_user_agent(mut self, user_agent: impl Into<String>) -> Self {
        self.configuration.user_agent = Some(user_agent.into());
        self
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

impl RegistrationTransport for HttpTransport {
    async fn register(
        &self,
        request: ServerRegistrationRequest,
    ) -> Result<RegistrationResponse, HttpError<RegisterError>> {
        api::register(&self.configuration, request).await
    }

    async fn update(
        &self,
        id: &str,
        key: &str,
        update: UpdateRegisteredServer,
    ) -> Result<UpdateResponse, HttpError<UpdateError>> {
        api::update(&self.configuration, key, id, update).await
    }

    async fn heartbeat(
        &self,
        id: &str,
        key: &str,
    ) -> Result<UpdateResponse, HttpError<HeartbeatError>> {
        api::heartbeat(&self.configuration, key, id).await
    }

    async fn delete(
        &self,
        id: &str,
        key: &str,
    ) -> Result<StatusResponse, HttpError<DeleteServerError>> {
        api::delete_server(&self.configuration, key, id).await
    }
}
