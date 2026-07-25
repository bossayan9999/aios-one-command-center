$AppRoot = "C:\Users\Christian\Downloads\aios-one-command-center"
$Python = Join-Path $AppRoot "venv\Scripts\python.exe"
$LogDir = Join-Path $AppRoot "logs"
$OutputLog = Join-Path $LogDir "aios-startup-output.log"
$ErrorLog = Join-Path $LogDir "aios-startup-error.log"
$Website = "https://aios.bossayan.com/?build=phase1h-mcp-runtime-4#command-center"

New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
Set-Location $AppRoot

$AlreadyRunning = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue

if (-not $AlreadyRunning) {
    Start-Process `
        -FilePath $Python `
        -ArgumentList @(
            "-m",
            "uvicorn",
            "api.main:app",
            "--env-file",
            "$AppRoot\.env.security",
            "--host",
            "127.0.0.1",
            "--port",
            "8000"
        ) `
        -WorkingDirectory $AppRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $OutputLog `
        -RedirectStandardError $ErrorLog
}

for ($attempt = 1; $attempt -le 30; $attempt++) {
    $Ready = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
    if ($Ready) {
        Start-Process $Website
        exit 0
    }
    Start-Sleep -Seconds 2
}

Add-Content $ErrorLog "$(Get-Date -Format o) AIOS did not become ready within 60 seconds."
exit 1
