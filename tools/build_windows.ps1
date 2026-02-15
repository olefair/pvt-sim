param(
    [string]$Python = "py",
    [string]$VenvPath = ".venv-build",
    [string]$Extras = "gui",
    [switch]$OneFile,
    [switch]$SkipCli
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $root

$logDir = Join-Path $root "build_logs"
New-Item -ItemType Directory -Force $logDir | Out-Null
$logPath = Join-Path $logDir "build_windows.log"
$transcriptStarted = $false
try {
    Start-Transcript -Path $logPath -Force
    $transcriptStarted = $true
} catch {
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $logPath = Join-Path $logDir ("build_windows_{0}.log" -f $timestamp)
    try {
        Start-Transcript -Path $logPath -Force
        $transcriptStarted = $true
    } catch {
        Write-Warning "Failed to start transcript logging. Continuing without transcript."
    }
}

Write-Host "Build root: $root"
Write-Host "Python: $Python"
Write-Host "Venv: $VenvPath"
Write-Host "Extras: $Extras"
Write-Host "OneFile: $OneFile"
Write-Host "Build CLI: $(-not $SkipCli)"

$buildDir = Join-Path $root "build"
$distDir = Join-Path $root "dist"
$buildOneFileDir = Join-Path $root "build_onefile"
$distOneFileDir = Join-Path $root "dist_onefile"

Remove-Item -Recurse -Force $buildDir, $distDir, $buildOneFileDir, $distOneFileDir -ErrorAction SilentlyContinue

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

function Initialize-TempDir {
    param(
        [string]$PythonExe
    )

    $tmpRoot = Join-Path $root ".tmp"
    New-Item -ItemType Directory -Force $tmpRoot | Out-Null
    $tmpDir = Join-Path $tmpRoot ("run-" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Force $tmpDir | Out-Null
    $env:TEMP = $tmpDir
    $env:TMP = $tmpDir

    & $PythonExe -c "import tempfile, pathlib; p = pathlib.Path(tempfile.gettempdir())/'pvt_temp_test.txt'; p.write_text('ok'); p.unlink()" 2>$null
    if ($LASTEXITCODE -eq 0) {
        return $tmpDir
    }

    $fallbackRoot = Join-Path $env:LOCALAPPDATA "Temp\\pvt-sim"
    New-Item -ItemType Directory -Force $fallbackRoot | Out-Null
    $fallbackDir = Join-Path $fallbackRoot ("run-" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Force $fallbackDir | Out-Null
    $env:TEMP = $fallbackDir
    $env:TMP = $fallbackDir

    & $PythonExe -c "import tempfile, pathlib; p = pathlib.Path(tempfile.gettempdir())/'pvt_temp_test.txt'; p.write_text('ok'); p.unlink()" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "TEMP/TMP is not writable for Python. Please adjust permissions or set TEMP/TMP to a writable location."
    }

    return $fallbackDir
}

$activeTemp = Initialize-TempDir -PythonExe $bootstrap
Write-Host "TEMP: $env:TEMP"
Write-Host "TMP: $env:TMP"

if (!(Test-Path $VenvPath)) {
    & $bootstrap -m venv $VenvPath
}

$venvPython = Join-Path $VenvPath "Scripts\python.exe"
if (!(Test-Path $venvPython)) {
    throw "Virtual environment not found at $venvPython"
}

$venvInfo = & $venvPython -c "import sys; print(sys.executable); print(sys.version.split()[0])"
Write-Host "Build venv Python executable: $($venvInfo[0])"
Write-Host "Build venv Python version: $($venvInfo[1])"

Write-Host "==> Step 1: Ensure pip is available"
$usingFallback = $false
& $venvPython -m pip --version | Out-Null
if ($LASTEXITCODE -ne 0) {
    & $venvPython -m ensurepip --upgrade --default-pip
    if ($LASTEXITCODE -ne 0) {
        $fallbackPython = Join-Path ".venv" "Scripts\python.exe"
        if (Test-Path $fallbackPython) {
            Write-Warning "pip bootstrap failed in $VenvPath. Falling back to existing .venv."
            $VenvPath = ".venv"
            $venvPython = $fallbackPython
            $usingFallback = $true
            $venvInfo = & $venvPython -c "import sys; print(sys.executable); print(sys.version.split()[0])"
            Write-Host "Build venv Python executable: $($venvInfo[0])"
            Write-Host "Build venv Python version: $($venvInfo[1])"
        } else {
            throw "pip bootstrap (ensurepip) failed with exit code $LASTEXITCODE."
        }
    }
    & $venvPython -m pip --version | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "pip is unavailable in the build venv after ensurepip."
    }
}

Write-Host "==> Step 2: Install dependencies"
if (-not $usingFallback) {
    & $venvPython -m pip install --upgrade pip setuptools wheel
    if ($LASTEXITCODE -ne 0) {
        throw "pip upgrade failed with exit code $LASTEXITCODE."
    }
    & $venvPython -m pip install -e (".[{0}]" -f $Extras)
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "pip install failed in repo-local TEMP. Retrying with fallback TEMP."
        $fallbackRoot = Join-Path $env:LOCALAPPDATA "Temp\\pvt-sim"
        New-Item -ItemType Directory -Force $fallbackRoot | Out-Null
        $fallbackDir = Join-Path $fallbackRoot ("run-" + [guid]::NewGuid().ToString("N"))
        New-Item -ItemType Directory -Force $fallbackDir | Out-Null
        $env:TEMP = $fallbackDir
        $env:TMP = $fallbackDir
        Write-Host "TEMP: $env:TEMP"
        Write-Host "TMP: $env:TMP"
        & $venvPython -m pip install -e (".[{0}]" -f $Extras)
        if ($LASTEXITCODE -ne 0) {
            throw "pip install (project extras) failed with exit code $LASTEXITCODE."
        }
    }
} else {
    Write-Host "Using existing .venv; skipping pip upgrade and editable install."
}

& $venvPython -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('PyInstaller') else 1)"
if ($LASTEXITCODE -ne 0) {
    & $venvPython -m pip install pyinstaller
    if ($LASTEXITCODE -ne 0) {
        throw "pip install (pyinstaller) failed with exit code $LASTEXITCODE."
    }
}

& $venvPython -m pip --version
& $venvPython -m pip freeze

if (-not $env:PYTHONHASHSEED) { $env:PYTHONHASHSEED = "0" }
# ZIP timestamps cannot be earlier than 1980-01-01; use that epoch for reproducible builds.
if (-not $env:SOURCE_DATE_EPOCH) { $env:SOURCE_DATE_EPOCH = "315532800" }

Write-Host "==> Step 3: PyInstaller build"
$env:PVT_ONEFILE = "0"
$env:PVT_BUILD_CLI = if ($SkipCli) { "0" } else { "1" }
& $venvPython -m PyInstaller --noconfirm --clean "packaging/pvtsim_gui.spec"
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE."
}

if ($OneFile) {
    $env:PVT_ONEFILE = "1"
    $env:PVT_BUILD_CLI = if ($SkipCli) { "0" } else { "1" }
    & $venvPython -m PyInstaller --noconfirm --clean --distpath "dist_onefile" --workpath "build_onefile" "packaging/pvtsim_gui.spec"
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller (onefile) failed with exit code $LASTEXITCODE."
    }
}

if ($transcriptStarted) {
    Stop-Transcript
}
