# Real vs synthetic evaluation

The existing 800-run archive remains intact. The experiments retrained on 480 archive examples, calibrated on 160 and scored on 160 examples from the historical held-out group. Development reused that group for comparison with the previous benchmark. It is not a new final holdout.

A second evaluation used **96 fresh simulated runs across 12 unseen configurations** under the current simulator physics, eight classes and no rejected reconstructions. The previously fitted artifacts were frozen before those configurations were generated. This test measures robustness to new configurations and the combined change in the simulator. It does not isolate the effect of either change.

| Model | Historical macro F1 | Historical coverage | Fresh macro F1 | Fresh coverage | Fresh macro F1 after abstention |
|---|---:|---:|---:|---:|---:|
| Physics features + logistic regression | 0.667 | 42.5% | 0.498 | 63.5% | 0.315 |
| LightGBM | 0.594 | 44.4% | 0.487 | 55.2% | 0.248 |
| Extra Trees | 0.608 | 30.6% | 0.484 | 57.3% | 0.282 |
| Dual-card CNN | 0.505 | 36.9% | 0.407 | 53.1% | 0.226 |

Raw macro F1 uses argmax. Coverage requires the existing 0.70 confidence and operating-range gates. Post-abstention F1 penalizes unclassified samples as missed class cases. The strongest historical comparison result was 0.667 versus 0.570 for V2 LightGBM on the historical split. The strongest fresh result was 0.498. A higher coverage under changed physics does not imply better calibration or transfer.

**Field result unavailable.** Zero independently labeled, permission-cleared real cards and zero independent real test wells were obtained. The 348 verified numerical points from two Echometer example traces provide import and geometry evidence only. No field accuracy, real-vs-synthetic accuracy delta, pseudo-label training, or adaptation on restricted records was reported.

[Historical split metrics, calibration and confusion matrices](../data/evaluation/remediation_metrics.json) · [Fresh synthetic confusion matrices and run manifest](../data/evaluation/remediation_fresh.json) · [Acquisition audit](REAL_DATASET_ACQUISITION.md).
