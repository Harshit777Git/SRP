# ML evaluation

Three models are implemented. The rules calculate engineering evidence and can abstain. A scikit-learn random forest uses features from both cards, including area, load bounds, direction asymmetry and load-slope variation. A PyTorch 1D CNN has separate surface and downhole branches plus a feature-fusion layer. Both learned models use phase-preserving channels with fixed engineering scales, avoiding normalization across individual cards that would erase amplitude.

The experiment generated 36 one-stroke simulation runs across healthy, gas interference and traveling-valve leakage. All strokes from one geometry went to the same partition. SRP_001 trained both models, SRP_002 supplied probability calibration, and SRP_003 was held out for testing. The groups use different depths, rod tapers and SPM ranges. Independent runs varied noise, speed and fault severity. The fault label is used by offline evaluation only.

| Held-out SRP_003, 12 simulated strokes | Accuracy before abstention | Macro F1 | Expected calibration error |
|---|---:|---:|---:|
| Random forest with sigmoid calibration | 66.7% | 0.556 | 0.127 |
| Dual-card CNN with temperature scaling | 33.3% | 0.167 | 0.661 |

The RF confused all four healthy holdout strokes with leakage and abstained on every held-out stroke at the deployment threshold. The CNN predicted gas interference for all 12 holdout inputs before the deployment SPM check. Both experimental artifacts are marked TRAINED_ON_SYNTHETIC. Available tests provide INSUFFICIENT_EVIDENCE for deployment as a validated fault classifier. Actual inference includes a confidence threshold and rejects SPM outside the training-domain bounds. A dedicated unseen-fault acceptance benchmark is pending.

Simulator support and diagnostic evidence are tracked independently. TRAINED_ON_SYNTHETIC applies to the three listed classes. VALIDATED_ON_HELD_OUT_SIMULATION requires evidence sufficient for the intended deployment. VALIDATED_ON_REAL_FIELD_DATA requires measured independent field cases. NOT_DETECTABLE is reserved for conditions shown to be unobservable with the available measurements. INSUFFICIENT_EVIDENCE applies where those tests are absent or inconclusive.

Confusion matrices, per-class metrics, calibration bins and batch inference timings are in the [executed evaluation](../data/evaluation/ml.json). False alarms per operating day and onset-to-alert latency remain unmeasured because the dataset consists of isolated steady strokes. Neither model has a measured field score.
