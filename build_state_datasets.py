import os
import sys
import json
import csv
import math
import datetime as dt
from pathlib import Path
from collections import defaultdict
import openpyxl

MASTER_DIR = Path(r"C:\Users\HARSHIT\OneDrive - TAS\Desktop\Master Dataset")
SRP_DIR = Path(r"C:\Users\HARSHIT\OneDrive - TAS\Desktop\SRP\srp-industrial-platform")
OUT_DIR = MASTER_DIR / "Consolidated_State_Datasets"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 33 Configuration Columns
CONFIG_COLUMNS = [
    "state_id",
    "well_id",
    "pumping_unit_type",
    "pumping_unit_model",
    "pumping_unit_geometry",
    "surface_stroke_length_in",
    "spm",
    "rod_section_length_ft",
    "rod_section_diameter_in",
    "rod_material_grade",
    "rod_youngs_modulus_psi",
    "rod_material_density_kg_m3",
    "pump_setting_depth_ft",
    "pump_plunger_diameter_in",
    "pump_clearance_in",
    "pump_type",
    "tubing_id_in",
    "tubing_anchor_status",
    "oil_api_gravity",
    "water_specific_gravity",
    "gas_specific_gravity",
    "water_cut_pct",
    "fluid_viscosity_cp",
    "dynamic_fluid_level_ft",
    "tubing_pressure_psi",
    "casing_pressure_psi",
    "flowline_pressure_psi",
    "motor_rated_hp",
    "motor_rated_voltage_v",
    "motor_rated_rpm",
    "fault_mechanism",
    "fault_severity",
    "model_damping_coefficient",
]

# 20 MQTT Telemetry Columns
MQTT_COLUMNS = [
    "well_id",
    "timestamp_ms",
    "stroke_id",
    "sample_index",
    "polished_rod_load_lbf",
    "polished_rod_position_in",
    "polished_rod_acceleration_m_s2",
    "spm",
    "motor_current_a",
    "motor_voltage_v",
    "motor_active_power_kw",
    "tubing_pressure_psi",
    "casing_pressure_psi",
    "flowline_pressure_psi",
    "dynamic_fluid_level_ft",
    "oil_rate_bpd",
    "water_rate_bpd",
    "gas_rate_mscfd",
    "pump_running",
    "data_quality",
]

# Unified columns (all columns merged, preserving unique attributes)
# Note well_id, spm, tubing_pressure_psi, casing_pressure_psi, flowline_pressure_psi, dynamic_fluid_level_ft align
UNIFIED_COLUMNS = list(CONFIG_COLUMNS) + [
    c for c in MQTT_COLUMNS if c not in CONFIG_COLUMNS
]

print(f"Unified schema has {len(UNIFIED_COLUMNS)} columns.")


def load_data_sources():
    # 1. State catalog matrix
    matrix_path = SRP_DIR / "reports/STATE96/96_STATE_ACQUISITION_MATRIX.csv"
    with open(matrix_path, encoding="utf-8-sig") as f:
        matrix = list(csv.DictReader(f))

    # 2. Diagnostic label audit
    audit_path = SRP_DIR / "reports/STATE93/PHASE5_1/DIAGNOSTIC_LABEL_AUDIT.csv"
    audit_by_id = {}
    if audit_path.exists():
        with open(audit_path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                audit_by_id[r["state_id"]] = r

    # 3. Field stage JSON
    stage_json_path = SRP_DIR / "outputs/01a1f1fd-6501-7a40-89e3-df4b424daa3b/field/field_stage.json"
    stage_by_id = {}
    if stage_json_path.exists():
        with open(stage_json_path, encoding="utf-8") as f:
            stage_data = json.load(f)
        for item in stage_data:
            if item[0].startswith("STATE-"):
                stage_by_id[item[0]] = (item[1], {b[0]: (b[1], b[2]) for b in item[2]})

    # 4. TAM Exp Test Inventory
    tam_test_inv_path = MASTER_DIR / "TAM_EXP_TEST_INVENTORY.csv"
    tam_test_by_state = defaultdict(list)
    if tam_test_inv_path.exists():
        with open(tam_test_inv_path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                tam_test_by_state[r["state_id"]].append(r)

    return matrix, audit_by_id, stage_by_id, tam_test_by_state


def compute_acceleration_and_time(positions_in, spm, base_timestamp_ms=0):
    """
    Computes numerical acceleration d^2x/dt^2 (m/s^2) and per-sample timestamps.
    positions_in: list of positions in inches
    spm: strokes per minute
    base_timestamp_ms: base timestamp in epoch ms
    """
    n = len(positions_in)
    if n < 2 or spm <= 0:
        return [0.0] * n, [base_timestamp_ms + i * 20 for i in range(n)]

    period_s = 60.0 / spm
    dt_s = period_s / max(n, 1)
    dt_ms = dt_s * 1000.0

    # Convert inches to meters
    pos_m = [p * 0.0254 for p in positions_in]

    accel = [0.0] * n
    timestamps = [int(base_timestamp_ms + i * dt_ms) for i in range(n)]

    # Central difference for internal points, forward/backward for endpoints (periodic assumption)
    dt_sq = dt_s * dt_s if dt_s > 0 else 1.0
    for i in range(n):
        p_prev = pos_m[(i - 1) % n]
        p_curr = pos_m[i]
        p_next = pos_m[(i + 1) % n]
        acc = (p_next - 2.0 * p_curr + p_prev) / dt_sq
        accel[i] = round(acc, 4)

    return accel, timestamps


def compute_motor_electrical(loads_lbf, positions_in, spm, rated_hp, rated_v=480.0, rated_rpm=1150.0):
    """
    Estimates motor active power (kW) and motor current (A) based on kinematic rod velocity and polished rod load.
    """
    n = len(positions_in)
    if n < 2 or spm <= 0:
        base_kw = rated_hp * 0.7457 * 0.4
        base_a = (base_kw * 1000.0) / (math.sqrt(3) * rated_v * 0.85)
        return [round(base_a, 2)] * n, [round(base_kw, 2)] * n

    period_s = 60.0 / spm
    dt_s = period_s / max(n, 1)

    currents = [0.0] * n
    powers = [0.0] * n

    eff = 0.82
    pf = 0.85
    idle_hp = rated_hp * 0.15

    for i in range(n):
        # velocity in in/s
        p_next = positions_in[(i + 1) % n]
        p_prev = positions_in[(i - 1) % n]
        v_in_s = (p_next - p_prev) / (2.0 * dt_s)
        load = max(loads_lbf[i], 0.0)

        # Polished rod mechanical power: P (hp) = (Load * v_in_s) / (12 * 550)
        mech_hp = max((load * v_in_s) / 6600.0, 0.0) + idle_hp
        kw = (mech_hp * 0.7457) / eff
        # 3-phase current: I = P / (sqrt(3) * V * PF)
        amps = (kw * 1000.0) / (math.sqrt(3) * rated_v * pf)

        powers[i] = round(kw, 3)
        currents[i] = round(amps, 2)

    return currents, powers


def build_all_state_datasets():
    matrix, audit_by_id, stage_by_id, tam_test_by_state = load_data_sources()

    all_states_config_rows = []
    all_states_unified_rows = []
    catalog_summary_rows = []

    for item in matrix:
        state_id = item["State ID"]
        state_name = item["State Name"] or f"State_{state_id}"
        print(f"Processing {state_id}: {state_name}...")

        stage_info = stage_by_id.get(state_id, (state_name, {}))
        blocks = stage_info[1]
        audit = audit_by_id.get(state_id, {})

        # --- 1. Extract Well ID ---
        well_id = f"WELL-{state_id}"
        if "TAM well metadata" in blocks:
            well_rows = blocks["TAM well metadata"][1]
            if well_rows and well_rows[0][0]:
                well_id = well_rows[0][0]

        # --- 2. Extract Equipment & PDF values ---
        eq_map = {}
        if "Equipment values reported in Echometer PDF" in blocks:
            for r in blocks["Equipment values reported in Echometer PDF"][1]:
                eq_map[r[0]] = r[1]

        # --- 3. Extract Rod sections ---
        rod_lengths = []
        rod_diams = []
        if "Rod string sections from Echometer PDF" in blocks:
            for r in blocks["Rod string sections from Echometer PDF"][1]:
                rod_lengths.append(str(r[1]))
                rod_diams.append(str(r[2]))

        # --- 4. Extract TAM test parameters ---
        tam_params = {}
        if "All original TAM test parameters" in blocks:
            for r in blocks["All original TAM test parameters"][1]:
                tam_params[r[1]] = r[3]

        # --- 5. Resolve 33 Configuration Attributes ---
        unit_type = eq_map.get("pumping_unit_class") or ("Mark II" if "mark" in state_name.lower() else "Conventional")
        unit_model = eq_map.get("pumping_unit_api") or ("C-640D-305-144" if "conventional" in str(unit_type).lower() else "M-228D-256-100")
        unit_geometry = f"API Class {'III' if 'mark' in str(unit_type).lower() else 'I'} Lever, Four-bar mechanism"

        # Stroke length
        stroke_in = eq_map.get("surface_stroke_in")
        if stroke_in is None:
            stroke_in = tam_params.get("Computed Stroke Length", 100.0)
        try:
            stroke_in = round(float(stroke_in), 2)
        except Exception:
            stroke_in = 100.0

        # SPM
        spm_val = tam_params.get("Strokes Per Minute")
        if spm_val is None:
            spm_val = eq_map.get("spm", 6.0)
        try:
            spm_val = round(float(spm_val), 3)
        except Exception:
            spm_val = 6.0

        # Rods
        rod_len_str = "; ".join(rod_lengths) if rod_lengths else "4500.0"
        rod_diam_str = "; ".join(rod_diams) if rod_diams else "0.875"
        rod_grade = "Grade D"
        rod_modulus = 30000000.0
        rod_density = 7850.0

        # Pump depth & plunger
        intake_depth = eq_map.get("pump_intake_depth_ft")
        if intake_depth is None:
            try:
                intake_depth = sum(float(x) for x in rod_lengths) if rod_lengths else 4500.0
            except Exception:
                intake_depth = 4500.0
        try:
            intake_depth = round(float(intake_depth), 1)
        except Exception:
            intake_depth = 4500.0

        plunger_diam = eq_map.get("plunger_diameter_in", 1.5)
        try:
            plunger_diam = round(float(plunger_diam), 3)
        except Exception:
            plunger_diam = 1.5

        pump_clearance = 0.003
        pump_type = eq_map.get("pump_type") or "Rod Insert Pump"
        tubing_id = 2.441

        # Anchor status
        anchor_status = "Unanchored" if ("unanchored" in state_name.lower() or "not set" in state_name.lower()) else "Anchored"

        # Fluid properties
        oil_api = 32.0
        water_sg = 1.01
        gas_sg = round(float(tam_params.get("Computed Gas Gravity from User Entered Velocity", 0.75)), 3)

        oil_bpd = tam_params.get("Oil Production")
        water_bpd = tam_params.get("Water Production")
        gas_mscfd = tam_params.get("Gas Production")

        try:
            oil_bpd = round(float(oil_bpd), 2) if oil_bpd is not None else 35.0
        except Exception:
            oil_bpd = 35.0

        try:
            water_bpd = round(float(water_bpd), 2) if water_bpd is not None else 15.0
        except Exception:
            water_bpd = 15.0

        try:
            gas_mscfd = round(float(gas_mscfd), 2) if gas_mscfd is not None else 25.0
        except Exception:
            gas_mscfd = 25.0

        tot_liquid = oil_bpd + water_bpd
        water_cut_pct = round((water_bpd / tot_liquid) * 100.0, 2) if tot_liquid > 0 else 30.0
        viscosity_cp = 15.0

        # Pressures & Levels
        fluid_level = tam_params.get("Distance to Liquid") or tam_params.get("Liquid Level - TVD")
        try:
            fluid_level = round(float(fluid_level), 1) if fluid_level is not None else round(intake_depth * 0.75, 1)
        except Exception:
            fluid_level = round(intake_depth * 0.75, 1)

        tubing_p = tam_params.get("DYN Tubing Pressure")
        try:
            tubing_p = round(float(tubing_p), 1) if tubing_p is not None else 50.0
        except Exception:
            tubing_p = 50.0

        casing_p = tam_params.get("DYN Casing Pressure") or tam_params.get("ACU Casing Pressure")
        try:
            casing_p = round(float(casing_p), 1) if casing_p is not None else 35.0
        except Exception:
            casing_p = 35.0

        flowline_p = tam_params.get("Back Pressure")
        try:
            flowline_p = round(float(flowline_p), 1) if flowline_p is not None else round(tubing_p * 0.6, 1)
        except Exception:
            flowline_p = round(tubing_p * 0.6, 1)

        # Motor nameplate
        motor_hp = eq_map.get("motor_rating_hp")
        try:
            motor_hp = round(float(motor_hp), 1) if motor_hp is not None else 50.0
        except Exception:
            motor_hp = 50.0

        motor_v = eq_map.get("motor_voltage_nameplate")
        try:
            motor_v = round(float(motor_v), 1) if motor_v is not None else 480.0
        except Exception:
            motor_v = 480.0

        motor_rpm = eq_map.get("motor_rated_rpm_nameplate")
        try:
            motor_rpm = round(float(motor_rpm), 1) if motor_rpm is not None else 1150.0
        except Exception:
            motor_rpm = 1150.0

        # Fault Mechanism & Severity & Damping
        fault_mech = state_name if state_name else f"State_{state_id}"
        fault_sev = 1.0

        damping_val = tam_params.get("Damping Factor Up Stroke") or tam_params.get("Damping Factor Down Stroke")
        try:
            damping_val = round(float(damping_val), 4) if damping_val is not None else 0.12
        except Exception:
            damping_val = 0.12

        config_row = {
            "state_id": state_id,
            "well_id": well_id,
            "pumping_unit_type": str(unit_type),
            "pumping_unit_model": str(unit_model),
            "pumping_unit_geometry": unit_geometry,
            "surface_stroke_length_in": stroke_in,
            "spm": spm_val,
            "rod_section_length_ft": rod_len_str,
            "rod_section_diameter_in": rod_diam_str,
            "rod_material_grade": rod_grade,
            "rod_youngs_modulus_psi": rod_modulus,
            "rod_material_density_kg_m3": rod_density,
            "pump_setting_depth_ft": intake_depth,
            "pump_plunger_diameter_in": plunger_diam,
            "pump_clearance_in": pump_clearance,
            "pump_type": str(pump_type),
            "tubing_id_in": tubing_id,
            "tubing_anchor_status": anchor_status,
            "oil_api_gravity": oil_api,
            "water_specific_gravity": water_sg,
            "gas_specific_gravity": gas_sg,
            "water_cut_pct": water_cut_pct,
            "fluid_viscosity_cp": viscosity_cp,
            "dynamic_fluid_level_ft": fluid_level,
            "tubing_pressure_psi": tubing_p,
            "casing_pressure_psi": casing_p,
            "flowline_pressure_psi": flowline_p,
            "motor_rated_hp": motor_hp,
            "motor_rated_voltage_v": motor_v,
            "motor_rated_rpm": motor_rpm,
            "fault_mechanism": fault_mech,
            "fault_severity": fault_sev,
            "model_damping_coefficient": damping_val,
        }
        all_states_config_rows.append(config_row)

        # --- 6. Extract / Assemble Time-Series Telemetry (Dynacard Samples) ---
        sample_rows = []
        data_quality_label = "VERIFIED_VENDOR"

        # Check vendor ordered samples in field_stage
        if "Ordered vendor dynacard samples" in blocks and len(blocks["Ordered vendor dynacard samples"][1]) > 0:
            vendor_samples = blocks["Ordered vendor dynacard samples"][1]
            data_quality_label = "VERIFIED_VENDOR"

            # Group samples by Capture ID
            by_capture = defaultdict(list)
            for s in vendor_samples:
                # s: [Capture ID, sample_index, polished_rod_position_in, polished_rod_load_lbf, pump_pos, pump_load]
                by_capture[s[0]].append(s)

            for cap_id, pts in by_capture.items():
                pts.sort(key=lambda x: x[1])  # sort by sample_index
                positions = [p[2] for p in pts]
                loads = [p[3] for p in pts]

                accels, timestamps = compute_acceleration_and_time(
                    positions, spm_val, base_timestamp_ms=1600000000000
                )
                currents, powers = compute_motor_electrical(
                    loads, positions, spm_val, motor_hp, motor_v, motor_rpm
                )

                stroke_num = cap_id.split("-")[-1].lstrip("0") or "1"
                for idx, pt in enumerate(pts):
                    s_row = {
                        "well_id": well_id,
                        "timestamp_ms": timestamps[idx],
                        "stroke_id": f"STROKE-{stroke_num.zfill(3)}",
                        "sample_index": idx,
                        "polished_rod_load_lbf": round(loads[idx], 2),
                        "polished_rod_position_in": round(positions[idx], 3),
                        "polished_rod_acceleration_m_s2": accels[idx],
                        "spm": spm_val,
                        "motor_current_a": currents[idx],
                        "motor_voltage_v": motor_v,
                        "motor_active_power_kw": powers[idx],
                        "tubing_pressure_psi": tubing_p,
                        "casing_pressure_psi": casing_p,
                        "flowline_pressure_psi": flowline_p,
                        "dynamic_fluid_level_ft": fluid_level,
                        "oil_rate_bpd": oil_bpd,
                        "water_rate_bpd": water_bpd,
                        "gas_rate_mscfd": gas_mscfd,
                        "pump_running": True,
                        "data_quality": data_quality_label,
                    }
                    sample_rows.append(s_row)

        else:
            # Check Synthetic assumed card in Master Dataset/Examples
            synth_card_path = MASTER_DIR / f"Examples/{state_name}/Synthetic assumed card.csv"
            if synth_card_path.exists():
                data_quality_label = "SYNTHETIC_ASSUMED"
                with open(synth_card_path, encoding="utf-8-sig") as f:
                    synth_pts = list(csv.DictReader(f))
                positions = [float(r["position_in"]) for r in synth_pts]
                loads = [float(r["load_lbf"]) for r in synth_pts]

                accels, timestamps = compute_acceleration_and_time(
                    positions, spm_val, base_timestamp_ms=1600000000000
                )
                currents, powers = compute_motor_electrical(
                    loads, positions, spm_val, motor_hp, motor_v, motor_rpm
                )

                for idx, pt in enumerate(synth_pts):
                    s_row = {
                        "well_id": well_id,
                        "timestamp_ms": timestamps[idx],
                        "stroke_id": "STROKE-001",
                        "sample_index": idx,
                        "polished_rod_load_lbf": round(loads[idx], 2),
                        "polished_rod_position_in": round(positions[idx], 3),
                        "polished_rod_acceleration_m_s2": accels[idx],
                        "spm": spm_val,
                        "motor_current_a": currents[idx],
                        "motor_voltage_v": motor_v,
                        "motor_active_power_kw": powers[idx],
                        "tubing_pressure_psi": tubing_p,
                        "casing_pressure_psi": casing_p,
                        "flowline_pressure_psi": flowline_p,
                        "dynamic_fluid_level_ft": fluid_level,
                        "oil_rate_bpd": oil_bpd,
                        "water_rate_bpd": water_bpd,
                        "gas_rate_mscfd": gas_mscfd,
                        "pump_running": True,
                        "data_quality": data_quality_label,
                    }
                    sample_rows.append(s_row)
            else:
                # Fallback: create representative kinematic baseline stroke (100 points)
                data_quality_label = "BASELINE_SIMULATED"
                n_pts = 100
                period_s = 60.0 / spm_val
                dt_s = period_s / n_pts
                positions = [round((stroke_in / 2.0) * (1.0 - math.cos(2.0 * math.pi * i / n_pts)), 3) for i in range(n_pts)]
                loads = [round(12000.0 + 6000.0 * math.sin(2.0 * math.pi * i / n_pts), 2) for i in range(n_pts)]
                accels, timestamps = compute_acceleration_and_time(
                    positions, spm_val, base_timestamp_ms=1600000000000
                )
                currents, powers = compute_motor_electrical(
                    loads, positions, spm_val, motor_hp, motor_v, motor_rpm
                )

                for idx in range(n_pts):
                    s_row = {
                        "well_id": well_id,
                        "timestamp_ms": timestamps[idx],
                        "stroke_id": "STROKE-001",
                        "sample_index": idx,
                        "polished_rod_load_lbf": loads[idx],
                        "polished_rod_position_in": positions[idx],
                        "polished_rod_acceleration_m_s2": accels[idx],
                        "spm": spm_val,
                        "motor_current_a": currents[idx],
                        "motor_voltage_v": motor_v,
                        "motor_active_power_kw": powers[idx],
                        "tubing_pressure_psi": tubing_p,
                        "casing_pressure_psi": casing_p,
                        "flowline_pressure_psi": flowline_p,
                        "dynamic_fluid_level_ft": fluid_level,
                        "oil_rate_bpd": oil_bpd,
                        "water_rate_bpd": water_bpd,
                        "gas_rate_mscfd": gas_mscfd,
                        "pump_running": True,
                        "data_quality": data_quality_label,
                    }
                    sample_rows.append(s_row)

        # --- 7. Merge into Unified Dataset Rows (per sample) ---
        state_unified_rows = []
        for s_row in sample_rows:
            unified_row = dict(config_row)
            # update with sample attributes
            for k, v in s_row.items():
                unified_row[k] = v
            state_unified_rows.append(unified_row)
            all_states_unified_rows.append(unified_row)

        # --- 8. Write State Files ---
        # 8a. Single unified CSV for the state
        unified_csv_path = OUT_DIR / f"{state_id}.csv"
        with open(unified_csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=UNIFIED_COLUMNS)
            writer.writeheader()
            writer.writerows(state_unified_rows)

        # 8b. Single well configuration CSV (33 columns)
        config_csv_path = OUT_DIR / f"{state_id}_well_configuration.csv"
        with open(config_csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CONFIG_COLUMNS)
            writer.writeheader()
            writer.writerow(config_row)

        # 8c. MQTT telemetry CSV (20 columns)
        mqtt_csv_path = OUT_DIR / f"{state_id}_mqtt_telemetry.csv"
        with open(mqtt_csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=MQTT_COLUMNS)
            writer.writeheader()
            writer.writerows(sample_rows)

        # 8d. Excel Workbook for state
        state_wb_path = OUT_DIR / f"{state_id}.xlsx"
        wb = openpyxl.Workbook()
        # Sheet 1: Unified
        ws_uni = wb.active
        ws_uni.title = "Unified_Dataset"
        ws_uni.append(UNIFIED_COLUMNS)
        for r in state_unified_rows:
            ws_uni.append([r.get(c) for c in UNIFIED_COLUMNS])

        # Sheet 2: Well Configuration
        ws_cfg = wb.create_sheet(title="Well_Configuration")
        ws_cfg.append(CONFIG_COLUMNS)
        ws_cfg.append([config_row.get(c) for c in CONFIG_COLUMNS])

        # Sheet 3: MQTT Telemetry
        ws_mq = wb.create_sheet(title="MQTT_Telemetry")
        ws_mq.append(MQTT_COLUMNS)
        for r in sample_rows:
            ws_mq.append([r.get(c) for c in MQTT_COLUMNS])

        wb.save(state_wb_path)

        catalog_summary_rows.append({
            "state_id": state_id,
            "state_name": state_name,
            "well_id": well_id,
            "fault_mechanism": fault_mech,
            "samples_count": len(sample_rows),
            "data_quality": data_quality_label,
            "spm": spm_val,
            "stroke_length_in": stroke_in,
            "pump_depth_ft": intake_depth,
            "motor_hp": motor_hp,
            "csv_file": f"{state_id}.csv",
            "xlsx_file": f"{state_id}.xlsx",
        })

    # --- 9. Write Global Master Datasets ---
    print("Writing global consolidated master datasets...")
    # Master Unified CSV
    master_uni_path = OUT_DIR / "MASTER_ALL_STATES_UNIFIED.csv"
    with open(master_uni_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=UNIFIED_COLUMNS)
        writer.writeheader()
        writer.writerows(all_states_unified_rows)

    # Master Configuration CSV (96 rows, 33 columns)
    master_cfg_path = OUT_DIR / "MASTER_ALL_STATES_CONFIGURATION.csv"
    with open(master_cfg_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CONFIG_COLUMNS)
        writer.writeheader()
        writer.writerows(all_states_config_rows)

    # Catalog Summary CSV
    catalog_path = OUT_DIR / "DATASET_CATALOG_SUMMARY.csv"
    with open(catalog_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(catalog_summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(catalog_summary_rows)

    print(f"Successfully generated datasets for all {len(matrix)} states in {OUT_DIR}!")
    print(f"Total unified sample rows across all states: {len(all_states_unified_rows)}")


if __name__ == "__main__":
    build_all_state_datasets()
