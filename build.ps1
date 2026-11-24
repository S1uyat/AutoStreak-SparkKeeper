param()
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$Python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) { throw 'Create .venv and install requirements-build.txt first.' }
& $Python -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
& $Python -m PyInstaller --noconfirm SparkKeeper.spec
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
Write-Output 'Built dist\SparkKeeper.exe'
