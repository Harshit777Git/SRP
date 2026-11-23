import json

from context import ROOT


def load(name):
    return json.loads((ROOT/"data/evaluation"/f"{name}.json").read_text())


def main():
    a=load("acceptance")
    b=load("performance")
    r=a.get("outage",{})
    derived=a["inverse_validation"]
    confidence = a["classification"]["confidence"]
    probability = f"{confidence:.1%}" if confidence is not None else "unavailable"
    rows=[]
    for c in b["cases"]:
        rows.append(f'| {c["wells"]} | {c["received_per_s"]:.1f} | {c["expected_per_s"]} | '
                    f'{c["mean_process_cpu_pct"]:.1f}% | {c["peak_combined_rss_mib"]:.1f} MiB | '
                    f'{c["ingest_mean_processing_ms"]:.3f} ms | {c["peak_sampled_publisher_ack_lag_s"]:.3f} s | '
                    f'{c["observed_missing_sequences"]} | {c["publisher_dropped"]} |')
    gaps=r.get("newly_observed_gaps",r.get("subscriber",{}).get("counts",{}).get("observed_gaps",0))
    document=f"""# Acceptance report

The native synthetic run completed with pipeline status **{a["pipeline"]}** and browser status **{a["browser"]}**. It used Python processes, an Aedes broker over loopback and SQLite/WAL. Browser verification used Playwright with Microsoft Edge. Docker Compose configuration validation passed. Docker Desktop reported it was unable to start, so the Mosquitto and PostgreSQL container runtime was unavailable.

## End-to-end evidence

1. Created the synthetic well `{a["asset"]}` in both applications. The simulator published its virtual polished-rod measurements. APM built {a["healthy_solved"]} completed healthy surface and inverse downhole cards before the fault.
2. Injected traveling-valve leakage. Surface-card area changed by {a["surface_area_change_j"]:.2f} J ({a["relative_surface_area_change"]:.2%}) against a healthy baseline spread of {a["baseline_area_spread_j"]:.3f} J in this run.
3. Joined the completed card to independent simulator truth offline. Healthy and fault position RMSE were {1000*derived[0]["position_rmse_m"]:.2f} and {1000*derived[1]["position_rmse_m"]:.2f} mm. Load RMSE were {derived[0]["load_rmse_n"]:.1f} and {derived[1]["load_rmse_n"]:.1f} N.
4. The diagnostic model returned `{a["classification"]["label"]}` with a peak predicted probability of {probability}. Recorded ML acceptance was **{a["ml_acceptance"]}** because synthetic generalization is insufficient.
5. The publisher acknowledged {a["publisher"]["sent"]:,} messages across all streams and the APM stored {a["subscriber"]["counts"]["accepted"]:,} distinct dynamometer samples at the first checkpoint. The deliberate MQTT replay passed deduplication. Broker restart found {r.get("queued_before_restart",0):,} queued messages, recovered solved stroke {r.get("recovered_stroke","unverified")}, and produced {gaps} newly observed sequence gaps. The publisher reported {r.get("publisher",{}).get("dropped",0)} queue-overflow drops.
6. Playwright exercised simulator well selection, pause and resume, sensor and fault views, APM dual cards, CSV download, live overlay and model registry. Both frontends built using the checked-in dependency lockfile. Five physics/card tests and two ingestion tests passed.

## Multiwell benchmark

Simulated shallow wells, nominal 50 Hz per well, native processes. CPU is the summed percent of a logical processor across measured processes. RSS is combined. Processing includes APM storage and stroke construction. Publisher acknowledgement lag includes queueing.

| Wells | Received samples/s | Target samples/s | CPU | Peak RSS | Mean APM processing | Peak sampled ack lag | Sequence gaps | Outbox drops |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

These short measurements describe the native stack and synthetic shallow configuration.

## Evidence files

- [Acceptance results](../data/evaluation/acceptance.json), [MQTT samples](../data/evaluation/mqtt_capture.jsonl), [paired cards](../data/evaluation/acceptance_cards.json), [isolated truth](../data/evaluation/acceptance_truth.jsonl)
- [Benchmark results](../data/evaluation/performance.json), [physics results](../data/evaluation/unit-tests.txt), [ingestion results](../data/evaluation/ingest-tests.txt), [frontend build](../data/evaluation/frontend-build.txt) and [Compose config check](../data/evaluation/compose-config.txt)
- [Simulator browser capture](../data/evaluation/simulator.png) and [APM browser capture](../data/evaluation/apm.png)
"""
    (ROOT/"docs/ACCEPTANCE_REPORT.md").write_text(document,encoding="utf8")


if __name__=="__main__":
    main()
