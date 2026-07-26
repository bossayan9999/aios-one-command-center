$ErrorActionPreference = "Stop"

$AppRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $AppRoot ".venv\Scripts\pythonw.exe"
$LogDir = Join-Path $AppRoot "logs"
$OutputLog = Join-Path $LogDir "aios-startup-output.log"
$ErrorLog = Join-Path $LogDir "aios-startup-error.log"

New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

if (-not (Test-Path -LiteralPath $Python)) {
    Add-Content -LiteralPath $ErrorLog -Value "$(Get-Date -Format o) Missing $Python. Run: python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
    exit 1
}

$AlreadyRunning = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if (-not $AlreadyRunning) {
    Start-Process `
        -FilePath $Python `
        -ArgumentList @(
            "-m",
            "uvicorn",
            "api.main:app",
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
    try {
        $Health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 2
        if ($Health.status -eq "ok") {
            exit 0
        }
    } catch {
        Start-Sleep -Seconds 2
    }
}

Add-Content -LiteralPath $ErrorLog -Value "$(Get-Date -Format o) AIOS did not become healthy within 60 seconds."
exit 1
