"""Atomically record one acquired STATE96 artifact."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECKPOINT = ROOT / "reports" / "STATE96" / "PROCESSING_CHECKPOINT.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--status", choices=("NOT_STARTED", "DISCOVERED", "EXPORTED", "VERIFIED", "FAILED", "BLOCKED", "NOT_AVAILABLE"), required=True)
    parser.add_argument("--path")
    parser.add_argument("--details")
    args = parser.parse_args()

    checkpoint = json.loads(CHECKPOINT.read_text(encoding="utf-8")) if CHECKPOINT.exists() else {"schema": "state96-acquisition/1", "states": {}}
    record: dict[str, object] = {
        "status": args.status,
        "updated_utc": datetime.now(timezone.utc).isoformat(),
    }
    if args.path:
        path = Path(args.path).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        record.update({
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    if args.details:
        record["details"] = args.details

    checkpoint["states"].setdefault(args.state, {})[args.artifact] = record
    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    temporary = CHECKPOINT.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(checkpoint, indent=2), encoding="utf-8")
    temporary.replace(CHECKPOINT)
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
