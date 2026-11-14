//! Run by the Python E2E suite, which owns the real Uvicorn server lifecycle.
use server_browser_client::apis::{
    api_v1_api as api, chiv2_compat_api as compat, configuration::Configuration, Error,
};
use server_browser_models::*;
use std::time::Duration;

#[track_caller]
fn success<T, E>(result: Result<T, Error<E>>) -> T {
    result.unwrap_or_else(|_| panic!("generated operation failed"))
}

fn status_error<T, E: serde::Serialize>(result: Result<T, Error<E>>, expected: u16) {
    match result {
        Err(Error::ResponseError(response)) => {
            assert_eq!(response.status.as_u16(), expected);
            let entity = response
                .entity
                .expect("declared error model was not decoded");
            let value = serde_json::to_value(entity).unwrap();
            assert!(value["status"].is_string() && value["message"].is_string());
        }
        _ => panic!("expected a decoded HTTP error"),
    }
}

#[test]
#[allow(deprecated)] // The retired endpoint remains part of the wire contract.
#[ignore = "requires the local Python server; run uv run pytest -q src/test/server_browser_backend/test_sdk_e2e.py"]
fn generated_client_against_python_backend() {
    let base_path = std::env::var("SDK_E2E_URL").expect("Python harness URL required");
    let admin = std::env::var("SDK_E2E_ADMIN_KEY").expect("Python harness credential required");
    let host = std::env::var("SDK_E2E_HOST").unwrap();
    let diagnostic = std::env::var("SDK_E2E_DIAGNOSTIC").unwrap() == "True";
    let config = Configuration {
        base_path,
        client: reqwest::blocking::Client::builder()
            .timeout(Duration::from_secs(5))
            .redirect(reqwest::redirect::Policy::none())
            .no_proxy()
            .build()
            .unwrap(),
        ..Configuration::default()
    };
    assert!(!success(api::jwks(&config)).keys.is_empty());
    assert!(success(api::send_swagger(&config)).contains("openapi:"));
    status_error(
        api::login(&config, LoginRequest::new("retired".into())),
        410,
    );
    assert!(success(api::get_servers(&config)).servers.is_empty());
    let request = ServerRegistrationRequest::new(
        Chivalry2Ports::new(7777, 7778, 7779),
        "SDK café 🛡".into(),
        "wire round trip".into(),
        "map".into(),
        1,
        32,
    );
    let registration = success(api::register(&config, request.clone()));
    assert_eq!(registration.server.name, request.name);
    assert!(serde_json::to_value(&registration.server)
        .unwrap()
        .get("ip_address")
        .is_none());
    let id = &registration.server.unique_id;
    let key = &registration.key;
    let mut invalid = request.clone();
    invalid.player_count = 1025;
    status_error(api::register(&config, invalid), 400);
    status_error(api::heartbeat(&config, "", id), 400);
    status_error(api::heartbeat(&config, "wrong", id), 403);
    success(api::heartbeat(&config, key, id));
    success(api::update(
        &config,
        key,
        id,
        UpdateRegisteredServer::new(2, 32, "next".into()),
    ));
    let listing = success(api::get_servers(&config));
    assert_eq!(listing.servers.len(), 1);
    assert_eq!(
        matches!(
            listing.servers[0],
            ServerListingItem::ServerResponseWithIp(_)
        ),
        diagnostic
    );
    let value = serde_json::to_value(&listing.servers[0]).unwrap();
    assert_eq!(value["current_map"], "next");
    assert_eq!(value["player_count"], 2);
    if diagnostic {
        assert_eq!(value["ip_address"], host);
        assert!(value.get("local_ip_address").unwrap().is_null());
    } else {
        assert!(value.get("ip_address").is_none());
    }

    status_error(api::get_ban_list(&config, ""), 403);
    status_error(api::get_verified_list(&config, "wrong"), 403);
    assert!(success(api::get_ban_list(&config, &admin))
        .banned_ips
        .is_empty());
    let bans = IpListRequest {
        banned_ips: Some(vec!["203.0.113.0/24".into(), "2001:db8::/32".into()]),
        ..IpListRequest::default()
    };
    assert_eq!(
        success(api::add_to_ban_list(&config, &admin, bans.clone()))
            .banned_ips
            .len(),
        2
    );
    for ip in ["203.0.113.4", "2001:db8::4"] {
        assert!(success(api::check_banned(&config, ip)).banned);
    }
    assert!(success(api::remove_from_ban_list(&config, &admin, bans))
        .banned_ips
        .is_empty());
    assert!(!success(api::check_banned(&config, "2001:db8::4")).banned);
    let verified = IpListRequest {
        verified_ips: Some(vec![host.clone()]),
        ..IpListRequest::default()
    };
    success(api::get_verified_list(&config, &admin));
    success(api::add_to_verified_list(&config, &admin, verified.clone()));
    assert_eq!(
        serde_json::to_value(&success(api::get_servers(&config)).servers[0]).unwrap()
            ["is_verified"],
        true
    );
    success(api::remove_from_verified_list(&config, &admin, verified));
    assert_eq!(
        serde_json::to_value(&success(api::get_servers(&config)).servers[0]).unwrap()
            ["is_verified"],
        false
    );

    let games = success(compat::tbio_get_servers(&config));
    assert!(games.success);
    assert_eq!(&games.data.games[0].lobby_id, id);
    let address = if host.contains(':') {
        format!("[{host}]")
    } else {
        host.clone()
    };
    assert_eq!(games.data.games[0].server_hostname, address);
    assert!(
        success(compat::get_motd(
            &config,
            MotdRequest {
                language: Some("en".into())
            }
        ))
        .success
    );
    let matched = success(compat::playfab_client_matchmake(
        &config,
        MatchmakeRequest::new(id.clone()),
    ));
    assert_eq!(matched.data.server_hostname, host);
    let mut advertised_request = request;
    advertised_request.local_ip_address = Some("[fd00::5]".into());
    advertised_request.password_protected = Some(true);
    advertised_request.mods = Some(vec![Mod {
        name: "mod".into(),
        organization: "org".into(),
        version: "1".into(),
        active: Some(true),
    }]);
    let advertised = success(api::register(&config, advertised_request));
    assert!(advertised.server.password_protected);
    assert_eq!(advertised.server.mods[0].active, Some(true));
    let games = success(compat::tbio_get_servers(&config));
    let game = games
        .data
        .games
        .iter()
        .find(|game| game.lobby_id == advertised.server.unique_id)
        .unwrap();
    assert_eq!(game.server_hostname, "[fd00::5]");
    let matched = success(compat::playfab_client_matchmake(
        &config,
        MatchmakeRequest::new(advertised.server.unique_id.clone()),
    ));
    assert_eq!(matched.data.server_hostname, "fd00::5");
    if diagnostic {
        let listing = success(api::get_servers(&config));
        let entry = listing
            .servers
            .iter()
            .map(|server| serde_json::to_value(server).unwrap())
            .find(|server| server["unique_id"] == advertised.server.unique_id)
            .unwrap();
        assert_eq!(entry["local_ip_address"], "fd00::5");
    }
    success(api::delete_server(
        &config,
        &advertised.key,
        &advertised.server.unique_id,
    ));
    success(api::delete_server(&config, key, id));
    assert!(success(api::get_servers(&config)).servers.is_empty());
    status_error(api::heartbeat(&config, key, id), 404);
    status_error(api::delete_server(&config, key, id), 404);
    match compat::playfab_client_matchmake(&config, MatchmakeRequest::new(id.clone())) {
        Err(Error::ResponseError(response)) => {
            assert_eq!(response.status.as_u16(), 404);
            match response.entity {
                Some(compat::PlayfabClientMatchmakeError::Status404(error)) => {
                    assert_eq!(error.code, 404);
                    assert!(!error.success);
                }
                _ => panic!("missing typed PlayFab error"),
            }
        }
        _ => panic!("expected missing lobby"),
    }
}
