# Corrected-physics synthetic model experiment

**Run date:** 2026-11-17  
**Simulator physics:** `srp-forward-2.0-plunger-clearance`  
**Status:** completed synthetic-only experiment; not approved for field use or deployment.

## Data and split

The audited source is `data/generated/balanced_independent_strokes_v2/`: 1,100 JSON records, 507,002 raw telemetry samples, 1,100 complete GOOD surface cards, 1,100 solved downhole cards and 30 virtual well configurations. The records contain 100 simulator-injected examples per mechanism, with 10%-100% severity levels for fault classes. They are synthetic labels and do not represent independently confirmed site diagnoses.

Exact surface-card hashing found 30 duplicate groups: 20 groups of three records and 10 groups of four, or 70 redundant copies. Thus there are 1,030 unique surface fingerprints and only 30 unique healthy cards. The modeling scripts discard identical fingerprints and enforce that a fingerprint cannot cross partitions. Well configurations are split as whole groups: 18 train, 6 calibration/model-selection and 6 holdout test. The training script skips test record contents entirely; the evaluation script opened that holdout once after model selection.

## Training and selection

The four candidates used `fault_detection.remediation.live_inputs()` so the feature construction, units, sequence order and normalization match the APM's defined candidate feature path. Candidates were logistic regression with robust scaling, Extra Trees, Random Forest and histogram gradient boosting. Selection was fixed in advance: highest calibration macro F1, then lower calibration log loss.

| Candidate | Calibration macro F1 | Calibration log loss |
|---|---:|---:|
| Logistic regression | 0.665 | 1.673 |
| Extra Trees | **0.667** | **0.878** |
| Random Forest | 0.639 | 0.928 |
| Histogram gradient boosting | 0.626 | 1.736 |

The simulator's `pump_wear` and `traveling_valve_leak` injections share leakage observables and are mapped to one diagnostic label, `plunger_or_traveling_valve_leakage`. This prevents the candidate from claiming component identification the synthetic signatures do not support.

## One-time held-out result

Selected candidate: **Extra Trees**. Test set: 196 unique cards from six held-out virtual well configurations.

| Metric | Result |
|---|---:|
| Macro F1 | 0.644 |
| Accuracy | 0.679 |
| Log loss | 0.848 |
| Coverage at existing 0.70 confidence threshold | 0.444 |
| Accuracy among accepted predictions | 0.977 |
| Expected calibration error | 0.064 |
| Real labeled test wells | 0 |

Accepted accuracy is conditioned on predicting only 44% of this synthetic set; it does not mean overall correctness is 97.7%. Probabilities are not calibrated. No confidence threshold was reduced.

Per-class test F1: position sensor fault 1.00 (19 cards), load cell drift 0.97 (19), rod friction 0.94 (19), incomplete fillage 0.80 (19), gas interference 0.76 (19), restricted inflow 0.76 (19), combined plunger/traveling-valve leakage 0.56 (38), abnormal speed 0.37 (19), standing-valve leakage 0.27 (19), healthy 0.00 (6). Largest reciprocal confusion was leakage with standing-valve leakage: 10 leakage records predicted as standing-valve leakage and 8 standing-valve leakage records predicted as leakage. Healthy cards were never predicted as healthy on this test set.

## Artifacts and commands

- Candidate training and calibration selection: `scripts/train_current_physics_v2_candidate.py`
- Frozen whole-configuration split: `scripts/freeze_current_physics_split.py`
- Held-out test evaluation: `scripts/evaluate_current_physics_v2_candidate.py`
- Data audit: `reports/PHASE3_2/CURRENT_PHYSICS_STROKE_AUDIT.json`
- Split manifest: `data/evaluation/current_physics_v2_split.json`
- Candidate artifact: `data/training/current_physics_v2_experimental.joblib`
- Selection metrics: `data/evaluation/current_physics_v2_model_selection.json`
- Immutable test metrics: `data/evaluation/current_physics_v2_test_7bb4af30bc17b896.json`

Executed with the configured Windows Python:

```powershell
& 'C:\Users\HARSHIT\AppData\Local\Python\bin\python.exe' scripts/freeze_current_physics_split.py
& 'C:\Users\HARSHIT\AppData\Local\Python\bin\python.exe' scripts/train_current_physics_v2_candidate.py
& 'C:\Users\HARSHIT\AppData\Local\Python\bin\python.exe' scripts/evaluate_current_physics_v2_candidate.py
```

## Readiness decision

**Not field-ready.** The experiment demonstrates that the revised physics can produce cards and that the shared APM feature path can be trained and tested. It does not provide independent field evidence. The held-out macro F1 and coverage miss the current gates (0.90 macro F1 and 0.70 coverage), healthy detection failed, six test wells are virtual configurations, no real labeled wells exist, and sensor noise/bias are disabled. Keep this artifact isolated and `deployed=False`. Next, calibrate the physical fault signatures and sensor-noise distributions against independently labeled field strokes; collect multiple strokes per verified fault and healthy state across different wells; then repeat whole-well and site-held-out evaluation. No metric from this experiment should be presented as real-field accuracy.
