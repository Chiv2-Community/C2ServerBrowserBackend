#!/bin/bash
set -euo pipefail

number='(0|[1-9][0-9]*)'
metadata='[0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*'
if [[ ! "$GITHUB_REF_NAME" =~ ^v$number\.$number\.$number(\+$metadata)?$ ]]; then
    echo "Expected vMAJOR.MINOR.PATCH with optional +build.metadata" >&2
    exit 1
fi

version=${GITHUB_REF_NAME#v}
image="ghcr.io/${GITHUB_REPOSITORY,,}"
docker_tag=${version/+/_}
if (( ${#docker_tag} > 128 )); then
    echo "Docker tag exceeds 128 characters" >&2
    exit 1
fi

{
    echo "version=$version"
    echo "image=$image"
    echo 'tags<<EOF'
    echo "$image:$docker_tag"
    if [[ "$version" != *+* ]]; then
        echo "$image:latest"
    fi
    echo 'EOF'
} >> "$GITHUB_OUTPUT"
