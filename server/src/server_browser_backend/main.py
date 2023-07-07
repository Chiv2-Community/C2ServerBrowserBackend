from typing import Dict, List, Tuple
from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from collections import defaultdict
from datetime import datetime, timedelta
import argparse

from server_browser_backend.models import UpdateRegisteredServer, Server, Heartbeat
from server_browser_backend.dict_util import DictKeyError, DictTypeError
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
@limiter.limit("10/minute") 
def heartbeat():
    server_ip = request.remote_addr
    request.json["ip_address"] = server_ip
    heartbeat = Heartbeat.from_json(request.json)
    server_id = (server_ip, heartbeat.port)

    if server_id not in servers:
        return jsonify({'status': 'server not registered'}), 400
    
    server = servers[server_id]
    server.last_heartbeat = datetime.now().timestamp()

    timeout = server.last_heartbeat + heartbeat_timeout

    app.logger.info(f"Heartbeat received from server \"{server.name}\" at {server.ip_address}:{server.port} (timeout: {timeout})")
    
    return jsonify({'status': 'heartbeat received', 'refresh_before': timeout}), 200


@app.route('/update', methods=['POST'])
@limiter.limit("60/minute") 
def update():
    server_ip = request.remote_addr
    request.json["ip_address"] = server_ip
    update_request = UpdateRegisteredServer.from_json(request.json)

    server_id = (server_ip, update_request.port)


    if server_id not in servers:
        return jsonify({'status': 'server not registered'}), 400
    
    server = servers[server_id]

    server.player_count = update_request.player_count
    server.max_players = update_request.max_players
    server.current_map = update_request.current_map

    timeout = server.last_heartbeat + heartbeat_timeout

    app.logger.info(f"Update received from server \"{server.name}\" at {server.ip_address}:{server.port})")

    return jsonify({'status': 'update received', 'refresh_before': timeout}), 200

@app.route('/servers', methods=['GET'])
@limiter.limit("60/minute")  
def get_servers():
    now = datetime.now().timestamp()
    app.logger.info(f"Server list requested")

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

@app.route('/swagger.yaml')
def send_swagger():
    return send_from_directory('.', "chiv2-server-browser-api.yaml")

@app.errorhandler(DictKeyError)
def handle_dict_key_error(e):
    return jsonify({'error': f"Missing key '{e.key}'", 'context': e.context}), 400

@app.errorhandler(DictTypeError)
def handle_dict_type_error(e):
    error_string = f"Invalid type for key '{e.key}'. Got '{e.actual_type.__name__}' with value '{e.value}', but expected '{e.expected_type.__name__}'"
    return jsonify({'error': error_string, 'context': e.context}), 400

def main():
    parser = argparse.ArgumentParser(description='Start the Flask server.')
    parser.add_argument('--host', type=str, default='0.0.0.0',
                        help='The interface to bind to.')
    parser.add_argument('--port', type=int, default=8080,
                        help='The port to bind to.')

    args = parser.parse_args()

    app.run(host=args.host, port=args.port, threaded=True)

if __name__ == "__main__":
    main()
