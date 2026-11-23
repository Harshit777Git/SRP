# MQTT protocol

The default transport is MQTT 3.1.1, QoS 1. Configure the clients with `MQTT_HOST`, `MQTT_PORT`, `MQTT_QOS`, `MQTT_USERNAME`, `MQTT_PASSWORD` or `MQTT_PASSWORD_FILE`, `MQTT_TLS`, and `MQTT_CA`. TLS requires a broker listener configured to match.

| Topic suffix under srp/v1/{asset_id}/ | Payload |
|---|---|
| telemetry/dynamometer | Version, asset, source, UTC timestamp, run, sequence, stroke, index, paired displacement in inches and load in lbf, crank angle, SPM and quality |
| telemetry/electrical | Run identity, sample time, motor speed, voltage, current, power and gearbox torque |
| telemetry/pressure | Run identity, sample time, tubing/casing/intake pressure and net delivered volume |
| events/stroke | Run identity and boundary stroke ID |
| status | Retained simulator run status |
| simulation/ground_truth | Local truth optionally published with `PUBLISH_TRUTH=1` under the simulator credential |

Sample UTC is anchored to wall time at run start and advances on the simulation sampling clock. At accelerated playback, it advances faster than wall time. Monotonic interval checks use time per run. The simulator Last Will is on `srp/v1/simulator/status`.

The publisher commits raw readings to a bounded SQLite outbox. It removes rows after the broker acknowledgment at configured QoS. Unacknowledged sends retry. Statistics include acknowledgments, outbox count, publish lag, retries and overflow. The APM subscribes to explicit telemetry/status topic suffixes and accepts only registered assets. The ACL grants APM no access to truth. MQTT QoS 1 can redeliver. The APM deduplicates by asset, run and sequence and acknowledges after handling. Record gaps and bad quality mark a stroke degraded. Outlet pressures and electrical streams update independently.

The offline assessment reports simulated broker outage behavior. Broker-side acknowledgments alone establish publisher-to-broker delivery. Subscriber results are measured independently.
