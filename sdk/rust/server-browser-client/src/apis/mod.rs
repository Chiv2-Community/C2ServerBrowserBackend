//! Shared protocol errors and generated operations.
use std::fmt;

#[derive(Debug, Clone)]
pub struct ResponseContent<T> {
    pub status: reqwest::StatusCode,
    pub content: String,
    pub entity: Option<T>,
}

#[derive(Debug)]
pub enum Error<T> {
    Reqwest(reqwest::Error),
    Serde(serde_json::Error),
    Io(std::io::Error),
    ResponseError(Box<ResponseContent<T>>),
}

impl<T> fmt::Display for Error<T> {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Reqwest(error) => write!(formatter, "HTTP error: {error}"),
            Self::Serde(error) => write!(formatter, "JSON error: {error}"),
            Self::Io(error) => write!(formatter, "I/O error: {error}"),
            Self::ResponseError(response) => write!(formatter, "HTTP status {}", response.status),
        }
    }
}

impl<T: fmt::Debug> std::error::Error for Error<T> {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Reqwest(error) => Some(error),
            Self::Serde(error) => Some(error),
            Self::Io(error) => Some(error),
            Self::ResponseError(_) => None,
        }
    }
}

impl<T> From<reqwest::Error> for Error<T> {
    fn from(error: reqwest::Error) -> Self {
        Self::Reqwest(error)
    }
}

impl<T> From<serde_json::Error> for Error<T> {
    fn from(error: serde_json::Error) -> Self {
        Self::Serde(error)
    }
}

impl<T> From<std::io::Error> for Error<T> {
    fn from(error: std::io::Error) -> Self {
        Self::Io(error)
    }
}

fn urlencode(value: &str) -> String {
    url::form_urlencoded::byte_serialize(value.as_bytes()).collect()
}

enum ContentType {
    Json,
    Text,
    Unsupported(String),
}

impl From<&str> for ContentType {
    fn from(value: &str) -> Self {
        if value.starts_with("application") && value.contains("json") {
            Self::Json
        } else if value.starts_with("text/plain") {
            Self::Text
        } else {
            Self::Unsupported(value.to_owned())
        }
    }
}

pub mod api_v1_api;

pub mod chiv2_compat_api;

pub mod configuration;
