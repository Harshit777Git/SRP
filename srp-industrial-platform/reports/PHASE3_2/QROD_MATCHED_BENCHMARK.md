# QRod example calculation — 17 November 2026

## Case opened and provenance

The user-supplied nested TWM bundle contains three QRod configuration files. `ChangePIP.qrd` was opened through QRod 3.1’s normal **File > Open** dialog and calculated in the installed application. Source path: `data/external_reference/onedrive_twm_examples/TWM Example Dyno Files/1_4_QRod_Quick_Rod_Design/ChangePIP.qrd`. File size 1,410 bytes; SHA-256 `FFFB3F4B6874FD42CD505FD0F09BCE7C76FB5480B24FC5A710ACD9B23ECA12F8`. The source archive’s license/training permission and the provenance of this demonstration case are unverified.

The loaded title was **Study Changes in Pump Intake Pressure**. Values visible in the QRod form:

| Input | Value shown |
|---|---:|
| Pump depth | 3,040 ft |
| Surface stroke length | 100.00 in |
| Pump diameter | 1.500 in |
| Tubing | 2.875 in OD, 6.40 lb/ft, 2.441 in ID |
| Tubing anchored | Yes |
| Rods | Steel; API rod number 76; grade D |
| Stroke rate | 9.50 SPM |
| Fluid specific gravity | 1.00 |
| Tubing pressure | 80.00 psi |
| Casing pressure | 0.00 psi |
| Pump intake pressure | 1.00 psi |

The UI displayed calculated rates of 226.7 and 215.3 (for 100% and 95% pump volumetric efficiency, respectively; shown in the app as rate, b/d), top steel-rod loading 78.5%, and minimum NEMA 0 motor size 20.33 hp. It rendered dynamometer-card, pump-velocity-versus-position, and torque-versus-angle plots. These are QRod calculations from a saved design, not field measurements. No raw plotted arrays were exported.

## Benchmark status

This is a reproducible **QRod reference calculation**, but it is not yet a matched simulator benchmark. No matching SRP simulator configuration was executed in this step, so no load, displacement, card-area, phase, or production error is calculated. The visible rates are application predictions, not independently measured production. The QRod menu’s Print Preview and Print Report entries were disabled in the inspected session; no printed report file was generated. The unchanged source `.qrd` remains in the extracted archive.

Use eligibility: reference-only pending source-data permission and explicit reconstruction of its exact configuration in the simulator. The result must not be counted as an independent real-field accuracy result or supervised ML training sample.

## Transferability check against the simulator contract

The visible scalar fields convert as follows, without inferring unshown configuration:

| QRod UI value | SI equivalent | Simulator field candidate |
|---|---:|---|
| Pump depth 3,040 ft | 926.592 m | Sum of `Well.rods[].length_m` (but the rod taper/schedule is not shown) |
| Surface stroke 100 in | 2.540 m | `Well.stroke_m` |
| Pump diameter 1.500 in | 0.03810 m | `Well.plunger_m` (candidate; exact pump/plunger convention needs confirmation) |
| Stroke rate 9.50 SPM | 9.50 stroke/min | `Well.spm` |
| Fluid SG 1.00 | 1,000 kg/m³ if referenced to water at 1,000 kg/m³ | `Well.fluid_kg_m3` (reference-temperature/property convention not shown) |
| Tubing pressure 80.00 psi | 551,580.6 Pa | `Well.tubing_pa` only if pressure reference and boundary definition match |
| Casing pressure 0.00 psi | 0 Pa on the displayed numeric scale | `Well.casing_pa` cannot directly accept zero because its schema minimum is 100,000 Pa; pressure basis is not established from the saved example alone |
| Pump intake pressure 1.00 psi | 6,894.8 Pa on the displayed numeric scale | No direct field; `intake_head_m` is a head input constrained to at least 5 m |

A faithful matched run is therefore not currently justified. QRod indicates anchored tubing, but `Well` has no tubing-anchor flag or tubing/rod coupling parameters. The form shows steel rod material, API rod number 76 and grade D but not a complete taper/section schedule; the simulator needs rod-segment lengths and diameters. The exact QRod surface unit and geometry were not captured in the current record, while the simulator requires crank, rocker, pitman, and pivot dimensions for its four-bar kinematics. Fluid viscosity, gas fraction, reservoir boundary and pressure-reference conventions also remain unspecified. Substituting fleet defaults would create a different well, not reproduce the QRod design.

Next matching requirements: capture QRod’s complete pumping-unit geometry and rod taper schedule through its supported design/report output; establish the pressure datum and fluid properties; map anchored-tubing behavior; then run the simulator with the same boundary conditions and compare numerical card arrays. Until then, the QRod case remains an engineering-reference calculation and cannot supply card/production error metrics.
