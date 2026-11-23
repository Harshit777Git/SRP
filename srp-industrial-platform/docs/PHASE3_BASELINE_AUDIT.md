# Phase 3 baseline audit

The existing native platform had three simulator presets, one `Engine` and `Sensors` instance per active `Run`, an SQLite MQTT outbox, APM stroke processing and harmonic inverse reconstruction. It did not have 30 fleet configurations, site-level controls or a measured 30-well load test. The experimental classifier remains untouched.

Baseline references inspected: `reports/SRP_COMPLETE_DATA_INTELLIGENCE_REPORT.pdf`, the prior data inventory and dictionary workbooks, `docs/V2_ACCEPTANCE_REPORT.md`, `docs/FAULT_MODEL_VALIDATION.md`, `docs/PHYSICS_MODEL.md`, and the forward/inverse solver source. The primary synthetic archive contained 800 runs; its reported LightGBM macro F1 was 0.570 on synthetic held-out configurations. That number is not field accuracy.

The checkout has no `.git` directory, so a commit-based baseline could not be created here. Original archives, vendor files, model artifacts and previous evaluation reports were left in place. Phase 3 outputs use new paths under `data/evaluation/phase3`, `data/engineering_reference/echometer`, `config/fleet`, and `reports/PHASE3`.

After the Phase 3 edits, `scripts/check_physics.py` passed 6 tests, `scripts/check_ingest.py` passed 4, `scripts/check_interchange_v2.py` passed 3, and `scripts/check_phase3_fleet.py` passed 3. The TypeScript/Vite build passed. These test counts do not establish QRod agreement or fleet MQTT capacity.
