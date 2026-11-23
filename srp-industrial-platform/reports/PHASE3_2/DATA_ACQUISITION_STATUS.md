# Phase 3.2 data acquisition status — 17 Nov 2026

## Simulator capture

The local fleet stack was started with `scripts/run_fleet_local.py` on simulator/APM API ports 18150/18151, UI ports 13150/13151, site API base 18160 and MQTT 18893. A single configured virtual well, `CO-DJ-001`, ran at the configured nominal speed. The APM snapshot recorded 1,255 dynamometer samples at the 25-second observation; collection continued while the capture was finalized. The SQLite export contains **3,129 simulator samples**, **7 completed strokes/cards**, **7 completed stroke jobs**, **7 solved downhole reconstructions**, and **0 failed jobs**. Queue depth was zero at the snapshot. All data are synthetic simulator outputs; there are no independent fault labels and no measured field data in this capture.

Exports are in `data/generated/apm_live_capture_2026-11-17/`: `telemetry.jsonl`, `telemetry.csv`, `cards.jsonl`, `stroke_jobs.json`, and `manifest.json`. The manifest contains run/well identity, synthetic-use restriction, record counts, and SHA-256 hashes.

## OneDrive archive

Source: `C:\Users\HARSHIT\Downloads\OneDrive_2026-11-16 (2).zip` (57,618,271 bytes; SHA-256 `be9c65a61c26cbf420f05a6761ca8a713239afe06fcf288652b4b9fc57e2b1b4`). The archive has one nested ZIP, 125 inner entries and 196,918,403 uncompressed bytes. The nested archive passed CRC checking; no unsafe paths, encrypted members, symlinks or duplicate names were found. Three same-content duplicate groups are recorded in `data/evaluation/onedrive_zip_inventory.json`.

The safe extractor retained supported allowlisted engineering/document formats under `data/external_reference/onedrive_2026-11-16_2/`; it did not execute archive content. Inner files include 4 XLS, 3 QRod `.qrd`, many Echometer `.001`/numbered records, PDFs and images. Representative binary files identify themselves as `UNVERIFIED` under the generic text inspector; no numerical sample count or engineering units are claimed for those proprietary files. Demonstration filenames may suggest scenarios but are not verified labels. No license proving ML training permission was established, so these files remain reference-only pending vendor terms and numerical-format verification.

## Training boundary and next actions

No real field data or independently confirmed fault labels were added, and no model was trained. The live synthetic capture is usable for pipeline, serialization, card-construction and simulator experiments only. Next, decode supported vendor files through the installed applications' documented Recall/export functions, preserve their source classification, and register only verified numeric exports. For real supervised fault work, collect field strokes with equipment metadata and engineer-confirmed diagnosis provenance.

## User-supplied TWM tutorial bundle (follow-up inspection)

The nested archive `OneDrive_2026-11-16.zip` was safely extracted (125 files, 196,889,629 bytes) to `data/external_reference/onedrive_twm_examples/`; each file SHA-256 was checked against the archive inventory. The original ZIP was preserved. Registry entry `onedrive-twm-example-bundle` marks permission `PERMISSION_UNVERIFIED`, measurement/reconstruction origin unknown, no verified labels, and training ineligible. The 125 files include numbered Echometer test records, three QRod `.qrd` configurations, four spreadsheets, three PDFs, one text file, and eight videos; three pairs/groups have identical contents. These file counts are not card counts.

TWM was inspected in Recall Mode through its normal UI. The screen states Recall Mode loads a previously acquired data set and a well-file snapshot; the active view showed `* NO WELL SELECTED *`. This inspection did not establish that the tutorial files had been imported into TWM’s Recall database or expose an exportable numeric trace. No numerical export is claimed. Next supported step: in TWM Recall Mode, select **F2 – Well & Data File** and choose the tutorial example’s well/data file from the installed example data location; then use **F3 – Select Test** and **F4 – Analyze Data**. If no example appears, use the application’s documented import/restore function for the vendor sample bundle, then export from the recalled dynamometer analysis. Preserve the original files and record the exact selected file and units before registering any extracted traces.

## TWM Recall Mode UI inspection

The installed TWM application opened `Examples > Gas Interference` in Recall Mode. It exposed one base well (`CO2 Flood`), an acoustic single shot, and three dated DYNA/VALVE records (05/01–02/1998; serial HLT023). The valve analysis displayed load and pressure quantities. See `reports/PHASE3_2/TWM_RECALL_INSPECTION.md` for visible values and exact qualification. TWM provides `File > Data Export...` with Dynamometer and Valve result modules. The supported Dynamometer summary export completed and produced 45 rows, but no raw load-position arrays; it contributes zero machine-readable cards. See `twm_export_20261117.csv` and its provenance sidecar.


## TAM installed-example UI inspection (follow-up)

TAM’s built-in `Examples > Tagging Unanchored` test was opened. Its Raw view plots load (k-lb) and acceleration (g) across four strokes; DYN History shows two card thumbnails. The “Export Well Status” attempt reported “Failed to Export,” so no successful numerical extraction is counted. A read-only inventory found 39 immediate example directories and 178 native non-header files (217 total files with 39 headers); those opaque records were not decoded. The scenario description is not a verified label. Training eligibility remains false. Detailed observations and export limitations: `reports/PHASE3_2/TAM_RECALL_INSPECTION.md`.

## TAM export clarification

A prior `Pick Well > Export` operation did successfully preserve `Tagging Unanchored` as `data/external_reference/tam_tagging_unanchored.TAM_EXP` (six ZIP entries, 59,088 bytes, SHA-256 `d3dbb6ea5759d854f4bba9e933b4b870a88b54f61fce6eb44c79ed5c90c7fd72`). It contains summary JSON and native DYN/acoustic members. Raw ordered load-position arrays remain unextracted; it is not counted as a machine-readable surface card. The separate `Export Well Status` operation observed during follow-up reported failure and is not counted as a successful export. See `reports/PHASE3_2/TAM_EXAMPLE_EXPORT.md` and `TAM_RECALL_INSPECTION.md`.

## QRod supported example calculation

QRod 3.1 opened and calculated the supplied `ChangePIP.qrd` case via its normal Open dialog. The input file and visible calculation outputs are recorded in `reports/PHASE3_2/QROD_MATCHED_BENCHMARK.md`. This is an application prediction only; no matching SRP simulator run or independent measurement was produced, and Print Report was unavailable in the inspected state.


## Public field-data follow-up

The article at PMC12031298 describes 1,650 measured cards across 60 pumping units and 11 conditions over three years; its data availability statement says data are available from corresponding author Bin Zhou on reasonable request (`freetzb@163.com`). The publication describes image cards; raw numerical vectors and usage permissions are not established. No request has been sent. A complete acquisition request draft is at `docs/REAL_DATA_AUTHOR_REQUEST_DRAFT.md`; eligible real labeled records remain zero.

## Additional high-priority field-dataset lead — Mossoró study

The paper at PMC8271678 reports more than 50,000 expert-classified dynamometer cards from 38 wells and makes its data available on request from corresponding author André Maitelli (`maitelli@dca.ufrn.br`). It describes normalized downhole cards; raw surface traces, per-well split identifiers, class counts and reuse rights still require confirmation. No data request has been sent and no new records are counted. A request draft is in `docs/REAL_DATA_AUTHOR_REQUEST_DRAFT.md`.
