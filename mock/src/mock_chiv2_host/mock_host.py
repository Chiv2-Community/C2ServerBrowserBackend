import requests
import json
import argparse
import time

def registerServer(address: str, port: int = 7777, name: str = "Chivalry 2 Server", 
                   description: str = "No description", current_map: str = "Unknown", 
                   player_count: int = -1, max_players: int = -1, mods = []):
    serverObj = {
        "port": port,
        "name": name,
        "description": description,
        "current_map": current_map,
        "player_count": player_count,
        "max_players": max_players,
        "mods": mods
    }
    response = requests.post(address+"/register", json=serverObj)
    if not response.ok:
        raise RuntimeError("Server could not be registered: error " + str(response.status_code))
    else:
        return float(response.json()['refresh_before'])
    
def heartbeat(address: str, port: int = 7777, 
              current_map: str = "Unknown", 
              player_count: int = -1, max_players: int = -1):
    heartbeatObj = {
        "port": port,
        "current_map": current_map,
        "player_count": player_count,
        "max_players": max_players
    }
    response = requests.post(address+"/heartbeat", json=heartbeatObj)
    if not response.ok:
        raise RuntimeError("Heartbeat failure: error " + str(response.status_code))
    else:
        return float(response.json()['refresh_before'])
    
def getServerList(address: str):
    response = requests.get(address+"/servers")
    if not response.ok:
        raise RuntimeError("Failed to retreive server list: error " + str(response.status_code))
    else:
        return response.json()["servers"]

def main():
    parser = argparse.ArgumentParser(description='Mock client for the Flask server.')
    parser.add_argument('--host', type=str, default='localhost',
                        help='The host of the Flask server.')
    parser.add_argument('--port', type=int, default=8080,
                        help='The port of the Flask server.')
    parser.add_argument('--file', type=str, required=True,
                        help='The file containing the list of mock servers.')
    args = parser.parse_args()

    address = f"http://{args.host}:{args.port}"

    with open(args.file, 'r') as f:
        servers = json.load(f)

    for server in servers:
        print("Registering server on port " + str(server["port"]))
        registerServer(address, **server)
        del server["name"]
        del server["description"]
        del server["mods"]

    while True:
        time.sleep(60)
        for server in servers:
            print("Sending heartbeat for server on port " + str(server["port"]))
            heartbeat(address, **server)

if __name__ == "__main__":
    main()
