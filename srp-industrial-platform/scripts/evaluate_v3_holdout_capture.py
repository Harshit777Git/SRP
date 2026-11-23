"""Score the frozen synthetic candidate on new runs from frozen test configurations."""
import hashlib
import json
import sys
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import classification_report, confusion_matrix, f1_score

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "apps/srp-apm")]
from fault_detection.remediation import live_inputs


def main():
    model_path = ROOT / "data/training/balanced_experimental.joblib"
    model_hash = hashlib.sha256(model_path.read_bytes()).hexdigest()
    bundle = joblib.load(model_path)
    metadata = bundle["metadata"]
    split = json.loads((ROOT / "data/evaluation/balanced_frozen_split.json").read_text())["partitions"]
    heldout_assets = set(split["test"])
    fit_run_ids = {Path(name).stem for name in metadata.get("source_hashes", {})}
    capture = ROOT / "data/generated/fault_training_candidate_3129_each_v3"
    manifest = json.loads((capture / "manifest.json").read_text())
    test_paths = [capture / "surface_downhole_cards.jsonl"]
    cards = []
    with test_paths[0].open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if row["asset_id"] not in heldout_assets:
                continue
            run_id = row["run_id"]
            if run_id in fit_run_ids:
                raise ValueError(f"Held-out run used during candidate fit/selection: {run_id}")
            label = metadata["diagnostic_label_mapping"].get(
                row["synthetic_fault_mechanism"], row["synthetic_fault_mechanism"])
            features = live_inputs(row)[1]
            cards.append((row, label, features))
    if not cards:
        raise RuntimeError("No new capture cards from frozen test wells")

    seen = {}
    kept = []
    duplicate_rows = []
    for row, label, features in cards:
        fingerprint = hashlib.sha256(json.dumps(row["surface_resampled"], sort_keys=True).encode()).hexdigest()
        if fingerprint in seen:
            if seen[fingerprint] != label:
                raise ValueError(f"Conflicting labels for duplicate input: {row['run_id']}")
            duplicate_rows.append(row["run_id"])
            continue
        seen[fingerprint] = label
        kept.append((row, label, features))
    classes = bundle["estimator"].classes_
    x = np.asarray([item[2] for item in kept])
    y = np.asarray([item[1] for item in kept])
    probabilities = bundle["estimator"].predict_proba(x)
    predicted = classes[probabilities.argmax(axis=1)]
    confidence = probabilities.max(axis=1)
    present = sorted(set(y))
    threshold = .70
    accepted = confidence >= threshold
    by_severity = {}
    for severity in sorted({float(item[0]["synthetic_severity"]) for item in kept}):
        mask = np.asarray([float(item[0]["synthetic_severity"]) == severity for item in kept])
        by_severity[str(severity)] = {
            "cards": int(mask.sum()),
            "accuracy": float(np.mean(predicted[mask] == y[mask])),
        }
    result = {
        "origin": "SYNTHETIC_NEW_RUNS_HELD_OUT_VIRTUAL_CONFIGURATIONS",
        "model_sha256": model_hash,
        "capture_dataset_id": manifest["dataset_id"],
        "capture_manifest_sha256": hashlib.sha256((capture / "manifest.json").read_bytes()).hexdigest(),
        "virtual_test_assets": sorted({item[0]["asset_id"] for item in kept}),
        "new_cards_before_deduplication": len(cards),
        "new_unique_cards_after_exact_deduplication": len(kept),
        "excluded_duplicate_runs": duplicate_rows,
        "classes_present": present,
        "macro_f1_present_classes": float(f1_score(y, predicted, labels=present, average="macro", zero_division=0)),
        "accuracy": float(np.mean(predicted == y)),
        "per_class": classification_report(y, predicted, labels=classes, output_dict=True, zero_division=0),
        "confusion": confusion_matrix(y, predicted, labels=classes).tolist(),
        "selective_threshold": threshold,
        "coverage": float(accepted.mean()),
        "accepted_accuracy": float(np.mean(predicted[accepted] == y[accepted])) if accepted.any() else None,
        "accuracy_by_severity": by_severity,
        "real_test_wells": 0,
        "field_ready": False,
        "limitation": "New synthetic runs use frozen test configurations, not physical field wells. Fault labels are simulator injections. Configured sensor noise and bias are zero.",
    }
    out = ROOT / "data/evaluation/balanced_v3_holdout_capture.json"
    out.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({k: result[k] for k in (
        "origin", "virtual_test_assets", "new_cards_before_deduplication",
        "new_unique_cards_after_exact_deduplication", "classes_present", "macro_f1_present_classes",
        "accuracy", "coverage", "accepted_accuracy", "real_test_wells", "field_ready")}, indent=2))


if __name__ == "__main__":
    main()
