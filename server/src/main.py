from typing import Dict, List, Tuple
from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from collections import defaultdict
from datetime import datetime, timedelta

from models import HeartbeatSignal, Server
from logging.config import dictConfig

dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] %(levelname)s: %(message)s',
    }},
    'handlers': {'wsgi': {
        'class': 'logging.StreamHandler',
        'stream': 'ext://flask.logging.wsgi_errors_stream',
        'formatter': 'default'
    }},
    'root': {
        'level': 'INFO',
        'handlers': ['wsgi']
    }
})

ban_list: List[str] = []

app = Flask(__name__)
limiter = Limiter(app = app, key_func=get_remote_address)

# dict structure to store servers with their last heartbeat
servers: Dict[Tuple[str, int], Server] = {}

# 1 minute timeout for heartbeats
heartbeat_timeout = 65

@app.route('/register', methods=['POST'])
@limiter.limit("5/minute") 
def register():
    server_ip = request.remote_addr
    request.json["ip_address"] = server_ip
    request.json["last_heartbeat"] = datetime.now().timestamp()

    server = Server.from_json(request.json)
    server_id = server.id()
    
    if server.ip_address in ban_list:
        return jsonify({'status': 'banned'}), 403

    servers[server_id] = server
    timeout = server.last_heartbeat + heartbeat_timeout

    app.logger.info(f"Registered server \"{server.name}\" at {server.ip_address}:{server.port}")
    return jsonify({'status': 'registered', 'refresh_before': timeout}), 201

@app.route('/heartbeat', methods=['POST'])
@limiter.limit("60/minute") 
def heartbeat():
    server_ip = request.remote_addr
    request.json["ip_address"] = server_ip
    heartbeat_signal = HeartbeatSignal.from_json(request.json)

    server_id = (server_ip, heartbeat_signal.port)


    if server_id not in servers:
        return jsonify({'status': 'server not registered'}), 400
    
    server = servers[server_id]

    server.last_heartbeat = datetime.now().timestamp()
    server.player_count = heartbeat_signal.player_count
    server.max_players = heartbeat_signal.max_players
    server.current_map = heartbeat_signal.current_map

    timeout = server.last_heartbeat + heartbeat_timeout

    app.logger.info(f"Heartbeat received from server \"{server.name}\" at {server.ip_address}:{server.port} (timeout: {timeout})")

    return jsonify({'status': 'heartbeat received', 'refresh_before': timeout}), 200

@app.route('/servers', methods=['GET'])
@limiter.limit("60/minute")  
def get_servers():
    now = datetime.now().timestamp()

    # filter out servers with outdated heartbeats
    inactive_servers = [(id, server) for id, server in servers.items() if (now - server.last_heartbeat) > heartbeat_timeout or server.ip_address in ban_list]
    
    for (id, server) in inactive_servers:
        app.logger.info(f"Removing server \"{server.name}\" at {server.ip_address}:{server.port} due to inactivity")
        try:
            del servers[id]
        except KeyError:
            app.logger.warning("WARNING: Concurrent modification of servers dict")

    return jsonify({'servers': list(servers.values())}), 200

from flask import send_from_directory

@app.route('/swagger.yaml>')
def send_report():
    return send_from_directory('.', "chiv2-server-browser-api.yaml")


def __main__():
    app.run(host='0.0.0.0', port=8080, threaded=True)

if __name__ == "__main__":
    __main__()
