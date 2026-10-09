$ErrorActionPreference="Stop"
$base=Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $base
if(-not(Test-Path ".\.venv\Scripts\python.exe")){throw "Run .\INSTALL_GRANTOPS_MVP.ps1 first"}
& ".\.venv\Scripts\python.exe" -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501