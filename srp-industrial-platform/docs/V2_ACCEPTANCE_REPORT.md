# V2 acceptance report

Native Windows pipeline **PASS**, pump browser playback **PASS**, engineering browser comparison **PASS**, and vendor browser comparison **PASS (geometry only)**. The existing simulator and APM ran as separate processes connected via Aedes MQTT. The native launcher continues to support the default local ports. Docker was unnecessary.

## Verified evidence

- The simulator was started in Playwright. APM received and processed the current stroke, reconstructed pump motion, scrubbed all three views together, froze the clock and advanced at 2×. Offline reconstruction versus isolated simulator truth: healthy 1.89 mm and 120.8 N; leak 1.66 mm and 104.5 N.
- Injected traveling-valve leakage through the simulator UI. APM detected the card change without the injected label and executed experimental model `cnn-v2/a63191e90177-13`. Recorded classification was `UNKNOWN`.
- Browser downloaded the engineering CSV, imported it, saved the dataset and downloaded the comparison report. Across 4 healthy/faulty surface/downhole round trips, maximum absolute SI position or force error was 9.09e-13. Raw and configuration CSV previews also validated.
- Imported the 132-point Echometer Overtravel example in the browser and generated a geometry-only comparison report. A separate parser check verified the Overtravel and 216-point Undertravel example blocks. Their full equipment and time alignment were unavailable.
- TypeScript/Vite builds, numerical physics, ingestion and mapping tests passed. The first V2 training pass exposed a NumPy scalar JSON serialization error. Metrics were regenerated after correcting serialization. The browser acceptance was repeated after adding vendor parsing and download headers.

## Remaining partial items

Valve actuation, flow direction, fillage and chamber-pressure observation are unresolved. New native DYN writing, TAM_EXP, complete TWM fixture coverage and installed vendor applications are unverified. A matched external numerical prediction run and longitudinal field ML evaluation are still required. See [model validation](FAULT_MODEL_VALIDATION.md) for the actual held-out results.

## Reproduce and inspect

- `python scripts/check_physics.py`, `python scripts/check_ingest.py`, and `python scripts/check_interchange_v2.py`
- `python scripts/run_v2_acceptance.py`. Optionally set SRP_VENDOR_EXAMPLE_ARCHIVE to the training ZIP and SRP_V2_ACCEPTANCE_MODEL to a candidate CNN .pt file.
- [Machine-readable acceptance](../data/evaluation/v2/acceptance.json), [playback](../data/evaluation/v2/animated_pump.png), [fault diagnosis](../data/evaluation/v2/fault_diagnosis.png), [external overlay](../data/evaluation/v2/external_dyn_benchmark.png), [external report](../data/evaluation/v2/external_dyn_comparison.json), [surface CSV](../data/evaluation/v2/healthy_surface.csv), [faulty downhole CSV](../data/evaluation/v2/leak_downhole.csv)
