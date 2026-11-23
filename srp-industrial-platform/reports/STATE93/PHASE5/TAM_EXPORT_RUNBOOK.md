# Phase 5 TAM numerical export runbook

The five-state pilot used TAM's Pick Well, historical DYN Field graph, graph
context menu, and Edit > Summary > PDF. These actions were observed in the
installed TAM release. The current exports and validation are in the state
folders; `PROCESSING_CHECKPOINT.json` records progress.

## Next stroke

1. In TAM, open the intended example and historical DYN test. Record the
   visible test time, comments, total strokes, and selected completed stroke.
2. Select the Field tab and the intended stroke. Confirm the TAM title and
   stroke counter before export.
3. Run `python scripts/phase5_tam_gui_assist.py --well "Exact well name" --test
   "observed-test-id" --stroke "observed-number" --outdir
   "data/state93/STATE-XXX/05_NUMERICAL_DATA/TAM/test_observed-id"` from the
   repository. Install `pywinauto` from PyPI first if this Python environment
   does not have it. Start with `--inspect` to review controls. The helper is
   **not yet acceptance tested**; if a named control is unavailable, use the
   supported TAM menu manually and record that exception.
4. Export the Summary PDF from Edit > Summary > PDF. Preserve the original PDF
   in `06_ENGINEERING_CONFIGURATION/TAM`. Do not substitute another test's
   equipment version.
5. Validate TXT/DYN paired surface arrays with
   `scripts/import_vendor_reference.py` and run
   `scripts/phase5_process_library.py` to update CSV, Parquet, checksums,
   matrices, and per-state checkpoint. A reviewed engineering configuration is
   required before APM reconstruction.

Use distinct stroke-specific filenames. TAM's default export name contains a
test time but may omit the stroke number, so never overwrite a prior export.
The five-state pilot observed 120 strokes in its selected tests but exported
one from each. STATE-077's selected test reported 32 strokes and has one
benchmark stroke. The other 146 reported strokes remain to be exported.

The 54 TWM-only states require a separately verified TAM import workflow.
Do not treat native TWM files as numerical Dynacards.
