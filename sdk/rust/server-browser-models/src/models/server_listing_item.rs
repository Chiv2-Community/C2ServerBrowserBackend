// Generated from OpenAPI anyOf. Do not edit; regenerate this module.
use crate::models;
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(untagged)]
pub enum ServerListingItem {
    ServerResponseWithIp(models::ServerResponseWithIp),
    ServerResponse(models::ServerResponse),
}

impl Default for ServerListingItem {
    fn default() -> Self {
        Self::ServerResponseWithIp(models::ServerResponseWithIp::default())
    }
}
