"""Persist vendor reference strokes separately from live telemetry cards."""
import hashlib
import json
import math
import re

import numpy as np

from shared.contracts import ASSET_PATTERN, INCH, LBF, Well
from wave_equation.solver import reconstruct


def _curve(values, name):
    if not isinstance(values, dict):
        raise ValueError(f"{name} must be a point series")
    x = np.asarray(values.get("position_in"), dtype=float)
    y = np.asarray(values.get("load_lbf"), dtype=float)
    if x.ndim != 1 or y.ndim != 1 or len(x) != len(y) or len(x) < 32 or len(x) > 15000:
        raise ValueError(f"{name} needs equal ordered point arrays")
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError(f"{name} contains nonfinite points")
    return x, y


def _area(x, y):
    return float(abs(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y) / 2))


def prepare(body):
    if (not isinstance(body.get("asset_id"), str) or
            not re.fullmatch(ASSET_PATTERN, body["asset_id"]) or
            body.get("data_mode") != "HISTORICAL_VENDOR_DEMONSTRATION"):
        raise ValueError("Reference identity and historical mode are required")
    surface_x, surface_y = _curve(body.get("surface"), "surface")
    vendor_x, vendor_y = _curve(body.get("vendor_downhole"), "vendor downhole")
    if len(surface_x) != len(vendor_x):
        raise ValueError("Paired cards need the same sample count")
    if body.get("vendor_downhole", {}).get("status") != "VENDOR_CALCULATED":
        raise ValueError("Vendor pump card must be identified as calculated")
    config = Well.model_validate(body.get("solver_configuration"))
    if config.asset_id != body["asset_id"]:
        raise ValueError("Solver asset identity differs")
    period = float(body.get("estimated_period_s"))
    if not 2 <= period <= 30:
        raise ValueError("Estimated period is outside supported range")
    prediction = reconstruct(surface_x * INCH, surface_y * LBF, period, config)
    px = np.asarray(prediction["position_m"]) / INCH
    py = np.asarray(prediction["load_n"]) / LBF
    difference_x, difference_y = px - vendor_x, py - vendor_y
    metrics = {
        "load_rmse_lbf": float(np.sqrt(np.mean(difference_y**2))),
        "load_mae_lbf": float(np.mean(abs(difference_y))),
        "displacement_rmse_in": float(np.sqrt(np.mean(difference_x**2))),
        "displacement_mae_in": float(np.mean(abs(difference_x))),
        "stroke_length_error_in": float(np.ptp(px) - np.ptp(vendor_x)),
        "card_area_error_percent": float(100 * (_area(px, py) - _area(vendor_x, vendor_y)) / _area(vendor_x, vendor_y)),
        "maximum_load_difference_lbf": float(np.max(py) - np.max(vendor_y)),
        "minimum_load_difference_lbf": float(np.min(py) - np.min(vendor_y)),
        "load_correlation": float(np.corrcoef(py, vendor_y)[0, 1]),
        "best_circular_shift_samples": int(min(range(len(px)), key=lambda shift: np.mean((np.roll(px, shift)-vendor_x)**2 + ((np.roll(py, shift)-vendor_y)/1000)**2))),
        "phase_basis": "ORDERED_SAMPLE_INDEX; TIMEBASE_ESTIMATED_FROM_SPM",
    }
    source_hash = body.get("source_sha256")
    if not isinstance(source_hash, str) or len(source_hash) != 64:
        raise ValueError("Source SHA-256 is required")
    version = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:16]
    return {"asset_id": body["asset_id"], "display_name": body.get("display_name", "Tagging Down Hard"),
            "data_mode": body["data_mode"], "stroke_id": str(body.get("stroke_id", "1")),
            "version": version, "source_sha256": source_hash,
            "surface": body["surface"], "vendor_downhole": body["vendor_downhole"],
            "apm_downhole": {"position_in": px.tolist(), "load_lbf": py.tolist(),
                             "status": "APM_RECONSTRUCTED", "solver_version": prediction["solver_version"]},
            "solver_configuration": config.model_dump(), "assumptions": body.get("assumptions", {}),
            "estimated_period_s": period, "timebase_status": "ESTIMATED", "metrics": metrics}


def save(store, body):
    record = prepare(body)
    db = store.db
    asset_args = (record["asset_id"], record["display_name"], record["data_mode"],
                  "Echometer TAM engineering demonstration", json.dumps({
                      "asset_id": record["asset_id"], "display_name": record["display_name"],
                      "asset_type": "SRP", "data_mode": record["data_mode"],
                      "source": "Echometer TAM engineering demonstration",
                      "solver_configuration": record["solver_configuration"],
                      "assumptions": record["assumptions"]}, allow_nan=False))
    if store.postgres:
        with db.transaction():
            store.execute("""INSERT INTO reference_assets(asset,display_name,data_mode,source,payload)
                         VALUES(?,?,?,?,?) ON CONFLICT(asset) DO NOTHING""", asset_args)
            store.execute("""INSERT INTO historical_references(asset,stroke,version,source_sha256,payload)
                         VALUES(?,?,?,?,?) ON CONFLICT(asset,stroke,version) DO NOTHING""",
                          (record["asset_id"], record["stroke_id"], record["version"],
                           record["source_sha256"], json.dumps(record, allow_nan=False)))
        return get(store, record["asset_id"], record["stroke_id"], record["version"])
    db.execute("BEGIN")
    try:
        store.execute("""INSERT INTO reference_assets(asset,display_name,data_mode,source,payload)
                      VALUES(?,?,?,?,?) ON CONFLICT(asset) DO NOTHING""", asset_args)
        store.execute("""INSERT INTO historical_references(asset,stroke,version,source_sha256,payload)
                      VALUES(?,?,?,?,?) ON CONFLICT(asset,stroke,version) DO NOTHING""",
                      (record["asset_id"], record["stroke_id"], record["version"],
                       record["source_sha256"], json.dumps(record, allow_nan=False)))
        db.execute("COMMIT")
    except Exception:
        db.execute("ROLLBACK")
        raise
    return get(store, record["asset_id"], record["stroke_id"], record["version"])


def get(store, asset, stroke, version=None):
    if version:
        row = store.execute("SELECT payload FROM historical_references WHERE asset=? AND stroke=? AND version=?",
                            (asset, stroke, version)).fetchone()
    else:
        row = store.execute("SELECT payload FROM historical_references WHERE asset=? AND stroke=? ORDER BY version DESC LIMIT 1",
                            (asset, stroke)).fetchone()
    if row is None:
        raise KeyError((asset, stroke, version))
    return json.loads(row[0])
