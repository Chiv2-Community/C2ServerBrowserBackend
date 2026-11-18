#!/bin/bash
set -euo pipefail

number='(0|[1-9][0-9]*)'
release_tag="${RELEASE_TAG:-${GITHUB_REF_NAME:-}}"
identifier="($number|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
prerelease="$identifier(\.$identifier)*"
if [[ ! "$release_tag" =~ ^v$number\.$number\.$number(-$prerelease)?$ ]]; then
    echo "Expected vMAJOR.MINOR.PATCH with optional -prerelease; build metadata is not supported" >&2
    exit 1
fi

version=${release_tag#v}
image="ghcr.io/${GITHUB_REPOSITORY,,}"
if (( ${#version} > 128 )); then
    echo "Docker tag exceeds 128 characters" >&2
    exit 1
fi

{
    echo "version=$version"
    echo "image=$image"
    echo 'tags<<EOF'
    echo "$image:$version"
    if [[ "$version" != *-* ]]; then
        echo "$image:latest"
    fi
    echo 'EOF'
} >> "$GITHUB_OUTPUT"
