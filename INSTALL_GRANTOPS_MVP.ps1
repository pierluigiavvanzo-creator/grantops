$ErrorActionPreference="Stop"
$base=Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $base
if(-not(Test-Path ".\.venv")){py -3.11 -m venv .venv}
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
Write-Host "[GrantOps MVP] INSTALL PASS"