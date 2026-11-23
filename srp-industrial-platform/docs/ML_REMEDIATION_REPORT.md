# ML remediation report

## Completed

1. Reviewed publications, GitHub and data portals, publisher supplement routes, the installed vendor examples and archived Echometer demos. Downloaded the Session 9 demonstration bundle, verified both ASCII traces in the existing Session 20 bundle and preserved the vendor audit. No permission or diagnosis was inferred from public visibility or file names.
2. Preserved the 800 original synthetic runs and created [separate partition records](../data/training/partitions.json). The real labeled and real unlabeled training partitions remain empty pending qualifying acquisitions.
3. Trained physics-feature logistic regression, LightGBM and Extra Trees with a held-out calibrator, then retrained the dual-branch CNN with temperature calibration. The archive benchmark improved from 0.570 to 0.667 raw macro F1 for the strongest candidate. Its result on 96 fresh simulated runs under current physics was 0.498.
4. Unified candidate features and calibration for evaluation and live inference. The live candidate requires a complete, solved record with engineering geometry and exactly aligned 200-point timestamps. Card phase is rotated jointly. Class scores are bounded by the existing 0.70 threshold and an operating-range gate.
5. Added explicit production artifact gating and a safe fallback. Unapproved synthetic candidates are available for explicitly opted-in simulator experiments. None is active on the live APM. Production approval requires independently split field evidence, at least ten independent field test wells, 0.90 macro F1, 0.85 minimum class precision and recall, and 70% coverage. The monitored label stays `FAULT_TYPE_UNDETERMINED` where evidence is insufficient.

## Verified live output

An 80% incomplete-fillage injection on SRP_001 raised a live MQTT/APM alert. Playwright verified the ordered investigations **incomplete liquid fillage or restricted supply**, then **gas interference**. The APM reported reconstructed work of **1,366 J** and late-downstroke load **5,074 N above reference**. The diagnosis remained `FAULT_TYPE_UNDETERMINED` with null confidence. The ranking is engineering triage. Healthy operation was restored.

[Browser evidence](../data/evaluation/remediation_live.png) · [Live diagnosis JSON](../data/evaluation/remediation_live.json).

## Reproduce

- Run `python scripts/audit_real_datasets.py` for archive inventory and checksums.
- Run `python scripts/train_remediation.py` with the workspace's LightGBM and CPU PyTorch dependencies for the archival benchmark.
- Run `python scripts/evaluate_remediation_fresh.py` after training for the frozen fresh-synthetic evaluation and controlled leakage/wear test.
- Run `python scripts/check_remediation.py` to check feature parity, invalid timing rejection, calibrated artifact inference, safe abstention, production rejection and synthetic/field boundaries. TypeScript checking and the live Edge test passed.
- See [root cause analysis](ML_FAILURE_ROOT_CAUSE.md), [separability analysis](FAULT_SEPARABILITY_ANALYSIS.md), and [real vs synthetic evaluation](REAL_VS_SYNTHETIC_EVALUATION.md).

## Remaining gap

Supervised field training and independent field evaluation require authorized records with timebase, units, well identities and corroborated fault events. The strongest remediation candidate failed the synthetic PoC target and has no field gate evidence. This work improves replay-safe inputs and operational triage while leaving causal field diagnosis unvalidated.
