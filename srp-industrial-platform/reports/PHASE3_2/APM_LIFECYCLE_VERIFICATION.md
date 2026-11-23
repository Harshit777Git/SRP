# APM lifecycle verification

## Status

Lifecycle acceptance is **incomplete**. The earlier process-exit cause remains unproven: no durable stdout/stderr logs or exit codes were captured for the two prior launches. During inspection, process command lines showed two independent invocations of `apps/srp-apm/backend/server.py` under separate PowerShell parents. Port 18140 health was `ready=true`, `connected=true` at one observation; both processes later disappeared without recorded exit evidence.

## Changes

- `apps/srp-apm/backend/server.py`: health now separates HTTP liveness, database readiness, MQTT connectivity and stroke-worker readiness, and reports persisted pending-job count and in-memory queue depth. `ready` requires database, MQTT and worker readiness. Worker shutdown is registered with `atexit`.
- `scripts/start_apm.ps1`: starts one independent Python process, refuses an occupied port or matching live PID metadata, redirects stdout/stderr to persistent files, writes PID/start/config metadata, and waits for all readiness checks.
- `scripts/stop_apm.ps1`: verifies repository, port, PID and executable identity before requesting graceful window close; refuses unidentified or reused PIDs.

## Commands and evidence

Earlier baseline commands: `python scripts/check_physics.py` (6 passed), `python scripts/check_ingest.py` (4 passed), `python scripts/check_interchange_v2.py` (3 passed). These were run before the launcher and latest health changes. No post-change tests or 10-cycle run have been completed.

Expected launcher commands:

```powershell
.\scripts\start_apm.ps1 -Port 18140 -MqttPort 1883
.\scripts\stop_apm.ps1 -Port 18140
```

No startup cycle, clean shutdown, no-orphan, MQTT-negative, worker-negative or database-negative test is claimed here. One-well and throughput acceptance remain unrun. No ML training occurred.
