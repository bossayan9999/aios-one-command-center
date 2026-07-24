param(
    [Parameter(Position = 0)]
    [string]$Phase = "phase-1e",

    [string]$ExpectedBranch = "",

    [switch]$FixRuff,

    [switch]$AllowMissingFocused,

    [switch]$SkipE2E,

    [string]$CommitMessage = "",

    [switch]$Push
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root "venv\Scripts\python.exe"
$Runner = Join-Path $Root "scripts\run_phase.py"

if (-not (Test-Path $Python)) {
    throw "AIOS virtual environment Python not found: $Python"
}

if (-not (Test-Path $Runner)) {
    throw "Phase runner not found: $Runner"
}

$Arguments = @($Runner, $Phase)

if ($ExpectedBranch) {
    $Arguments += @("--expected-branch", $ExpectedBranch)
}

if ($FixRuff) {
    $Arguments += "--fix-ruff"
}

if ($AllowMissingFocused) {
    $Arguments += "--allow-missing-focused"
}

if ($SkipE2E) {
    $Arguments += "--skip-e2e"
}

if ($CommitMessage) {
    $Arguments += @("--commit", $CommitMessage)
}

if ($Push) {
    $Arguments += "--push"
}

& $Python @Arguments
exit $LASTEXITCODE
