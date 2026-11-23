"""
Advanced Sucker Rod Pump (SRP) Dynacard Fault Classification Model
Fuses Computer Vision (Hu Moments, Contour Harmonics, Pixel Projections)
with Wave Equation Dynamometer Physics (Shoelace Loop Work, Valve Delays, Load Hysteresis)
Trains on DH_IMG_PREDICTION_ML_DATASET and evaluates on the held-out test split.
"""

import os
import sys
import math
import joblib
from pathlib import Path
import numpy as np
import pandas as pd
import cv2
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier, HistGradientBoostingClassifier, VotingClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score

DATASET_DIR = Path(r"C:\Users\HARSHIT\OneDrive - TAS\Desktop\SRP\DH_IMG_PREDICTION_ML_DATASET")
INDEX_CSV = DATASET_DIR / "DOWNHOLE_CARD_DATASET_INDEX.csv"
COORDS_CSV = DATASET_DIR / "DOWNHOLE_CARD_COORDINATES.csv"
TRAIN_CSV = DATASET_DIR / "splits" / "train.csv"
VAL_CSV = DATASET_DIR / "splits" / "val.csv"
TEST_CSV = DATASET_DIR / "splits" / "test.csv"
MODEL_SAVE_PATH = DATASET_DIR / "dynacard_fault_model.joblib"


def extract_visual_features(image_path: Path) -> np.ndarray:
    """Extract invariant computer vision features from 224x224 dynacard image."""
    img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"Cannot load image {image_path}")

    # Threshold binary card contour
    _, thresh = cv2.threshold(img, 240, 255, cv2.THRESH_BINARY_INV)

    # 1. Hu Moments (log-transformed)
    moments = cv2.moments(thresh)
    hu = cv2.HuMoments(moments).flatten()
    log_hu = []
    for h in hu:
        if abs(h) > 1e-15:
            log_hu.append(-math.copysign(1.0, h) * math.log10(abs(h)))
        else:
            log_hu.append(0.0)

    # 2. Contour geometric properties
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        cnt = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(cnt)
        perimeter = cv2.arcLength(cnt, True)
        x, y, w, h = cv2.boundingRect(cnt)
        aspect_ratio = float(w) / max(1, h)
        extent = float(area) / max(1, w * h)
        hull = cv2.convexHull(cnt)
        hull_area = cv2.contourArea(hull)
        solidity = float(area) / max(1, hull_area)
    else:
        area, perimeter, aspect_ratio, extent, solidity = 0, 0, 1.0, 0, 0

    # 3. Horizontal and vertical projection histograms (32 bins each)
    h_proj = cv2.resize(thresh, (32, 32)).mean(axis=1) / 255.0
    v_proj = cv2.resize(thresh, (32, 32)).mean(axis=0) / 255.0

    return np.concatenate([
        np.array(log_hu),
        [area / (224 * 224), perimeter / (224 * 4), aspect_ratio, extent, solidity],
        h_proj,
        v_proj
    ])


def extract_coordinate_features(row) -> np.ndarray:
    """Extract physical dynamometer indicator features from 100-point time series."""
    norm_pos = np.array([float(v) for v in row["norm_pos_100"].split(";")])
    norm_load = np.array([float(v) for v in row["norm_load_100"].split(";")])
    n = len(norm_pos)

    # Enclosed loop area via Shoelace formula
    shoelace_area = 0.5 * abs(np.dot(norm_pos, np.roll(norm_load, 1)) - np.dot(norm_load, np.roll(norm_pos, 1)))

    # Upstroke vs downstroke segmentation (dx >= 0 vs dx < 0)
    dx = np.gradient(norm_pos)
    up_mask = dx >= 0
    down_mask = dx < 0

    up_load_mean = float(np.mean(norm_load[up_mask])) if np.any(up_mask) else 0.5
    down_load_mean = float(np.mean(norm_load[down_mask])) if np.any(down_mask) else 0.5
    hysteresis_delta = up_load_mean - down_load_mean

    # Lower shelf impact detection (fluid pound characteristic flat shelf at bottom)
    down_loads = norm_load[down_mask]
    down_pos = norm_pos[down_mask]
    if len(down_loads) > 10:
        shelf_std = float(np.std(down_loads[:len(down_loads) // 2]))
        # Gradient slope on downstroke
        down_slope = np.gradient(down_loads, max(1e-4, np.ptp(down_pos)))
        max_down_slope = float(np.max(np.abs(down_slope)))
    else:
        shelf_std, max_down_slope = 0.0, 0.0

    # Valve opening / closing slanted edge slopes
    # TV delay: load pickup slope near BOS
    bos_idx = int(np.argmin(norm_pos))
    tos_idx = int(np.argmax(norm_pos))

    # Load pickup rate around BOS
    near_bos_indices = [(bos_idx + k) % n for k in range(-4, 5)]
    pickup_rate = float(np.ptp(norm_load[near_bos_indices]))

    # Load drop rate around TOS
    near_tos_indices = [(tos_idx + k) % n for k in range(-4, 5)]
    drop_rate = float(np.ptp(norm_load[near_tos_indices]))

    # Peak and minimum loads
    peak_l = float(np.max(norm_load))
    min_l = float(np.min(norm_load))

    # Fourier harmonics of the 100-point signal
    fft_load = np.abs(np.fft.rfft(norm_load)[:8]) / n
    fft_pos = np.abs(np.fft.rfft(norm_pos)[:8]) / n

    return np.concatenate([
        [shoelace_area, up_load_mean, down_load_mean, hysteresis_delta,
         shelf_std, max_down_slope, pickup_rate, drop_rate, peak_l, min_l],
        fft_load,
        fft_pos
    ])


def build_feature_matrix(df, coords_lookup):
    """Build unified feature matrix for dataset."""
    X_list, y_list, ids = [], [], []

    for _, row in df.iterrows():
        img_id = row["image_id"]
        img_path = DATASET_DIR / row["image_path"]

        # 1. Computer Vision features from image
        vis_feat = extract_visual_features(img_path)

        # 2. Coordinate physics features
        c_row = coords_lookup.get(img_id)
        if c_row is not None:
            coord_feat = extract_coordinate_features(c_row)
        else:
            coord_feat = np.zeros(26)

        # Combine
        combined = np.concatenate([vis_feat, coord_feat])
        X_list.append(combined)
        y_list.append(int(row["fault_class_id"]))
        ids.append(img_id)

    return np.array(X_list), np.array(y_list), ids


def main():
    print("=" * 80)
    print("SUCKER ROD PUMP (SRP) DYNACARD COMPUTER VISION & PHYSICS FAULT CLASSIFIER")
    print("=" * 80)

    train_df = pd.read_csv(TRAIN_CSV)
    val_df = pd.read_csv(VAL_CSV)
    test_df = pd.read_csv(TEST_CSV)
    coords_df = pd.read_csv(COORDS_CSV)
    coords_lookup = {row["image_id"]: row for _, row in coords_df.iterrows()}

    print(f"Loaded Train: {len(train_df)} | Val: {len(val_df)} | Test: {len(test_df)}")
    print("Extracting multi-modal computer vision and wave equation dynacard features...")

    X_train, y_train, _ = build_feature_matrix(train_df, coords_lookup)
    X_val, y_val, _ = build_feature_matrix(val_df, coords_lookup)
    X_test, y_test, test_ids = build_feature_matrix(test_df, coords_lookup)

    print(f"Extracted {X_train.shape[1]} features per Dynacard sample.")

    # Ensemble: Random Forest + Extra Trees + HistGradientBoosting
    print("\nTraining Ensemble Model (RandomForest + ExtraTrees + HistGradientBoosting)...")
    rf = RandomForestClassifier(n_estimators=150, max_depth=16, random_state=42, n_jobs=-1)
    et = ExtraTreesClassifier(n_estimators=150, max_depth=16, random_state=42, n_jobs=-1)
    hgb = HistGradientBoostingClassifier(max_iter=100, random_state=42)

    ensemble = VotingClassifier(
        estimators=[('rf', rf), ('et', et), ('hgb', hgb)],
        voting='soft',
        n_jobs=-1
    )

    ensemble.fit(X_train, y_train)

    # Validation evaluation
    val_preds = ensemble.predict(X_val)
    val_acc = accuracy_score(y_val, val_preds)
    print(f"\n--- VALIDATION ACCURACY: {val_acc * 100:.2f}% ---")

    # Held-out Test evaluation
    test_preds = ensemble.predict(X_test)
    test_acc = accuracy_score(y_test, test_preds)
    test_f1 = f1_score(y_test, test_preds, average='weighted')

    print(f"\n>>> FINAL HELD-OUT TEST ACCURACY: {test_acc * 100:.2f}% (Weighted F1: {test_f1 * 100:.2f}%) <<<")

    # Map labels to human-readable names
    id_to_name = dict(zip(train_df["fault_class_id"], train_df["fault_class_name"]))
    labels = sorted(list(id_to_name.keys()))
    target_names = [id_to_name[i] for i in labels]

    print("\n" + "=" * 80)
    print("DETAILED PER-CLASS CLASSIFICATION REPORT ON TEST SET:")
    print("=" * 80)
    print(classification_report(y_test, test_preds, labels=labels, target_names=target_names, digits=4, zero_division=0))

    # Save model
    model_payload = {
        "model": ensemble,
        "classes": target_names,
        "class_id_map": id_to_name,
        "test_accuracy": test_acc,
        "n_features": X_train.shape[1]
    }
    joblib.dump(model_payload, MODEL_SAVE_PATH)
    print(f"\nSaved trained model artifact to: {MODEL_SAVE_PATH}")


if __name__ == "__main__":
    main()
