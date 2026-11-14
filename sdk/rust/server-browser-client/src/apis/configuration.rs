//! HTTP configuration. Credentials are supplied explicitly to each operation.

#[derive(Clone)]
pub struct Configuration {
    pub base_path: String,
    pub user_agent: Option<String>,
    pub client: reqwest::blocking::Client,
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
}

impl Default for Configuration {
    fn default() -> Self {
        Self {
            base_path: "http://localhost".to_owned(),
            user_agent: Some("server-browser-client/1.0.0".to_owned()),
            client: reqwest::blocking::Client::new(),
        }
    }
}
