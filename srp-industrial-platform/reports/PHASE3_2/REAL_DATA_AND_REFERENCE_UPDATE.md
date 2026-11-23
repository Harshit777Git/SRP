# Real-data and reference acquisition update

**Audit date:** 2026-11-18  
**Scope:** Verify usable reference data and assess whether new materials can support field-level simulator calibration or supervised fault training. No ML training was performed in this update.

## Findings

| Source | Actual local content | What it supports | Training status |
|---|---|---|---|
| NK Oil Well Sensor Monitoring ([dataset page](https://huggingface.co/datasets/Arailym-tleubayeva/NK-Oil-Well-Sensor-Monitoring)) | `data/external_reference/nk_well_monitoring/wells_dataset.csv`: 186,251 hourly long-format observations, 10 wells (7 sucker-rod pump, 3 fountain), 8 distinct parameters | Aggregate operating-envelope checks for SRP speed, pump-fillage, rod-load summaries and a unitless dynamometer-area field; not card reconstruction | Excluded from supervised fault training: 0 cards, 0 fault labels, no independent label verification. Source claims field measurements and Apache-2.0, with additional data-owner/confidentiality obligations. Use only as aggregate reference unless those obligations are cleared. |
| CUPBJJB/Dynamometer-card ([repository](https://github.com/CUPBJJB/Dynamometer-card)) | `data/external_reference/cupbjj_dynamometer_card/datasets/{DK3,DK6,S22}.txt`; normalized losslessly under `.../normalized/`; 3 cards, 67 ordered pairs each, 201 pairs total | Importer/plotting/reference-pipeline checks only | Excluded: origin and data-use permission unverified; no well identity or fault labels; source axis declarations (kN, m) are unverified and position spans about 5.43–5.69 source units. No unit conversion applied. Source commit: `d11e3802c9897ff9b686c46c5f908127bff62929`. |
| `mulzahrian/production_optimization` ([source audit](https://github.com/vamseeachanta/digitalmodel/issues/1873)) | Downloaded to `data/external_reference/production_optimization/`: two CSVs, 76 timestamped surface cards total from one well, LA-0024. Hashes and file-level profiles are in `data/evaluation/production_optimization_card_audit.json`. | Restricted local plotting/ingest-format reference only; 10,119 ordered surface load-position pairs, 132–134 points/card, no fault labels. **No valid downhole card pairs:** September file has blank downhole arrays; all 43 October records have `Downhole Positions` identical to `Downhole Loads`, so those cannot be treated as load/position pairs. One exact repeated surface trace fingerprint. | Public issue states no license and says all rights reserved. Kept marked `RESTRICTED`; no redistribution, publication of raw data, or training. Do not treat `Card Type` as diagnosis. File headers do not declare units; numeric fields remain `UNIT_UNVERIFIED`. The source issue reports measurement provenance; it was not independently authenticated. |
| `vamseeachanta/digitalmodel` dynacard library ([issue #1288](https://github.com/vamseeachanta/digitalmodel/issues/1288)) | Public issue describes an example library planned/built from about 245 digitized cards from a private hand-labeled archive, 3 measured cards from two wells, and about 88 synthetic variants. The issue is not itself a downloadable data archive; no files were imported. | Potential reference only if the actual files, provenance and rights are confirmed. | Do not count the source issue's described records as downloaded or usable. The digitized card-label origin is a private archive; card-level measurement provenance and data rights need verification. Synthetic cards remain synthetic. |
| TAM example `Tagging Unanchored` | Prior supported export exists at `data/external_reference/tam_tagging_unanchored.TAM_EXP`; one well, two tests (one dynamometer summary/test and one liquid-level test), with proprietary DYN payload | Engineering summary inspection and matching equipment/context where fields are supported | Raw numerical load-position points are not confirmed through an authorized numerical export. Example comment is not ground-truth diagnosis; no supervised training. See `TAM_EXAMPLE_EXPORT.md`. |
| Other TAM examples | `Tagging Down Hard.TAM_EXP`, `PFL_High.TAM_EXP` retained, but TAM reported “Failed to Export”; their packages contain summaries only and no raw `Tests/` payload | Summary-only reference, not card validation | Excluded. Names/comments are not verified diagnoses. |
| TAM application on this audit | Launch reached a vendor acceptance screen. No agreement was accepted. | No new extraction in this session | Blocked pending user interaction with the vendor acceptance screen, and then a supported export workflow. |
| User OneDrive archive | Previously extracted to `data/external_reference/onedrive_2026-11-16_2` and audited; contents are not automatically considered SRP card data. See `ONEDRIVE_ARCHIVE_AUDIT.json`. | File-specific use only after the archive audit and provenance/license review | No new training-eligible fault labels identified in this update. |
| OilGuard ([repository](https://github.com/QiZishi/OilGuard)) | Source code and class-name list; data folders are not present in the public checkout | Method/code inspection only | No numerical training records locally available. A code license does not grant rights to an absent dataset. |
| 2021 Sensors paper ([paper/data availability](https://www.mdpi.com/1424-8220/21/13/4546)) | Paper reports >50,000 cards from 38 wells and 10 operating/sensor-fault groups. Published table counts include normal 10,282; gas interference 260; fluid pound 38,298; traveling-valve leak 67; standing-valve leak 172; rod parted 29; gas lock 6; tubing-anchor malfunction 30; rotated card 895; line card 73. | High-value potential for labeled diagnosis research if numerical arrays and ground-truth definitions are provided. The dominant fluid-pound class means per-class and per-well splits are essential. | Data availability says available on request from the J.N. author. No numerical files or supplement were found in the public material examined. Request has not been sent; training-use terms and label adjudication remain unknown. |
| 2025 Sensors paper ([paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC12031298/)) | Paper reports 1,650 measured multi-source samples from 60 pumping units over 3 years, 150 per each of 11 operating conditions, including ground dynamometer and electrical power cards. | Potential paired-card and multi-sensor evaluation/training, subject to numerical format and independent labels. | Correspondence in the article: `freetzb@163.com`; data are described as available upon reasonable request. No public numerical archive was found. Request has not been sent, and reuse terms remain unknown. |
| 2023 Petroleum Science article ([paper](https://www.sciencedirect.com/science/article/pii/S1995822623002297)) | Article describes over 100,000 cards collected from an oilfield and an experimental subset of 3,500 samples for each of eight conditions (28,000 samples); each card has 200 load-displacement pairs. | Could be valuable if the numerical source, well grouping, class adjudication and permissions can be obtained. | The article material found in this search describes the study and figures but did not expose a downloadable numerical archive or data license. Direct publisher page returned HTTP 403 in this session; no download was attempted from an alternate restricted route. Do not count the reported 28,000 as locally available data. |

## `chuymtz/dynacard` numerical reference audit

The public repository was cloned at commit `b05684df1b6fb601a30bc453288a64249f252411` for direct file inspection. `Everitt/case1s.mat` contains one ordered numeric `X`/`F` vector pair with 456 finite points (X range 0.10168–54.046; F range 1,579.1–8,766.0, source units unverified). `Everitt/PUnit.mat` contains 360 finite `Xi` kinematic values (range −22.7364–22.8446). The included `Everitt.m` describes an Everitt–Jennings wave-equation reconstruction and consumes `X/F` as its surface input; the code does not establish whether the card was measured, digitized from a publication, or simulated. The repository has no `LICENSE` file; permission is therefore unverified. The card is retained as a single engineering/reference input, not a verified field card, training example, or independent downhole truth. Raw geometry profiling gives 53.94432 position range, 7,186.9 load range, and 195,500.91 raw-units-squared shoelace area. Its first/last samples differ by 0.01271 position and 739.3 load units, so phase/closure handling must be resolved before using it to judge the solver. There are no fault labels, well metadata, or downhole numerical traces. File hashes and variable profiling are recorded in `data/external_reference/chuymtz_dynacard_source/PROVENANCE.json`; it is registered in `data/dataset_registry.json` as training-ineligible.

## Additional field-dataset access lead (not downloaded)

The 2020 open-access Sensors paper [Automatic Recognition of Sucker-Rod Pumping System Working Conditions Using Dynamometer Cards with Transfer Learning and SVM](https://pmc.ncbi.nlm.nih.gov/articles/PMC7582724/) states that its study used 8,000 sensor-measured cards (1,000 in each of eight conditions) and normalized each card to 200 load/displacement points. Its article license is CC BY, but I found no downloadable numerical card archive or dataset-specific reuse statement; paper figures are not the underlying card records. The paper reports a random 80/20 split, without a well-grouped holdout in the reported method, which would need careful leakage review before relying on its performance results. The corresponding author is listed as `yhb@sia.cn`. This source is an author-access lead only and contributes zero records to local data totals; no email has been sent.

## NK telemetry profile

The profile generated from the actual CSV is at `data/evaluation/nk_field_reference_profile.json`; reproducible command:

```powershell
python scripts/audit_nk_field_reference.py
```

The CSV has columns `timestamp`, `well_id`, `parameter`, `unit`, `value`, and `well_type`. The eight actual parameters and row counts are:

| Parameter | Rows | Wells | Unit as provided | Observed quality note |
|---|---:|---:|---|---|
| SPM | 31,778 | 7 | strokes/min | Median 5.7945; max 7.39 |
| pump_fillage | 28,714 | 7 | % | Median 45.058; bounded 0–100 |
| min_rod_weight | 31,943 | 7 | kg | Summary only, not a load trace |
| max_rod_weight | 31,943 | 7 | kg | Summary only, not a load trace |
| dynamometer_area | 28,715 | 7 | unitless | 665 negative values and wide range; definition/scale requires source clarification |
| tubing_pressure | 13,895 | 3 | atm | Fountain wells only in this file |
| line_pressure | 11,076 | 3 | atm | Fountain wells only |
| casing_pressure | 8,187 | 2 | atm | Fountain wells only |

There are no duplicate `(well, parameter, timestamp)` keys in the inspected CSV. Median observed sample spacing is hourly in each series, but time gaps exist. The source README says the year was inferred from monthly files; the timestamps span 2026-01-01 to 2026-07-20. No full dynamometer arrays, production-rate series, equipment configuration, or independently verified fault labels are present. Do not interpret the row count as 186,251 independent strokes or cards.

## Existing synthetic evidence remains separate

The current physics-v2 synthetic experiment contains 1,100 paired simulated strokes/cards across 30 virtual configurations. These are controlled simulator labels, not field measurements. Its held-out virtual-configuration macro F1 is 0.644; the current candidate misses the acceptance gates and remains undeployed. The 800-run older archive is not additive proof of 800 independent new field examples. See `CURRENT_PHYSICS_V2_MODEL_REPORT.md` and `data/evaluation/current_physics_v2_split.json`.

No external records above were added to the supervised training set. In particular, no classifier-generated labels were promoted to ground truth. New field operating ranges can inform a **separate** simulator calibration experiment only after confirming the semantics and units; no calibration factors were inferred from summary statistics in this audit.

## TAM interaction blocker

TAM was launched using its installed application entry. It displayed a vendor notice with **Accept** and **Do Not Accept** controls. No control was clicked. A previous authorized export is already documented in `TAM_EXAMPLE_EXPORT.md`; the current session did not obtain additional traces. To continue, the user must review and accept or decline the vendor notice themselves. If accepted, reopen the example via **Pick Well → Examples → select well → Load**, open **Dynamometer**, choose the desired stroke, then use the application's documented **Report/Export** function. Preserve the export unchanged and confirm the saved file contains ordered numerical load-position points before adding it as a card reference. Do not treat the displayed pump animation or a well name/comment as a verified diagnosis.

## Author-access leads (not contacted)

- 2025 measured-card paper: corresponding author contact is listed in the article as `freetzb@163.com`; request the numerical traces, class definitions, well-level split identifiers, measurement units, consent to use for research/training, and redistribution restrictions.
- 2021 large-card paper: access is described as available on request from the J.N. author. Verify the current address in the paper before sending; request the same provenance/license details. No message has been sent.
- 2023 multiwell paper: no author data-access contact was confirmed from the accessible material. First request the actual numerical archive, data license and label adjudication details from the authors or publisher.

Before any author-provided file enters `data/training/real_labeled/`, verify its source, measurement origin, units, stable well/run identities, fault adjudication method, permission to train, and duplicate/near-duplicate relationships. Until then, keep it in an isolated acquisition/reference area.

## 76-card local audit

The two raw GitHub CSVs were downloaded after the first sandbox request failed DNS resolution; a subsequent elevated request completed. The pipe-delimited files parse as 33 + 43 rows, 76 cards, one well, 74 `Current` and 2 `Full` acquisition types. Their exact observed timestamp ranges are 2020-09-28 16:45:53Z through 2020-09-30 15:25:53Z and 2020-10-03 06:25:51Z through 2020-10-04 14:45:49Z. Each card contains 132, 133, or 134 aligned surface points, for 10,119 surface pairs. No duplicate timestamp exists within either file; one exact duplicate surface trace occurs in the second file. The raw CSV SHA-256 hashes, exact source URLs and file-level summaries are in `data/external_reference/production_optimization/PROVENANCE.json`; profiling and duplicate results are in `data/evaluation/production_optimization_card_audit.json`. A point-preserving normalized copy with order and original numeric values is in `data/external_reference/production_optimization/normalized/LA-0024_surface_points.csv`; card-level metadata is in `.../LA-0024_card_metadata.csv`. The normalized SHA-256 hashes are in the provenance JSON. No units were converted, and no diagnoses were assigned. The reproducible audit/export command is:

```powershell
& 'C:\Users\HARSHIT\AppData\Local\Python\bin\python.exe' scripts/audit_production_optimization_cards.py
```

The source issue says no license exists and all rights are reserved, so local files remain restricted and training-ineligible. No raw CSV data have been copied into this markdown report or any distributable artifact. The script found 43 October records with downhole arrays but in every one `Downhole Loads` equals `Downhole Positions`; it found no usable downhole pair. This reconciles the file-content audit with the maintainer's correction that the export lacks valid downhole data.

## Decision

**Real-field supervised training readiness: NO-GO.** The new public numerical examples have unverified permissions and/or origin, and none has independently verified fault labels. The NK telemetry can support aggregate SRP operating-range context, not card physics calibration or fault classification. The simulator remains useful for controlled synthetic experimentation, but neither 10/10 field fidelity nor 10/10 field ML readiness is established.
