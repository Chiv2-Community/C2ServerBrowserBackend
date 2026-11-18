//! HTTP configuration. Credentials are supplied explicitly to each operation.

#[derive(Clone)]
pub struct Configuration {
    pub base_path: String,
    pub user_agent: Option<String>,
    pub client: reqwest::Client,
}

impl std::fmt::Debug for Configuration {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter.write_str("Configuration([REDACTED])")
    }
}

impl Configuration {
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Use an existing transport without constructing a default HTTP client.
    #[must_use]
    pub fn with_client(client: reqwest::Client) -> Self {
        Self {
            base_path: "http://localhost".to_owned(),
            user_agent: Some(
                concat!("server-browser-client/", env!("CARGO_PKG_VERSION")).to_owned(),
            ),
            client,
        }
    }
}

impl Default for Configuration {
    fn default() -> Self {
        Self::with_client(
            reqwest::Client::builder()
                .redirect(reqwest::redirect::Policy::none())
                .build()
                .expect("HTTP client initialization failed"),
        )
    }
}
