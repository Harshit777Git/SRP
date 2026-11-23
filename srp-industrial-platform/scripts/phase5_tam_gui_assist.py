"""Supervised TAM export helper for the currently selected completed stroke.

Requires pywinauto on the user's unlocked Windows desktop. The helper checks
the actual TAM title, uses UI Automation for menus/dialogs, and stops when a
control cannot be identified. It does not select tests or accept agreements.
"""
import argparse
import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unique(candidates, label):
    items = list(candidates)
    if len(items) != 1:
        raise RuntimeError(f"Expected one {label}; found {len(items)}. Inspect TAM and retry.")
    return items[0]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--well", required=True, help="Exact well name visible in TAM title")
    p.add_argument("--test", required=True, help="Observed DYN test identifier; do not guess")
    p.add_argument("--stroke", required=True, help="Observed completed stroke number")
    p.add_argument("--outdir", type=Path, required=True)
    p.add_argument("--inspect", action="store_true", help="List controls without exporting")
    args = p.parse_args()
    try:
        from pywinauto import Desktop
    except ImportError as exc:
        raise SystemExit("Install pywinauto from PyPI in this Python environment, then rerun.") from exc
    desktop = Desktop(backend="uia")
    tam = unique((w for w in desktop.windows() if w.window_text().startswith("TAM - Examples :")), "TAM example window")
    title = tam.window_text()
    if args.well.casefold() not in title.casefold():
        raise RuntimeError(f"Selected TAM well differs: {title!r}")
    tam.restore(); tam.set_focus()
    if args.inspect:
        tam.print_control_identifiers()
        return
    outdir = args.outdir.resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    base = f"{args.well}_test-{args.test}_stroke-{args.stroke}"
    for label, menu_name, suffix in (("four_column", "Export Data to File", ".txt"),
                                      ("surface_dyn", "Export Stroke to DYN", ".dyn")):
        target = outdir / (base + suffix)
        if target.exists():
            print(f"SKIP existing {target}")
            continue
        # TAM's card is owner-drawn. The relative click is only to reveal the
        # context menu; its named menu command must then be found through UIA.
        rect = tam.rectangle()
        tam.click_input(button="right", coords=(int(rect.width()*.47),int(rect.height()*.54)))
        menu = unique((w for w in desktop.windows() if w.element_info.control_type == "Menu"), "TAM context menu")
        command = unique((c for c in menu.descendants(control_type="MenuItem")
                          if c.window_text().strip().casefold() == menu_name.casefold()), menu_name)
        command.click_input()
        dialog = unique((w for w in desktop.windows() if w.window_text() == "Save As"), "Save As dialog")
        filename_host = dialog.child_window(auto_id="FileNameControlHost")
        filename = unique(filename_host.descendants(control_type="Edit"), "filename edit")
        filename.set_edit_text(str(target))
        save = dialog.child_window(title="Save", control_type="Button")
        save.click_input()
        if not target.is_file() or target.stat().st_size == 0:
            raise RuntimeError(f"TAM did not create {target}; check the active dialog")
        print(json.dumps({"well":args.well,"test":args.test,"stroke":args.stroke,
                          "kind":label,"path":str(target),"bytes":target.stat().st_size,
                          "sha256":digest(target)}))
    print("Review the TXT/DYN numerical agreement before marking this stroke extracted.")


if __name__ == "__main__":
    main()
