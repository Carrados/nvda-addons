# Creates .venv with the add-on build tools. Run once, or again to update them.
# The template targets Python 3.13, the same version NVDA itself runs on.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path .venv)) { py -3.13 -m venv .venv }
.venv\Scripts\python.exe -m pip install --quiet --upgrade pip
.venv\Scripts\python.exe -m pip install --quiet -r requirements.txt
Write-Output "Build tools ready."
