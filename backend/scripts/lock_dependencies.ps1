param(
    [string]$PythonCommand = ""
)

$ErrorActionPreference = "Stop"
$backendDirectory = Resolve-Path (Join-Path $PSScriptRoot "..")
$localPython = Join-Path $backendDirectory "venv\Scripts\python.exe"

if (-not $PythonCommand) {
    $PythonCommand = if (Test-Path -LiteralPath $localPython) { $localPython } else { "python" }
}

Push-Location $backendDirectory
$previousCompileCommand = $env:CUSTOM_COMPILE_COMMAND
$env:CUSTOM_COMPILE_COMMAND = "powershell -File scripts/lock_dependencies.ps1"
try {
    & $PythonCommand -m piptools compile --generate-hashes --strip-extras --resolver=backtracking --output-file requirements.txt requirements.in
    if ($LASTEXITCODE -ne 0) { throw "Production dependency lock failed." }

    & $PythonCommand -m piptools compile --generate-hashes --strip-extras --allow-unsafe --resolver=backtracking --output-file requirements-dev.txt requirements-dev.in
    if ($LASTEXITCODE -ne 0) { throw "Development dependency lock failed." }
}
finally {
    $env:CUSTOM_COMPILE_COMMAND = $previousCompileCommand
    Pop-Location
}
