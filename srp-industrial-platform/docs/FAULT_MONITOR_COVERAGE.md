# Fault monitor coverage

The Fault Laboratory accepts 0.1%–100% and converts percent to the simulator's internal fraction. New UI-scheduled faults wait for the initial reference strokes when necessary. The APM uses measurements and decoded stroke geometry. It receives no injection labels. The selected stroke displays measured changes and alert thresholds.

## Verification

`python scripts/check_fault_coverage.py` covers 180 steady synthetic cases. Each severity has 30 cases across three preset wells and ten selectable fault types. Nine further healthy control strokes stayed within their references.

| Injected severity | Cases with a telemetry alert |
|---:|---:|
| 0.1% | 2 of 30 |
| 1% | 16 of 30 |
| 10% | 24 of 30 |
| 50% | 30 of 30 |
| 80% | 30 of 30 |
| 100% | 30 of 30 |

The severity points are discrete. Intermediate severities, noisy field wells and fault-class accuracy remain unvalidated. The full 0.1%–100% detection requirement is unmet. At 0.1%, the verified alerts were abnormal-speed cases in two presets.

`python scripts/check_live_fault_coverage.py` verified alerts for all ten selectable faults at 80% on SRP_001 through native MQTT and the APM API, with recovery between scenarios. In the first pass, the APM missed standing-valve leakage because only the surface load waveform crossed its threshold. The revised monitor recognizes this measured surface evidence when the noisier downhole estimate stays within its threshold. The rerun passed.

Playwright verified that entering 0.1% schedules severity 0.001 internally and delays early injection until the initial reference window. The live speed test detected a change from 8.0000 to 8.0028 SPM.

Rules report measured observations such as delayed unloading, a load offset, a travel change, or a stroke-rate change. These observations can have multiple causes. Previous classifier results apply to earlier simulator formulations. See [severity sweep](../data/evaluation/v2/fault_severity_coverage.json) and [live MQTT coverage](../data/evaluation/v2/live_fault_coverage.json).
