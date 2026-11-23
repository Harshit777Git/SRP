param([int]$Port=18140,[string]$Python='C:\Users\HARSHIT\AppData\Local\Python\bin\python.exe',[string]$MqttHost='127.0.0.1',[int]$MqttPort=1883)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$state=Join-Path $root 'state\apm_supervised'
$null=New-Item -ItemType Directory -Force -Path $state
$pidFile=Join-Path $state 'apm.pid.json'; $out=Join-Path $state 'apm.stdout.log'; $err=Join-Path $state 'apm.stderr.log'
if(Test-Path $pidFile){
  try{$meta=Get-Content -Raw $pidFile|ConvertFrom-Json; $p=Get-Process -Id ([int]$meta.pid) -ErrorAction Stop
    if($p.Path -eq $Python -and $meta.root -eq $root){throw "APM already running as PID $($meta.pid)"}
  }catch{if($_.Exception.Message -like 'APM already running*'){throw}; Remove-Item -LiteralPath $pidFile -Force}
}
$listener=Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
if($listener){throw "Port $Port is already owned by PID $($listener[0].OwningProcess); refusing duplicate launch."}
if(!(Test-Path $Python)){throw "Python executable not found: $Python"}
$env:API_PORT="$Port";$env:MQTT_HOST=$MqttHost;$env:MQTT_PORT="$MqttPort";$env:APM_DATA=(Join-Path $root 'state\apm');$env:PYTHONPATH="$root;.audit_deps;$root\apps\srp-apm"
$proc=Start-Process -FilePath $Python -ArgumentList @((Join-Path $root 'apps\srp-apm\backend\server.py')) -WorkingDirectory $root -RedirectStandardOutput $out -RedirectStandardError $err -PassThru
$meta=[ordered]@{pid=$proc.Id;root=$root;python=$Python;port=$Port;mqtt_host=$MqttHost;mqtt_port=$MqttPort;started=(Get-Date).ToString('o');stdout=$out;stderr=$err;command="$Python apps/srp-apm/backend/server.py"}
$meta|ConvertTo-Json|Set-Content -Encoding UTF8 $pidFile
$deadline=(Get-Date).AddSeconds(30)
while((Get-Date)-lt $deadline){
  if($proc.HasExited){Get-Content $err -ErrorAction SilentlyContinue;throw "APM exited with code $($proc.ExitCode). See $err"}
  try{$h=Invoke-RestMethod "http://127.0.0.1:$Port/health" -TimeoutSec 2;if($h.ready -and $h.database_ready -and $h.mqtt_connected -and $h.stroke_worker_ready){$h|ConvertTo-Json -Depth 4;Write-Output "APM PID $($proc.Id) ready. PID metadata: $pidFile";exit 0}}catch{}
  Start-Sleep -Milliseconds 300
}
throw "APM failed readiness on port $Port; inspect $out and $err"
