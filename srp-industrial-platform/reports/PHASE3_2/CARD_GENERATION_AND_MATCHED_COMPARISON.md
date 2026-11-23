# Card generation repair and matched comparison — 17 November 2026

## Repair

`scripts/generate_fault_training_capture.py` had reset `previous=[]` after a stroke boundary. The boundary sample belongs to the next stroke and has `sample_index=0`; discarding it made every subsequent stroke fail the card quality gate. The generator now carries that boundary sample forward as `previous=[sample]` and ignores the initial partial stroke. Simulator truth now retains per-sample timestamps for phase alignment.

Regeneration command: `python scripts/generate_fault_training_capture.py`. The manifest reports 3,129 telemetry samples per mechanism (10 faults plus healthy), 34,419 total, 57 complete GOOD surface cards and 57 SOLVED downhole reconstructions. Previously the same set had 57 DEGRADED surface cards and zero solved downhole cards. SHA-256 hashes are in `data/generated/fault_training_candidate_3129_each/manifest.json`.

## Matched synthetic forward/reconstruction comparison

Command: `python scripts/compare_phase32_cards.py`. All 57 complete reconstructed cards were matched by run, stroke and sequence to the simulator's saved true pump states. Details: `MATCHED_SYNTHETIC_CARD_COMPARISON.json`; summary: `MATCHED_SYNTHETIC_CARD_COMPARISON_SUMMARY.json`.

| Metric | Median | 95th percentile | Maximum |
|---|---:|---:|---:|
| Pump-load RMSE / true load range | 1.22% | 7.10% | 14.28% |
| Centered plunger-displacement RMSE | 2.80 mm | 48.59 mm | 157.39 mm |
| Absolute card-area error | 0.37% | 21.24% | 41.98% |

Median absolute displacement phase error was 0.042 degrees. The upper-tail displacement and area errors are material and require investigation before calling the inverse solver accurate across faults. The absolute displacement offset is retained per case in the JSON because inverse-card origins can differ.

## Independent reference limits

The available Echometer demonstration cards and OneDrive TWM/QRod files do not establish a matched configuration, numerical timebase, sensor units, complete equipment metadata and independent production measurement for these 57 virtual runs. Consequently there are **zero matched measured/vendor cases** in this comparison. The reported error metrics are synthetic self-consistency only. Measured production error is unavailable. The simulator's net delivered volume is saved as simulation truth, but no independent production observation or APM production estimate is available to form an error.

No ML model was trained or deployed. No field accuracy claim follows from these results.
