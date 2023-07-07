from typing import Dict, List, Tuple
from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from collections import defaultdict
from datetime import datetime, timedelta
import argparse
import secrets
from uuid import UUID, uuid4

from server_browser_backend.models import UpdateRegisteredServer, Server, Heartbeat, SecuredResource
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

# dict structure to store server list results  heartbeat
servers: Dict[Tuple[str, int], SecuredResource[Server]] = {}

# 1 minute timeout for heartbeats
heartbeat_timeout = 65

def get_ip(request) -> str:
    return request.headers.get('X-Forwarded-For', request.remote_addr)

@app.route('/servers', methods=['POST'])
@limiter.limit("5/minute") 
def register():
    server_ip = get_ip(request)
    if server_ip in ban_list:
        return jsonify({'status': 'banned'}), 403

    # Insert inferred params in to the json so we can build the server object from json.
    # Not the prettiest, but simplifies construction somewhat
    request.json["unique_id"] = str(uuid4())
    request.json["ip_address"] = server_ip
    request.json["last_heartbeat"] = datetime.now().timestamp()

    server = Server.from_json(request.json)
    key = secrets.token_hex(128)

    secured_resource = SecuredResource(key, server)

    servers[server.unique_id] = secured_resource
    timeout = server.last_heartbeat + heartbeat_timeout

    app.logger.info(f"Registered server \"{server.name}\" at {server.ip_address}:{server.port}")

    return jsonify({'status': 'registered', 'refresh_before': timeout, 'key': key, 'server': server}), 201

@app.route('/servers/<server_id>/heartbeat', methods=['POST'])
@limiter.limit("10/minute") 
def heartbeat(server_id):
    server_ip = get_ip(request)
    request.json["ip_address"] = server_ip
    request.json["unique_id"] = server_id
    heartbeat = Heartbeat.from_json(request.json)

    if heartbeat.unique_id not in servers:
        return jsonify({'status': 'server not registered'}), 400

    secured_server = servers[heartbeat.unique_id]

    result = secured_server.update(
        heartbeat.key, 
        lambda server: server.with_heartbeat(
            heartbeat, 
            server.last_heartbeat + heartbeat_timeout
        )
    )

    if not result:
        app.logger.warning("Heartbeat failed. Invalid request.")
        return jsonify({'status': 'forbidden'}), 403

    servers[heartbeat.unique_id] = result

    server = result.get()

    timeout = server.last_heartbeat + heartbeat_timeout

    app.logger.info(f"Heartbeat received from server \"{server.name}\" at {server.ip_address}:{server.port} (timeout: {timeout})")

    return jsonify({'status': 'heartbeat received', 'refresh_before': timeout, 'server': result.get()}), 200


@app.route('/servers/<server_id>', methods=['PUT'])
@limiter.limit("60/minute") 
def update(server_id):
    server_ip = get_ip(request)
    request.json["ip_address"] = server_ip
    request.json["unique_id"] = server_id
    update_request = UpdateRegisteredServer.from_json(request.json)

    if update_request.unique_id not in servers:
        return jsonify({'status': 'server not registered'}), 400

    secured_server = servers[update_request.unique_id]

    result = secured_server.update(
        update_request.key, 
        lambda server: server.with_update(update_request)
    )

    if not result:
        app.logger.warning("Update failed. Invalid request.")
        return jsonify({'status': 'forbidden'}), 403

    servers[update_request.unique_id] = result
    server = result.get()

    timeout = server.last_heartbeat + heartbeat_timeout

    app.logger.info(f"Update received from server \"{server.name}\" at {server.ip_address}:{server.port})")

    return jsonify({'status': 'update received', 'refresh_before': timeout, 'server': result.get()}), 200

@app.route('/servers', methods=['GET'])
@limiter.limit("60/minute")  
def get_servers():
    now = datetime.now().timestamp()
    app.logger.info(f"Server list requested")

    server_list = [(id, secured_resource.get()) for id, secured_resource in servers.items()]

    # filter out servers with outdated heartbeats
    inactive_servers = [(id, server) for id, server in server_list if (now - server.last_heartbeat) > heartbeat_timeout or server.ip_address in ban_list]
    
    for (id, server) in inactive_servers:
        app.logger.info(f"Removing server \"{server.name}\" at {server.ip_address}:{server.port} due to inactivity")
        try:
            del servers[id]
        except KeyError:
            app.logger.warning("WARNING: Concurrent modification of servers dict")

    return jsonify({'servers': list(map(lambda x: x.get(), servers.values()))}), 200

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
