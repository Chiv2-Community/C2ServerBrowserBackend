param(
    [Parameter(Mandatory=$false)]
    [string]$Version = "latest",

    [Parameter(Mandatory=$false)]
    [string]$AdminKey = $env:ADMIN_KEY
)

# Fail if AdminKey is not provided
if ([string]::IsNullOrWhiteSpace($AdminKey)) {
    Write-Error "ADMIN_KEY is missing."
    Write-Host "You must provide an admin key to run this server." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Option 1: Set the environment variable (Recommended)"
    Write-Host "    `$env:ADMIN_KEY = 'your_secret_key'"
    Write-Host "    .\run-in-docker.ps1"
    Write-Host ""
    Write-Host "Option 2: Pass it as a parameter"
    Write-Host "    .\run-in-docker.ps1 -AdminKey 'your_secret_key'"
    exit 1
}

# Get the absolute path for the config directory based on current location
$HOST_CONFIG_DIR = Join-Path (Get-Location).Path "config"

# Ensure the config directory exists to avoid docker errors
if (-not (Test-Path $HOST_CONFIG_DIR)) {
    New-Item -ItemType Directory -Force -Path $HOST_CONFIG_DIR | Out-Null
}

docker run `
  -p 8080:8080 `
  -e ADMIN_KEY="$AdminKey" `
  -e CONFIG_DIR='/config' `
  -v "${HOST_CONFIG_DIR}:/config" `
  -it `
  "jacoby6000/chivalry2-unofficial-server-browser-backend:$Version" `
    -b 0.0.0.0:8080 `
    -w 1