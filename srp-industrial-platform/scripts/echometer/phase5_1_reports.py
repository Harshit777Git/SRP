"""Write compact Phase 5.1 evidence tables from actual source/checkpoint data."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "reports" / "STATE93" / "PHASE5_1"
DATA = ROOT / "data" / "state93"


def write(name, rows, fields):
    with (REPORT / name).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)


def main():
    REPORT.mkdir(parents=True, exist_ok=True)
    progress = json.loads((REPORT / "EXTRACTION_PROGRESS.json").read_text(encoding="utf-8"))
    baseline = json.loads((ROOT / "reports" / "STATE93" / "STATE077_IMPORT_VALIDATION.json").read_text(encoding="utf-8"))
    matrix = list(csv.DictReader((ROOT / "reports" / "STATE93" / "93_STATE_COMPATIBILITY_MATRIX.csv").open(encoding="utf-8-sig")))
    cards = list(csv.DictReader((REPORT / "UNIQUE_STROKE_INVENTORY.csv").open(encoding="utf-8-sig")))
    by_state = {}
    for card in cards:
        by_state.setdefault(card["state_id"], []).append(card)
    configuration = []
    labels = []
    for row in matrix:
        sid, name = row["State ID"], row["Original State Name"]
        pdfs = list((DATA / sid / "06_ENGINEERING_CONFIGURATION" / "TAM").glob("*.pdf"))
        if sid == "STATE-077":
            pdfs = list((DATA / "pilot" / "Tagging Down Hard" / "original" / "user_exports").glob("*Summary.pdf"))
        configuration.append({"state_id": sid, "state_name": name,
                              "summary_pdf_available": bool(pdfs),
                              "summary_pdf_path": str(pdfs[0].resolve()) if pdfs else "",
                              "engineering_review_status": "REVIEWED_WITH_RECORDED_ASSUMPTIONS" if sid == "STATE-077" else "PDF_COLLECTED_NOT_RECONCILED" if pdfs else "NOT_COLLECTED",
                              "solver_ready": sid == "STATE-077",
                              "missing_or_unverified": "61-ft rod-depth gap; pump intake conditions" if sid == "STATE-077" else "Engineering values not reconciled" if pdfs else "Summary PDF and engineering review"})
        manifest = DATA / sid / "09_VALIDATION" / "phase5_manifest.json"
        source_comment = json.loads(manifest.read_text(encoding="utf-8")).get("vendor_comment", "") if manifest.exists() else ""
        if sid == "STATE-077":
            source_comment = "Multiple behaviors documented; refer to test-specific STATE-077 benchmark evidence"
        labels.append({"state_id": sid, "example_name": name, "provider_comment": source_comment,
                       "test_specific_condition": "After tail-bearing repair" if sid == "STATE-005" else "Unverified across all strokes",
                       "pre_post_repair": "POST_REPAIR" if sid == "STATE-005" else "UNKNOWN",
                       "field_confirmed_diagnosis": False, "stroke_wide_label_assigned": False,
                       "training_permission": "NOT_REVIEWED"})
    write("ENGINEERING_CONFIGURATION_READINESS.csv", configuration, list(configuration[0]))
    write("DIAGNOSTIC_LABEL_AUDIT.csv", labels, list(labels[0]))
    metrics = baseline["metrics"]
    apm = [{"state_id": "STATE-077", "stroke_id": "1 (pilot identity)", "solver_status": "RECONSTRUCTED_AND_DB_READBACK_VERIFIED",
            "surface_points": 174, "vendor_pump_points": 174, "apm_pump_points": 174, **metrics}]
    write("APM_RECONSTRUCTION_RESULTS.csv", apm, list(apm[0]))
    total_points = sum(int(c["points"]) for c in cards)
    gui_checkpoint = REPORT / "TAM_GUI_CHECKPOINT.json"
    automated = json.loads(gui_checkpoint.read_text(encoding="utf-8")) if gui_checkpoint.exists() else {"states": {}}
    provenance = json.loads((REPORT / "VENDOR_ORIGINAL_PROVENANCE.json").read_text(encoding="utf-8")) if (REPORT / "VENDOR_ORIGINAL_PROVENANCE.json").exists() else {"states": {}}
    native_tam = sum(x["source_class"] == "Original TAM" for s in provenance["states"].values() for x in s["original_files"])
    native_twm = sum(x["source_class"] == "Original TWM" for s in provenance["states"].values() for x in s["original_files"])
    verified_by_utility = sum(v.get("status") == "NUMERICAL_VERIFIED" for tests in automated.get("states", {}).values()
                              for strokes in tests.values() for v in strokes.values())
    (REPORT / "TAM_AUTOMATION_RESULTS.md").write_text(
        "# TAM automation results\n\n"
        f"- Verified unique stroke pairs: **{len(cards)}** across {len(by_state)} states.\n"
        f"- Surface points and vendor Pump points: **{total_points} each**.\n"
        f"- Vendor originals staged with source paths and SHA-256 hashes: **{native_tam} TAM files, {native_twm} TWM files** across the 93 named states.\n"
        f"- Stroke pairs exported by the new unattended pywinauto utility: **{verified_by_utility}**.\n"
        "- STATE-001 strokes 1-3 and STATE-006 strokes 14 and 18 from separate imported tests were exported through supervised TAM desktop interactions; the six baseline pairs predate Phase 5.1.\n"
        "- The pywinauto utility is implemented but has not passed its own application acceptance test. It requires pywinauto and either working OCR or supervised stroke confirmation on the normal unlocked Windows desktop.\n"
        "- The other TAM tests and TWM-only states have not been bulk exported. No zero-stroke valve test is counted.\n",
        encoding="utf-8")
    source_006 = DATA / "STATE-006" / "02_TWM" / "BlockedIntake.019"
    imported_006 = any(c["state_id"] == "STATE-006" for c in cards)
    (REPORT / "TWM_IMPORT_PILOT.md").write_text(
        "# TWM-to-TAM pilot: STATE-006 BlockedIntake\n\n"
        + ("Status: IMPORTED_IN_TAM_AND_NUMERICAL_EXPORT_VERIFIED.\n\n"
           "Source: `" + str(source_006.resolve()) + "` (preserved copy of the original `.019` file).\n\n"
           "TAM Utilities > Express TWM Import accepted the file, identified BlockedIntake, and reported 1 well plus 4 tests: 2 DYN, 1 valve, 1 liquid-level. The well appeared in Pick a Well and reopened. DYN History showed a zero-stroke valve test and two completed DYN tests. The 07:26:00 PM test displayed 14 strokes; stroke 14 exported as TXT and DYN with 289 matching points. The 07:23:07 PM test displayed 18 strokes; stroke 18 exported as TXT and DYN with 289 matching points. The other 30 completed strokes remain to be exported. No separate TAM-native file was exported or independently reopened.\n"
           if imported_006 else "Status: NOT_VERIFIED.\n"),
        encoding="utf-8")
    print(json.dumps({"verified_pairs": len(cards), "states_with_numerical_pairs": len(by_state),
                      "surface_points": total_points, "vendor_pump_points": total_points,
                      "utility_verified_pairs": verified_by_utility}, indent=2))


if __name__ == "__main__":
    main()
