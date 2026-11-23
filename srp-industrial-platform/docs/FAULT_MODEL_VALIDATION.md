# Fault model validation

**SYNTHETIC VALIDATION ONLY**

The 800-run results below apply to the previous underfill and restricted-inflow simulator formulation. The updated model adds compressible void for the missing liquid charge. The operating Dynacard monitor has been tested on the new mechanism. These classifier artifacts require retraining before they can be evaluated against it.

Accepted dataset size was **800 independent runs**, one stroke per run, with 0 rejected reconstructions. Class counts were gas_interference 100, healthy 100, incomplete_fillage 100, pump_wear 100, restricted_inflow 100, rod_friction 100, standing_valve_leak 100, traveling_valve_leak 100. Wells were grouped by equipment configuration. Training used 60 configurations, calibration used 20 and evaluation used 20 unseen configurations.

| Model | Mean raw macro F1 ± seed standard deviation | Raw accuracy (seed 13) | ECE (seed 13) | UNKNOWN after guards (seed 13) | Accepted healthy-run false-positive fraction |
|---|---:|---:|---:|---:|---:|
| LightGBM | 0.570 ± 0.000 | 0.581 | 0.072 | 71.2% | 0.0% |
| Dual-branch CNN | 0.430 ± 0.016 | 0.444 | 0.102 | 74.4% | 0.0% |
| Probability average | 0.557 ± 0.008 | 0.569 | 0.042 | 75.0% | 0.0% |

| Model, seed 13 | Classes at ≥0.85 precision | Classes at ≥0.85 recall |
|---|---:|---:|
| tabular | 1 / 8 | 2 / 8 |
| cnn | 2 / 8 | 2 / 8 |
| ensemble | 2 / 8 | 2 / 8 |

Metrics before abstention use the highest class score. UNKNOWN uses the 0.70 confidence gate and training SPM domain. The rules provide evidence rather than a classified root cause. False alarms per well-day and detection latency require longitudinal data. The native acceptance classifier was explicitly selected for this isolated check. The live default stays on the engineering baseline and Dynacard reference monitor. The experiments provide no field validation.

Run `python scripts/train_v2.py --runs-per-class 100 --workers 8 --tag v2_full` with CPU PyTorch and LightGBM installed. The JSON includes per-class precision, recall, F1, confusion matrices, calibration and latency for every seed. The training directory retains equipment, severity and seed for each run plus versioned experimental artifacts. [Machine-readable model results](../data/evaluation/v2_full_ml.json).
