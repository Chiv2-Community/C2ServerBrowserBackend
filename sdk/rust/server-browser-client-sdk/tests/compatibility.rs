use server_browser_client::apis::chiv2_compat_api;
use server_browser_client_sdk::compatibility::{playfab_matchmake_url, tbio_base_url};

#[test]
fn native_urls_preserve_prefixes_and_normalize_trailing_slashes() {
    for (configured, base) in [
        ("http://localhost:8080", "http://localhost:8080"),
        ("http://localhost:8080/", "http://localhost:8080"),
        (
            "https://example.test/browser///",
            "https://example.test/browser",
        ),
        ("http://[::1]:8080/prefix/", "http://[::1]:8080/prefix"),
        ("https://example.test/a%2Fb/", "https://example.test/a%2Fb"),
    ] {
        let tbio = tbio_base_url(configured);
        assert_eq!(tbio, format!("{base}/api/tbio"));
        assert_eq!(
            playfab_matchmake_url(configured),
            format!("{base}/api/playfab/Client/Matchmake")
        );
        assert_eq!(
            format!("{tbio}/GetMotd"),
            chiv2_compat_api::get_motd_url(configured)
        );
        assert_eq!(
            format!("{tbio}/GetCurrentGames"),
            chiv2_compat_api::tbio_get_servers_url(configured)
        );
    }
}
