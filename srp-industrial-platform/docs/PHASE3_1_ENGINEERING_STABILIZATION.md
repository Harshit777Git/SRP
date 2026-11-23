# Phase 3.1 engineering stabilization

## Decision

**NO-GO for synthetic ML experimentation.** No ML model was trained, retrained, fine-tuned, selected or deployed in this phase. Field-trained or field-validated fault detection remains unsupported by independently labeled field cards.

## MQTT root-cause measurements

The original outbox blocked on QoS 1 acknowledgement batches. The revised publisher keeps the SQLite outbox durable, publishes a bounded set of messages in flight and deletes rows only after acknowledgement. A callback/lock deadlock found during development was fixed with a thread-safe acknowledgement queue. A later lock-scope experiment regressed throughput and was reverted. The final code is the bounded asynchronous publisher in `apps/srp-simulator/mqtt_publisher/outbox.py`.

- Broker alone: 15,000/15,000 messages received at 1,865/s.
- Outbox alone: 3,000 messages committed and drained, final queue zero.
- APM alone: 42,090/42,090 replayed samples persisted across 30 wells, with 60 cards, at 1,646/s. Per-sample run metadata and late-stroke lookups were reduced without changing duplicate keys or recovery behavior.
- Combined live at 20 wells: 1,238 broker acknowledgements/s and 996 APM-persisted dynamometer samples/s; queue 33 to 18 in 8.1 s.
- Combined live at 30 wells: 1,140 broker acknowledgements/s and 719 APM-persisted dynamometer samples/s; queue 740 to 21,816 in 30.1 s. No reported outbox drops or APM rejections. RAM across broker, APM and six site processes grew from about 519 to 678 MB during that stage. This is a failed stability test, not evidence of durable 30-well delivery.

The combined 30-well slowdown is unresolved. Separate component capacity does not prove that the complete stack has enough concurrent CPU and I/O capacity. The six-process site arrangement did not meet the gate on this host. The requested 30-minute stable run was not started because the 30-second queue trend was unbounded; running it would accumulate a large backlog without demonstrating stability.

At five wells, broker interruption increased the durable queue to 928 messages. After restart and pausing production, it drained to zero. APM persisted 7,737 samples and 15 cards across the five wells with zero observed sequence gaps and no reported drops. This is a five-well recovery result only.

Evidence: `reports/PHASE3_1/broker_only.json`, `outbox_only.json`, `apm_only.json`, `staged_30wells.json`, `recovery_5wells.json`, and the MQTT stability workbook.

## Continuous synthetic physics

All 30 fictional configurations completed three consecutive offline strokes each. The dataset contains 90 Surface cards, 90 reconstructed Downhole cards and 42,150 sensor-equivalent dynamometer readings. The 90 strokes passed the recorded synthetic self-consistency gates. Median load RMSE against isolated simulator truth was 167.9 N; maximum was 233.4 N. Maximum centered downhole-position RMSE was 6.08 mm and maximum card-area error was 0.56%. No full drive energy balance is claimed because the model omits parts of the drive and counterbalance.

At the unchanged 50 Hz sensor cadence, a 30-well one-stroke comparison of 0.0067 s and 0.002 s solver steps found maximum load RMSE of 0.319% of load range and maximum pump-position RMSE of 0.021% of stroke. The 0.0067 s fleet setting is a provisional throughput setting. Long-run convergence, physical plausibility against independent field or QRod outputs and 30-minute stability remain open.

## Fault sensitivity

The matched synthetic study covers 30 wells, 10 supported mechanisms and severities 0.2 and 0.8: 600 cases with no failed solver runs after partial warm-up strokes were excluded. It compares raw readings, Surface and reconstructed Downhole cards, motor current, chamber/intake pressure and delivered volume. It does not prove class discrimination. At severity 0.2, 29 of 30 standing-valve leakage cases and 29 of 30 restricted-inflow cases changed Surface load by less than 500 N RMS against their own healthy baseline. Traveling-valve leakage and pump wear remain potentially confusable because the present model uses related leakage conductances. Sensor faults act in the measurement channel. Additional operating conditions, true field labels, and independent physics benchmarks remain necessary.

## APM and exports

APM registers the six-site fleet at startup. Its fleet endpoint and UI show site membership, latest telemetry, stroke and sequence counts; its existing selected-well views show received Surface/Downhole cards and exports. A native gateway exposes all six simulator site processes through one simulator API. A smoke test found 30 gateway wells, 33 APM assets including the legacy presets, both UI endpoints available, and five Midland wells producing 3,118 APM-accepted samples and one card each. Full browser interaction across all 30 wells was not completed.

The `data/generated/phase31/` export has CSV and Parquet dynamometer/electrical/pressure/feature rows, JSON card and validation records, configuration, file hashes and a configuration-isolated future split. True downhole state and scenario labels reside under `simulation_truth/`, outside `ml_inputs/`. Round-trip, identity, checksum and leakage tests passed. Only healthy multi-stroke runs were exported in this dataset; the 600 fault cases are sensitivity results, not complete raw training-candidate runs.

## QRod and provider boundary

Ten QRod `.qrd` designs remain inventoried, with zero supported numerical prediction exports and zero equivalent-input comparisons. QRod opened to its design screen, but a File-menu attempt was interrupted by concurrent user input; no design was changed or exported. The prior TWM operating-conditions dialog was not accepted. An authorized operator must review any provider terms personally and use normal QRod/TWM export controls to obtain complete numerical inputs and curves before an independent benchmark can be attempted. Screenshots alone cannot establish numerical agreement.

## Reproduce

From the repository root on Windows, with the audit dependencies installed:

```powershell
$env:PYTHONPATH = "$PWD\.audit_deps"
& 'C:\Users\HARSHIT\AppData\Local\Python\bin\python.exe' scripts/run_fleet_local.py
```

The native launcher prints simulator and APM UI addresses. The 30-well live performance gate remains failed; operate the fleet with queue monitoring. Regenerate offline evidence with `scripts/generate_phase31_dataset.py`, `scripts/evaluate_phase31_faults.py`, and `scripts/phase31_timestep_convergence.py`. The generated files are versioned under `reports/PHASE3_1/` and `data/generated/phase31/`.
