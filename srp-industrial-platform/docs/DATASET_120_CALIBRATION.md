# 120-well dataset calibration

The supplied `DIGITAL_TWIN_DATASET` is synthetic. It contains 120 wells and 60,000 telemetry rows. It does not establish onsite accuracy.

## Calibration performed

Configuration values were converted to SI, including tapered rod sections, elastic modulus, fluid mixture density, viscosity, pressures, plunger diameter and fluid submergence. Pump clearance is interpreted as a diametral fit and divided by two to obtain radial clearance. Four-bar dimensions and plunger length are absent; the existing defaults remain assumptions.

Four strokes per well were used to fit surface stroke amplitude, position bias and phase alignment. The fifth stroke was held out. Phase alignment is an evaluation parameter; the simulator remains free to start at its own crank phase.

Surface load was then evaluated against three bounded damping candidates (0.6, 1.0 and 1.4 times the imported value, within schema limits), using supported source fault mechanisms and their supplied severity. The candidate with the lowest four-stroke load RMSE was selected. No arbitrary load multiplier or offset was fitted. Acceptance requires a supported condition and fifth-stroke RMSE at most 15% of the fifth-stroke load range. This threshold is an engineering acceptance choice, not a field accuracy certification.

All 120 wells were processed. 103 passed this acceptance criterion. Seventeen lack a matching physical fault mechanism: 4 unanchored tubing slip, 5 fluid pound, 4 severe gas lock and 4 hard tagging. Their baseline equipment is configured and generates data, but their source fault is not reproduced or certified. Each fleet entry carries its acceptance result and source condition.

## Data inconsistencies

50 source rows have active power greater than three-phase apparent power. All source liquid rates exceed a surface swept-volume reference by more than 5%; for prairie-001 the source states 107.92 m³/day versus 28.73 m³/day from plunger area, surface stroke and SPM. The latter is a geometric screening reference, not a substitute for actual downhole stroke or a production test. These output columns are not fitted into the physics model.

## Evidence

- `reports/DATASET_120_CALIBRATION.json`: per-well kinematic train/holdout residuals and finite forward calculations.
- `reports/DATASET_120_LOAD_FIT.json`: per-well load residuals, supported-condition flag and acceptance.
- `reports/DATASET_120_PHYSICAL_SOURCE_AUDIT.json`: source electrical and production screening counts.
- `reports/DATASET_120_CONVERGENCE.json`: representative imported-configuration timestep comparison at 2 ms and 1 ms. This covers one well per field and is not a full convergence proof for every condition.
- `reports/DATASET_120_MQTT_VERIFICATION.json`: loopback broker tests of all 120 kinematically calibrated wells across all 11 supported conditions, 100 samples per combination. This exercise precedes the final damping selection.
- `reports/DATASET_120_LIVE_VERIFICATION.json`: separate final-artifact live fleet check, written after runtime verification completes.

The fifth stroke comes from the same synthetic source as the fitting strokes. Independent well tests, calibrated sensors, actual linkage dimensions, tubing stiffness/contact geometry, pump dimensions and labeled fault evidence are still required for onsite validation.

The live load check initially exposed growing publisher queues. Publisher appends now group concurrent well writes into durable SQLite transactions and return only after COMMIT. APM ingestion also batches database work and sends MQTT acknowledgements only after COMMIT. Focused checks cover durable return, per-well ordering, bounded capacity, duplicate counting and rollback/recovery. Live acceptance additionally requires acknowledgement lag below 5 seconds and APM sequence lag no more than 250 samples per well. These are operational thresholds, not physics-accuracy thresholds.

## Run

`scripts/run_fleet_local.py` chooses `config/fleet/dataset_120_calibrated.json` when present and starts all wells automatically. The fleet runs in four field processes with a gateway and APM receiver. `SIM_AUTO_START=0` disables automatic startup when starting the simulator backend directly. Local launcher APIs and MQTT bind to loopback. Runtime databases and buffered truth logs default to the local temporary directory `srp_dataset_120_grouped`; `state/dataset_runtime.json` records the actual location. `--state-dir` overrides it. This avoids syncing high-frequency runtime writes through OneDrive. Canonical configuration and evidence reports remain in the repository.

To reproduce calibration: run `import_twin_dataset.py`, `calibrate_dataset_fleet.py`, `fit_dataset_loads.py` and `finalize_dataset_calibration.py` in that order. The MQTT verification scripts launch local sockets and require permission to use them in a restricted environment.
