# Research and implementation gaps

Reviewed 2026-11-17: Lv et al., *Adaptive fault diagnosis of sucker rod pump systems based on optimal perceptron and simulation data*, Petroleum Science 19 (2022), 743–760, DOI 10.1016/j.petsci.2021.09.012. [University-hosted original paper](https://www.cup.edu.cn/petroleumscience/docs/2022-05/c25c5cca6dc64b24bc48d.pdf).

The paper explicitly includes viscous and Coulomb friction in its rod equation (section 2.1.1). It uses measured dynamometer cards to identify model parameters and evaluates against field observations. This supports investigating friction and calibration; it does not validate this repository or transfer the authors' metrics to our model. The article states CC BY-NC-ND 4.0; no numerical field dataset or training permission was acquired from it in this review.

## Verified repository limitation

The pre-17-November `srp-forward-1.x` implementation added traveling-valve leakage and pump wear to one conductance. The current `srp-forward-2.0-plunger-clearance` removes that coding collision: traveling-valve leakage uses its valve conductance, and pump wear uses pressure-driven annular leakage from plunger/barrel clearance. A single synthetic card sensitivity pilot found only a 0.343% healthy load-range RMSE at 80% wear and 0.535% at 100% under illustrative fit assumptions. The code paths differ; whether the field mechanisms are diagnostically separable is unproven. See `PUMP_WEAR_PHYSICS_PILOT.json`.

The experimental classifier retains a combined leakage diagnostic outcome. The new physics path is a hypothesis-backed improvement, but it does not justify separate component-level diagnosis: required pump-fit values remain illustrative, and the observed card effect is weak. Keep the combined output or return undetermined pending inspection, pressure, production or other independently validated evidence. Distinct labels must not be forced by arbitrary curve perturbations.

The inverse solver's linear viscous model does not include the simulator's nonlinear distributed friction. Adding the injected severity to the inverse solver would leak simulation truth. Any correction must instead use independently available engineering inputs or parameter estimates with uncertainty.

## Immediate validation requirements

- Preserve original class-level evaluation alongside any combined diagnosis; report unresolved component distinctions.
- Verify friction reconstruction against matched measured or provider numerical cases with equipment metadata.
- Test sensor noise and calibration error separately; the current fleet has zero configured noise.
- Collect independently confirmed component diagnoses before claiming field fault accuracy.
