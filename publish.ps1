$ErrorActionPreference = "Stop"
$version = (Get-Content -Raw VERSION).Trim()
uv run --no-project python scripts/sync_versions.py --check --tag "v$version"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# If we can't login, no reason to continue.
docker login
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

./ci.ps1
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$tags = @("-t", "jacoby6000/chivalry2-unofficial-server-browser-backend:$version")
if (-not $version.Contains("-")) {
    $tags += @("-t", "jacoby6000/chivalry2-unofficial-server-browser-backend:latest")
}
docker buildx build . @tags --push
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

git tag "v$version"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
git push origin "refs/tags/v$version"
exit $LASTEXITCODE
