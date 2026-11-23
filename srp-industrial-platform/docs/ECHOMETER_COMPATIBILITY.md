# Echometer interoperability

| Workflow | Status |
|---|---|
| QRod surface DYN numerical import to APM | Verified against the 132-point Overtravel and 216-point Undertravel files in Echometer's public Session 20 bundle. The importer reads the observed count followed by ordered comma-separated position/load pairs. The operator selects units. The trailing metadata is opaque. |
| Export new DYN for QRod import | Unverified. The two verified examples differ in trailing metadata. Timestamp, units, metadata semantics, additional variants and native QRod acceptance of a newly generated file require further verification. |
| TAM numerical imports into APM | Use an authorized numerical stroke export and map point columns, order and units. TAM's own interchange archive has a separate workflow. |
| TAM_EXP | Native format unverified. The Session 20 archive contains an example. APM currently accepts its supported numerical formats. |
| TWM data export | The quick reference documents spreadsheet exports of selected module results and separate graphical copying. A summary report or an image cannot supply a point-by-point card. For an authorized complete numerical export, use explicit column mapping. Vendor-specific structured numerical TWM fixtures remain unverified. |

Archive SHA-256 and original file checksums are recorded in local inspection results. The third-party archive was used for local verification and kept under ignored state. Inspect a copy with `python scripts/inspect_vendor_file.py FILE`. Validate the examples with `python scripts/check_vendor_v2.py state/vendor/echometer-session20.zip`.

[Echometer Session 20 public example archive](https://drive.google.com/file/d/1Nzp6DK76Gbnt6GYKAQSl6UsyhF4aHinV/view) · [QRod supported comparison workflow](https://www.echometer.com/software/qrod) · [TWM quick reference](https://www.echometer.com/Portals/0/Quick%20Reference%20Guides/TWM%20Quick%20Ref.pdf).
