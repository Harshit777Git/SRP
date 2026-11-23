"""One-time held-out virtual-configuration evaluation for the v2 candidate."""
import hashlib
import json
import sys
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import classification_report, confusion_matrix, f1_score, log_loss

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "apps/srp-apm")]
from fault_detection.remediation import CONFIDENCE, GATES, live_inputs

DATA = ROOT / "data/generated/balanced_independent_strokes_v2"
SPLIT_PATH = ROOT / "data/evaluation/current_physics_v2_split.json"
MODEL_PATH = ROOT / "data/training/current_physics_v2_experimental.joblib"


def main():
    split = json.loads(SPLIT_PATH.read_text(encoding="utf-8"))
    bundle = joblib.load(MODEL_PATH)
    model, metadata = bundle["estimator"], bundle["metadata"]
    if metadata.get("test_partition_opened") is not False:
        raise RuntimeError("Candidate metadata indicates test data was used during selection")
    selected_wells = set(split["groups_by_virtual_well"]["test"])
    train_cal_hashes = metadata["source_hashes_train_and_calibration"]
    rows, seen, duplicates = [], {}, []
    for path in sorted(DATA.glob("balanced-v2-*.json")):
        row = json.loads(path.read_text(encoding="utf-8"))
        if row["split_group"] not in selected_wells:
            continue
        if path.name in train_cal_hashes:
            raise ValueError(f"Test file appeared in candidate selection provenance: {path.name}")
        label = metadata["class_mapping"].get(row["mechanism"], row["mechanism"])
        fingerprint = hashlib.sha256(json.dumps(row["card"]["surface_resampled"], sort_keys=True).encode()).hexdigest()
        if fingerprint in seen:
            if seen[fingerprint] != label:
                raise ValueError("Duplicate test card has conflicting labels")
            duplicates.append(path.name)
            continue
        seen[fingerprint] = label
        rows.append((row, label, live_inputs(row["card"])[1]))
    if not rows:
        raise RuntimeError("Held-out test partition is empty")
    x = np.asarray([r[2] for r in rows])
    y = np.asarray([r[1] for r in rows])
    probabilities = model.predict_proba(x)
    predicted = model.classes_[probabilities.argmax(axis=1)]
    confidence = probabilities.max(axis=1)
    accepted = confidence >= CONFIDENCE
    correct = predicted == y
    calibration_bins, ece = [], 0.0
    for lower in np.arange(0, 1, .1):
        upper = lower + .1
        mask = (confidence >= lower) & ((confidence < upper) if lower < .9 else (confidence <= 1))
        if mask.any():
            accuracy, mean_conf = float(correct[mask].mean()), float(confidence[mask].mean())
            ece += float(mask.mean()) * abs(accuracy - mean_conf)
            calibration_bins.append({"lower": float(lower), "count": int(mask.sum()),
                                     "accuracy": accuracy, "confidence": mean_conf})
    mechanisms = {}
    for mechanism in sorted({r[0]["mechanism"] for r in rows}):
        mask = np.asarray([r[0]["mechanism"] == mechanism for r in rows])
        mechanisms[mechanism] = {"records": int(mask.sum()),
            "diagnostic_label": str(y[mask][0]), "accuracy": float(np.mean(predicted[mask] == y[mask])),
            "mean_top_probability": float(confidence[mask].mean())}
    by_severity = {}
    for severity in sorted({float(r[0]["severity"]) for r in rows}):
        mask = np.asarray([float(r[0]["severity"]) == severity for r in rows])
        by_severity[str(severity)] = {"records": int(mask.sum()),
            "accuracy": float(np.mean(predicted[mask] == y[mask]))}
    model_sha = hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()
    report = {
        "origin": "HELD_OUT_SYNTHETIC_VIRTUAL_CONFIGURATIONS",
        "model_sha256": model_sha, "selected_model": metadata["selected_model"],
        "physics_model_version": metadata["physics_model_version"],
        "test_virtual_wells": sorted({r[0]["split_group"] for r in rows}),
        "raw_test_records": len(rows) + len(duplicates), "unique_test_cards": len(rows),
        "exact_duplicates_excluded": duplicates,
        "macro_f1": float(f1_score(y, predicted, average="macro")),
        "accuracy": float(np.mean(correct)), "log_loss": float(log_loss(y, probabilities, labels=model.classes_)),
        "per_class": classification_report(y, predicted, labels=model.classes_, output_dict=True, zero_division=0),
        "classes": model.classes_.tolist(),
        "confusion_matrix": confusion_matrix(y, predicted, labels=model.classes_).tolist(),
        "by_original_injected_mechanism": mechanisms, "by_severity": by_severity,
        "confidence_threshold": CONFIDENCE, "coverage_at_existing_threshold": float(accepted.mean()),
        "accepted_accuracy": float(np.mean(correct[accepted])) if accepted.any() else None,
        "expected_calibration_error": float(ece), "calibration_bins": calibration_bins,
        "real_test_wells": 0, "field_ready": False, "deployed": False,
        "deployment_gates": GATES,
        "limitations": ["Test is six held-out virtual well configurations, not independent field wells.",
            "Simulator-injected fault labels are not independently confirmed fault diagnoses.",
            "Configured sensor noise and bias are zero; no real sensor/domain shift is represented.",
            "Plunger wear and traveling-valve leakage share a single combined diagnostic output.",
            "Probabilities are uncalibrated and the existing confidence threshold was not lowered."],
    }
    output = ROOT / "data/evaluation" / f"current_physics_v2_test_{model_sha[:16]}.json"
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite immutable evaluation: {output}")
    output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("selected_model", "macro_f1", "accuracy", "log_loss",
        "coverage_at_existing_threshold", "accepted_accuracy", "expected_calibration_error",
        "unique_test_cards", "real_test_wells", "field_ready")}, indent=2))
    print("report:", output)


if __name__ == "__main__":
    main()
