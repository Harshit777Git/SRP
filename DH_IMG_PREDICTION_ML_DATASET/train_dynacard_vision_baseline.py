"""
Computer Vision & Machine Learning Baseline Classifier for Sucker Rod Pump Downhole Dynacards
Extracts visual shape features (Hu Moments & Spatial Downsampled Contours) from the 224x224 images
and trains a Random Forest Classifier with full evaluation metrics and confusion matrix.
Runs directly with OpenCV and Scikit-Learn (no GPU required).
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import cv2
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

BASE_DIR = Path(__file__).resolve().parent
TRAIN_CSV = BASE_DIR / "splits" / "train.csv"
TEST_CSV = BASE_DIR / "splits" / "test.csv"


def extract_features(df):
    X, y, ids = [], [], []
    for _, row in df.iterrows():
        img_p = BASE_DIR / row["image_path"]
        if not img_p.exists():
            continue
        img = cv2.imread(str(img_p), cv2.IMREAD_GRAYSCALE)
        img_small = cv2.resize(img, (64, 64))
        moments = cv2.moments(img_small)
        hu = cv2.HuMoments(moments).flatten()
        raw_pixels = (img_small.flatten() < 240).astype(float)
        feat = np.concatenate([hu, raw_pixels])
        X.append(feat)
        y.append(int(row["fault_class_id"]))
        ids.append(row["image_id"])
    return np.array(X), np.array(y), ids


def main():
    print("=" * 70)
    print("SUCKER ROD PUMP DYNACARD COMPUTER VISION PATTERN RECOGNITION BASELINE")
    print("=" * 70)

    train_df = pd.read_csv(TRAIN_CSV)
    test_df = pd.read_csv(TEST_CSV)
    print(f"Loaded {len(train_df)} train samples and {len(test_df)} test samples.")

    print("\nExtracting computer vision shape features from downhole dynacard images...")
    X_train, y_train, _ = extract_features(train_df)
    X_test, y_test, test_ids = extract_features(test_df)

    print(f"Feature vector dimension: {X_train.shape[1]} features per image.")
    print("Training Random Forest Classifier (100 estimators)...")
    clf = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    clf.fit(X_train, y_train)

    # Predict
    y_pred = clf.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    print(f"\n>>> HELD-OUT TEST ACCURACY: {acc * 100:.2f}% <<<")

    # Map class IDs to names
    id_to_name = dict(zip(train_df["fault_class_id"], train_df["fault_class_name"]))
    labels = sorted(list(id_to_name.keys()))
    target_names = [id_to_name[i] for i in labels]

    print("\nDetailed Classification Report:")
    print(classification_report(y_test, y_pred, labels=labels, target_names=target_names, zero_division=0))


if __name__ == "__main__":
    main()
