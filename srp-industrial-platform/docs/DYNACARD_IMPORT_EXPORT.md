# Engineering import and export

Open Import / Export Center. Export the selected completed stroke. The existing simple SI card export remains available from the card comparison tab.

| Contract | Fields and semantics |
|---|---|
| Raw telemetry | well_id, stroke_id, timestamp, sequence within source stroke via sample_index, crank_angle_deg, polished_rod_position_in, polished_rod_load_lbf, spm, quality, source |
| Surface Dynacard | well_id, stroke_id, UTC timestamp, sample_index, position_in, load_lbf, stroke_phase, source |
| Downhole Dynacard | well_id, stroke_id, UTC timestamp, sample_index, plunger_position_in, pump_load_lbf, solver_version, quality |
| Configuration | well_id, unit_system=SI, pump_setting_depth_m and fields of the shared Well contract using their declared SI units. rods_json contains an ordered array of objects with length_m, diameter_m, density in kg/m³ and modulus in Pa. Companion JSON uses asset_id and rods. |
| Diagnostics | Identity, time, prediction, confidence, severity when available, evidence, model version, dataset provenance, status and input quality |
| Synchronized stroke | Identity, timestamp, sample_index, surface position/load and reconstructed plunger position/load on the same timebase |

For unfamiliar numerical files, expand the mapping controls, supply the exact field headers and select position/load units. The browser decodes UTF-8, BOM-marked UTF-16 and Windows-1252 fallback. The API detects comma, semicolon, tab and pipe delimiters. Preview before saving. The native batch size is at most 15,000 rows under the existing HTTP request limit. Each stroke is sorted by input index. Duplicate indices, non-finite values and partial or nonmonotonic timestamp sets are rejected. Missing point indices degrade the stroke; untimed records permit geometry-only comparisons.

Imports use a content and interpretation hash. Re-import of the same dataset is idempotent. Imports never overwrite operating stroke records. Raw import preserves validated telemetry separately from the live MQTT stream; operator registration of a configuration is separate from preview.

Examples and round-trip metrics are in [V2 evidence](../data/evaluation/v2). Full-precision exports preserve the original IEEE-754 values through unit conversion within 1e-9 in SI. Canonical timestamps use microsecond resolution.
