# Limitations

- Engineering values describe illustrative synthetic assets. This model needs time-series field validation before engineering use.
- The pumping-unit drive prescribes crank speed. Motor startup, counterbalance and regenerative behavior are unmodeled. The pump assumes effective bulk compliance, simplified pressure flow and limited reservoir dynamics.
- Gas lock, rod parting and generic mechanical loading anomaly are unsupported. Overlapping fault symptoms are plausible. Synthetic metrics provide insufficient evidence for field root-cause detection.
- Periodic crank-angle reconstruction expects a genuine cycle with stable cadence and sample indices. Field adapters must supply this contract. Position-only or OPC-UA ingestion remains unimplemented.
- Compose supplies PostgreSQL and the native workflow uses SQLite/WAL. Timescale hypertables, full production retention automation, long-duration field operation and industrial availability testing remain open.
- The discovery references did not supply reusable synchronized field data. QRod and libzrod numerical validation remain open.
- The UI presents an operating view for synthetic wells and advisory analysis. Deployment-wide API authorization, organization-specific retention rules and broker TLS provisioning are production integration work.
