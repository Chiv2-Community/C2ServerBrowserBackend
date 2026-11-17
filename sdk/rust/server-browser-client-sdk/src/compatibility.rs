//! Contract-derived URLs for applications using the game's native HTTP transport.
use server_browser_client::apis::chiv2_compat_api;

pub use chiv2_compat_api::playfab_client_matchmake_url as playfab_matchmake_url;

/// Build the TBIO base URL to which the native client appends operation names.
/// Preserves deployment prefixes and removes trailing slashes from the configured base.
#[must_use]
pub fn tbio_base_url(base_url: &str) -> String {
    let mut url = chiv2_compat_api::get_motd_url(base_url);
    if let Some(index) = url.rfind('/') {
        url.truncate(index);
    }
    url
}
