"""Reusable, conservative Echometer TXT/DYN/Summary -> APM reference importer.

The PDF is retained as source evidence. Engineering values must be supplied in a
reviewed configuration JSON; this tool does not infer a rod string from PDF text.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "apps" / "srp-apm"), str(ROOT)]
from backend.historical_reference import save  # noqa: E402
from backend.storage import Store  # noqa: E402
from shared.contracts import ASSET_PATTERN, Well  # noqa: E402


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def four_column(path):
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    if not lines or not lines[0].startswith("#Surface Card Position"):
        raise ValueError("Expected verified Echometer four-column card header")
    values = []
    for line in lines[1:]:
        if line.strip():
            fields = line.split()
            if len(fields) != 4:
                raise ValueError("Four-column TXT row has unexpected width")
            values.append([float(v) for v in fields])
    raw = np.asarray(values, dtype=float)
    if raw.ndim != 2 or raw.shape[1] != 4 or not 32 <= len(raw) <= 15000 or not np.isfinite(raw).all():
        raise ValueError("Four-column TXT has invalid point data")
    return raw


def dyn_surface(path):
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    try:
        count = int(lines[0].strip())
        raw = np.asarray([[float(v) for v in line.split(",")] for line in lines[1:count+1]])
    except (IndexError, ValueError) as exc:
        raise ValueError("Invalid counted DYN surface block") from exc
    if raw.shape != (count, 2) or not 32 <= count <= 15000 or not np.isfinite(raw).all():
        raise ValueError("DYN point count or numerical data invalid")
    return raw


def inspect_sources(txt, dyn, summary):
    from pypdf import PdfReader
    raw = four_column(txt)
    surface = dyn_surface(dyn)
    if len(raw) != len(surface):
        raise ValueError("TXT and DYN surface point counts differ")
    position_max = float(np.max(np.abs(raw[:, 0] - surface[:, 0])))
    load_max = float(np.max(np.abs(raw[:, 1] * 1000 - surface[:, 1])))
    if position_max > 1e-5 or load_max > .05:
        raise ValueError(f"TXT/DYN surface mismatch: {position_max} in, {load_max} lbf")
    pages = PdfReader(str(summary)).pages
    if not pages or not any((p.extract_text() or "").strip() for p in pages):
        raise ValueError("Summary PDF has no inspectable text; manual review required")
    return raw, {"points": len(raw), "surface_position_max_difference_in": position_max,
                 "surface_load_max_difference_lbf": load_max, "summary_pages": len(pages),
                 "source_files": [{"path": str(p.resolve()), "sha256": digest(p), "bytes": p.stat().st_size}
                                  for p in (txt, dyn, summary)]}


def package(asset, name, txt, dyn, summary, config=None):
    if not re.fullmatch(ASSET_PATTERN, asset):
        raise ValueError("Invalid asset ID")
    raw, audit = inspect_sources(txt, dyn, summary)
    result = {"asset_id": asset, "display_name": name,
              "data_mode": "HISTORICAL_VENDOR_DEMONSTRATION", "stroke_id": "1",
              "source_sha256": digest(dyn),
              "surface": {"position_in": raw[:, 0].tolist(), "load_lbf": (raw[:, 1]*1000).tolist()},
              "vendor_downhole": {"position_in": raw[:, 2].tolist(),
                                  "load_lbf": (raw[:, 3]*1000).tolist(), "status": "VENDOR_CALCULATED"},
              "source_audit": audit}
    if config:
        document = json.loads(config.read_text(encoding="utf-8"))
        well = Well.model_validate(document.get("apm_well", document) | {"asset_id": asset})
        result["solver_configuration"] = well.model_dump()
        result["estimated_period_s"] = 60 / well.spm
        result["assumptions"] = document.get("assumptions", {})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("asset-id", "display-name", "txt", "dyn", "summary", "output"):
        parser.add_argument("--" + flag, required=True)
    parser.add_argument("--configuration", help="Reviewed engineering configuration JSON")
    parser.add_argument("--database", help="Optional APM database; requires --configuration")
    args = parser.parse_args()
    if args.database and not args.configuration:
        parser.error("--database requires --configuration")
    body = package(args.asset_id, args.display_name, Path(args.txt), Path(args.dyn),
                   Path(args.summary), Path(args.configuration) if args.configuration else None)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(body, indent=2), encoding="utf-8")
    if args.database:
        record = save(Store(Path(args.database)), {k:v for k,v in body.items() if k != "source_audit"})
        print(json.dumps({"status": "IMPORTED_AND_READ_BACK", "version": record["version"],
                          "points": len(record["surface"]["position_in"]), "metrics": record["metrics"]}, indent=2))
    else:
        print(json.dumps({"status": "NUMERICAL_PACKAGE_ONLY", "points": body["source_audit"]["points"],
                          "summary_pages": body["source_audit"]["summary_pages"]}, indent=2))


if __name__ == "__main__":
    main()
