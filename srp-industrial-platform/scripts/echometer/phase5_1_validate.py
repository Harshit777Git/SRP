"""Validate preserved TAM TXT/DYN stroke pairs and checkpoint Phase 5.1.

Run after each GUI export. This only counts a stroke when the two original
vendor files agree numerically. It never changes either source file.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from import_vendor_reference import dyn_surface, four_column  # noqa: E402

DATA = ROOT / "data" / "state93"
REPORT = ROOT / "reports" / "STATE93" / "PHASE5_1"
PHASE5 = ROOT / "reports" / "STATE93" / "PHASE5"
KNOWN = {
    "STATE-001": ("1995-06-07_215400", 4, 4),
    "STATE-002": ("2002-01-11_012908", 99, 99),
    "STATE-003": ("1997-12-13_045700", 5, 1),
    "STATE-004": ("1995-02-25_100152", 7, 7),
    "STATE-005": ("1996-02-22_043000", 5, 5),
}
JOBS_PATH = REPORT / "TAM_GUI_JOBS.json"


def jobs():
    result = {state: {test: {"reported_strokes": total, "pilot_stroke": pilot}}
              for state, (test, total, pilot) in KNOWN.items()}
    if JOBS_PATH.exists():
        custom = json.loads(JOBS_PATH.read_text(encoding="utf-8"))
        for state, tests in custom.get("states", {}).items():
            result.setdefault(state, {}).update(tests)
    return result


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        for attempt in range(6):
            try:
                tmp.replace(path)
                return
            except PermissionError:
                if attempt == 5:
                    raise
                time.sleep(0.25 * (attempt + 1))
    finally:
        if tmp.exists():
            tmp.unlink()


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def source_pair(state: str, test: str, stroke: int, pilot_stroke: int) -> tuple[Path, Path]:
    folder = DATA / state / "05_NUMERICAL_DATA" / "TAM" / ("test_" + test)
    if stroke == pilot_stroke:
        txt = [p for p in folder.glob("*.txt") if "_stroke-" not in p.name]
        dyn = [p for p in folder.glob("*.dyn") if "_stroke-" not in p.name]
    else:
        txt = list(folder.glob(f"*_stroke-{stroke}.txt"))
        dyn = list(folder.glob(f"*_stroke-{stroke}.dyn"))
    if len(txt) != 1 or len(dyn) != 1:
        raise FileNotFoundError(f"{state} {test} stroke {stroke}: TXT={len(txt)}, DYN={len(dyn)}")
    return txt[0], dyn[0]


def partial_status(state: str, test: str, stroke: int, pilot_stroke: int) -> str:
    folder = DATA / state / "05_NUMERICAL_DATA" / "TAM" / ("test_" + test)
    if stroke == pilot_stroke:
        txt = [p for p in folder.glob("*.txt") if "_stroke-" not in p.name]
        dyn = [p for p in folder.glob("*.dyn") if "_stroke-" not in p.name]
    else:
        txt = list(folder.glob(f"*_stroke-{stroke}.txt"))
        dyn = list(folder.glob(f"*_stroke-{stroke}.dyn"))
    if len(txt) > 1 or len(dyn) > 1:
        return "FAILED"
    if txt and not dyn:
        return "TXT_EXPORTED"
    if dyn and not txt:
        return "DYN_EXPORTED"
    return "NOT_STARTED"


def verify(state: str, test: str, stroke: int, pilot_stroke: int) -> dict:
    txt, dyn = source_pair(state, test, stroke, pilot_stroke)
    raw, surf = four_column(txt), dyn_surface(dyn)
    if raw.ndim != 2 or raw.shape[1] != 4 or not np.isfinite(raw).all():
        raise ValueError("TXT lacks four finite numerical columns")
    if surf.ndim != 2 or surf.shape[1] != 2 or not np.isfinite(surf).all():
        raise ValueError("DYN lacks two finite Surface columns")
    if len(raw) < 20 or len(raw) != len(surf):
        raise ValueError("Incomplete or unequal sample arrays")
    dx = float(np.max(np.abs(raw[:, 0] - surf[:, 0])))
    dy = float(np.max(np.abs(raw[:, 1] * 1000 - surf[:, 1])))
    if dx > 1e-5 or dy > 0.05:
        raise ValueError(f"TXT/DYN mismatch: position={dx} in, load={dy} lbf")
    source_hashes = {"txt": digest(txt), "dyn": digest(dyn)}
    fingerprint = hashlib.sha256(np.round(raw, 5).astype("<f8").tobytes()).hexdigest()
    out = DATA / state / "05_NUMERICAL_DATA" / "normalized" / ("test_" + test) / ("stroke_" + str(stroke))
    out.mkdir(parents=True, exist_ok=True)
    for label, x, y in (("surface", raw[:, 0], raw[:, 1]), ("vendor_pump", raw[:, 2], raw[:, 3])):
        rows = [{"state_id": state, "test_id": test, "stroke_id": stroke,
                 "sample_index": i, "position_in": float(a), "load_lbf": float(b * 1000)}
                for i, (a, b) in enumerate(zip(x, y))]
        write_csv(out / f"{label}.csv", rows, list(rows[0]))
        pq.write_table(pa.Table.from_pylist(rows), out / f"{label}.parquet")
    return {"state_id": state, "test_id": test, "stroke_id": stroke,
            "status": "NUMERICAL_VERIFIED", "points": len(raw),
            "position_unit": "in", "load_unit": "lbf", "txt_surface_load_unit": "klbf",
            "max_position_difference_in": dx, "max_load_difference_lbf": dy,
            "txt_path": str(txt.resolve()), "dyn_path": str(dyn.resolve()),
            "txt_sha256": source_hashes["txt"], "dyn_sha256": source_hashes["dyn"],
            "sample_array_fingerprint": fingerprint, "normalized_dir": str(out.resolve())}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", help="Validate one state; default validates all registered TAM tests")
    args = parser.parse_args()
    REPORT.mkdir(parents=True, exist_ok=True)
    checkpoint_path = PHASE5 / "PROCESSING_CHECKPOINT.json"
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    progress_path = REPORT / "EXTRACTION_PROGRESS.json"
    progress = json.loads(progress_path.read_text(encoding="utf-8")) if progress_path.exists() else {"schema": "phase5.1/1", "states": {}}
    inventory: list[dict] = []
    validation: list[dict] = []
    failures: list[dict] = []
    for state, tests in jobs().items():
        if args.state and state != args.state:
            continue
        record = progress["states"].setdefault(state, {"tests": {}})
        for test, job in tests.items():
          total, pilot_stroke = int(job["reported_strokes"]), int(job.get("pilot_stroke", 0))
          test_record = record["tests"].setdefault(test, {"reported_strokes": total, "strokes": {}})
          for stroke in range(1, total + 1):
              key = str(stroke)
              prior = test_record["strokes"].get(key, {})
              try:
                  txt, dyn = source_pair(state, test, stroke, pilot_stroke)
              except FileNotFoundError:
                  if prior.get("status") != "NUMERICAL_VERIFIED":
                      test_record["strokes"][key] = {"status": partial_status(state, test, stroke, pilot_stroke)}
                  continue
              try:
                  if prior.get("status") == "NUMERICAL_VERIFIED" and prior.get("txt_sha256") == digest(txt) and prior.get("dyn_sha256") == digest(dyn) and Path(prior["normalized_dir"]).joinpath("surface.parquet").exists():
                      result = prior
                  else:
                      result = verify(state, test, stroke, pilot_stroke)
                  test_record["strokes"][key] = result
                  inventory.append(result)
                  validation.append(result)
              except Exception as exc:
                  failure = {"state_id": state, "test_id": test, "stroke_id": stroke, "status": "FAILED", "error": str(exc)}
                  test_record["strokes"][key] = failure
                  failures.append(failure)
              atomic_json(progress_path, progress)
        verified = sum(v.get("status") == "NUMERICAL_VERIFIED" for t in record["tests"].values() for v in t["strokes"].values())
        record["status"] = "NUMERICAL_EXTRACTED" if verified else "DISCOVERED"
        record["verified_strokes"] = verified
        checkpoint["states"].setdefault(state, {})["phase5_1"] = record
        atomic_json(checkpoint_path, checkpoint)
        atomic_json(progress_path, progress)
    # Report from the full checkpoint, including states not selected in this run.
    all_results = [r for s in progress["states"].values() for t in s["tests"].values()
                   for r in t["strokes"].values() if r.get("status") == "NUMERICAL_VERIFIED"]
    prior_077 = json.loads((ROOT / "reports" / "STATE93" / "STATE077_IMPORT_VALIDATION.json").read_text(encoding="utf-8"))
    if prior_077.get("readback_passed") and prior_077.get("surface_points") == 174:
        files = prior_077["source_audit"]["source_files"]
        txt, dyn = Path(files[0]["path"]), Path(files[1]["path"])
        if txt.exists() and dyn.exists() and digest(txt) == files[0]["sha256"] and digest(dyn) == files[1]["sha256"]:
            raw, surf = four_column(txt), dyn_surface(dyn)
            if len(raw) == len(surf) == 174:
                all_results.append({"state_id": "STATE-077", "test_id": "2003-03-13_020920",
                                    "stroke_id": "1 (pilot identity)", "status": "NUMERICAL_VERIFIED",
                                    "points": 174, "position_unit": "in", "load_unit": "lbf",
                                    "max_position_difference_in": float(np.max(np.abs(raw[:, 0] - surf[:, 0]))),
                                    "max_load_difference_lbf": float(np.max(np.abs(raw[:, 1] * 1000 - surf[:, 1]))),
                                    "txt_path": str(txt), "dyn_path": str(dyn),
                                    "txt_sha256": files[0]["sha256"], "dyn_sha256": files[1]["sha256"],
                                    "sample_array_fingerprint": hashlib.sha256(np.round(raw, 5).astype("<f8").tobytes()).hexdigest(),
                                    "normalized_dir": str(ROOT / "data" / "state93" / "pilot" / "STATE-077")})
    seen = {}
    for r in all_results:
        prior = seen.setdefault(r["sample_array_fingerprint"], (r["state_id"], r["test_id"], r["stroke_id"]))
        r["duplicate_of"] = "" if prior == (r["state_id"], r["test_id"], r["stroke_id"]) else "/".join(map(str, prior))
    fields = ["state_id", "test_id", "stroke_id", "status", "points", "position_unit", "load_unit",
              "max_position_difference_in", "max_load_difference_lbf", "sample_array_fingerprint",
              "duplicate_of", "txt_path", "dyn_path", "txt_sha256", "dyn_sha256", "normalized_dir"]
    write_csv(REPORT / "UNIQUE_STROKE_INVENTORY.csv", all_results, fields)
    write_csv(REPORT / "NUMERICAL_EXPORT_VALIDATION.csv", all_results + failures, fields + ["error"])
    progress["updated_utc"] = datetime.now(timezone.utc).isoformat()
    progress["verified_strokes"] = len(all_results)
    progress["verified_new_after_phase5"] = max(0, len(all_results) - 6)
    known_verified = sum(1 for r in all_results if r["state_id"] in KNOWN or r["state_id"] == "STATE-077")
    progress["known_remaining"] = 152 - known_verified
    registered_total = sum(int(job["reported_strokes"]) for tests in jobs().values() for job in tests.values()) + 32
    progress["registered_test_strokes"] = registered_total
    progress["registered_remaining"] = registered_total - len(all_results)
    progress["failed"] = failures
    atomic_json(progress_path, progress)
    print(json.dumps({k: progress[k] for k in ("verified_strokes", "verified_new_after_phase5", "known_remaining", "registered_remaining", "failed")}, indent=2))


if __name__ == "__main__":
    main()
