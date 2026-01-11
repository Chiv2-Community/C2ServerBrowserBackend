#!/bin/bash

# Default values
VERSION="latest"
ADMIN_KEY="${ADMIN_KEY}"

# Function to display usage
usage() {
    echo "Usage: $0 [-v VERSION] [-k ADMIN_KEY]"
    echo "  -v VERSION    Docker image version (default: latest)"
    echo "  -k ADMIN_KEY  Admin key for the server"
    exit 1
}

# Parse command line arguments
while getopts "v:k:" opt; do
    case "$opt" in
        v) VERSION=$OPTARG ;;
        k) ADMIN_KEY=$OPTARG ;;
        *) usage ;;
    esac
done

# Fail if ADMIN_KEY is not provided
if [ -z "$ADMIN_KEY" ]; then
    echo "Error: ADMIN_KEY is missing." >&2
    echo "You must provide an admin key to run this server."
    echo ""
    echo "Option 1: Set the environment variable (Recommended)"
    echo "    export ADMIN_KEY='your_secret_key'"
    echo "    $0"
    echo ""
    echo "Option 2: Pass it as a parameter"
    echo "    $0 -k 'your_secret_key'"
    exit 1
fi

# Get the absolute path for the config directory
HOST_CONFIG_DIR="$(pwd)/config"

# Ensure the config directory exists
mkdir -p "$HOST_CONFIG_DIR"

docker run \
  -p 8080:8080 \
  -e ADMIN_KEY="$ADMIN_KEY" \
  -e CONFIG_DIR='/config' \
  -v "${HOST_CONFIG_DIR}:/config" \
  -it \
  "jacoby6000/chivalry2-unofficial-server-browser-backend:$VERSION" \
    -b 0.0.0.0:8080 \
    -w 1
