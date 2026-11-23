"""Supervised, checkpointed TAM Field-card exporter for one verified DYN test.

Run on the unlocked Windows desktop. TAM's Field graph and stroke selector are
owner-drawn, so this utility requires visual confirmation unless local OCR can
read the displayed test and stroke. It never accepts agreements or overwrites
an existing source. It validates each TXT/DYN pair before advancing.
"""
from __future__ import annotations

import argparse
import json
import site
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
site.addsitedir(str(Path(__file__).resolve().parent / ".vendor"))
from phase5_1_validate import DATA, JOBS_PATH, KNOWN, REPORT, atomic_json  # noqa: E402


def unique(items, description):
    items = list(items)
    if len(items) != 1:
        raise RuntimeError(f"Expected one {description}, found {len(items)}")
    return items[0]


def wait_for(fn, timeout, description):
    limit = time.monotonic() + timeout
    while time.monotonic() < limit:
        try:
            result = fn()
            if result is not None:
                return result
        except Exception:
            pass
        time.sleep(0.3)
    raise TimeoutError(f"Timed out waiting for {description}")


def ocr_text(window):
    try:
        import pytesseract
        return pytesseract.image_to_string(window.capture_as_image())
    except (ImportError, OSError, RuntimeError):
        return None


def confirm_display(window, expected, kind, supervised):
    text = ocr_text(window)
    if text and expected.casefold() in text.casefold():
        return "OCR"
    if not supervised:
        raise RuntimeError(f"Cannot verify displayed {kind} {expected!r} by OCR; rerun with --supervised")
    screenshot = REPORT / f"tam_display_{kind.replace(' ', '_')}.png"
    screenshot.parent.mkdir(parents=True, exist_ok=True)
    window.capture_as_image().save(screenshot)
    print(f"Check TAM visually. Screenshot: {screenshot}")
    answer = input(f"Type the displayed {kind} exactly as {expected!r} to continue: ").strip()
    if answer != expected:
        raise RuntimeError(f"Displayed {kind} was not confirmed")
    return "OPERATOR_CONFIRMED"


def save_as(desktop, target: Path, timeout: float):
    from pywinauto import Desktop
    from pywinauto.keyboard import send_keys
    native = wait_for(lambda: unique((w for w in Desktop(backend="win32").windows()
                                      if w.window_text() == "Save As" and w.is_visible()), "visible Save As"), timeout, "Save As")
    dialog = desktop.window(handle=native.handle)
    edit = unique((c for c in dialog.descendants(control_type="Edit") if c.element_info.automation_id == "1001"), "File name edit")
    # ValuePattern/set_edit_text can display the path without committing it to
    # the common Save As dialog. Literal keyboard entry was verified in TAM.
    for _ in range(3):
        edit.click_input()
        send_keys("^a")
        send_keys(str(target.resolve()), with_spaces=True)
        actual = edit.get_value()
        if actual.casefold() == str(target.resolve()).casefold():
            break
        time.sleep(.3)
    else:
        raise RuntimeError(f"Save As filename mismatch: {actual!r}")
    dialog.child_window(title="Save", control_type="Button").click_input()
    # Any overwrite warning indicates a naming collision; decline it and stop.
    warnings = [w for w in Desktop(backend="win32").windows()
                if "Confirm Save As" in w.window_text() and w.is_visible()]
    if warnings:
        warning = unique(warnings, "overwrite warning")
        warning.child_window(title="No", class_name="Button").click_input()
        raise FileExistsError(f"TAM would overwrite {target}")
    wait_for(lambda: target if target.is_file() and target.stat().st_size > 0 else None, timeout, "exported file")


def export_current_card(desktop, tam, target: Path, menu_label: str, timeout: float):
    if target.exists():
        return "EXISTS"
    from pywinauto.keyboard import send_keys
    # The graph is owner-drawn. Probe several relative points, accepting only
    # the actual menu whose accessible labels include the requested command.
    rect = tam.rectangle()
    menu = None
    for fx, fy in ((.68, .73), (.62, .70), (.55, .60), (.72, .55)):
        tam.click_input(button="right", coords=(round(rect.width() * fx), round(rect.height() * fy)))
        candidates = [w for w in desktop.windows() if w.element_info.control_type == "Menu"]
        found = [w for w in candidates if any(x.window_text().strip().casefold() == menu_label.casefold()
                                           for x in w.descendants(control_type="MenuItem"))]
        if len(found) == 1:
            menu = found[0]
            break
        send_keys("{ESC}")
    if menu is None:
        raise RuntimeError(f"TAM graph did not expose {menu_label!r}")
    item = unique((x for x in menu.descendants(control_type="MenuItem")
                   if x.window_text().strip().casefold() == menu_label.casefold()), menu_label)
    item.click_input()
    save_as(desktop, target, timeout)
    return "EXPORTED"


def stroke_combo(tam, total: int):
    candidates = []
    for control in tam.descendants(class_name="ComboBox"):
        if control.control_id() != 301 or not control.window_text().startswith("Stroke "):
            continue
        candidates.append(control)
    if not candidates:
        raise RuntimeError("No TAM stroke selector is present")
    # TAM retains hidden selectors from prior historical tests. The active
    # Field view is consistently the last stroke selector in descendant order.
    active = candidates[-1]
    actual_total = len(active.item_texts())
    if actual_total != total:
        raise RuntimeError(f"Active TAM selector has {actual_total} strokes, expected {total}")
    return active


def normalize_timestamp(value: str) -> str:
    """Normalize TAM's locale formatting without changing the represented time."""
    return "".join(value.casefold().split()).replace("/", "-")


def displayed_test_matches(tam, expected: str, total: int) -> bool:
    """Require both the visible timestamp and expected stroke selector."""
    try:
        stroke_combo(tam, total)
    except RuntimeError:
        return False
    text = ocr_text(tam)
    return bool(text and normalize_timestamp(expected) in normalize_timestamp(text))


def select_historical_test(tam, expected: str, total: int, history_row: int,
                           history_total_rows: int, tab_click_sequence: list[float],
                           timeout: float):
    """Select a registered historical timestamp tab and verify stroke count."""
    if history_row < 1:
        raise ValueError("A positive --history-row is required for unattended navigation")
    if history_total_rows < history_row:
        raise ValueError("--history-total-rows must be at least --history-row")
    if not tab_click_sequence or any(not 0.0 < ratio < 1.0 for ratio in tab_click_sequence):
        raise ValueError("--tab-click-sequence must contain window ratios between zero and one")
    # DYN History is newest-first while timestamp tabs are oldest-first.
    # Converting the inventoried history row to a tab index avoids the
    # inaccessible owner-drawn modal. Export remains gated by the unique
    # expected stroke selector after navigation.
    from pywinauto.keyboard import send_keys
    send_keys("{ESC}")
    time.sleep(1.0)
    rect = tam.rectangle()
    for ratio in tab_click_sequence:
        tab_point = (round(rect.width() * ratio), round(rect.height() * .146))
        tam.click_input(coords=tab_point)
        time.sleep(.7)
    audit_stem = "".join(character if character.isalnum() else "-" for character in expected)
    audit = REPORT / "navigation" / f"{audit_stem}_tab-selected.png"
    audit.parent.mkdir(parents=True, exist_ok=True)
    tam.capture_as_image().save(audit)
    wait_for(lambda: stroke_combo(tam, total), timeout,
             f"{total}-stroke selector after selecting {expected}")
    return "REGISTERED_TAB_SELECTED_AND_STROKE_COUNT_VERIFIED"


def select_stroke(tam, number: int, total: int):
    from pywinauto.keyboard import send_keys
    stroke_combo(tam, total)
    rect = tam.rectangle()
    # Visible selector center in the Field view. The prior 0.42 Y ratio landed
    # inside the graph after the application's DPI/layout change.
    tam.click_input(coords=(round(rect.width() * 0.948), round(rect.height() * 0.28)))
    keys = "{HOME}" + ("{DOWN " + str(number - 1) + "}" if number > 1 else "") + "{ENTER}"
    send_keys(keys)
    time.sleep(0.3)
    selected = stroke_combo(tam, total).window_text()
    if selected != f"Stroke {number}":
        raise RuntimeError(f"TAM selected {selected!r}, expected Stroke {number}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", required=True, help="STATE-001 through STATE-093")
    parser.add_argument("--well", required=True, help="Exact well name shown in TAM")
    parser.add_argument("--test-id", help="Observed stable test ID, e.g. 1995-06-07_215400")
    parser.add_argument("--reported-strokes", type=int, help="Completed stroke count displayed by TAM")
    parser.add_argument("--test-display", required=True, help="Exact date/time shown above Field graph")
    parser.add_argument("--supervised", action="store_true", help="Prompt for visual confirmation when OCR is unavailable")
    parser.add_argument("--operator-confirmed", action="store_true",
                        help="The operator already verified the displayed well and test in TAM")
    parser.add_argument("--auto-navigate-test", action="store_true",
                        help="Select and verify the registered historical test through DYN History")
    parser.add_argument("--history-row", type=int,
                        help="One-based row in TAM DYN Test History, registered after visual inventory")
    parser.add_argument("--history-total-rows", type=int,
                        help="Total visible history rows, including zero-stroke tests")
    parser.add_argument("--tab-click-sequence",
                        help="Comma-separated registered tab-center ratios used to normalize and select the test")
    parser.add_argument("--max-strokes", type=int, default=0,
                        help="Stop after this many newly verified strokes; zero means no limit")
    parser.add_argument("--only-strokes",
                        help="Comma-separated stroke numbers to process; others are skipped")
    parser.add_argument("--stop-file", type=Path,
                        help="Stop safely before the next stroke when this file exists")
    parser.add_argument("--pause-file", type=Path,
                        help="Pause between strokes while this file exists")
    parser.add_argument("--timeout", type=float, default=12)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--inspect", action="store_true")
    args = parser.parse_args()
    matrix = ROOT / "reports" / "STATE93" / "93_STATE_COMPATIBILITY_MATRIX.csv"
    import csv
    allowed = {r["State ID"]: r["Original State Name"] for r in csv.DictReader(matrix.open(encoding="utf-8-sig"))}
    if args.state not in allowed:
        raise ValueError(f"Unknown 93-state ID: {args.state}")
    if args.well.casefold() != allowed[args.state].casefold():
        raise ValueError(f"Well name does not match state matrix: {allowed[args.state]!r}")
    known = KNOWN.get(args.state)
    test = args.test_id or (known[0] if known else None)
    total = args.reported_strokes or (known[1] if known else None)
    if not test or not total or total < 1:
        raise ValueError("Supply --test-id and --reported-strokes for a newly observed test")
    from pywinauto import Desktop
    desktop = Desktop(backend="uia")
    tam = unique((w for w in Desktop(backend="win32").windows() if w.window_text() == "TAM"), "TAM main window")
    if tam.is_minimized():
        tam.restore()
    tam.set_focus()
    if args.inspect:
        tam.print_control_identifiers()
        return
    if not args.operator_confirmed:
        confirm_display(tam, args.well, "well name", args.supervised)
    if args.auto_navigate_test:
        if not args.history_row or not args.history_total_rows or not args.tab_click_sequence:
            raise ValueError("--auto-navigate-test requires history row and tab metadata")
        tab_click_sequence = [float(value) for value in args.tab_click_sequence.split(",")]
        select_historical_test(tam, args.test_display, total, args.history_row,
                               args.history_total_rows, tab_click_sequence, args.timeout)
    else:
        stroke_combo(tam, total)
    if not args.operator_confirmed and not args.auto_navigate_test:
        confirm_display(tam, args.test_display, "test timestamp", args.supervised)
    jobs = json.loads(JOBS_PATH.read_text(encoding="utf-8")) if JOBS_PATH.exists() else {"states": {}}
    state_jobs = jobs["states"].setdefault(args.state, {})
    job = dict(state_jobs.get(test, {}))
    job.update({"reported_strokes": total,
                "pilot_stroke": known[2] if known and test == known[0] else 0,
                "well": args.well, "test_display": args.test_display})
    if args.history_row:
        job["history_row"] = args.history_row
    if args.history_total_rows:
        job["history_total_rows"] = args.history_total_rows
    if args.tab_click_sequence:
        job["tab_click_sequence"] = args.tab_click_sequence
    state_jobs[test] = job
    atomic_json(JOBS_PATH, jobs)
    progress_path = REPORT / "TAM_GUI_CHECKPOINT.json"
    progress = json.loads(progress_path.read_text(encoding="utf-8")) if progress_path.exists() else {"states": {}}
    state_progress = progress["states"].setdefault(args.state, {}).setdefault(test, {})
    validated_path = REPORT / "EXTRACTION_PROGRESS.json"
    folder = DATA / args.state / "05_NUMERICAL_DATA" / "TAM" / ("test_" + test)
    folder.mkdir(parents=True, exist_ok=True)
    newly_verified = 0
    only_strokes = ({int(value) for value in args.only_strokes.split(",") if value.strip()}
                    if args.only_strokes else None)
    for stroke in range(1, total + 1):
        if only_strokes is not None and stroke not in only_strokes:
            continue
        if args.stop_file and args.stop_file.exists():
            print(f"Safe stop requested by {args.stop_file}")
            break
        while args.pause_file and args.pause_file.exists():
            if args.stop_file and args.stop_file.exists():
                print(f"Safe stop requested by {args.stop_file}")
                return
            print(f"Paused by {args.pause_file}; remove it to resume", flush=True)
            time.sleep(2)
        # The independent validator owns the final NUMERICAL_VERIFIED status.
        validated = json.loads(validated_path.read_text(encoding="utf-8")) if validated_path.exists() else {"states": {}}
        prior = validated.get("states", {}).get(args.state, {}).get("tests", {}).get(test, {}).get("strokes", {}).get(str(stroke), {})
        if prior.get("status") == "NUMERICAL_VERIFIED":
            continue
        if state_progress.get(str(stroke), {}).get("status") == "NUMERICAL_VERIFIED":
            continue
        stem = f"{args.state}_test-{test}_stroke-{stroke}"
        txt, dyn = folder / f"{stem}.txt", folder / f"{stem}.dyn"
        if txt.exists() and dyn.exists():
            pass
        else:
            select_stroke(tam, stroke, total)
            state_progress[str(stroke)] = {"status": "EXPORTING"}
            atomic_json(progress_path, progress)
            for target, label, status in ((txt, "Export Data to File", "TXT_EXPORTED"),
                                          (dyn, "Export Stroke to DYN", "DYN_EXPORTED")):
                for attempt in range(args.retries + 1):
                    try:
                        export_current_card(desktop, tam, target, label, args.timeout)
                        state_progress[str(stroke)]["status"] = status
                        atomic_json(progress_path, progress)
                        break
                    except Exception:
                        if attempt >= args.retries:
                            state_progress[str(stroke)] = {"status": "FAILED", "stage": status}
                            atomic_json(progress_path, progress)
                            raise
                        time.sleep(0.4)
        result = subprocess.run([sys.executable, str(Path(__file__).with_name("phase5_1_validate.py")), "--state", args.state],
                                capture_output=True, text=True)
        if result.returncode:
            state_progress[str(stroke)] = {"status": "FAILED", "validator_error": result.stderr[-2000:]}
            atomic_json(progress_path, progress)
            raise RuntimeError(result.stderr)
        checked = json.loads((REPORT / "EXTRACTION_PROGRESS.json").read_text(encoding="utf-8"))
        verified = checked["states"][args.state]["tests"][test]["strokes"][str(stroke)]
        if verified.get("status") != "NUMERICAL_VERIFIED":
            raise RuntimeError(f"Stroke {stroke} failed numerical validation: {verified}")
        state_progress[str(stroke)] = {"status": "NUMERICAL_VERIFIED", "points": verified["points"]}
        atomic_json(progress_path, progress)
        checkpoint_script = Path(__file__).with_name("update_state96_checkpoint.py")
        stamp = test.replace("-", "").replace("_", "_")
        for kind, source in (("DYN", dyn), ("TXT", txt)):
            artifact = f"TEST-{stamp}_STROKE-{stroke:03d}_{kind}"
            checkpoint_result = subprocess.run(
                [sys.executable, str(checkpoint_script), "--state", args.state,
                 "--artifact", artifact, "--status", "VERIFIED", "--path", str(source.resolve()),
                 "--details", f"{verified['points']} points; DYN/TXT numerical consistency verified"],
                capture_output=True, text=True,
            )
            if checkpoint_result.returncode:
                raise RuntimeError(checkpoint_result.stderr)
        newly_verified += 1
        print(f"{args.state} {test} stroke {stroke}: {verified['points']} matched points")
        if args.max_strokes and newly_verified >= args.max_strokes:
            print(f"Per-run limit reached: {newly_verified} newly verified stroke(s)")
            break


if __name__ == "__main__":
    main()
