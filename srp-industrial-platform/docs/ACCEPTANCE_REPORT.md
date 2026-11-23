# Acceptance report

The native synthetic run completed with pipeline status **PASS** and browser status **PASS**. It used Python processes, an Aedes broker over loopback and SQLite/WAL. Browser verification used Playwright with Microsoft Edge. Docker Compose configuration validation passed. Docker Desktop reported it was unable to start, so the Mosquitto and PostgreSQL container runtime was unavailable.

## End-to-end evidence

1. Created the synthetic well `CHECK_E6FAFC6` in both applications. The simulator published its virtual polished-rod measurements. APM built 3 completed healthy surface and inverse downhole cards before the fault.
2. Injected traveling-valve leakage. Surface-card area changed by 76.41 J (0.76%) against a healthy baseline spread of 0.034 J in this run.
3. Joined the completed card to independent simulator truth offline. Healthy and fault position RMSE were 1.89 and 1.69 mm. Load RMSE were 120.8 and 104.5 N.
4. The diagnostic model returned `UNKNOWN` with a peak predicted probability of 50.1%. Recorded ML acceptance was **INCOMPLETE** because synthetic generalization is insufficient.
5. The publisher acknowledged 2,821 messages across all streams and the APM stored 2,304 distinct dynamometer samples at the first checkpoint. The deliberate MQTT replay passed deduplication. Broker restart found 256 queued messages, recovered solved stroke 14, and produced 0 newly observed sequence gaps. The publisher reported 0 queue-overflow drops.
6. Playwright exercised simulator well selection, pause and resume, sensor and fault views, APM dual cards, CSV download, live overlay and model registry. Both frontends built using the checked-in dependency lockfile. Five physics/card tests and two ingestion tests passed.

## Multiwell benchmark

Simulated shallow wells, nominal 50 Hz per well, native processes. CPU is the summed percent of a logical processor across measured processes. RSS is combined. Processing includes APM storage and stroke construction. Publisher acknowledgement lag includes queueing.

| Wells | Received samples/s | Target samples/s | CPU | Peak RSS | Mean APM processing | Peak sampled ack lag | Sequence gaps | Outbox drops |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 50.1 | 50 | 18.4% | 178.4 MiB | 0.276 ms | 0.022 s | 0 | 0 |
| 5 | 250.0 | 250 | 35.3% | 178.4 MiB | 0.179 ms | 0.013 s | 0 | 0 |
| 10 | 501.0 | 500 | 80.8% | 185.1 MiB | 0.196 ms | 0.019 s | 0 | 0 |

These short measurements describe the native stack and synthetic shallow configuration.

## Evidence files

- [Acceptance results](../data/evaluation/acceptance.json), [MQTT samples](../data/evaluation/mqtt_capture.jsonl), [paired cards](../data/evaluation/acceptance_cards.json), [isolated truth](../data/evaluation/acceptance_truth.jsonl)
- [Benchmark results](../data/evaluation/performance.json), [physics results](../data/evaluation/unit-tests.txt), [ingestion results](../data/evaluation/ingest-tests.txt), [frontend build](../data/evaluation/frontend-build.txt) and [Compose config check](../data/evaluation/compose-config.txt)
- [Simulator browser capture](../data/evaluation/simulator.png) and [APM browser capture](../data/evaluation/apm.png)
