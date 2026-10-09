$ErrorActionPreference="Stop"
$base=Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $base
$env:PYTHONPATH=$base
if(Test-Path ".\.venv\Scripts\python.exe"){$py=".\.venv\Scripts\python.exe";$args=@()}else{$py="py";$args=@("-3.11")}
& $py @args "tests\test_core.py"
if($LASTEXITCODE -ne 0){throw "GrantOps MVP tests failed"}
Write-Host "[GrantOps MVP] PASS_MVP_CORE_TESTS"