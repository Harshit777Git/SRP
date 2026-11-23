"""Produce a reproducible inventory of synthetic capture and model evidence."""
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def lines(path):
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def main():
    captures = []
    for folder in ("fault_training_candidate_3129_each", "fault_training_candidate_3129_each_v2",
                   "fault_training_candidate_3129_each_v3", "fault_training_candidate_3129_each_v4"):
        root = ROOT / "data/generated" / folder
        if not (root / "manifest.json").exists():
            continue
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        truth = list(lines(root / "simulation_truth_labels.jsonl"))
        cards = list(lines(root / "surface_downhole_cards.jsonl"))
        samples_by_class = Counter(row["fault_mechanism"] for row in truth)
        runs_by_class = defaultdict(set)
        severity_by_class = defaultdict(set)
        for row in truth:
            runs_by_class[row["fault_mechanism"]].add(row["run_id"])
            severity_by_class[row["fault_mechanism"]].add(row["severity"])
        cards_by_class = Counter(row.get("synthetic_fault_mechanism") for row in cards)
        hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in root.glob("*.jsonl")}
        hash_checks = {name: hashes.get(name) == digest for name, digest in manifest["files"].items()}
        captures.append({
            "dataset_id": manifest["dataset_id"],
            "physics_model_version": manifest.get("physics_model_version"),
            "raw_telemetry_rows_per_fault": dict(samples_by_class),
            "raw_telemetry_total": len(truth),
            "independent_runs_per_fault": {k: len(v) for k, v in runs_by_class.items()},
            "fault_severity_values_per_fault": {k: sorted(v) for k, v in severity_by_class.items()},
            "completed_cards_total": len(cards),
            "completed_cards_per_fault": dict(cards_by_class),
            "distinct_virtual_wells": len(manifest["wells"]),
            "manifest_hashes_match": hash_checks,
        })
    if not captures:
        raise FileNotFoundError("No verified 3,129-per-mechanism capture manifests were found")
    initial_capture = captures[0]

    fleet = json.loads((ROOT / "config/fleet/us_srp_30_wells.json").read_text(encoding="utf-8"))["wells"]
    well_noise = [{"asset_id": entry["well"]["asset_id"],
                   "noise_position_m": entry["well"]["noise_position_m"],
                   "noise_load_n": entry["well"]["noise_load_n"],
                   "position_bias_m": entry["well"]["position_bias_m"],
                   "load_bias_n": entry["well"]["load_bias_n"]} for entry in fleet]
    zero_noise_wells = sum(not any(row[k] for k in ("noise_position_m", "noise_load_n", "position_bias_m", "load_bias_n"))
                           for row in well_noise)

    complete_strokes = list((ROOT / "data/generated/balanced_independent_strokes").glob("*.json"))
    balanced_manifest = json.loads((ROOT / "reports/PHASE3_2/BALANCED_CAPTURE_AUDIT.json").read_text(encoding="utf-8"))
    balanced_eval_path = ROOT / "data/evaluation/balanced_test_be791160cf685178.json"
    balanced_eval = json.loads(balanced_eval_path.read_text(encoding="utf-8"))
    challenge_path = ROOT / "data/evaluation/balanced_v3_holdout_capture.json"
    challenge_eval = json.loads(challenge_path.read_text(encoding="utf-8")) if challenge_path.exists() else None
    remediation = json.loads((ROOT / "data/evaluation/remediation_metrics.json").read_text(encoding="utf-8"))
    remediation_best = max(remediation["models"], key=lambda name: remediation["models"][name]["macro_f1"])

    report = {
        "generated_at_utc": "2026-11-17",
        "classification": "SYNTHETIC_EVIDENCE_ONLY",
        "fault_capture_revisions": captures,
        "capture_count_interpretation": "The requested count is telemetry rows per mechanism, not independent strokes. Revisions report actual run and card counts separately.",
        "sensor_noise_and_bias": {
            "configured_wells": len(well_noise),
            "wells_with_zero_position_and_load_noise_and_bias": zero_noise_wells,
            "noise_is_field_calibrated": False,
            "interpretation": "The present synthetic captures do not test robustness to measurement noise, drift outside injected sensor faults, or calibration variation.",
        },
        "balanced_complete_stroke_experiment": {
            "complete_stroke_files": len(complete_strokes),
            "complete_strokes": balanced_manifest["complete_strokes"],
            "class_summary": balanced_manifest["classes"],
            "exact_duplicate_surface_signal_groups": len(balanced_manifest["identical_surface_signal_groups"]),
            "held_out_virtual_wells": balanced_eval["independent_virtual_wells"],
            "unique_held_out_strokes_after_exact_deduplication": balanced_eval["unique_test_strokes"],
            "macro_f1": balanced_eval["macro_f1"],
            "coverage_at_threshold": balanced_eval["coverage"],
            "accepted_accuracy": balanced_eval["accepted_accuracy"],
            "expected_calibration_error": balanced_eval["expected_calibration_error"],
            "field_test_wells": balanced_eval["real_test_wells"],
            "deployment_gates_passed": balanced_eval["field_ready"],
        },
        "new_capture_holdout_challenge": challenge_eval,
        "previous_800_run_model_comparison": {
            "synthetic_test_counts": remediation["counts"],
            "best_model": remediation_best,
            "best_macro_f1": remediation["models"][remediation_best]["macro_f1"],
            "best_coverage": remediation["models"][remediation_best]["coverage"],
            "real_labeled_test_wells": remediation["real_labeled_test_wells"],
            "model_deployed": remediation["deployed_model"] is not None,
        },
        "field_training_readiness": json.loads((ROOT / "reports/PHASE3_2/FIELD_TRAINING_READINESS.json").read_text(encoding="utf-8")),
        "data_integrity": {
            "all_capture_manifest_hashes_match": all(all(c["manifest_hashes_match"].values()) for c in captures),
        },
        "decision": "NOT_FIELD_READY",
        "reason": "No independently verified, permission-cleared labeled field stroke test set exists; synthetic metrics do not establish site accuracy.",
    }
    out = ROOT / "reports/PHASE3_2/MODEL_AND_SYNTHETIC_EVIDENCE_AUDIT.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    summary = [
        "# Model and synthetic evidence audit", "",
        "This report is derived from the current generated files and evaluation artifacts. It does not claim field performance.", "",
        "## 3,129-per-fault capture", "",
        f"- Audited {len(captures)} capture revisions. Revision 1 contains {initial_capture['raw_telemetry_total']:,} telemetry rows and {initial_capture['completed_cards_total']} complete paired cards.",
        f"- Revision 1 uses three runs per fault and covers only 10%, 20% and 40% fault severity.",
        (f"- Revision 2 contains {captures[1]['raw_telemetry_total']:,} rows, {sum(captures[1]['independent_runs_per_fault'].values())} runs, "
         f"{captures[1]['completed_cards_total']} complete paired cards, and six fault severity settings." if len(captures) > 1 else ""),
        (f"- Revision 3 contains {captures[2]['raw_telemetry_total']:,} rows, {sum(captures[2]['independent_runs_per_fault'].values())} runs, "
         f"{captures[2]['completed_cards_total']} complete paired cards." if len(captures) > 2 else ""),
        (f"- Revision 4 contains {captures[3]['raw_telemetry_total']:,} rows and {captures[3]['completed_cards_total']} complete card pairs under physics `{captures[3]['physics_model_version']}`; it is a new synthetic capture and has not yet been used to train/evaluate a model." if len(captures) > 3 else ""),
        f"- {zero_noise_wells}/{len(well_noise)} virtual well configurations have zero noise and zero bias.",
        "- The data therefore satisfy the raw sample-row target but do not provide 3,129 independent fault strokes per class.", "",
        "## Complete-stroke model evidence", "",
        f"- {balanced_manifest['complete_strokes']:,} complete synthetic strokes, {balanced_eval['independent_virtual_wells']} held-out virtual wells, and {balanced_eval['unique_test_strokes']} unique held-out cards after exact duplicate removal.",
        f"- Held-out synthetic macro F1 {balanced_eval['macro_f1']:.3f}; coverage {balanced_eval['coverage']:.3f}; accepted accuracy {balanced_eval['accepted_accuracy']:.3f}; ECE {balanced_eval['expected_calibration_error']:.3f}.",
        f"- Earlier 800-run experiment best synthetic model: {remediation_best}, macro F1 {remediation['models'][remediation_best]['macro_f1']:.3f}, coverage {remediation['models'][remediation_best]['coverage']:.3f}.",
        "- Neither evaluation includes an independent real well; neither candidate is approved for deployment.", "",
        (f"- Supplemental new-capture challenge: {challenge_eval['new_unique_cards_after_exact_deduplication']} cards from {len(challenge_eval['virtual_test_assets'])} frozen test configurations, "
         f"{len(challenge_eval['classes_present'])} classes present, macro F1 {challenge_eval['macro_f1_present_classes']:.3f}. "
         "This small synthetic-only check does not replace the larger held-out score or field validation." if challenge_eval else ""),
        "## Engineering gaps before field testing", "",
        "1. Acquire permission-cleared measured cards from multiple physical wells with independently reviewed fault evidence and complete equipment metadata.",
        "2. Collect sensor model, calibration, sampling and uncertainty metadata; do not invent noise parameters where the instrumentation is unknown.",
        "3. Expand the simulator's operating envelope from documented well inputs and verify predicted surface cards against independently exportable measured/reference traces.",
        "4. The revised clearance-leak model produces a weak synthetic pump-wear card signature; calibrate it to pump specifications/inspection evidence and retain combined/undetermined diagnosis until independent tests show reliable separability.",
        "5. Evaluate by held-out physical wells and operating periods; use synthetic tests for development only.", "",
        "Machine-readable detail: `MODEL_AND_SYNTHETIC_EVIDENCE_AUDIT.json`.",
    ]
    (out.with_suffix(".md")).write_text("\n".join(summary) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(out), "capture_revisions": len(captures),
                      "latest_rows": captures[-1]["raw_telemetry_total"],
                      "latest_cards": captures[-1]["completed_cards_total"],
                      "balanced_strokes": balanced_manifest["complete_strokes"],
                      "field_ready": False}, indent=2))


if __name__ == "__main__":
    main()
