//! Bounded default transport and a typed injection boundary for lifecycle tests.
use server_browser_client::apis::{api_v1_api as api, configuration::Configuration, Error};
use server_browser_models::{
    RegistrationResponse, ServerRegistrationRequest, UpdateRegisteredServer, UpdateResponse,
};
use std::{net::IpAddr, time::Duration};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RequestFailure {
    Http(u16),
    Transport,
    InvalidResponse,
}

pub trait RegistrationTransport {
    fn register(
        &self,
        request: ServerRegistrationRequest,
    ) -> Result<RegistrationResponse, RequestFailure>;
    fn update(
        &self,
        id: &str,
        key: &str,
        update: UpdateRegisteredServer,
    ) -> Result<UpdateResponse, RequestFailure>;
    fn heartbeat(&self, id: &str, key: &str) -> Result<UpdateResponse, RequestFailure>;
    fn delete(&self, id: &str, key: &str) -> Result<(), RequestFailure>;
}

#[derive(Clone)]
pub struct HttpTransport(Configuration);

impl std::fmt::Debug for HttpTransport {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str("HttpTransport([REDACTED])")
    }
}

impl HttpTransport {
    pub fn new(base_url: &str, source_ip: Option<IpAddr>) -> Result<Self, reqwest::Error> {
        let mut builder = reqwest::blocking::Client::builder()
            .timeout(Duration::from_secs(10))
            .connect_timeout(Duration::from_secs(5))
            .redirect(reqwest::redirect::Policy::none());
        if let Some(ip) = source_ip {
            builder = builder.local_address(ip);
        }
        Ok(Self(Configuration {
            base_path: base_url.trim_end_matches('/').into(),
            client: builder.build()?,
            ..Configuration::default()
        }))
    }

    /// Callers supplying a transport own its timeout, redirect and proxy policy.
    pub fn from_configuration(configuration: Configuration) -> Self {
        Self(configuration)
    }

    pub fn configuration(&self) -> &Configuration {
        &self.0
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
        api::register(&self.0, request).map_err(safe_failure)
    }

    fn update(
        &self,
        id: &str,
        key: &str,
        update: UpdateRegisteredServer,
    ) -> Result<UpdateResponse, RequestFailure> {
        api::update(&self.0, key, id, update).map_err(safe_failure)
    }

    fn heartbeat(&self, id: &str, key: &str) -> Result<UpdateResponse, RequestFailure> {
        api::heartbeat(&self.0, key, id).map_err(safe_failure)
    }

    fn delete(&self, id: &str, key: &str) -> Result<(), RequestFailure> {
        api::delete_server(&self.0, key, id)
            .map(|_| ())
            .map_err(safe_failure)
    }
}
