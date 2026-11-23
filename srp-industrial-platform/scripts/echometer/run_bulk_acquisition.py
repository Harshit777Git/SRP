"""Persistent, resumable controller for registered TAM stroke acquisition jobs.

Run this from the interactive Windows desktop session with TAM already open.
The registered well is confirmed once; historical tests and strokes are then
selected and verified automatically with persistent checkpoints.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PHASE51 = ROOT / "reports" / "STATE93" / "PHASE5_1"
STATE96 = ROOT / "reports" / "STATE96"
JOBS = PHASE51 / "TAM_GUI_JOBS.json"
PROGRESS = PHASE51 / "EXTRACTION_PROGRESS.json"
EXPORTER = Path(__file__).with_name("tam_export_automation.py")
STOP = STATE96 / "STOP_ACQUISITION"
PAUSE = STATE96 / "PAUSE_ACQUISITION"
LOG = STATE96 / "BULK_ACQUISITION.log"


def load(path: Path, default: dict) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def log(message: str) -> None:
    STATE96.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.now(timezone.utc).isoformat()} {message}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as stream:
        stream.write(line + "\n")


def pending(state: str, test: str, total: int, failed_only: bool) -> list[int]:
    progress = load(PROGRESS, {"states": {}})
    strokes = progress.get("states", {}).get(state, {}).get("tests", {}).get(test, {}).get("strokes", {})
    result = []
    for stroke in range(1, total + 1):
        status = strokes.get(str(stroke), {}).get("status", "NOT_STARTED")
        if failed_only:
            if status == "FAILED":
                result.append(stroke)
        elif status != "NUMERICAL_VERIFIED":
            result.append(stroke)
    return result


def selected_jobs(args: argparse.Namespace) -> list[tuple[str, str, dict]]:
    registered = load(JOBS, {"states": {}}).get("states", {})
    chosen = []
    for state, tests in sorted(registered.items()):
        if args.state and state != args.state:
            continue
        for test, job in sorted(tests.items()):
            if args.test_id and test != args.test_id:
                continue
            chosen.append((state, test, job))
    if not chosen:
        raise SystemExit("No registered acquisition job matches the requested scope")
    return chosen


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--state", help="Process one registered state")
    scope.add_argument("--all", action="store_true", help="Process all registered states/tests")
    parser.add_argument("--test-id", help="Limit a state to one historical test")
    parser.add_argument("--dry-run", action="store_true", help="Show pending strokes without touching TAM")
    parser.add_argument("--retry-failed", action="store_true", help="Select only FAILED strokes")
    parser.add_argument("--max-strokes", type=int, default=0, help="Limit new strokes per test run")
    parser.add_argument("--yes", action="store_true",
                        help="Confirm the currently open registered well without prompting")
    parser.add_argument("--timeout", type=float, default=15)
    parser.add_argument("--retries", type=int, default=1)
    args = parser.parse_args()

    jobs = selected_jobs(args)
    failures = 0
    for index, (state, test, job) in enumerate(jobs, start=1):
        total = int(job["reported_strokes"])
        all_remaining = pending(state, test, total, False)
        failed_candidates = pending(state, test, total, True)
        remaining = failed_candidates if args.retry_failed else all_remaining
        log(f"JOB {index}/{len(jobs)} state={state} test={test} "
            f"verified={total-len(all_remaining)} remaining={len(all_remaining)} "
            f"selected={len(remaining)} failed={len(failed_candidates)}")
        if args.dry_run or not remaining:
            continue
        if STOP.exists():
            log(f"SAFE_STOP file={STOP}")
            return
        well = job.get("well")
        display = job.get("test_display")
        if not well or not display:
            log(f"BLOCKED state={state} test={test} reason=missing well/test_display registration")
            continue
        if not args.yes:
            answer = input(f"Confirm TAM is open on well {well!r}, then type the well name: ").strip()
            if answer != well:
                log(f"SAFE_STOP state={state} test={test} reason=operator confirmation mismatch")
                return
        command = [
            sys.executable, str(EXPORTER), "--state", state, "--well", well,
            "--test-id", test, "--reported-strokes", str(total),
            "--test-display", display, "--operator-confirmed", "--auto-navigate-test",
            "--timeout", str(args.timeout), "--retries", str(args.retries),
            "--stop-file", str(STOP), "--pause-file", str(PAUSE),
        ]
        history_row = job.get("history_row")
        history_total_rows = job.get("history_total_rows")
        tab_click_sequence = job.get("tab_click_sequence")
        if not history_row or not history_total_rows or not tab_click_sequence:
            log(f"BLOCKED state={state} test={test} reason=missing registered history/tab metadata")
            failures += 1
            continue
        if isinstance(tab_click_sequence, list):
            tab_click_sequence = ",".join(str(value) for value in tab_click_sequence)
        command.extend(("--history-row", str(history_row),
                        "--history-total-rows", str(history_total_rows),
                        "--tab-click-sequence", str(tab_click_sequence)))
        if args.max_strokes:
            command.extend(("--max-strokes", str(args.max_strokes)))
        if args.retry_failed:
            command.extend(("--only-strokes", ",".join(map(str, remaining))))
        log(f"START state={state} test={test} pending={remaining}")
        result = subprocess.run(command, cwd=ROOT)
        if result.returncode:
            log(f"FAILED state={state} test={test} exit={result.returncode}")
            failures += 1
            continue
        after = pending(state, test, total, False)
        log(f"FINISH state={state} test={test} verified={total-len(after)} remaining={len(after)}")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
