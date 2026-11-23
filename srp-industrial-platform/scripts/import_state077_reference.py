"""Idempotently load STATE-077 into the APM historical-reference database."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "apps" / "srp-apm"), str(ROOT)]
from backend.storage import Store  # noqa: E402
from backend.historical_reference import save, get  # noqa: E402
from import_vendor_reference import package  # noqa: E402

PILOT = ROOT / "data" / "STATE93" / "pilot" / "Tagging Down Hard"
REPORT = ROOT / "reports" / "STATE93"


def main():
    originals = PILOT / "original" / "user_exports"
    prepared = package("STATE-077", "Tagging Down Hard",
                       next(originals.glob("*.txt")), next(originals.glob("*.dyn")),
                       next(originals.glob("*.pdf")),
                       PILOT / "normalized" / "engineering_config.json")
    body = {k: v for k, v in prepared.items() if k != "source_audit"}
    dbpath = ROOT / "state" / "state93" / "apm.db"
    store = Store(dbpath)
    before = store.execute("SELECT count(*) FROM historical_references").fetchone()[0]
    first = save(store, body)
    second = save(store, body)
    after = store.execute("SELECT count(*) FROM historical_references").fetchone()[0]
    retrieved = get(store, "STATE-077", "1", first["version"])
    if first != second or first != retrieved or after-before not in (0, 1):
        raise ValueError("Idempotency or database readback failed")
    if (len(retrieved["surface"]["position_in"]) != 174 or
            len(retrieved["vendor_downhole"]["position_in"]) != 174 or
            len(retrieved["apm_downhole"]["position_in"]) != 174):
        raise ValueError("Persisted point count mismatch")
    REPORT.mkdir(parents=True, exist_ok=True)
    result = {"database": str(dbpath), "asset_id": "STATE-077", "stroke_id": "1",
              "version": first["version"], "rows_before": before, "rows_after": after,
              "second_import_created_duplicate": False, "readback_passed": True,
              "surface_points": 174, "vendor_pump_points": 174, "apm_pump_points": 174,
              "source_audit": prepared["source_audit"],
              "metrics": first["metrics"]}
    (REPORT / "STATE077_IMPORT_VALIDATION.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (PILOT / "apm" / "historical_reference_payload.json").write_text(json.dumps(body, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
