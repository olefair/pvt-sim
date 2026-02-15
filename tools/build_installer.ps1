param(
    [string]$Python = "py",
    [string]$VenvPath = ".venv-build",
    [string]$Extras = "gui",
    [switch]$SkipCli
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $root

$tmpRoot = Join-Path $root ".tmp"
New-Item -ItemType Directory -Force $tmpRoot | Out-Null
$tmpDir = Join-Path $tmpRoot ("run-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force $tmpDir | Out-Null
$env:TEMP = $tmpDir
$env:TMP = $tmpDir
# ZIP timestamps cannot be earlier than 1980-01-01; use that epoch for reproducible builds.
if (-not $env:SOURCE_DATE_EPOCH) { $env:SOURCE_DATE_EPOCH = "315532800" }

$logDir = Join-Path $root "build_logs"
New-Item -ItemType Directory -Force $logDir | Out-Null
$logPath = Join-Path $logDir "build_installer.log"
Start-Transcript -Path $logPath -Force

$bootstrap = $Python
$bootstrapInfo = & $bootstrap -c "import sys; print(sys.executable); print(sys.version.split()[0])" 2>$null
if ($LASTEXITCODE -ne 0) {
    $bootstrap = "py"
    $bootstrapInfo = & $bootstrap -c "import sys; print(sys.executable); print(sys.version.split()[0])" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Python launcher not found. Install Python or provide -Python."
    }
}

Write-Host "Bootstrap Python executable: $($bootstrapInfo[0])"
Write-Host "Bootstrap Python version: $($bootstrapInfo[1])"
Write-Host "TEMP: $env:TEMP"
Write-Host "TMP: $env:TMP"

$buildScript = Join-Path $PSScriptRoot "build_windows.ps1"
& $buildScript -Python $bootstrap -VenvPath $VenvPath -Extras $Extras -SkipCli:$SkipCli

$versionMatch = Select-String -Path "pyproject.toml" -Pattern '^\s*version\s*=\s*"([^"]+)"'
if (-not $versionMatch) {
    throw "Could not parse version from pyproject.toml"
}
$version = $versionMatch.Matches[0].Groups[1].Value

$distDir = Join-Path $root "dist\pvtsim"
if (-not (Test-Path $distDir)) {
    throw "Expected build output at $distDir. Run tools\\build_windows.ps1 first."
}

$possibleIscc = @(
    (Join-Path $env:INNOSETUP "ISCC.exe"),
    "C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe",
    "C:\\Program Files\\Inno Setup 6\\ISCC.exe"
) | Where-Object { $_ -and (Test-Path $_) }

if ($possibleIscc.Count -eq 0) {
    Write-Host "Inno Setup not found (ISCC.exe)."
    Write-Host "Install Inno Setup 6 from the official installer, then re-run."
    Write-Host "If installed to a custom location, set INNOSETUP to the install folder."
    Stop-Transcript
    exit 1
}

$iscc = $possibleIscc[0]
$installerDir = Join-Path $root "dist_installer"
New-Item -ItemType Directory -Force $installerDir | Out-Null

& $iscc "packaging\\installer\\pvtsim.iss" "/DAppVersion=$version" "/DDistDir=$distDir" "/DOutputDir=$installerDir"

Stop-Transcript
