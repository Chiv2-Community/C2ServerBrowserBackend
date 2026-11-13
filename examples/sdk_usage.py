"""Type-checked downstream SDK usage; importing this file performs no network I/O."""
from server_browser_client import AsyncClient, Client
from server_browser_models.models import ServerListResponse, ServerResponse


def list_servers(base_url: str) -> list[ServerResponse]:
    with Client(base_url) as client:
        result = client.get_servers()
        if not isinstance(result.body, ServerListResponse):
            raise RuntimeError(f"Unexpected response: {result.status}")
        return list(result.body.servers)


async def list_servers_async(base_url: str) -> list[ServerResponse]:
    async with AsyncClient(base_url) as client:
        result = await client.get_servers()
        if not isinstance(result.body, ServerListResponse):
            raise RuntimeError(f"Unexpected response: {result.status}")
        return list(result.body.servers)
