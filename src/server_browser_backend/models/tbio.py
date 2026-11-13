"""Domain conversions for the generated TBIO contract."""
from ipaddress import IPv4Address, IPv6Address

from server_browser_models.models import TbioGame, TbioServerListData, TbioTags
from server_browser_backend.models.base_models import Server


def game_from_server(
    server: Server, client_ip: IPv4Address | IPv6Address | None,
    fixed_name: str | None = None,
) -> TbioGame:
    address = server.address_for(client_ip)
    return TbioGame(
        region="paris", lobby_id=server.unique_id, max_players=server.max_players,
        official=server.is_verified, build_version="dummy", game_mode="40p",
        player_user_ids=list(range(server.player_count)), run_time=500, game_server_state=1,
        tags=TbioTags(
            build_id_s="dummy", server_name_s=fixed_name if fixed_name is not None else server.name,
            region_s="paris", official_b=str(server.is_verified).lower(), platform_s="any",
            ffa_b="true", ms_i="2", map_name_s=server.current_map,
            ping_port_i=str(server.ports.ping), query_port_i=str(server.ports.a2s),
            t0_c="0", pp_b="true" if server.password_protected else "false", t1_c="6", mtim_i="277",
        ),
        last_heartbeat=int(server.last_heartbeat), server_hostname=address,
        server_ipv4_address=address, server_port=server.ports.game,
    )


def server_list_data(
    servers: list[Server], client_ip: IPv4Address | IPv6Address | None,
    fixed_name: str | None = None,
) -> TbioServerListData:
    return TbioServerListData(
        game_count=len(servers), player_count=sum(s.player_count for s in servers),
        games=[game_from_server(server, client_ip, fixed_name) for server in servers],
    )
