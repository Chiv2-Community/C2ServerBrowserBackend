# If we can't login, no reason to continue.
docker login

$version = Select-String -Path "pyproject.toml" -Pattern "version" |
        Select-Object -First 1 |
        ForEach-Object { $_.Line -replace 'version = ', '' -replace '"', '' -replace "'", '' } |
        ForEach-Object { $_.Trim() }

./ci.ps1

docker buildx build . `
  -t "jacoby6000/chivalry2-unofficial-server-browser-backend:$version" `
  -t "jacoby6000/chivalry2-unofficial-server-browser-backend:latest" `
  --push