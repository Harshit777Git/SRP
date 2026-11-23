# PLOS S1 Supporting Data Audit

Source: [PLOS article](https://doi.org/10.1371/journal.pone.0326973) and [S1 Data archive](https://doi.org/10.1371/journal.pone.0326973.s001). The article states that S1 Data contains dynamometer and electrical-parameter data. Reuse is under CC BY 4.0 with attribution.

Audit command: `python scripts/audit_plos_supplement.py` (Python dependencies: openpyxl). Canonical file inventory: `data/external_reference/plos_0326973_s001/PROVENANCE.json`; complete column profile: `data/evaluation/plos_0326973_s001_profile.json`.

## Inventory

| Files | Records | Details |
|---|---:|---|
| DC1–DC4 | 4 cards / 576 pairs | 144 ordered surface displacement/load rows per card; Sheet1 contains data. |
| ED1–ED4 | 41,699 rows | Four electrical-parameter sheets with 9 columns each; no timestamp column. |
| Fault-labeled records | 0 | No verified row/card-to-fault labels or DC/ED crosswalk. |

The article describes actual electrical measurements and generated electrical values from cards, but does not identify which ED workbook belongs to which origin. Treat ED1–ED4 as `MEASURED_OR_GENERATED_UNRESOLVED`, not as verified measured or simulated subsets. The card workbooks are described as surface dynamometer measurements, but card-level well identity, fault label, units and collection times are absent. DC2–DC4 each end with one adjacent repeated point pair; these raw rows are preserved and not interpreted as errors or removed.

## Electrical columns

| Original field | Common name | Physical meaning | Units / sampling |
|---|---|---|---|
| `A相电压` | `phase_a_voltage` | Three-phase motor electrical channel A voltage. | `UNIT_UNVERIFIED`; sample interval unknown |
| `A相电流` | `phase_a_current` | Three-phase motor electrical channel A current. | `UNIT_UNVERIFIED`; sample interval unknown |
| `B相电压` | `phase_b_voltage` | Three-phase motor electrical channel B voltage. | `UNIT_UNVERIFIED`; sample interval unknown |
| `B相电流` | `phase_b_current` | Three-phase motor electrical channel B current. | `UNIT_UNVERIFIED`; sample interval unknown |
| `C相电压` | `phase_c_voltage` | Three-phase motor electrical channel C voltage. | `UNIT_UNVERIFIED`; sample interval unknown |
| `C相电流` | `phase_c_current` | Three-phase motor electrical channel C current. | `UNIT_UNVERIFIED`; sample interval unknown |
| `功率` | `power` | Motor power channel; physical scale/unit not confirmed from workbook. | `UNIT_UNVERIFIED`; sample interval unknown |
| `功率因数` | `power_factor` | Power-factor channel; precise convention not stated in workbook. | `UNIT_UNVERIFIED`; sample interval unknown |
| `备注` | `remarks_code` | Source remarks field; code meanings not documented. | `CATEGORY_UNVERIFIED`; sample interval unknown |

All nine columns contain 41,699 total values across the four workbooks with zero missing cells. Each workbook has 5,621–17,222 rows. The remark field takes values `0`, `111`, and `222`; no code definitions are supplied, so these values are not treated as labels. Per-workbook ranges, means, standard deviations, unique counts, hashes and row-level duplicate counts are in the JSON profile.

## Use and limitations

- Keep the original XLSX files unchanged; UTF-8 CSV derivatives preserve source header text, row order and cell values exactly. No timestamps, unit conversions, labels or joins were invented.
- The DC cards can be plotted as engineering references. Do not compare load/displacement errors until units, phase conventions and equipment association are verified.
- The electrical workbooks support source-format and unlabeled signal-profile analysis. They are not a validated supervised fault dataset, and their exact measured-versus-generated provenance is unresolved per file.
- Use the published model details as research context only; do not assume one workbook is a normal/fault class based on its filename, numerical signature or remarks code.
- No records from this supplement were added to `data/training/real_labeled/`.
