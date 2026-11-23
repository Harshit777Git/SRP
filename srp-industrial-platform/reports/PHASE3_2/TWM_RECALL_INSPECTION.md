# TWM Recall Mode inspection — 17 November 2026

## What was opened

Using TWM's built-in `Recall Mode` → `F2 Well & Data File` → `Examples` → `Gas Interference`, the installed application successfully opened its bundled example (also represented in the extracted user archive under `TWM Example Dyno Files/1_6_Dynamometer Analysis/Gas Interference.001`). TWM identified the selected case as well `CO2 Flood`, group `Examples`, dataset description `Gas Interference`. The application's comments describe a CO2-flood well with a high fluid level and pump gas interference; they state pump fillage 40% and mention comparison with tested oil/water rates. Those are tutorial annotations, not independently adjudicated labels.

The recalled record exposed an acoustic `SINGLESHOT` on 05/01/1998 23:53:17 (`High Fluid Level`) and three dynamometer/valve records:

| Date/time shown by TWM | Test type | Serial | Description |
|---|---|---|---|
| 05/01/1998 23:59:00 | DYNA | HLT023 | Gas Interference |
| 05/02/1998 00:02:00 | VALVE | HLT023 | Traveling Valve |
| 05/02/1998 00:11:00 | VALVE | HLT023 | Standing Valve |

TWM's valve-analysis view showed a time-series chart titled `Traveling And Standing Valve Loads (K-Lbs) vs Time (sec)` and these displayed analysis values: traveling-valve calculated buoyant rod weight plus maximum fluid load 17,987 lbf, measured load 15,154 lbf, leakage 0.0 BBL/D; standing-valve calculated buoyant rod weight 10,699 lbf, measured load 10,439 lbf, intake pressure 647.1 psi(g); calculated fluid load 7,287 lbf. The UI labels several values as calculated and the two `Measured Load` fields as measured. No units, provenance beyond the demonstration application, or independent label confirmation were recovered.

## Supported UI export result

From the analysis view, TWM `File` offered `Data Export...` and `Batch File Export...`. I completed `Data Export...` through its supported wizard: `All Valid Dates` → group `Examples` → all listed example data sets → `Dynamometer` module. Selected summary fields were Pump Displacement, PPRL, MPRL, SPM, Effective Plunger Stroke and Pump Volumetric Fillage; delimiter comma. Output is `data/external_reference/twm_export_20261117.csv`, SHA-256 `9d8a6da7ba2bdab9be58adbcf4018f4ac7955a943f5bf10c4336d8fc1154365f`; sidecar provenance is `data/external_reference/twm_export_20261117.provenance.json`.

The file contains **45 summary rows**, eight named fields plus an empty trailing column. It is a calculated summary export, **not** 45 complete raw cards: no load-position arrays or sample ordering were exported. Ten rows have `X`/missing values in each of five signals; 24 rows have `X`/missing fillage. Reported SPM values span 4,444–30,202 although the header says `spm`; PPRL values span 2.2–878.1, and Effective Plunger Stroke 3–245.4. These range/scale concerns remain unresolved. Values are preserved unchanged, not normalized. Do not use them for supervised training or claim card reconstruction validation.

During compilation, at least three records triggered the TWM warning that calculated acceleration-derived stroke length differs materially from the well-file stroke length (examples shown: 42 vs 47 in, 288 vs 328 in, and 42 vs 48 in). The preselected `Well File Stroke Length` was retained for those prompts; this records the application default choice, not an independent engineering determination. This is an additional reason to keep the output reference-only until source configurations and units are reconciled.
## Provenance and eligibility

The supplied nested TWM archive is preserved and separately extracted at `data/external_reference/onedrive_twm_examples/`. Archive-level file hashes are recorded in that directory's `provenance.json`; dataset registry entry is `onedrive-twm-example-bundle`. Permission is `PERMISSION_UNVERIFIED`; origin is `DEMONSTRATION_UNKNOWN_ORIGIN`; supervised training eligibility is false. Keep the traces reference-only unless provider/data-owner terms and provenance are clarified. The generated simulator capture and simulator fault runs remain synthetic and cannot be counted as field validation.


