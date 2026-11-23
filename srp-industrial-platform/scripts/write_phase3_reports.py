"""Assemble evidence tables and explicit Phase 3 gate decisions."""
import hashlib
import json
import statistics
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/PHASE3"


def read(path):
    return json.loads((ROOT / path).read_text())


def write(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    fleet = read("config/fleet/us_srp_30_wells.json")["wells"]
    cases = read("data/evaluation/phase3/validation.json")["cases"]
    echometer = read("data/engineering_reference/echometer_manifest.json")["records"]
    distances = read("reports/PHASE3/fault_observability.json")
    mqtt = read("reports/PHASE3/MQTT_MULTIWELL_BENCHMARK.json")
    write("ECHOMETER_EXTRACTION_INVENTORY.json", echometer)
    qrod = []
    for path in sorted((ROOT / "data/external_reference/onedrive_2026-11-16_2").rglob("*.qrd")):
        qrod.append(dict(path=str(path), sha256=sha(path), status="REFERENCE_EXPORT_UNAVAILABLE",
                         numerical_prediction_available=False, equivalent_inputs_verified=False))
    with zipfile.ZipFile(ROOT / "state/vendor/echometer-session20.zip") as archive:
        for name in archive.namelist():
            if name.lower().endswith(".qrd"):
                qrod.append(dict(path="state/vendor/echometer-session20.zip", member=name,
                    sha256=hashlib.sha256(archive.read(name)).hexdigest(),
                    status="REFERENCE_EXPORT_UNAVAILABLE", numerical_prediction_available=False,
                    equivalent_inputs_verified=False))
    write("QROD_BENCHMARK_RESULTS.json", qrod)
    configurations = [dict(site_id=x["site_id"], **{k:v for k,v in x["well"].items() if k != "rods"},
                           rods=json.dumps(x["well"]["rods"])) for x in fleet]
    write("SRP_30_WELL_CONFIGURATION.json", configurations)
    write("SIMULATION_PHYSICS_VALIDATION.json", cases)
    write("FAULT_SIGNATURE_SEPARABILITY.json", distances)
    wave = [{k: row[k] for k in ("site_id", "asset_id", "status", "centered_position_rmse_m",
             "load_rmse_n", "load_rmse_fraction_of_range", "card_area_error_fraction") if k in row}
            for row in cases]
    write("WAVE_EQUATION_VALIDATION.json", wave)
    write("MQTT_MULTIWELL_BENCHMARK_TABLE.json", [{k: mqtt[k] for k in (
        "benchmark_duration_s", "startup_s", "active_wells", "published_delta",
        "published_messages_per_s", "dropped_delta", "topic_count")} | {
        "queued_before": mqtt["before"]["queued"], "queued_after": mqtt["after"]["queued"],
        "ack_lag_after_s": mqtt["after"]["ack_lag_s"]}])
    catalog = []
    for row in cases:
        asset = row["asset_id"]
        files = [ROOT / f"data/evaluation/phase3/{asset}.{suffix}" for suffix in
                 ("sensor.jsonl", "truth.json", "cards.json")]
        catalog.append(dict(site_id=row["site_id"], asset_id=asset,
            status=row["status"], source="SYNTHETIC", samples=row["sample_count"],
            surface_cards=row["surface_card_count"], downhole_cards=row["downhole_card_count"],
            sensor_path=str(files[0].relative_to(ROOT)) if files[0].exists() else None,
            sensor_sha256=sha(files[0]) if files[0].exists() else None,
            truth_path=str(files[1].relative_to(ROOT)) if files[1].exists() else None,
            cards_path=str(files[2].relative_to(ROOT)) if files[2].exists() else None,
            validation="SYNTHETIC_SELF_CONSISTENCY_ONLY"))
    write("SIMULATION_DATASET_CATALOG.json", catalog)
    write("ML_INPUT_READINESS.json", [dict(site_id=r["site_id"], asset_id=r["asset_id"],
        interface_compatible=r["status"] == "SYNTHETIC_VALIDATED", training_performed=False,
        independent_physics_benchmark=False, fleet_mqtt_gate=False,
        decision="NOT_READY_FOR_ML_EXPERIMENTATION") for r in cases])
    acceptance = dict(phase="PHASE3", decision="NO_GO", model_training_performed=False,
        vendor_numerical_surface_cards=2, qrod_design_files=len(qrod), qrod_numerical_comparisons=0,
        sites=len(set(x["site_id"] for x in fleet)), wells=len(fleet),
        synthetic_validated_strokes=sum(r["status"] == "SYNTHETIC_VALIDATED" for r in cases),
        surface_cards=sum(r["surface_card_count"] for r in cases),
        reconstructed_downhole_cards=sum(r["downhole_card_count"] for r in cases),
        raw_sensor_samples=sum(r["sample_count"] for r in cases),
        mqtt_published_in_15s=mqtt["published_delta"], mqtt_rate_per_s=mqtt["published_messages_per_s"],
        mqtt_queued_after=mqtt["after"]["queued"],
        gates=dict(extraction="PARTIAL_VENDOR_GUI_BLOCKED", qrod_benchmark="FAIL_NO_NUMERICAL_REFERENCE",
            physics="PARTIAL_SYNTHETIC_SELF_CONSISTENCY_ONLY", fault_fidelity="PARTIAL_EIGHT_CLASSES_STUDIED",
            fleet="PASS_CONFIGURATION_AND_OFFLINE_EXECUTION", mqtt="FAIL_BACKLOG_AND_LOW_THROUGHPUT",
            dynacards="PASS_THIRTY_SYNTHETIC_STROKES", data_readiness="PARTIAL_SPLIT_PREPARED_NO_INDEPENDENT_BENCHMARK",
            ml_boundary="PASS_NO_TRAINING"))
    write("PHASE3_ACCEPTANCE_RESULTS.json", acceptance)
    print(json.dumps(acceptance, indent=2))


if __name__ == "__main__":
    main()
