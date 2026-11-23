# Phase 5.1 continuation

The 93-state source inventory is staged under `data/state93/STATE-xxx/01_TAM` and `02_TWM`. The originals remain at the source paths recorded in `VENDOR_ORIGINAL_PROVENANCE.json`.

## Current accepted numerical evidence

- 24 unique TXT/DYN stroke pairs across 7 states, 6,282 Surface and 6,282 vendor Pump points.
- STATE-001's inspected four-stroke test is complete.
- STATE-006 BlockedIntake was imported through TAM Utilities > Express TWM Import. TAM reported 2 DYN tests, 1 valve test, and 1 liquid-level test. Fifteen of its 32 completed DYN strokes are verified; the valve test is retained as a zero-stroke history record.
- Historical tests for the other states are not fully enumerated.

## Running the local exporter

The GUI exporter has passed consecutive-stroke, safe-stop, and checkpoint-resume acceptance tests on STATE-006. It requires `pywinauto`, an unlocked interactive Windows desktop, and a correctly staged TAM well/test. It stops on an unverified stroke, dialog, or file mismatch and will not overwrite an original.

Example for the imported BlockedIntake 18-stroke test:

```powershell
& 'C:\Users\HARSHIT\AppData\Local\Python\bin\python.exe' scripts/echometer/tam_export_automation.py --state STATE-006 --well BlockedIntake --test-id 2007-08-16_192307 --reported-strokes 18 --test-display '08/16/2007 07:23:07PM' --supervised
```

After each pair, `phase5_1_validate.py` checks all four TXT columns against the DYN Surface trace, writes normalized CSV and Parquet files, and checkpoints the stroke. It skips matching completed pairs on rerun. To recheck the full registered inventory:

```powershell
& 'C:\Users\HARSHIT\AppData\Local\Python\bin\python.exe' scripts/echometer/phase5_1_validate.py
& 'C:\Users\HARSHIT\AppData\Local\Python\bin\python.exe' scripts/echometer/phase5_1_reports.py
```

For a newly observed test, supply its state ID, exact well name, stable test ID, displayed timestamp, and stroke count. The exporter registers that test in `TAM_GUI_JOBS.json`. Zero-stroke valve tests must be recorded as test history but must not be registered as completed Dynacards.

## Persistent batch runner

Run from the repository root. The normal mode prompts once per registered
historical test so the operator can stage the correct TAM well and Field view.
Use `--yes` only after visually verifying the displayed well and test.

```powershell
# Inspect without touching TAM
.\scripts\run_echometer_acquisition.ps1 --state STATE-006 --dry-run

# Resume one state
.\scripts\run_echometer_acquisition.ps1 --state STATE-006

# Resume the currently staged 18-stroke test
.\scripts\run_echometer_acquisition.ps1 --state STATE-006 --test-id 2007-08-16_192307 --yes

# Process every registered job
.\scripts\run_echometer_acquisition.ps1 --all

# Retry only FAILED strokes
.\scripts\run_echometer_acquisition.ps1 --state STATE-006 --retry-failed

# Pause and resume between artifacts
New-Item reports\STATE96\PAUSE_ACQUISITION -ItemType File
Remove-Item -LiteralPath reports\STATE96\PAUSE_ACQUISITION

# Request a safe stop before the next artifact
New-Item reports\STATE96\STOP_ACQUISITION -ItemType File

# Clear a prior stop marker
Remove-Item -LiteralPath reports\STATE96\STOP_ACQUISITION

# Follow persistent progress
Get-Content -Wait reports\STATE96\BULK_ACQUISITION.log
```

The runner uses finite timeouts and bounded retries. It does not accept license
agreements. Checksum-backed checkpoints skip verified strokes on resume.

## Remaining application work

Well and historical-test transitions remain operator-staged and explicitly confirmed. The other TAM-available and TWM-only states still need application opening, test enumeration, per-stroke export, and Summary PDFs. The installed TAM provides **Express TWM Import** for separate `.019` files; it succeeded for BlockedIntake, but no other TWM-only file has been imported. No other TAM import is claimed.
