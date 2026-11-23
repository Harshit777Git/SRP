# TAM example export — Tagging Unanchored

On 2026-11-17, the installed Echometer TAM 2.1.19 application's **Pick a Well → Export** command saved the open `Examples / Tagging Unanchored` well as [tam_tagging_unanchored.TAM_EXP](../../data/external_reference/tam_tagging_unanchored.TAM_EXP). TAM confirmed: **1 well exported, 2 tests exported (1 dynamometer, 1 liquid level)**.

| Property | Verified value |
|---|---|
| Export size | 59,088 bytes |
| SHA-256 | `d3dbb6ea5759d854f4bba9e933b4b870a88b54f61fce6eb44c79ed5c90c7fd72` |
| Container | ZIP, 6 entries, 389,396 uncompressed bytes |
| Export metadata | `Source: Tam`, `SourceVersion: 2.1.19`, `DateExported: 2026-11-17T08_55_06Z` |
| Well ID | `{1DFA8253-FAFB-44DB-A5C2-DB80E8D95D63}` |
| Dynamometer test | `1996-04-13T02:30:00Z`; 55 numerical summary fields, 6 text fields |
| Acoustic test | `1996-04-13T02:16:44Z`; 36 numerical summary fields, 9 text fields |
| Raw proprietary entries | `Tests/DYN.1996-04-13T02_30_00Z` (69,059 bytes); `Tests/ACU.1996-04-13T02_16_44Z` (149,336 bytes) |

The `TestResults.json` entry includes calculated and recorded summaries such as peak/minimum polished rod load, stroke length, SPM, fillage estimates, pump displacement, casing/tubing pressure and distance to liquid. The application displayed the comment “Tapping Pump on Down Stroke Unanchored Tbg - Tagging Down” and a Raw chart. The comment is a demonstration description, **not** an independently verified fault label. The proprietary DYN entry has not been decoded through a supported numerical export, so the number of raw surface-card points is **unverified**. TAM's animation and downhole calculations are not independent measured ground truth.

**Use:** preserve this original export as an engineering reference. Its JSON summaries can inform a documented comparison of equipment and card-level metrics, subject to verifying each unit in the application. Do not put this example into supervised fault training. Data training permission is unverified.

**Reproduction:** In TAM, open **Pick Well**, select **Examples → Tagging Unanchored**, click **Load**, then **Pick Well → Export**. Save the `.TAM_EXP` to `data/external_reference/`. The complete binary test entries are retained in the original file.

## Additional Pick a Well examples checked

The picker lists other named example wells, including `PFL_High`, `PFL_Gaslift`, `PFL_Liner`, `Tagging Down Hard`, `Tagging Fiberglass Rods on Downstroke`, and others. Two additional wells were exported through the same supported command. The ZIP containers pass their CRC checks, but **TAM displayed “Failed to Export”** and omitted the binary test entries. Their `TestResults.json` summaries list tests; those summaries are not substitutes for the missing traces.

| Export | SHA-256 | ZIP entries | Summary test rows | Raw `Tests/` entries | TAM result |
|---|---|---:|---:|---:|---|
| `Tagging Down Hard.TAM_EXP` | `029ab63350ccb1e0f61b34897a8578bc51bd8d762b9ba17fd829af7670adfa5a` | 4 | 3 DYN, 2 ACU | 0 | Failed to Export |
| `PFL_High.TAM_EXP` | `9404f19c0289ca2f8e453526d8a0b1a1e0676155f2abc8703ed58a6fea0e2d78` | 4 | 1 ACU | 0 | Failed to Export |

These two files are retained for provenance and summary-field inspection only. They must not be counted as exported numerical cards. The name of an example well is not a confirmed diagnosis. The next supported route for additional cards is to load each example in TAM and check its dynamometer test's own Export/Report controls, then verify any saved file contains ordered load–displacement pairs with units.
