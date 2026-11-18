#!/bin/bash
set -euo pipefail

VERSION=$(tr -d '\r\n' < VERSION)
uv run --no-project python scripts/sync_versions.py --check --tag "v$VERSION"

# If we can't login, no reason to continue.
docker login

/bin/bash ./ci.sh

tags=(-t "jacoby6000/chivalry2-unofficial-server-browser-backend:$VERSION")
if [[ "$VERSION" != *-* ]]; then
  tags+=(-t "jacoby6000/chivalry2-unofficial-server-browser-backend:latest")
fi
docker buildx build . "${tags[@]}" --push

git tag "v$VERSION"
git push origin "refs/tags/v$VERSION"
