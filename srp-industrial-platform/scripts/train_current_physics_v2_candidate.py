"""Fit a synthetic-only candidate from corrected-physics whole-well partitions."""
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, f1_score, log_loss
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import RobustScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "apps/srp-apm")]
from fault_detection.remediation import SCHEMA, live_inputs

DATA = ROOT / "data/generated/balanced_independent_strokes_v2"
SPLIT_PATH = ROOT / "data/evaluation/current_physics_v2_split.json"
OUT_MODEL = ROOT / "data/training/current_physics_v2_experimental.joblib"
OUT_REPORT = ROOT / "data/evaluation/current_physics_v2_model_selection.json"
VERSION = "srp-forward-2.0-plunger-clearance"
LABEL_MAP = {"pump_wear": "plunger_or_traveling_valve_leakage",
             "traveling_valve_leak": "plunger_or_traveling_valve_leakage"}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    split = json.loads(SPLIT_PATH.read_text(encoding="utf-8"))
    partition_for_well = {well: part for part, wells in split["groups_by_virtual_well"].items() for well in wells}
    rows, fingerprints, source_hashes, duplicate_names = [], {}, {}, []
    for path in sorted(DATA.glob("balanced-v2-*.json")):
        row = json.loads(path.read_text(encoding="utf-8"))
        if row.get("physics_model_version") != VERSION or row.get("origin") != "SYNTHETIC_SIMULATOR":
            raise ValueError(f"Unexpected provenance/version: {path.name}")
        part = partition_for_well.get(row["split_group"])
        if part is None:
            raise ValueError(f"Unassigned well {row['split_group']}")
        # Do not read held-out test card contents during fit or selection.
        if part == "test":
            continue
        label = LABEL_MAP.get(row["mechanism"], row["mechanism"])
        card_fp = hashlib.sha256(json.dumps(row["card"]["surface_resampled"], sort_keys=True).encode()).hexdigest()
        if card_fp in fingerprints:
            previous = fingerprints[card_fp]
            if previous["partition"] != part or previous["label"] != label:
                raise ValueError(f"Duplicate card crosses partitions or labels: {path.name}")
            duplicate_names.append(path.name)
            continue
        fingerprints[card_fp] = {"partition": part, "label": label}
        source_hashes[path.name] = digest(path)
        rows.append((row, part, label, live_inputs(row["card"])[1]))

    if not rows:
        raise RuntimeError("No deduplicated train/calibration rows found")
    x = np.asarray([r[3] for r in rows], dtype=np.float64)
    y = np.asarray([r[2] for r in rows])
    parts = np.asarray([r[1] for r in rows])
    train, calibration = parts == "train", parts == "calibration"
    if not train.any() or not calibration.any() or not np.isfinite(x).all():
        raise ValueError("Invalid feature matrix or empty partition")
    classes = sorted(set(y[train]))
    if set(y[calibration]) != set(classes):
        raise ValueError("Train/calibration class mismatch")

    candidates = {
        "logistic_robust": make_pipeline(RobustScaler(), LogisticRegression(
            max_iter=5000, C=0.5, class_weight="balanced", random_state=73129)),
        "extra_trees": ExtraTreesClassifier(n_estimators=500, min_samples_leaf=2,
            max_features=0.8, n_jobs=2, random_state=73129, class_weight="balanced"),
        "random_forest": RandomForestClassifier(n_estimators=500, min_samples_leaf=2,
            max_features="sqrt", n_jobs=2, random_state=73129, class_weight="balanced_subsample"),
        "hist_gradient": HistGradientBoostingClassifier(max_iter=250, max_leaf_nodes=15,
            l2_regularization=1.0, learning_rate=0.08, random_state=73129),
    }
    metrics = {}
    selected_predictions = {}
    for name, model in candidates.items():
        if name == "hist_gradient":
            counts = Counter(y[train])
            weights = np.asarray([len(y[train]) / (len(counts) * counts[label]) for label in y[train]])
            model.fit(x[train], y[train], sample_weight=weights)
        else:
            model.fit(x[train], y[train])
        probs = model.predict_proba(x[calibration])
        pred = model.classes_[probs.argmax(axis=1)]
        selected_predictions[name] = (pred, probs)
        metrics[name] = {
            "macro_f1_calibration": float(f1_score(y[calibration], pred, average="macro")),
            "log_loss_calibration": float(log_loss(y[calibration], probs, labels=model.classes_)),
            "accuracy_calibration": float(np.mean(pred == y[calibration])),
            "classes": model.classes_.tolist(),
            "confusion_calibration": confusion_matrix(y[calibration], pred, labels=model.classes_).tolist(),
            "per_class_calibration": classification_report(y[calibration], pred, output_dict=True, zero_division=0),
        }
        print(name, metrics[name]["macro_f1_calibration"], metrics[name]["log_loss_calibration"], flush=True)

    # Selection criterion is fixed in advance: macro F1 first, log-loss as tie-breaker.
    selected = max(metrics, key=lambda name: (metrics[name]["macro_f1_calibration"],
                                               -metrics[name]["log_loss_calibration"]))
    model = candidates[selected]
    artifact_metadata = {
        "origin": "SYNTHETIC_ONLY", "deployed": False, "field_ready": False,
        "model_version": f"current-physics-v2/{selected}", "physics_model_version": VERSION,
        "feature_schema": SCHEMA, "selected_on": "calibration partition only",
        "selection_rule": "highest calibration macro-F1, then lower calibration log-loss",
        "selected_model": selected, "calibration_metrics": metrics[selected],
        "all_candidate_calibration_metrics": metrics,
        "class_mapping": LABEL_MAP, "source_hashes_train_and_calibration": source_hashes,
        "excluded_exact_duplicate_records_train_calibration": duplicate_names,
        "unique_train_counts": dict(Counter(y[train])),
        "unique_calibration_counts": dict(Counter(y[calibration])),
        "split_sha256": digest(SPLIT_PATH), "test_partition_opened": False,
        "confidence_calibration": "none; probabilities are uncalibrated",
        "real_labeled_wells": 0,
        "limitations": ["Synthetic-only simulator injections; not measured diagnoses.",
            "Zero configured sensor noise/bias; no field robustness assessment.",
            "Pump wear is merged with traveling-valve leakage and cannot be component-resolved.",
            "Virtual configurations share one model and parameter-generation envelope."],
    }
    OUT_MODEL.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"estimator": model, "metadata": artifact_metadata}, OUT_MODEL)
    OUT_REPORT.write_text(json.dumps(artifact_metadata, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"model": str(OUT_MODEL), "selected": selected,
        "train_cards": int(train.sum()), "calibration_cards": int(calibration.sum()),
        "deduplicated": len(duplicate_names), "test_partition_opened": False}, indent=2))


if __name__ == "__main__":
    main()
