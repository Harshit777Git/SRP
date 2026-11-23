# Live application UI and feature audit

Source reviewed: `http://192.168.1.155:8111/` on 2026-11-23.

## Well and field inventory

The application contains 120 wells, evenly distributed across four fields:

| Field | Well IDs | Count |
|---|---|---:|
| Prairie | `prairie-001` through `prairie-030` | 30 |
| Canyon | `canyon-001` through `canyon-030` | 30 |
| Mesa | `mesa-001` through `mesa-030` | 30 |
| Delta | `delta-001` through `delta-030` | 30 |

## UI/UX extracted

- Compact dark-green product bar with live/environment indicator.
- Fleet overview card with Wells, Running, Fields and Tripped/Attention totals.
- Expandable automatic-scenario coverage and TWM dynacard comparison sections.
- Searchable/filterable well directory grouped by field, with condition and run-state badges.
- Master-detail layout: directory on the left and selected-well diagnostics on the right.
- Selected-well header, run state, control entry point, pump-condition card and latest telemetry tiles.
- Stroke capture selector; surface, downhole and motor-profile plots; cross-plot sample comparison.
- Downhole method selector (Simulated, Gibbs, Everitt–Jennings, Both), fillage and valve-opening readings.
- Trend selector, electrical phase readings, motor/pressure readings, event history and JSON/CSV exports.
- Responsive single-column mobile behavior retaining the same information hierarchy.

## Feature segregation

| Capability | Digital Twin | APM |
|---|:---:|:---:|
| Fleet/field directory, search, filters, status badges | Yes | Yes |
| Fleet totals and scenario coverage | Yes | Yes |
| Start/pause/stop/reset and forced scenarios | Yes | No |
| Well/equipment configuration | Yes | Read-only context |
| Automatic fault/scenario generation | Yes | Consume and diagnose |
| Live surface dynacard | Generate | Monitor |
| Downhole methods and multi-card overlay | Reference/validation | Yes |
| Stroke capture history | Generate/store | Search/compare |
| Telemetry trends and electrical readings | Generate | Monitor/history |
| Fault detection, probability and evidence | Ground-truth injection | Yes |
| Events, alarms and audit trail | Emit | Yes |
| JSON/CSV import/export | Yes | Yes |
| Model registry and dataset intelligence | No | Yes |
| TWM/reference-card comparison | Physics validation | Engineering benchmark |

## Implementation

An `Operations Console` has been added to both applications. It reproduces the audited master-detail information architecture, fleet totals, grouped well directory, filters, state badges, condition card, telemetry tiles and paired dynacard workspace while retaining the existing product navigation and API-backed asset lists. Existing specialized Digital Twin and APM pages remain available for their respective control and diagnostic workflows.
