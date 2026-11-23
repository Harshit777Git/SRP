"""Inventory and safely consolidate acquired Echometer artifacts.

Original vendor files remain in place.  Newly acquired DYN/TXT/PDF files are
copied into each existing Master Dataset example under ``Collected Acquisition``.
An existing destination is accepted only when its SHA-256 matches the source.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STATE_ROOT = ROOT / "data" / "state93"
REPORT_ROOT = ROOT / "reports" / "STATE96"
MATRIX = ROOT / "reports" / "STATE93" / "93_STATE_COMPATIBILITY_MATRIX.csv"
VALIDATION = ROOT / "reports" / "STATE93" / "PHASE5_1" / "NUMERICAL_EXPORT_VALIDATION.csv"
EXPECTED_STROKES = ROOT / "reports" / "STATE96" / "TAM_EXP_EXPECTED_STROKE_QUEUE.csv"
DEFAULT_MASTER = Path(r"C:\Users\HARSHIT\OneDrive - TAS\Desktop\Master Dataset")


STEPS = [
    (1, "TAM", "Export individual well", "TAM_EXP"),
    (2, "TAM", "Edit -> Summary", "Field Summary PDF"),
    (3, "TAM", "F11 -> DYN Test History -> PDF", "Test History PDF"),
    (4, "TAM", "Select historical test -> Raw", "Raw sensor exports"),
    (5, "TAM", "Field -> Select Stroke -> Export Stroke to DYN", "DYN"),
    (6, "TAM", "Field -> Export Data to File", "Surface/Pump TXT"),
    (7, "TAM", "Repeat Steps 5-6 for all strokes", "Complete stroke collection"),
    (8, "TAM", "Details -> Calculation settings", "Damping and solver parameters"),
    (9, "TAM", "Report", "Individual test PDF"),
    (10, "TAM", "Power Torque / Power Analysis", "Mechanical and electrical data"),
    (11, "TAM", "Acoustic / Pressure / Valve Tests", "Additional measurements"),
    (12, "TAM", "Well and test comments", "Diagnostic evidence"),
    (13, "TWM", "Recall -> File Transfer", "Native files"),
    (14, "TWM", "File -> Data Export", "Available numerical results"),
    (15, "TWM", "Dynamometer analysis -> Stroke export", "TWM numerical references"),
    (16, "TWM", "File -> Batch Print", "Historical reports"),
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def files(root: Path, pattern: str = "*") -> list[Path]:
    return sorted(path for path in root.rglob(pattern) if path.is_file()) if root.exists() else []


def copy_verified(source: Path, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_hash = sha256(source)
    if destination.exists():
        if destination.is_file() and sha256(destination) == source_hash:
            return "ALREADY_PRESENT_IDENTICAL"
        raise FileExistsError(f"Refusing to overwrite non-identical file: {destination}")
    shutil.copy2(source, destination)
    if sha256(destination) != source_hash:
        raise IOError(f"Checksum verification failed after copy: {destination}")
    return "COPIED_AND_VERIFIED"


def read_matrix() -> list[dict[str, str]]:
    with MATRIX.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def validated_strokes() -> dict[str, list[dict[str, str]]]:
    result: dict[str, list[dict[str, str]]] = {}
    if not VALIDATION.exists():
        return result
    with VALIDATION.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if row.get("status") == "NUMERICAL_VERIFIED":
                result.setdefault(row["state_id"], []).append(row)
    return result


def expected_strokes() -> dict[str, int]:
    result: Counter[str] = Counter()
    if not EXPECTED_STROKES.exists():
        return {}
    with EXPECTED_STROKES.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            result[row["state_id"]] += 1
    return dict(result)


def classify_state(
    row: dict[str, str],
    verified: dict[str, list[dict[str, str]]],
    expected: dict[str, int],
) -> dict:
    state_id = row["State ID"]
    state_name = row["Original State Name"]
    state_dir = STATE_ROOT / state_id
    master_dir = Path(row["Original Directory"])
    tam_exp = files(state_dir / "01_TAM", "*.TAM_EXP")
    tam_native_members = files(state_dir / "01_TAM" / "EXTRACTED_NATIVE_MEMBERS")
    installed_tam_native = files(state_dir / "01_TAM" / "INSTALLED_TAM_NATIVE")
    twm_native = files(state_dir / "02_TWM")
    dyn = files(state_dir / "05_NUMERICAL_DATA" / "TAM", "*.dyn")
    txt = files(state_dir / "05_NUMERICAL_DATA" / "TAM", "*.txt")
    pdf = files(state_dir, "*.pdf")
    summary = [p for p in pdf if "summary" in p.name.casefold()]
    history = [p for p in pdf if "test_history" in p.name.casefold() or "test history" in p.name.casefold()]
    test_reports = [p for p in pdf if p not in summary and p not in history]
    all_state_files = files(state_dir)
    def in_export_area(path: Path, names: set[str]) -> bool:
        return bool({part.casefold() for part in path.parts} & names)
    raw = [p for p in all_state_files if in_export_area(p, {"raw_telemetry", "raw_sensor_data", "06_raw_sensor_data"})]
    settings = [p for p in all_state_files if in_export_area(p, {"calculation_settings", "05_engineering_parameters"})]
    power = [p for p in all_state_files if in_export_area(p, {"power_torque", "power_analysis", "electrical_tests"})]
    additional = [p for p in all_state_files if in_export_area(p, {"acoustic_tests", "pressure_tests", "valve_tests", "production_data"})]
    diagnostic = [p for p in files(state_dir / "08_DIAGNOSTIC_EVIDENCE") if p.suffix.casefold() not in {".json"}]
    normalized = files(state_dir / "NORMALIZED_DATA")
    twm_numerical = [p for p in twm_native if p.suffix.casefold() in {".txt", ".csv", ".dyn"}]
    twm_reports = [p for p in twm_native if p.suffix.casefold() == ".pdf"]
    verified_rows = verified.get(state_id, [])
    verified_dyn = [Path(r["dyn_path"]) for r in verified_rows if r.get("dyn_path") and Path(r["dyn_path"]).is_file()]
    verified_txt = [Path(r["txt_path"]) for r in verified_rows if r.get("txt_path") and Path(r["txt_path"]).is_file()]
    verified_pairs = len(verified_rows)
    verified_points = sum(int(r.get("points") or 0) for r in verified_rows)
    expected_stroke_count = expected.get(state_id)
    complete_strokes = expected_stroke_count is not None and verified_pairs >= expected_stroke_count

    counts = {
        1: len(tam_exp), 2: len(summary), 3: len(history), 4: len(raw),
        5: len(dyn), 6: len(txt), 7: verified_pairs if complete_strokes else 0,
        8: len(settings), 9: len(test_reports), 10: len(power), 11: len(additional),
        12: len(diagnostic), 13: len(twm_native), 14: len(twm_numerical),
        15: len([p for p in twm_numerical if p.suffix.casefold() == ".dyn"]),
        16: len(twm_reports),
    }
    statuses = {number: ("COLLECTED" if counts[number] else "MISSING") for number, *_ in STEPS}
    if expected_stroke_count is None:
        statuses[7] = "NOT_ENUMERATED"
    elif not complete_strokes:
        statuses[7] = f"PARTIAL_{verified_pairs}_OF_{expected_stroke_count}"

    if not tam_exp:
        next_action = "1 - Export individual TAM well"
    elif not summary:
        next_action = "2 - Export Field Summary PDF"
    elif not history:
        next_action = "3 - Export DYN Test History PDF and enumerate tests/strokes"
    elif not complete_strokes:
        next_action = "4-7 - Export Raw data and every DYN/TXT stroke pair"
    elif not settings:
        next_action = "8 - Capture calculation settings"
    else:
        next_action = "9-12 - Collect reports, power/torque, other tests and comments"

    return {
        "state_id": state_id,
        "state_name": state_name,
        "identity_status": "IDENTIFIED",
        "master_directory": str(master_dir),
        "standard_directory": str(state_dir),
        "tam_exp_count": len(tam_exp),
        "field_summary_count": len(summary),
        "test_history_count": len(history),
        "dyn_count": len(dyn),
        "txt_count": len(txt),
        "verified_pair_count": verified_pairs,
        "verified_point_count": verified_points,
        "expected_strokes": expected_stroke_count,
        "twm_native_count": len(twm_native),
        "next_manual_action": next_action,
        "counts": counts,
        "statuses": statuses,
        "copy_sources": {
            "01_TAM_EXP": tam_exp,
            "01_TAM_NATIVE_MEMBERS": tam_native_members,
            "01_TAM_INSTALLED_NATIVE": installed_tam_native,
            "02_FIELD_SUMMARY": summary,
            "03_TEST_HISTORY": history,
            "05_DYN": verified_dyn,
            "06_SURFACE_PUMP_TXT": verified_txt,
            "07_NORMALIZED_DATA": normalized,
            "08_CALCULATION_SETTINGS": settings,
            "09_TEST_REPORTS": test_reports,
            "10_POWER_TORQUE": power,
            "11_ADDITIONAL_MEASUREMENTS": additional,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--master", type=Path, default=DEFAULT_MASTER)
    parser.add_argument("--organize", action="store_true", help="Copy new acquired artifacts into Master Dataset")
    args = parser.parse_args()
    if not args.master.is_dir():
        raise FileNotFoundError(args.master)

    verified = validated_strokes()
    expected = expected_strokes()
    states = [classify_state(row, verified, expected) for row in read_matrix()]
    for number in range(94, 97):
        states.append({
            "state_id": f"STATE-{number:03d}", "state_name": "UNVERIFIED_STATE_IDENTITY",
            "identity_status": "UNVERIFIED_STATE_IDENTITY", "master_directory": "",
            "standard_directory": "", "tam_exp_count": 0, "field_summary_count": 0,
            "test_history_count": 0, "dyn_count": 0, "txt_count": 0,
            "verified_pair_count": 0, "verified_point_count": 0, "expected_strokes": None,
            "twm_native_count": 0, "next_manual_action": "Resolve state identity from original vendor sources",
            "counts": {number: 0 for number, *_ in STEPS},
            "statuses": {number: "IDENTITY_UNVERIFIED" for number, *_ in STEPS},
            "copy_sources": {},
        })

    copied = []
    if args.organize:
        for state in states:
            if state["identity_status"] != "IDENTIFIED":
                continue
            master_dir = Path(state["master_directory"])
            for category, sources in state["copy_sources"].items():
                for source in sources:
                    destination = master_dir / "Collected Acquisition" / category / source.name
                    if destination.exists() and destination.is_file() and sha256(destination) != sha256(source):
                        destination = destination.with_name(
                            f"{destination.stem}__sha256-{sha256(source)[:12]}{destination.suffix}"
                        )
                    status = copy_verified(source, destination)
                    copied.append({
                        "state_id": state["state_id"], "state_name": state["state_name"],
                        "category": category, "source": str(source), "destination": str(destination),
                        "bytes": source.stat().st_size, "sha256": sha256(source), "status": status,
                    })

    status_counts = Counter()
    for state in states:
        for status in state["statuses"].values():
            status_counts[status] += 1
    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "master_dataset": str(args.master),
        "states_requested": 96,
        "states_identified": 93,
        "states_unverified": 3,
        "steps": [{"number": n, "application": app, "action": action, "output": output}
                  for n, app, action, output in STEPS],
        "states": states,
        "copy_results": copied,
        "status_counts": dict(status_counts),
    }
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    output = REPORT_ROOT / "MANUAL_COLLECTION_INVENTORY.json"
    output.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(json.dumps({
        "output": str(output), "identified_states": 93, "unverified_states": 3,
        "copied": sum(item["status"] == "COPIED_AND_VERIFIED" for item in copied),
        "already_present": sum(item["status"] == "ALREADY_PRESENT_IDENTICAL" for item in copied),
        "tam_exp_states": sum(state["tam_exp_count"] > 0 for state in states),
        "dyn_states": sum(state["dyn_count"] > 0 for state in states),
        "summary_states": sum(state["field_summary_count"] > 0 for state in states),
        "history_states": sum(state["test_history_count"] > 0 for state in states),
        "verified_pairs": sum(state["verified_pair_count"] for state in states),
        "verified_points": sum(state["verified_point_count"] for state in states),
    }, indent=2))


if __name__ == "__main__":
    main()
