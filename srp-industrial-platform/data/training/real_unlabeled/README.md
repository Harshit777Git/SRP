# Real unlabeled SRP cards

This partition is empty. Place only provenance-verified, use-authorized field records here. Use them for benchmarking or explicitly authorized unsupervised adaptation. Model predictions cannot populate supervised ground truth. Vendor demonstrations remain separately cataloged in the acquisition audit.

## Field collection handoff

No field strokes or calibration records have been received. To build a defensible field validation set, export ordered load-position-time samples from the site dynamometer and retain the original file unchanged. Record a stable well and run identity, complete pumping-unit/rod/pump configuration, sensor identity, calibration certificate/date and stated uncertainty, sample units/rate, operating pressure/fluid-level/production context, and timestamp.

For supervised diagnoses, link each stroke to an independently documented inspection, valve test, workover finding or operator-confirmed event with date and reviewer. Record training permission for the data itself. The label must describe the evidence and its time relationship to the stroke. Never use a filename, TAM demonstration name, curve appearance, or model output as ground truth.

Use `../real_labeled/field_strokes_template.csv` for the record manifest. The template is a handoff schema, not a dataset; leave unknown values blank and do not represent the template as collected data. Keep all records from a well together when splitting evaluation data.
