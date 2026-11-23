"""Rebuild a conservative, provenance-preserving Echometer state inventory."""
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

SOURCE = Path(r"C:\Users\HARSHIT\OneDrive - TAS\Desktop\Master Dataset\Examples")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "state93"
REPORT = ROOT / "reports" / "STATE93"
APPS = ("01_TAM", "02_TWM", "03_AWP2000", "04_QROD", "05_SRP_APM")


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, rows[0].keys())
        w.writeheader()
        w.writerows(rows)


def main():
    if not SOURCE.is_dir():
        raise SystemExit(f"State library missing: {SOURCE}")
    states = sorted(p for p in SOURCE.iterdir() if p.is_dir())
    if len(states) != 93:
        raise SystemExit(f"Expected 93 states; found {len(states)}")
    OUT.mkdir(parents=True, exist_ok=True)
    REPORT.mkdir(parents=True, exist_ok=True)
    matrix, inventory, gaps, validation, log = [], [], [], [], []
    hashes = defaultdict(list)
    for number, state in enumerate(states, 1):
        sid = f"STATE-{number:03d}"
        target = OUT / sid
        target.mkdir(exist_ok=True)
        for app in APPS:
            (target / app).mkdir(exist_ok=True)
        tam = sorted((state / "Original TAM").rglob("*")) if (state / "Original TAM").exists() else []
        twm = sorted((state / "Original TWM").rglob("*")) if (state / "Original TWM").exists() else []
        qrod = sorted((state / "QRod reference").rglob("*.qrd")) if (state / "QRod reference").exists() else []
        tam = [p for p in tam if p.is_file()]
        twm = [p for p in twm if p.is_file()]
        statuses = {
            "01_TAM": "VENDOR_GUI_ACTION_REQUIRED" if tam else "UNSUPPORTED_CONVERSION",
            "02_TWM": "VENDOR_GUI_ACTION_REQUIRED" if twm else "UNSUPPORTED_CONVERSION",
            "03_AWP2000": "MISSING_REQUIRED_INPUTS",
            "04_QROD": "VENDOR_GUI_ACTION_REQUIRED" if qrod else "MISSING_REQUIRED_INPUTS",
            "05_SRP_APM": "MISSING_REQUIRED_INPUTS",
        }
        files = []
        for app, paths in (("TAM", tam), ("TWM", twm), ("QROD", qrod)):
            for p in paths:
                digest = sha256(p)
                hashes[digest].append(str(p))
                row = {"State ID": sid, "Original State Name": state.name, "Application": app,
                       "Original path": str(p), "Extension": p.suffix, "Bytes": p.stat().st_size,
                       "SHA256": digest, "Open verified": "NO", "Provenance": "Supplied source archive"}
                inventory.append(row)
                files.append(row)
        metadata = {"state_id": sid, "name": state.name, "source_directory": str(state),
                    "source_files": files, "destination_status": statuses,
                    "application_open_tests": {app: "NOT_RUN" for app in APPS},
                    "measured_card_points": None, "well_identity_verified": False,
                    "synthetic_card_excluded": True}
        (target / "manifest.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        (target / "05_SRP_APM" / "metadata.json").write_text(json.dumps({
            "state_id": sid, "source_state": state.name, "surface_card": None,
            "downhole_card": None, "reason": "No verified ordered numerical samples extracted"
        }, indent=2), encoding="utf-8")
        matrix.append({"State ID": sid, "Original State Name": state.name,
                       "TAM Original": len(tam), "TAM Generated": 0, "TAM Open Verified": "NO",
                       "TWM Original": len(twm), "TWM Generated": 0, "TWM Open Verified": "NO",
                       "QRod Generated": 0, "QRod Open Verified": "NO",
                       "AWP2000 Generated": 0, "AWP2000 Open Verified": "NO",
                       "Raw Numerical Card Available": "UNVERIFIED", "Surface Dynacard Available": "UNVERIFIED",
                       "Downhole Dynacard Available": "UNVERIFIED", "Well Metadata Complete": "UNVERIFIED",
                       "Missing Engineering Parameters": "Rod string; geometry; fluid data; pressure boundaries unverified",
                       "Simulation Readiness": "NOT_ESTABLISHED", "ML Dataset Eligibility": "NO_VERIFIED_LABELS",
                       "Source Permission": "UNVERIFIED", "Conversion Errors": "Native import/open not verified",
                       "Original Directory": str(state), "Standard Directory": str(target),
                       "QRod Reference Designs": len(qrod), "AWP2000 Records": 0})
        gaps.append({"State ID": sid, "State": state.name, "QRod": statuses["04_QROD"],
                     "AWP2000": statuses["03_AWP2000"], "Required inputs":
                     "Pump depth, rods, unit geometry, SPM, pump, fluid, fluid level and pressure boundaries need verification"})
        validation.append({"State ID": sid, "State": state.name, "Surface points": "UNKNOWN",
                           "Downhole points": "UNKNOWN", "Card area": "NOT_CALCULATED",
                           "Reason": "Native records not numerically decoded through supported export"})
        log.append({"State ID": sid, "State": state.name, "TWM to TAM": "NOT_RUN",
                    "TAM to TWM": "NOT_RUN", "QRod": statuses["04_QROD"],
                    "AWP2000": statuses["03_AWP2000"], "Open test": "NOT_RUN"})
    breakdown = {"paired": sum(bool(r["TAM Original"]) and bool(r["TWM Original"]) for r in matrix),
                 "tam_only": sum(bool(r["TAM Original"]) and not r["TWM Original"] for r in matrix),
                 "twm_only": sum(bool(r["TWM Original"]) and not r["TAM Original"] for r in matrix)}
    if breakdown != {"paired": 20, "tam_only": 19, "twm_only": 54}:
        raise SystemExit(f"Unexpected source breakdown: {breakdown}")
    for filename, rows in (("93_STATE_COMPATIBILITY_MATRIX.csv", matrix),
                           ("93_STATE_NUMERICAL_INVENTORY.csv", inventory),
                           ("93_STATE_ENGINEERING_INPUT_GAPS.csv", gaps),
                           ("93_STATE_DYNACARD_VALIDATION.csv", validation),
                           ("93_STATE_CONVERSION_LOG.csv", log)):
        write_csv(REPORT / filename, rows)
    duplicates = {h: paths for h, paths in hashes.items() if len(paths) > 1}
    (REPORT / "duplicate_files.json").write_text(json.dumps(duplicates, indent=2), encoding="utf-8")
    summary = {"states": len(states), **breakdown, "source_file_entries": len(inventory),
               "duplicate_hash_groups": len(duplicates), "verified_native_open_tests": 0,
               "generated_native_projects": 0, "complete_numerical_cards_verified": 0}
    (REPORT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
