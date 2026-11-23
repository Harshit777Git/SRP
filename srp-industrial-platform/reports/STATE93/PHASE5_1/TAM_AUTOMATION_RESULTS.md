# TAM automation results

- Verified unique stroke pairs: **24** across 7 states.
- Surface points and vendor Pump points: **6282 each**.
- Vendor originals staged with source paths and SHA-256 hashes: **39 TAM files, 128 TWM files** across the 93 named states.
- Stroke pairs exported by the new unattended pywinauto utility: **6**.
- STATE-001 strokes 1-3 and STATE-006 strokes 14 and 18 from separate imported tests were exported through supervised TAM desktop interactions; the six baseline pairs predate Phase 5.1.
- The pywinauto utility is implemented but has not passed its own application acceptance test. It requires pywinauto and either working OCR or supervised stroke confirmation on the normal unlocked Windows desktop.
- The other TAM tests and TWM-only states have not been bulk exported. No zero-stroke valve test is counted.
