# Model and synthetic evidence audit

This report is derived from the current generated files and evaluation artifacts. It does not claim field performance.

## 3,129-per-fault capture

- Audited 4 capture revisions. Revision 1 contains 34,419 telemetry rows and 57 complete paired cards.
- Revision 1 uses three runs per fault and covers only 10%, 20% and 40% fault severity.
- Revision 2 contains 34,419 rows, 66 runs, 47 complete paired cards, and six fault severity settings.
- Revision 3 contains 34,851 rows, 66 runs, 66 complete paired cards.
- Revision 4 contains 34,851 rows and 66 complete card pairs under physics `srp-forward-2.0-plunger-clearance`; it is a new synthetic capture and has not yet been used to train/evaluate a model.
- 30/30 virtual well configurations have zero noise and zero bias.
- The data therefore satisfy the raw sample-row target but do not provide 3,129 independent fault strokes per class.

## Complete-stroke model evidence

- 2,970 complete synthetic strokes, 6 held-out virtual wells, and 540 unique held-out cards after exact duplicate removal.
- Held-out synthetic macro F1 0.538; coverage 0.437; accepted accuracy 0.958; ECE 0.136.
- Earlier 800-run experiment best synthetic model: physics_features, macro F1 0.667, coverage 0.425.
- Neither evaluation includes an independent real well; neither candidate is approved for deployment.

- Supplemental new-capture challenge: 12 cards from 6 frozen test configurations, 7 classes present, macro F1 0.905. This small synthetic-only check does not replace the larger held-out score or field validation.
## Engineering gaps before field testing

1. Acquire permission-cleared measured cards from multiple physical wells with independently reviewed fault evidence and complete equipment metadata.
2. Collect sensor model, calibration, sampling and uncertainty metadata; do not invent noise parameters where the instrumentation is unknown.
3. Expand the simulator's operating envelope from documented well inputs and verify predicted surface cards against independently exportable measured/reference traces.
4. The revised clearance-leak model produces a weak synthetic pump-wear card signature; calibrate it to pump specifications/inspection evidence and retain combined/undetermined diagnosis until independent tests show reliable separability.
5. Evaluate by held-out physical wells and operating periods; use synthetic tests for development only.

Machine-readable detail: `MODEL_AND_SYNTHETIC_EVIDENCE_AUDIT.json`.
