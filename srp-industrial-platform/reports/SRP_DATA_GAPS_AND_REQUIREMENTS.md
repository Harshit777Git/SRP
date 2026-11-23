# SRP data gaps and requirements

## Verified usable inputs

- NK monitoring: 186,251 hourly parameter observations across ten reported wells, seven SRP and three fountain. The SRP portion contains SPM, provider fillage, rod-weight extrema and a card-area scalar. The original time year was assigned by the publisher and the source owner caveat remains. There are no load-position sequences or verified fault events.
- Echometer Session 20: two complete standalone ASCII surface card point blocks (132 and 216 points). Demo aliases and filenames do not establish physical well identity, measurement origin or fault truth.
- The user ZIP: 125 inner entries, of which 115 non-executable engineering/document files were preserved. Its numbered TWM records are native binary, and the four XLS workbooks are engineering forms/calculators. No complete supported numerical card export has been verified from this ZIP.
- Simulator: 800 archived labeled synthetic runs across eight classes and 100 configurations; no field labels.

## Missing for each engineering use

| Use | Missing prerequisite |
|---|---|
| Forward SRP simulation | Complete well configuration: rod taper, rod materials, pump depth/size, unit geometry, tubing, fluid properties, pressure boundaries and verified stroke rate. A stored card or a form with blanks is insufficient. |
| Measured surface card | Ordered polished-rod load and displacement with engineering units, per-sample time or crank angle, source well, test time, calibration and cycle boundary. |
| Downhole inverse solution | Surface card plus rod string, pump depth, timebase, damping/model choice and independent reference for error assessment. |
| Valve/fillage fault differentiation | Intake pressure, valve tests, fluid level, gas handling, production response or service inspection tied to the same stroke. |
| Production/efficiency | Measured flow, fluid properties, pressure and electrical input synchronized to cards. |
| Motor diagnosis | Calibrated current/power/torque waveforms and confirmed motor fault events. |
| RUL | Installation, repair and failure dates, failure modes, operating exposure and right-censoring for surviving equipment. |

## Acquisition request

Request a documented export from TWM/TAM containing numerical surface and provider-calculated downhole samples, original units, sample order, timestamp, well configuration and test ID. Request the data-owner's permission for internal benchmarking separately from supervised training. Obtain independent valve, workover or inspection records and an adjudicated label codebook before treating any demonstration condition as ground truth. For the public 76 controller cards, request retention/plotting terms, units, equipment metadata and downhole method from both repository and data owners.
