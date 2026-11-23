# SRP Industrial Platform

Two separately runnable applications compute and analyze sucker-rod pumping telemetry. The simulator publishes raw measurements over MQTT. The APM consumes them, reconstructs completed Dynacards and displays advisory diagnostics.

## Run with Docker Compose

```sh
docker compose up --build -d
python -m pip install -r requirements.txt
python -m playwright install chromium
python scripts/run_acceptance.py
```

| Service | Local URL |
|---|---|
| Simulator UI | http://localhost:3001 |
| APM UI | http://localhost:3002 |
| Simulator API | http://localhost:8001 |
| APM API | http://localhost:8002 |
| MQTT | localhost:1883 |

Open the simulator and start a preset. Open the matching asset in APM. A complete periodic stroke is needed before the inverse card appears. Use the simulator Fleet page to create a synthetic well and register its equipment JSON independently in the APM Fleet page.

## V2 APM tools

Open **Animated Pump Analysis**, **Import / Export Center**, or **Engineering Benchmark Laboratory** in APM after starting a well. Synchronization is available for newly captured strokes. The [V2 acceptance report](docs/V2_ACCEPTANCE_REPORT.md) links to browser screenshots, numerical exports, and measured test results.

## Native verification

Run these commands in the platform directory with Python 3.12 and Node 24. Native mode launches isolated process instances and an Aedes test broker for the duration of the test.

```sh
python -m pip install -r requirements.txt
npm ci
python -m playwright install chromium
python scripts/run_acceptance.py --local
```

Start the interactive native stack with `python scripts/run_local.py`. It serves the simulator at http://127.0.0.1:13001 and the APM at http://127.0.0.1:13002 until stopped. Use `--sim`, `--apm`, `--sim-ui` and `--apm-ui` to set alternate acceptance URLs. Set `PLAYWRIGHT_BROWSER_PATH` to use an installed Chromium-compatible browser. Evidence is saved under [data/evaluation](data/evaluation).

## Reproduce the numerical and ML experiments

```sh
python scripts/check_physics.py
python scripts/check_ingest.py
python scripts/evaluate_wave.py
python scripts/train_models.py
python -m pip install --index-url https://download.pytorch.org/whl/cpu torch
python scripts/train_models.py --reuse --cnn
python scripts/write_manifest.py
python scripts/benchmark.py
```

The baseline returns engineering evidence and an UNKNOWN diagnosis when validation is insufficient. An explicitly supplied local model can produce experimental synthetic-only predictions. See the [evaluation](docs/ML_EVALUATION.md) and [acceptance report](docs/ACCEPTANCE_REPORT.md) for the actual results.
