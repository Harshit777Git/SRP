# Field model readiness execution

Current rating: **1/5**. The read-only audit `python scripts/audit_field_training_readiness.py` found **0 eligible measured labeled strokes** and **0 field wells** in `data/training/real_labeled/`. Its machine-readable result is `reports/PHASE3_2/FIELD_TRAINING_READINESS.json`.

## Work completed with available data

- Audited existing synthetic model selection: 800 simulated runs in 8 classes; best previously reported synthetic macro F1 0.667. The newer experimental candidate reached 0.631 and was not deployed.
- Repaired synthetic stroke boundaries: 57/57 complete cards now reconstruct downhole. Synthetic reconstruction median errors: load 1.22% of true range, centered displacement 2.80 mm, card area 0.37%; 95th-percentile area error 21.24% still requires engineering investigation.
- Kept the OneDrive/Echometer demonstrations as references: their filenames and calculated cards do not establish independent field fault labels or training rights.
- Added a field-manifest validator with duplicate, origin, permission, independent-label, sample-completeness and coverage checks. It does not import or relabel records.
- Revised pump wear from a shared traveling-valve conductance to a separate annular plunger/barrel clearance-leak equation, with explicit configuration fields and simulator physics-version provenance. The 7-case physics suite and 5-case ingestion regression suite pass. A severity sweep shows the current illustrative model produces only 0.015%–0.535% of healthy load-range phase-aligned RMSE from 10%–100% wear, so the synthetic signature remains weak and needs clearance/production calibration.
- Generated synthetic capture v4 under `srp-forward-2.0-plunger-clearance`: 34,851 telemetry rows (at least 3,129 per mechanism), 30 virtual wells, 66 runs/cards, 66 downhole reconstructions, and six fault severity settings. This is a versioned synthetic experiment only; it has not been used to fit a field model and its injected labels are not field diagnoses.

## Required site handoff

Place permission-cleared measured stroke files and a `field_strokes.csv` manifest in `data/training/real_labeled/`. The manifest needs the columns listed in `scripts/audit_field_training_readiness.py`: physical well/run/stroke IDs, original file hash, measured origin, load/position units, point count, diagnosis and evidence, evidence date/reviewer, training permission, and equipment configuration ID. Supply the equipment records (unit geometry, rod taper/grade, pump diameter/depth, speed, fluid properties, tubing/casing pressures), fluid level or intake pressure where available, production records, and documented maintenance/valve-test/workover findings. Preserve originals and timestamps. An engineer must confirm ambiguous labels.

## Gates before 5/5

1. Validate source files, units, ordered stroke samples, duplicate events and permissions.
2. Reconstruct cards with the exact field configuration; compare load, travel, area and phase to matched provider calculations and production where measured.
3. Calibrate healthy physics per well and document residuals; validate fault response against confirmed events.
4. Split by physical well and event before any tuning. Keep an untouched prospective set from at least 10 real wells.
5. Re-evaluate per-class precision/recall, calibration, abstention coverage, false alarms per well-day, detection delay and drift. The current project gates specify macro F1 ≥0.90, every class precision/recall ≥0.85, coverage ≥0.70, and ≥10 real test wells. Promote only after all gates pass.

No model was promoted. The readiness audit still reports 0 eligible measured labeled strokes and 0 field wells. Field acquisition, engineer labels, independent card comparison, site calibration and prospective trial remain blocked by absent site records and access to confirmed diagnoses. The rating remains 1/5; code changes and synthetic scores do not increase field readiness.
