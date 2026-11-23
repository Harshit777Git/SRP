"""Build factual Phase 3.1 acceptance tables from measured artifacts."""
import json
import statistics
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/"reports/PHASE3_1"
TABLES=REPORT/"tables"


def load(name):
    return json.loads((REPORT/name).read_text())


def rows(path):
    return [json.loads(line) for line in (ROOT/path).read_text().splitlines() if line.strip()]


def save(name,value):
    TABLES.mkdir(parents=True,exist_ok=True)
    (TABLES/name).write_text(json.dumps(value,indent=2)+"\n")


def main():
    manifest=json.loads((ROOT/"data/generated/phase31/manifest.json").read_text())
    validation=rows("data/generated/phase31/validation.jsonl")
    convergence=load("physics_timestep_convergence.json")
    fault=rows("reports/PHASE3_1/fault_observability.jsonl")
    benchmark=load("staged_30wells.json")
    recovery=load("recovery_5wells.json")
    broker=load("broker_only.json")
    apm=load("apm_only.json")
    outbox=load("outbox_only.json")
    by_asset=defaultdict(list)
    for row in validation:by_asset[row["asset_id"]].append(row)
    conv={row["asset_id"]:row for row in convergence}
    physics=[]
    for asset,items in sorted(by_asset.items()):
        physics.append(dict(asset_id=asset,site_id=items[0]["site_id"],
            completed_strokes=len(items),valid_strokes=sum(x["status"]=="SYNTHETIC_VALIDATED" for x in items),
            min_surface_load_n=min(x["surface_min_load_n"] for x in items),
            max_surface_load_n=max(x["surface_max_load_n"] for x in items),
            median_stroke_s=statistics.median(x["period_s"] for x in items),
            median_card_area_j=statistics.median(x["surface_area_j"] for x in items),
            max_centered_position_rmse_m=max(x["centered_position_rmse_m"] for x in items),
            max_load_rmse_n=max(x["load_rmse_n"] for x in items),
            max_card_area_error_fraction=max(x["card_area_error_fraction"] for x in items),
            step_0067_vs_002_load_rmse_range_fraction=conv[asset]["candidate_002_vs_0067"]["load_rmse_range_fraction"],
            independent_reference="NONE",energy_balance="UNAVAILABLE_FULL_DRIVE_MODEL_ABSENT"))
    save("FLEET_PHYSICS_VALIDATION.json",physics)
    save("FAULT_OBSERVABILITY.json",fault)
    save("QROD_ENGINEERING_COMPARISON.json",json.loads((ROOT/"reports/PHASE3/QROD_BENCHMARK_RESULTS.json").read_text()))
    save("DATASET_INVENTORY.json",manifest["files"])
    stages=benchmark["stages"]
    mqtt=[dict(test="broker_only",active_wells=0,duration_s=broker["elapsed_s"],
               broker_ack_rate_per_s=broker["receive_rate_per_s"],apm_persist_rate_per_s=None,
               queued_before=None,queued_after=None,dropped_delta=broker["missing"],result="ISOLATED_PASS")]
    mqtt.append(dict(test="apm_replay_three_strokes",active_wells=30,duration_s=apm["elapsed_s"],
                     broker_ack_rate_per_s=None,apm_persist_rate_per_s=apm["ingest_rate_per_s"],
                     queued_before=None,queued_after=None,dropped_delta=apm["submitted"]-apm["persisted"],
                     result="ISOLATED_PASS" if apm["persisted"]==apm["submitted"] else "FAIL"))
    mqtt += [dict(test="combined_live",**stage,
                  result="FAIL" if stage["queued_after"]>stage["queued_before"]+500 else "PARTIAL")
             for stage in stages]
    mqtt.append(dict(test="five_well_broker_restart",active_wells=5,
                     duration_s=None,broker_ack_rate_per_s=None,apm_persist_rate_per_s=None,
                     queued_before=recovery["recovery"]["during"],
                     queued_after=recovery["recovery"]["final_queued"],
                     dropped_delta=recovery["recovery"]["drops"],
                     observed_sequence_gaps=recovery["observed_sequence_gaps"],
                     result="PASS" if recovery["recovery"]["drained"] and
                     recovery["observed_sequence_gaps"]==0 else "FAIL"))
    mqtt.append(dict(test="30_minute_stable_run",active_wells=30,duration_s=0,
                     broker_ack_rate_per_s=None,apm_persist_rate_per_s=None,
                     queued_before=None,queued_after=None,dropped_delta=None,
                     result="NOT_RUN_COMBINED_SHORT_TEST_FAILED"))
    save("MQTT_STABILITY.json",mqtt)
    fault_weak=defaultdict(int)
    for row in fault:
        if row.get("status")=="MEASURED_SYNTHETIC_SENSITIVITY" and row["surface_load_rmse_n"]<500:
            fault_weak[f"{row['mechanism']}@{row['severity']}"]+=1
    acceptance=dict(phase="PHASE3_1",decision="NO-GO",model_training_performed=False,
        field_fault_validation=False,independent_qrod_comparisons=0,
        fleet_wells=30,site_groups=6,synthetic_completed_strokes=manifest["completed_strokes"],
        synthetic_validated_strokes=manifest["valid_strokes"],
        raw_dynamometer_samples=manifest["raw_dynamometer_samples"],
        electrical_samples=manifest["electrical_samples"],pressure_samples=manifest["pressure_samples"],
        fault_sensitivity_cases=len(fault),fault_study_failed_cases=sum(x["status"]=="FAILED" for x in fault),
        weak_surface_changes_under_500n=dict(fault_weak),
        broker_only_rate_per_s=broker["receive_rate_per_s"],
        apm_only_rate_per_s=apm["ingest_rate_per_s"],
        combined_30_well_rate_per_s=next((x["broker_ack_rate_per_s"] for x in stages if x["active_wells"]==30),None),
        combined_30_well_apm_rate_per_s=next((x["apm_persist_rate_per_s"] for x in stages if x["active_wells"]==30),None),
        thirty_minute_stable_run_completed=False,
        five_well_restart_recovery_passed=bool(recovery["recovery"]["drained"] and recovery["observed_sequence_gaps"]==0),
        browser_e2e_30_wells_completed=False,
        gates=dict(mqtt="FAIL_COMBINED_QUEUE_GROWTH",continuous_physics="PARTIAL_THREE_STROKES_PER_WELL",
                   qrod="FAIL_NO_INDEPENDENT_NUMERICAL_EXPORT",faults="PARTIAL_TWO_SEVERITIES_NO_FIELD_PROOF",
                   apm="PARTIAL_API_AND_REPLAY_ONLY",dataset="PARTIAL_HEALTHY_EXPORTS_ONLY",
                   ml_boundary="PASS_NO_MODEL_TRAINING"))
    (REPORT/"ACCEPTANCE_RESULTS.json").write_text(json.dumps(acceptance,indent=2)+"\n")
    save("ML_READINESS_MATRIX.json",[dict(gate=k,status=v,training_allowed=False) for k,v in acceptance["gates"].items()])
    print(json.dumps({k:acceptance[k] for k in ("decision","synthetic_completed_strokes",
         "fault_sensitivity_cases","combined_30_well_rate_per_s","combined_30_well_apm_rate_per_s")}))


if __name__=="__main__":main()
