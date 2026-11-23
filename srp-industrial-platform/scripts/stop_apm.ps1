param([int]$Port=18140)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path;$pidFile=Join-Path $root 'state\apm_supervised\apm.pid.json'
if(!(Test-Path $pidFile)){throw "No supervised APM PID metadata at $pidFile; refusing to stop an unidentified process."}
$meta=Get-Content -Raw $pidFile|ConvertFrom-Json
if($meta.root -ne $root -or [int]$meta.port -ne $Port){throw 'PID metadata does not match this repository and requested port.'}
$p=Get-Process -Id ([int]$meta.pid) -ErrorAction Stop
if($p.Path -ne $meta.python){throw 'PID has been reused by a different executable; refusing to stop it.'}
$p.CloseMainWindow()|Out-Null
try{$p.WaitForExit(10000)}catch{}
if(!$p.HasExited){throw "APM PID $($p.Id) did not exit gracefully; leaving it running for manual review."}
Remove-Item -LiteralPath $pidFile -Force
Write-Output "APM PID $($p.Id) stopped; exit code $($p.ExitCode)."
