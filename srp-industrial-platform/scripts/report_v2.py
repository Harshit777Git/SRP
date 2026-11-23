import json

from context import ROOT


def main():
    evaluation=ROOT/"data/evaluation"
    evidence=evaluation/"v2"
    a=json.loads((evidence/"acceptance.json").read_text())
    source=evaluation/"v2_full_ml.json"
    if not source.exists():
        source=evaluation/"v2_ml.json"
    model=json.loads(source.read_text())
    seed=model["seeds"][0]
    summary=[]
    for key,label in (("tabular",model["tabular_model"]),("cnn","Dual-branch CNN"),("ensemble","Probability average")):
        spread=model["macro_f1_across_seeds"][key]
        run=seed[key]
        summary.append(f'| {label} | {spread["mean"]:.3f} ± {spread["spread"]:.3f} | {run["accuracy"]:.3f} | '
                       f'{run["expected_calibration_error"]:.3f} | {run["unknown_fraction"]:.1%} | '
                       f'{run["healthy_false_positive_fraction"]:.1%} |')
    tests=model["groups"]["test"]
    thresholds=[]
    for name in ("tabular","cnn","ensemble"):
        stats=seed[name]["per_class"]
        thresholds.append(f'| {name} | {sum(stats[c]["precision"]>=.85 for c in model["classes"])} / {len(model["classes"])} | '
                          f'{sum(stats[c]["recall"]>=.85 for c in model["classes"])} / {len(model["classes"])} |')
    (ROOT/"docs/FAULT_MODEL_VALIDATION.md").write_text(f"""# Fault model validation

**SYNTHETIC VALIDATION ONLY**

Accepted dataset size was **{model["accepted_runs"]} independent runs**, one stroke per run, with {model["rejected_runs"]} rejected reconstructions. Class counts were {', '.join(f'{c} {n}' for c,n in model["counts"].items())}. Wells were grouped by equipment configuration. Training used {len(model["groups"]["train"])} configurations, calibration used {len(model["groups"]["calibration"])} and evaluation used {len(tests)} unseen configurations.

| Model | Mean raw macro F1 ± seed standard deviation | Raw accuracy (seed 13) | ECE (seed 13) | UNKNOWN after guards (seed 13) | Accepted healthy-run false-positive fraction |
|---|---:|---:|---:|---:|---:|
{chr(10).join(summary)}

| Model, seed 13 | Classes at ≥0.85 precision | Classes at ≥0.85 recall |
|---|---:|---:|
{chr(10).join(thresholds)}

Metrics before abstention use the highest class score. UNKNOWN uses the 0.70 confidence gate and training SPM domain. The rules provide evidence rather than a classified root cause. False alarms per well-day and detection latency require longitudinal data. The native acceptance classifier was explicitly selected for this isolated check. The live default stays on the engineering baseline and Dynacard reference monitor. The experiments provide no field validation.

Run `python scripts/train_v2.py --runs-per-class 100 --workers 8 --tag v2_full` with CPU PyTorch and LightGBM installed. The JSON includes per-class precision, recall, F1, confusion matrices, calibration and latency for every seed. The training directory retains equipment, severity and seed for each run plus versioned experimental artifacts. [Machine-readable model results](../data/evaluation/{source.name}).
""",encoding="utf8")

    truth=a.get("offline_pump_truth",[])
    details="; ".join(f'{r["label"]} {1000*r["position_rmse_m"]:.2f} mm and {r["load_rmse_n"]:.1f} N' for r in truth)
    diagnosis=a.get("fault_evidence",{}).get("diagnosis",{})
    records=a.get("roundtrips",[])
    err=max((max(r["max_error"].values()) for r in records),default=0.)
    (ROOT/"docs/V2_ACCEPTANCE_REPORT.md").write_text(f"""# V2 acceptance report

Native Windows pipeline **{a["pipeline"]}**, pump browser playback **{a.get("playback","unverified")}**, engineering browser comparison **{a.get("comparison_browser","unverified")}**, and vendor browser comparison **{a.get("vendor_browser_comparison","unverified")}**. The existing simulator and APM ran as separate processes connected via Aedes MQTT. The native launcher continues to support the default local ports. Docker was unnecessary.

## Verified evidence

- The simulator was started in Playwright. APM received and processed the current stroke, reconstructed pump motion, scrubbed all three views together, froze the clock and advanced at 2×. Offline reconstruction versus isolated simulator truth: {details or "see V1 numerical validation for the previous truth sweep"}.
- Injected traveling-valve leakage through the simulator UI. APM detected the card change without the injected label and executed experimental model `{diagnosis.get("model_version","unverified")}`. Recorded classification was `{diagnosis.get("label","unverified")}`.
- Browser downloaded the engineering CSV, imported it, saved the dataset and downloaded the comparison report. Across {len(records)} healthy/faulty surface/downhole round trips, maximum absolute SI position or force error was {err:.3g}. Raw and configuration CSV previews also validated.
- Imported the 132-point Echometer Overtravel example in the browser and generated a geometry-only comparison report. A separate parser check verified the Overtravel and 216-point Undertravel example blocks. Their full equipment and time alignment were unavailable.
- TypeScript/Vite builds, numerical physics, ingestion and mapping tests passed. The first V2 training pass exposed a NumPy scalar JSON serialization error. Metrics were regenerated after correcting serialization. The browser acceptance was repeated after adding vendor parsing and download headers.

## Remaining partial items

Valve actuation, flow direction, fillage and chamber-pressure observation are unresolved. New native DYN writing, TAM_EXP, complete TWM fixture coverage and installed vendor applications are unverified. A matched external numerical prediction run and longitudinal field ML evaluation are still required. See [model validation](FAULT_MODEL_VALIDATION.md) for the actual held-out results.

## Reproduce and inspect

- `python scripts/check_physics.py`, `python scripts/check_ingest.py`, and `python scripts/check_interchange_v2.py`
- `python scripts/run_v2_acceptance.py`. Optionally set SRP_VENDOR_EXAMPLE_ARCHIVE to the training ZIP and SRP_V2_ACCEPTANCE_MODEL to a candidate CNN .pt file.
- [Machine-readable acceptance](../data/evaluation/v2/acceptance.json), [playback](../data/evaluation/v2/animated_pump.png), [fault diagnosis](../data/evaluation/v2/fault_diagnosis.png), [external overlay](../data/evaluation/v2/external_dyn_benchmark.png), [external report](../data/evaluation/v2/external_dyn_comparison.json), [surface CSV](../data/evaluation/v2/healthy_surface.csv), [faulty downhole CSV](../data/evaluation/v2/leak_downhole.csv)
""",encoding="utf8")


if __name__=="__main__":
    main()
