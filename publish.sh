#!/bin/bash
set -euo pipefail

VERSION=$(uv run --locked bump-my-version show current_version)

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
