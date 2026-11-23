param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$AcquisitionArgs
)

$Repository = Split-Path -Parent $PSScriptRoot
$PreferredPython = 'C:\Users\HARSHIT\AppData\Local\Python\bin\python.exe'
$Python = if (Test-Path -LiteralPath $PreferredPython) { $PreferredPython } else { 'python' }

Set-Location -LiteralPath $Repository
& $Python 'scripts\echometer\run_bulk_acquisition.py' @AcquisitionArgs
exit $LASTEXITCODE
