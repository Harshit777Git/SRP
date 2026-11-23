"""
Inference & Digital Twin Cross-Verification Tool for Sucker Rod Pump Dynacard Fault Model
Loads the trained model and performs blind inference on any downhole dynacard image or telemetry stroke.
Compares predictions against Digital Twin ground truth for verification.
"""

import os
import sys
import argparse
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import cv2

DATASET_DIR = Path(__file__).resolve().parent
MODEL_PATH = DATASET_DIR / "dynacard_fault_model.joblib"
INDEX_CSV = DATASET_DIR / "DOWNHOLE_CARD_DATASET_INDEX.csv"
COORDS_CSV = DATASET_DIR / "DOWNHOLE_CARD_COORDINATES.csv"

# Import feature extraction functions from training pipeline
from train_advanced_dynacard_model import extract_visual_features, extract_coordinate_features


def load_model():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model file not found at {MODEL_PATH}. Train the model first.")
    return joblib.load(MODEL_PATH)


def predict_from_image(image_path: Path, coords_row=None):
    payload = load_model()
    model = payload["model"]
    classes = payload["classes"]

    # 1. Computer vision features
    vis_feat = extract_visual_features(image_path)

    # 2. Coordinate features
    if coords_row is not None:
        coord_feat = extract_coordinate_features(coords_row)
    else:
        coord_feat = np.zeros(26)

    sample = np.concatenate([vis_feat, coord_feat]).reshape(1, -1)

    # Prediction
    pred_idx = model.predict(sample)[0]
    probs = model.predict_proba(sample)[0]
    predicted_class = classes[pred_idx]
    confidence = probs[pred_idx] * 100.0

    # Top 3 ranking
    top3_indices = np.argsort(probs)[::-1][:3]
    top3 = [(classes[i], probs[i] * 100.0) for i in top3_indices]

    return {
        "predicted_class": predicted_class,
        "class_id": int(pred_idx),
        "confidence_pct": confidence,
        "top3": top3,
        "all_probs": {classes[i]: probs[i] for i in range(len(classes))}
    }


def main():
    parser = argparse.ArgumentParser(description="Predict SRP Fault from Dynacard")
    parser.add_argument("--image", type=str, help="Path to 224x224 downhole dynacard image")
    parser.add_argument("--well", type=str, help="Well ID to test from dataset (e.g., prairie-001)")
    parser.add_argument("--stroke", type=str, default="strk_001", help="Stroke ID (e.g., strk_001)")
    parser.add_argument("--verify", action="store_true", help="Cross-verify against digital twin ground truth")
    args = parser.parse_args()

    if not args.image and not args.well:
        # Default demo: pick a sample from test set
        test_df = pd.read_csv(DATASET_DIR / "splits" / "test.csv")
        sample_row = test_df.sample(n=1, random_state=42).iloc[0]
        args.image = str(DATASET_DIR / sample_row["image_path"])
        args.verify = True
        print(f"[*] No input specified. Running test sample: {sample_row['image_id']} ({sample_row['well_id']} {sample_row['stroke_id']})")

    coords_df = pd.read_csv(COORDS_CSV)
    coords_lookup = {row["image_id"]: row for _, row in coords_df.iterrows()}

    img_p = Path(args.image)
    if not img_p.is_absolute():
        img_p = DATASET_DIR / img_p

    # Lookup coordinate row if available
    index_df = pd.read_csv(INDEX_CSV)
    matched = index_df[index_df["image_path"] == str(img_p.relative_to(DATASET_DIR)).replace("\\", "/")]
    coords_row = None
    gt_fault = None
    if len(matched) > 0:
        img_id = matched.iloc[0]["image_id"]
        coords_row = coords_lookup.get(img_id)
        gt_fault = matched.iloc[0]["fault_mechanism"]
        gt_class = matched.iloc[0]["fault_class_name"]

    result = predict_from_image(img_p, coords_row)

    print("\n" + "=" * 65)
    print("           SRP DYNACARD FAULT INFERENCE REPORT")
    print("=" * 65)
    print(f" Image Analyzed:       {img_p.name}")
    print(f" PREDICTED FAULT:      {result['predicted_class']}")
    print(f" Class ID:             {result['class_id']}")
    print(f" Confidence Score:     {result['confidence_pct']:.2f}%")
    print("-" * 65)
    print(" Top 3 Diagnoses Probability Distribution:")
    for rank, (cls_name, prob) in enumerate(result['top3'], 1):
        bar = "█" * int(prob / 5)
        print(f"  {rank}. {cls_name:<25} {prob:6.2f}% {bar}")

    if args.verify and gt_fault:
        match = result['predicted_class'] == gt_class
        print("-" * 65)
        print(" DIGITAL TWIN CROSS-VERIFICATION:")
        print(f" Digital Twin Truth:   {gt_fault} ({gt_class})")
        print(f" Model Match Status:   {'[PASS] VERIFIED MATCH' if match else '[WARN] DISCREPANCY'}")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
