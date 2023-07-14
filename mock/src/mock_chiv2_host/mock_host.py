import argparse
import json
import time

import requests


def registerServer(
    address: str,
    port: int = 7777,
    name: str = "Chivalry 2 Server",
    description: str = "No description",
    current_map: str = "Unknown",
    player_count: int = -1,
    max_players: int = -1,
    mods=[],
):
    serverObj = {
        "ports": {"ping": 3077, "a2s": 27015, "game": port},
        "name": name,
        "description": description,
        "current_map": current_map,
        "player_count": player_count,
        "max_players": max_players,
        "mods": mods,
    }
    response = requests.post(address + "/api/v1/servers", json=serverObj)
    if not response.ok:
        print(response.text)
        raise RuntimeError(
            "Server could not be registered: error " + str(response.status_code)
        )
    else:
        return response.json()


def heartbeat(address: str, unique_id: str, key: str):
    response = requests.post(
        address + f"/api/v1/servers/{unique_id}/heartbeat",
        headers={"x-chiv2-server-browser-key": key},
    )
    if not response.ok:
        raise RuntimeError("Heartbeat failure: error " + str(response.status_code))
    else:
        return response.json()


def getServerList(address: str):
    response = requests.get(address + "/api/v1/servers")
    if not response.ok:
        raise RuntimeError(
            "Failed to retreive server list: error " + str(response.status_code)
        )
    else:
        return response.json()["servers"]


def main():
    parser = argparse.ArgumentParser(description="Mock client for the Flask server.")
    parser.add_argument(
        "--host", type=str, default="localhost", help="The host of the Flask server."
    )
    parser.add_argument(
        "--port", type=int, default=None, help="The port of the Flask server."
    )
    parser.add_argument(
        "--file",
        type=str,
        default="assets/servers.json",
        help="The file containing the list of mock servers.",
    )
    parser.add_argument(
        "-s",
        "--tls",
        default=False,
        action="store_true",
        help="Whether to use TLS or not",
    )
    args = parser.parse_args()

    if args.port is None:
        args.port = 443 if args.tls else 80

    protocol = "https" if args.tls else "http"
    address = f"{protocol}://{args.host}:{args.port}"

    with open(args.file, "r") as f:
        servers = json.load(f)

    registered_servers = []
    for server in servers:
        print("Registering server on port " + str(server["port"]))
        result = registerServer(address, **server)
        print(
            "Registered server on port "
            + str(server["port"])
            + " with unique id "
            + result["server"]["unique_id"]
        )

        registered_servers.append(
            {"key": result["key"], "unique_id": result["server"]["unique_id"]}
        )

    while True:
        time.sleep(60)
        for server in registered_servers:
            print("Sending heartbeat for server on port " + server["unique_id"])
            heartbeat(address, **server)


if __name__ == "__main__":
    main()
