# TAM installed-example inspection — 17 November 2026

## Scope and source inventory

The installed application was located at `C:\Program Files (x86)\Echometer\TAM\TAM Application.exe`. Read-only inventory of `C:\Program Files (x86)\Echometer\TAM\Documents\Echometer\TAM\Wells` found 39 immediate example/well directories, 217 files total, 39 `.{HEADER}` metadata files, and 178 other native files; aggregate file size was 32,830,980 bytes. This is an application-store file inventory, not a verified count of unique wells, tests, strokes, or cards. The native records were not decoded.

## Example viewed in TAM

The built-in `Examples > Tagging Unanchored` well was selected in the normal TAM UI. Test display: 13 April 1996 08:00 AM; comment “Tapping Pump on Down Stroke Unanchored Tbg - Tagging Down”; 4 total strokes; average 5.17 SPM; displayed test duration 59 seconds. In the Raw tab, TAM plotted load in k-lb and acceleration in g against time, marking strokes 1–4. DYN History displayed two card thumbnails for the selected date. This establishes that the installed example can be opened and visualized in TAM, but the chart pixels and thumbnails do not provide an exported numerical load-displacement sequence.

The application showed the “Pick Sensor to Begin” prompt and an unconnected cloud status. No live sensor capture was initiated.

## Export attempts and result

The earlier supported `Pick Well > Export` operation succeeded for `Examples / Tagging Unanchored` and produced `data/external_reference/tam_tagging_unanchored.TAM_EXP`. Its verified SHA-256 is `d3dbb6ea5759d854f4bba9e933b4b870a88b54f61fce6eb44c79ed5c90c7fd72`; the ZIP container has six entries and 389,396 uncompressed bytes. It includes one DYN and one acoustic native test entry plus `TestResults.json`. The DYN test summary contains 55 numerical fields and 6 text fields. The native DYN entry itself has not been decoded, so ordered raw load-position point count remains unverified and **zero numerical card arrays are extracted**. This does count as a successfully preserved application export, but not as an extracted numerical stroke dataset.

A separate `Export Well Status` operation produced a modal titled “Failed to Export” while its message reported “1 Well Exported, 1 Test Exported, 1 Liquid Level test.” Because that operation explicitly reported failure and no validated output was located, it is not counted as a second successful export. No installed-app native data was copied or modified.

## Data classification and usage

The example is vendor-bundled application demonstration material. Its measured-versus-simulated origin, license for reuse/training, independent diagnosis, equipment metadata completeness, and trace units beyond the displayed plot axes remain unverified. The scenario wording in the example name/comment is not treated as a verified fault label. Training eligibility: **false**. A TAM application export is preserved, but numeric raw card arrays extracted: **0**. Surface cards visually available in the app: **at least 2 thumbnails** in DYN History for the displayed date; these are not counted as machine-readable cards.

## Manual next step for numerical export

Use TAM’s documented/support-provided export feature for the selected test and choose a format that exports ordered per-sample load and position (or load and time plus a verified position channel). The `.TAM_EXP` export preserves the native DYN test, but the supported path used so far has only yielded summary JSON plus an opaque native test member. Request a numeric export or format/export instructions from Echometer support if the installed version has no such option; do not extract arrays by reverse engineering.

## Installed example names (inventory only)

The following 39 directory names are labels supplied by the example store; they were not independently verified diagnoses. Names are retained as displayed to guide future application-supported review:

- Anchored but NOT Set
- Anchored With Rod Stretch
- Asphaltenes in Pump
- average_well
- Bad Tail Bearing
- Deep_well
- FluidPoundUnAnchoredTubing
- Flumping
- Gas Interference
- GearboxBalance
- Gunk in Pump
- Leak Hole In Pump Barrel
- Leak Standing Valve
- Leak Tubing Hole
- Leak TV Unanchored
- Need Gas Separator
- PFL_Anomaly
- PFL_DHM_CasingWtChange
- PFL_DHM_CoalBedPerfs
- PFL_Gaseous_noisy
- PFL_Gaslift
- PFL_High
- PFL_High_liquid_low_gas
- PFL_Imp_Exp
- PFL_Liner
- PFL_Lot of Gas2
- PFL_SBHP
- PFL_Tubing_anchor
- Plunger_Normal Cycle
- RodPart_5365
- RodPart_NoPlunger
- Tagging Down Hard
- Tagging Fiberglass Rods on Downstroke
- Tagging Unanchored
- Trash Sticks SV Open
- Trash Sticks TV Open
- TV Action Erratic
- Unaccounted Wellbore Friction
- V11

