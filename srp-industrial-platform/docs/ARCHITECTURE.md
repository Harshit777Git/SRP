# Architecture

```text
Simulator API / SSE ── Simulator UI
         │
Four-bar mechanism → dynamic tapered rod → compressible pump
         │
Virtual sensors → durable outbox → MQTT broker → APM subscriber
                                                   │
                    Raw telemetry DB ← validation + deduplication
                                                   │
                    Stroke records ← acquired load–position pairs
                                                   │
                 Surface card → independent harmonic transfer → downhole card
                                                                      │
                 APM UI ── API / SSE ← versioned advisory diagnosis ← ML worker
```

The simulator and APM have distinct modules, processes, data directories and APIs. The simulator stores configuration, run truth and retry state in its own volume. APM uses PostgreSQL in Compose and SQLite/WAL in native verification. Equipment metadata are registered independently. Both apps use the same contract and engineering units. No runtime path within APM imports the simulator or reads its storage.

A stroke can be traced through its asset, run, ordered raw sequence interval and first-sequence foreign key. APM snapshots registered geometry at first receipt for each run. Card records include card and solver versions, quality, configuration, and the diagnostic payload. An offline evaluator reads both isolated outputs after collection.

The Compose ML worker is an internal APM service. APM sends reconstructed card channels and context over its private HTTP interface. The common UI components provide graphics and transport within each application. Cross-application telemetry uses MQTT.
