# SRP forward-physics revision verification — 17 November 2026

## Change

The former `pump_wear` implementation increased the same valve conductance used by traveling-valve leakage. The simulator now reports physics version `srp-forward-2.0-plunger-clearance`; traveling-valve leakage remains a valve path, while pump wear increases plunger/barrel radial clearance and drives a separate pressure-driven annular slippage term:

`q = π D δ³ (p_discharge - p_chamber) / (12 μ L)`

The governing approximation is based on the leakage equation in [Lv et al. (2022)](https://www.cup.edu.cn/petroleumscience/docs/2022-05/c25c5cca6dc64b24bc48.pdf). Published work also discusses Couette flow, eccentricity and transient behavior; those effects remain outside this reduced model. The defaults of 38.1 μm radial clearance and 76.2 μm full-severity growth are illustrative, not measured pump-fit values. [Li et al.](https://www.mdpi.com/2673-3161/7/1/25)

The simulator exposes plunger length, radial clearance and clearance growth in the well configuration, emits leakage/slippage diagnostics, and tags simulator telemetry with the physics version. These changes preserve the distinction between modeled pump wear and measured field diagnoses.

## Verification

- Command: `python scripts/check_physics.py` using the repository's configured interpreter.
- Result: **7/7 passed** in 30.826 seconds. This includes deterministic behavior, numerical stability/refinement, card construction and reconstruction, ingestion-level sample validation, path separation between pump wear and valve leakage, and cubic clearance-to-conductance scaling.
- Command: `python scripts/check_ingest.py`.
- Result: **5/5 passed** in 0.389 seconds, including duplicate/late recovery, monitoring, calibration metadata, reset sequencing and run/asset isolation.
- Command: `python scripts/evaluate_pump_clearance_separability.py`.
- Result: synthetic-only severity sweep and card comparison written to `PUMP_WEAR_PHYSICS_PILOT.json`.

## Pilot evidence and limits

On the default SRP_001 configuration, phase-aligned surface-load RMSE versus healthy rose from 1.55 N (0.015% of healthy load range) at 10% modeled wear to 54.53 N (0.535%) at 100%. At 80% it was 34.94 N (0.343%). For context within this same synthetic run, an 80% traveling-valve leak produced 528.10 N (5.18%) RMSE. This indicates distinct simulator responses but a weak modeled card signature for pump wear at the chosen assumed fit range. It does not establish detection probability or physical accuracy.

## Versioned capture

`data/generated/fault_training_candidate_3129_each_v4/` contains 34,851 telemetry rows (at least 3,129 per simulated mechanism), 30 virtual wells, 66 simulation runs, 66 complete surface/downhole card pairs and six nonzero severity settings. The manifest and each raw sample record the physics version; SHA-256 values are recorded in the manifest and dataset registry. This version has not been used to train or evaluate a model. Its six cards per mechanism are inadequate to support independent field claims. Prior v1-v3 captures and model metrics predate the new physics and should not be treated as equivalent to it for pump-wear model development.

The field readiness audit still reports zero eligible measured, independently labeled strokes and zero field test wells. No real-field simulation calibration or field ML validation has been completed.
