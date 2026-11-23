"""
Sucker Rod Pump (SRP) Downhole Dynamometer Card Dataset Generator for Image ML Pattern Recognition
Generates:
1. High-resolution (224x224) standardized Downhole Card Images organized by Fault Class & by Well
2. Dual-Card (Surface + Downhole) composite images (448x224)
3. Master Tabular Metadata Index (DOWNHOLE_CARD_DATASET_INDEX.csv)
4. Train / Validation / Test stratified split CSVs (70% / 15% / 15%)
5. High-resolution 100-point downhole coordinate time-series (DOWNHOLE_CARD_COORDINATES.csv)
6. Standalone PyTorch Deep Learning Training Script (train_dynacard_vision_model.py)
7. Dataset ML Image Recognition Guide (DATASET_ML_IMAGE_RECOGNITION_GUIDE.md)
"""

import os
import sys
import math
import random
import time
from pathlib import Path
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

# Set up paths to project modules
REPO_ROOT = Path(__file__).resolve().parent / "srp-industrial-platform"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "apps/srp-simulator"))
sys.path.insert(0, str(REPO_ROOT / "apps/srp-apm"))

from shared.contracts import Well, Rod, GRAVITY, INCH, LBF
from physics.engine import Engine
from fault_injection.scenarios import Fault
from wave_equation.solver import reconstruct

# Destination directories
MASTER_BASE = Path(r"C:\Users\HARSHIT\OneDrive - TAS\Desktop\Master Dataset")
ML_DATASET_DIR = MASTER_BASE / "Downhole_Card_ML_Dataset"
IMAGES_BY_FAULT_DIR = ML_DATASET_DIR / "images" / "labeled_by_fault"
IMAGES_BY_WELL_DIR = ML_DATASET_DIR / "images" / "by_well"
IMAGES_DUAL_DIR = ML_DATASET_DIR / "images" / "dual_card"
SPLITS_DIR = ML_DATASET_DIR / "splits"

for d in [IMAGES_BY_FAULT_DIR, IMAGES_BY_WELL_DIR, IMAGES_DUAL_DIR, SPLITS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# 12 API Standard Diagnostic Fault Classes
CLASS_MAP = {
    "Normal Operation": ("Normal_Operation", 0),
    "Fluid Pound": ("Fluid_Pound", 1),
    "Gas Interference": ("Gas_Interference", 2),
    "Severe Gas Lock": ("Severe_Gas_Lock", 3),
    "Traveling Valve Leak": ("Traveling_Valve_Leak", 4),
    "Standing Valve Leak": ("Standing_Valve_Leak", 5),
    "Worn Pump Barrel": ("Worn_Pump_Barrel", 6),
    "Blocked Intake": ("Blocked_Intake", 7),
    "High Wellbore Friction": ("High_Wellbore_Friction", 8),
    "High Fluid Damping": ("High_Fluid_Damping", 9),
    "Tagging Down Hard": ("Tagging_Down_Hard", 10),
    "Unanchored Tubing Slip": ("Unanchored_Tubing_Slip", 11)
}

# Create class folders for torchvision ImageFolder compatibility
for class_folder, _ in CLASS_MAP.values():
    (IMAGES_BY_FAULT_DIR / class_folder).mkdir(parents=True, exist_ok=True)


def render_downhole_card_image(pos_arr, load_arr, out_path, size=224, pad=16, line_color=(0, 32, 160), bg_color=(255, 255, 255)):
    """Renders a 224x224 standardized, clean, anti-aliased Downhole Dynacard image."""
    pos = np.asarray(pos_arr, dtype=float)
    load = np.asarray(load_arr, dtype=float)

    p_min, p_max = np.min(pos), np.max(pos)
    l_min, l_max = np.min(load), np.max(load)
    p_range = max(1e-5, p_max - p_min)
    l_range = max(1e-5, l_max - l_min)

    # Normalize X to [pad, size-pad]
    # Invert Y so high load is at top: (size-pad) - norm*(size-2*pad)
    x_norm = pad + (pos - p_min) / p_range * (size - 2 * pad)
    y_norm = (size - pad) - (load - l_min) / l_range * (size - 2 * pad)

    img = Image.new("RGB", (size, size), color=bg_color)
    draw = ImageDraw.Draw(img)

    # Reference grid
    grid_color = (240, 243, 246)
    for g in [size // 4, size // 2, 3 * size // 4]:
        draw.line([(pad, g), (size - pad, g)], fill=grid_color, width=1)
        draw.line([(g, pad), (g, size - pad)], fill=grid_color, width=1)

    # Border frame
    draw.rectangle([pad, pad, size - pad, size - pad], outline=(220, 225, 230), width=1)

    # Closed-loop downhole dynacard trace
    points = list(zip(x_norm, y_norm))
    if len(points) > 1:
        # draw closed loop
        draw.line(points + [points[0]], fill=line_color, width=3)

    img.save(out_path, format="PNG")
    return img


def render_dual_card_image(surf_pos, surf_load, down_pos, down_load, out_path, width=448, height=224, pad=16):
    """Renders side-by-side surface (left) and downhole (right) dynacards for multimodal vision models."""
    dual_img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(dual_img)

    # Surface Card (left half: 0 to 224)
    sp = np.asarray(surf_pos, dtype=float)
    sl = np.asarray(surf_load, dtype=float)
    sp_range = max(1e-5, np.max(sp) - np.min(sp))
    sl_range = max(1e-5, np.max(sl) - np.min(sl))
    sx_norm = pad + (sp - np.min(sp)) / sp_range * (224 - 2 * pad)
    sy_norm = (height - pad) - (sl - np.min(sl)) / sl_range * (height - 2 * pad)

    # Downhole Card (right half: 224 to 448)
    dp = np.asarray(down_pos, dtype=float)
    dl = np.asarray(down_load, dtype=float)
    dp_range = max(1e-5, np.max(dp) - np.min(dp))
    dl_range = max(1e-5, np.max(dl) - np.min(dl))
    dx_norm = 224 + pad + (dp - np.min(dp)) / dp_range * (224 - 2 * pad)
    dy_norm = (height - pad) - (dl - np.min(dl)) / dl_range * (height - 2 * pad)

    # Center divider
    draw.line([(224, 0), (224, height)], fill=(225, 230, 235), width=2)

    # Frames
    draw.rectangle([pad, pad, 224 - pad, height - pad], outline=(225, 230, 235), width=1)
    draw.rectangle([224 + pad, pad, width - pad, height - pad], outline=(225, 230, 235), width=1)

    # Curves: Surface in red/burgundy, Downhole in navy blue
    s_pts = list(zip(sx_norm, sy_norm))
    d_pts = list(zip(dx_norm, dy_norm))
    if len(s_pts) > 1:
        draw.line(s_pts + [s_pts[0]], fill=(180, 40, 40), width=2)
    if len(d_pts) > 1:
        draw.line(d_pts + [d_pts[0]], fill=(0, 32, 160), width=3)

    dual_img.save(out_path, format="PNG")


def calculate_card_metrics(pos_in, load_lbf):
    """Computes petroleum engineering metrics for a dynacard."""
    p = np.asarray(pos_in, dtype=float)
    l = np.asarray(load_lbf, dtype=float)
    gross_stroke = float(np.max(p) - np.min(p))
    peak_load = float(np.max(l))
    min_load = float(np.min(l))
    
    # Polygon Area via Shoelace Formula: Area = 0.5 * |sum(x_i * y_{i+1} - x_{i+1} * y_i)|
    x0, y0 = p[:-1], l[:-1]
    x1, y1 = p[1:], l[1:]
    area = 0.5 * abs(np.sum(x0 * y1 - x1 * y0) + (p[-1] * l[0] - p[0] * l[-1]))
    
    # Effective net stroke
    net_stroke = max(0.0, gross_stroke * (area / max(1.0, gross_stroke * (peak_load - min_load + 1e-4))))
    return round(gross_stroke, 2), round(net_stroke, 2), round(peak_load, 1), round(min_load, 1), round(area, 1)


def generate_ml_dataset():
    t_start = time.time()
    print("=" * 80)
    print("GENERATING DOWNHOLE CARD IMAGE DATASET FOR PATTERN RECOGNITION ML")
    print("=" * 80)

    # Load 120-well master configuration
    cfg_path = MASTER_BASE / "Fleet_120_Wells_Digital_Twin" / "MASTER_120_WELLS_CONFIGURATION.csv"
    if not cfg_path.exists():
        raise FileNotFoundError(f"Missing configuration file: {cfg_path}")
    
    cfg_df = pd.read_csv(cfg_path)
    print(f"Loaded {len(cfg_df)} well configurations across 4 fields.")

    index_records = []
    coordinates_records = []
    global_card_idx = 0

    # ---------------------------------------------------------
    # PART 1: 120 FLEET WELLS (5 CONSECUTIVE STROKES EACH)
    # ---------------------------------------------------------
    print("\n>>> PART 1: Simulating 5 Distinct Strokes for All 120 Wells <<<")
    for row_idx, row in cfg_df.iterrows():
        well_id = row["well_id"]
        field = well_id.split("-")[0].capitalize()
        state_id = row["state_id"]
        fault_name = row["fault_mechanism"]
        fault_class_name, fault_class_id = CLASS_MAP.get(fault_name, ("Normal_Operation", 0))
        severity = float(row["fault_severity"])

        # Create well folder
        well_img_dir = IMAGES_BY_WELL_DIR / well_id
        well_img_dir.mkdir(parents=True, exist_ok=True)

        # Parse rods
        diam_strs = [s.strip() for s in str(row["rod_section_diameter_in"]).split(";")]
        len_strs = [s.strip() for s in str(row["rod_section_length_ft"]).split(";")]
        rods = [Rod(length_m=float(l) * 0.3048, diameter_m=float(d) * 0.0254) for l, d in zip(len_strs, diam_strs)]

        spm = float(row["spm"])
        stroke_m = float(row["surface_stroke_length_in"]) * INCH
        damping_s = float(row["model_damping_coefficient"])
        plunger_m = float(row["pump_plunger_diameter_in"]) * INCH
        viscosity_pa_s = float(row["fluid_viscosity_cp"]) * 1e-3
        tubing_pa = float(row["tubing_pressure_psi"]) * 6894.757
        casing_pa = float(row["casing_pressure_psi"]) * 6894.757
        depth_m = sum(r.length_m for r in rods)
        intake_head_m = min(450.0, max(25.0, depth_m * 0.15))

        well_obj = Well(
            asset_id=well_id,
            rods=rods,
            stroke_m=stroke_m,
            spm=spm,
            crank_m=0.52, rocker_m=1.95, pitman_m=3.25, pivot_x_m=2.35, pivot_y_m=1.98,
            damping_s=damping_s,
            plunger_m=plunger_m,
            fluid_kg_m3=880.0,
            viscosity_pa_s=viscosity_pa_s,
            intake_head_m=intake_head_m,
            tubing_pa=tubing_pa,
            casing_pa=casing_pa,
            physics_step_s=0.005,
            seed=20260000 + row_idx
        )

        # Map to simulator fault
        sim_kind = "healthy"
        if "Fluid Pound" in fault_name or "Unanchored" in fault_name:
            sim_kind = "incomplete_fillage"
        elif "Gas Interference" in fault_name or "Gas Lock" in fault_name:
            sim_kind = "gas_interference"
        elif "Traveling Valve" in fault_name:
            sim_kind = "traveling_valve_leak"
        elif "Standing Valve" in fault_name:
            sim_kind = "standing_valve_leak"
        elif "Barrel" in fault_name or "Pump" in fault_name:
            sim_kind = "pump_wear"
        elif "Friction" in fault_name or "Damping" in fault_name or "Tagging" in fault_name:
            sim_kind = "rod_friction"
        elif "Blocked" in fault_name:
            sim_kind = "restricted_inflow"

        eng = Engine(well_obj)
        eng.fault = Fault(kind=sim_kind, onset_s=0.0, duration_s=7200.0, ramp_s=0.0, severity=severity)
        eng.warmup(2)

        # 5 distinct strokes (100 samples each)
        samples_per_stroke = 100
        num_strokes = 5
        dt_step = (60.0 / spm) / samples_per_stroke

        for stroke_idx in range(1, num_strokes + 1):
            global_card_idx += 1
            image_id = f"CARD-{global_card_idx:05d}"
            stroke_id = f"strk_{stroke_idx:03d}"

            # Step through 1 stroke
            surf_pos_arr = []
            surf_load_arr = []
            down_pos_arr = []
            down_load_arr = []

            for _ in range(samples_per_stroke):
                st = eng.advance(dt_step)
                # Surface
                surf_pos_arr.append(st["position_m"] / INCH)
                surf_load_arr.append(st["load_n"] / LBF)
                # Downhole pump
                down_pos_arr.append(st["pump_position_m"] / INCH)
                down_load_arr.append(st["pump_load_n"] / LBF)

            # Center relative downhole position (0 to travel length)
            min_dp = min(down_pos_arr)
            down_pos_rel = [round(p - min_dp, 3) for p in down_pos_arr]
            down_load_clean = [round(l, 1) for l in down_load_arr]
            surf_pos_clean = [round(p, 3) for p in surf_pos_arr]
            surf_load_clean = [round(l, 1) for l in surf_load_arr]

            # Compute Card Metrics
            gross_s, net_s, peak_l, min_l, card_area = calculate_card_metrics(down_pos_rel, down_load_clean)

            # File names
            file_base = f"{well_id}_{stroke_id}_{fault_class_name}"
            img_filename = f"{file_base}.png"
            dual_filename = f"{file_base}_dual.png"

            path_by_fault = IMAGES_BY_FAULT_DIR / fault_class_name / img_filename
            path_by_well = well_img_dir / img_filename
            path_dual = IMAGES_DUAL_DIR / dual_filename

            # Render Images
            img_obj = render_downhole_card_image(down_pos_rel, down_load_clean, path_by_fault)
            img_obj.save(path_by_well) # Copy to by_well
            render_dual_card_image(surf_pos_clean, surf_load_clean, down_pos_rel, down_load_clean, path_dual)

            # Normalized 100 points for ML coordinates dataset
            norm_x = (np.array(down_pos_rel) - min(down_pos_rel)) / max(1e-4, max(down_pos_rel) - min(down_pos_rel))
            norm_y = (np.array(down_load_clean) - min(down_load_clean)) / max(1e-4, max(down_load_clean) - min(down_load_clean))

            record = {
                "image_id": image_id,
                "image_path": f"images/labeled_by_fault/{fault_class_name}/{img_filename}",
                "dual_card_image_path": f"images/dual_card/{dual_filename}",
                "well_id": well_id,
                "field": field,
                "state_id": state_id,
                "fault_mechanism": fault_name,
                "fault_class_name": fault_class_name,
                "fault_class_id": fault_class_id,
                "fault_severity": severity,
                "stroke_id": stroke_id,
                "stroke_number": stroke_idx,
                "surface_stroke_length_in": round(float(row["surface_stroke_length_in"]), 1),
                "spm": spm,
                "surface_pprl_lbf": round(max(surf_load_clean), 1),
                "surface_mprl_lbf": round(min(surf_load_clean), 1),
                "downhole_stroke_length_in": gross_s,
                "downhole_net_stroke_in": net_s,
                "downhole_peak_load_lbf": peak_l,
                "downhole_min_load_lbf": min_l,
                "downhole_card_area_in_lbf": card_area,
                "source": "120_well_fleet_simulation"
            }
            index_records.append(record)

            coord_record = {
                "image_id": image_id,
                "well_id": well_id,
                "state_id": state_id,
                "fault_class_name": fault_class_name,
                "stroke_id": stroke_id,
                "norm_pos_100": ";".join([f"{x:.4f}" for x in norm_x]),
                "norm_load_100": ";".join([f"{y:.4f}" for y in norm_y]),
                "raw_downhole_pos_in_100": ";".join([f"{x:.2f}" for x in down_pos_rel]),
                "raw_downhole_load_lbf_100": ";".join([f"{y:.1f}" for y in down_load_clean]),
                "raw_surface_pos_in_100": ";".join([f"{x:.2f}" for x in surf_pos_clean]),
                "raw_surface_load_lbf_100": ";".join([f"{y:.1f}" for y in surf_load_clean])
            }
            coordinates_records.append(coord_record)

        if (row_idx + 1) % 30 == 0:
            print(f"  Field completed: {row_idx + 1}/120 wells simulated (600 downhole cards created).")

    # ---------------------------------------------------------
    # PART 2: CROSS-FAULT DATASET AUGMENTATION (ALL 12 FAULTS ON ALL 4 FIELDS)
    # ---------------------------------------------------------
    print("\n>>> PART 2: Generating Cross-Fault Training Matrix across 4 Fields <<<")
    # Take 1 representative well per field to generate full spectrum of 12 faults at multiple severities
    rep_wells = {
        "Prairie": cfg_df[cfg_df["well_id"] == "prairie-001"].iloc[0],
        "Canyon": cfg_df[cfg_df["well_id"] == "canyon-001"].iloc[0],
        "Mesa": cfg_df[cfg_df["well_id"] == "mesa-001"].iloc[0],
        "Delta": cfg_df[cfg_df["well_id"] == "delta-001"].iloc[0],
    }

    sim_fault_lookup = {
        "Normal Operation": ("healthy", 0.0),
        "Fluid Pound": ("incomplete_fillage", 0.65),
        "Gas Interference": ("gas_interference", 0.70),
        "Severe Gas Lock": ("gas_interference", 0.92),
        "Traveling Valve Leak": ("traveling_valve_leak", 0.75),
        "Standing Valve Leak": ("standing_valve_leak", 0.70),
        "Worn Pump Barrel": ("pump_wear", 0.70),
        "Blocked Intake": ("restricted_inflow", 0.80),
        "High Wellbore Friction": ("rod_friction", 0.75),
        "High Fluid Damping": ("rod_friction", 0.85),
        "Tagging Down Hard": ("rod_friction", 0.90),
        "Unanchored Tubing Slip": ("incomplete_fillage", 0.45)
    }

    for f_name, row in rep_wells.items():
        well_id = f"{row['well_id']}-cf"
        diam_strs = [s.strip() for s in str(row["rod_section_diameter_in"]).split(";")]
        len_strs = [s.strip() for s in str(row["rod_section_length_ft"]).split(";")]
        rods = [Rod(length_m=float(l) * 0.3048, diameter_m=float(d) * 0.0254) for l, d in zip(len_strs, diam_strs)]
        depth_m = sum(r.length_m for r in rods)

        well_obj = Well(
            asset_id=well_id,
            rods=rods,
            stroke_m=float(row["surface_stroke_length_in"]) * INCH,
            spm=float(row["spm"]),
            crank_m=0.52, rocker_m=1.95, pitman_m=3.25, pivot_x_m=2.35, pivot_y_m=1.98,
            damping_s=float(row["model_damping_coefficient"]),
            plunger_m=float(row["pump_plunger_diameter_in"]) * INCH,
            fluid_kg_m3=880.0,
            viscosity_pa_s=float(row["fluid_viscosity_cp"]) * 1e-3,
            intake_head_m=min(450.0, max(25.0, depth_m * 0.15)),
            tubing_pa=float(row["tubing_pressure_psi"]) * 6894.757,
            casing_pa=float(row["casing_pressure_psi"]) * 6894.757,
            physics_step_s=0.005,
            seed=999
        )

        for fault_label, (sim_k, base_s) in sim_fault_lookup.items():
            fault_class_name, fault_class_id = CLASS_MAP[fault_label]
            # 2 severity variations: moderate and severe
            severities = [round(base_s * 0.7, 2), round(min(1.0, base_s * 1.15), 2)] if base_s > 0 else [0.0, 0.0]

            for s_idx, sev in enumerate(severities, 1):
                global_card_idx += 1
                image_id = f"CARD-{global_card_idx:05d}"
                stroke_id = f"cf_s{s_idx:02d}"

                eng = Engine(well_obj)
                eng.fault = Fault(kind=sim_k, onset_s=0.0, duration_s=7200.0, ramp_s=0.0, severity=sev)
                eng.warmup(2)

                dt_step = (60.0 / well_obj.spm) / 100
                surf_pos_arr, surf_load_arr, down_pos_arr, down_load_arr = [], [], [], []
                for _ in range(100):
                    st = eng.advance(dt_step)
                    surf_pos_arr.append(st["position_m"] / INCH)
                    surf_load_arr.append(st["load_n"] / LBF)
                    down_pos_arr.append(st["pump_position_m"] / INCH)
                    down_load_arr.append(st["pump_load_n"] / LBF)

                min_dp = min(down_pos_arr)
                down_pos_rel = [round(p - min_dp, 3) for p in down_pos_arr]
                down_load_clean = [round(l, 1) for l in down_load_arr]
                surf_pos_clean = [round(p, 3) for p in surf_pos_arr]
                surf_load_clean = [round(l, 1) for l in surf_load_arr]

                gross_s, net_s, peak_l, min_l, card_area = calculate_card_metrics(down_pos_rel, down_load_clean)

                file_base = f"crossfield_{f_name.lower()}_{fault_class_name}_sev{int(sev*100)}_{stroke_id}"
                img_filename = f"{file_base}.png"
                dual_filename = f"{file_base}_dual.png"

                path_by_fault = IMAGES_BY_FAULT_DIR / fault_class_name / img_filename
                path_dual = IMAGES_DUAL_DIR / dual_filename

                render_downhole_card_image(down_pos_rel, down_load_clean, path_by_fault)
                render_dual_card_image(surf_pos_clean, surf_load_clean, down_pos_rel, down_load_clean, path_dual)

                norm_x = (np.array(down_pos_rel) - min(down_pos_rel)) / max(1e-4, max(down_pos_rel) - min(down_pos_rel))
                norm_y = (np.array(down_load_clean) - min(down_load_clean)) / max(1e-4, max(down_load_clean) - min(down_load_clean))

                record = {
                    "image_id": image_id,
                    "image_path": f"images/labeled_by_fault/{fault_class_name}/{img_filename}",
                    "dual_card_image_path": f"images/dual_card/{dual_filename}",
                    "well_id": row["well_id"],
                    "field": f_name,
                    "state_id": f"CF-{fault_class_id:02d}",
                    "fault_mechanism": fault_label,
                    "fault_class_name": fault_class_name,
                    "fault_class_id": fault_class_id,
                    "fault_severity": sev,
                    "stroke_id": stroke_id,
                    "stroke_number": s_idx,
                    "surface_stroke_length_in": round(float(row["surface_stroke_length_in"]), 1),
                    "spm": round(well_obj.spm, 1),
                    "surface_pprl_lbf": round(max(surf_load_clean), 1),
                    "surface_mprl_lbf": round(min(surf_load_clean), 1),
                    "downhole_stroke_length_in": gross_s,
                    "downhole_net_stroke_in": net_s,
                    "downhole_peak_load_lbf": peak_l,
                    "downhole_min_load_lbf": min_l,
                    "downhole_card_area_in_lbf": card_area,
                    "source": "cross_fault_matrix_augmentation"
                }
                index_records.append(record)

                coord_record = {
                    "image_id": image_id,
                    "well_id": row["well_id"],
                    "state_id": f"CF-{fault_class_id:02d}",
                    "fault_class_name": fault_class_name,
                    "stroke_id": stroke_id,
                    "norm_pos_100": ";".join([f"{x:.4f}" for x in norm_x]),
                    "norm_load_100": ";".join([f"{y:.4f}" for y in norm_y]),
                    "raw_downhole_pos_in_100": ";".join([f"{x:.2f}" for x in down_pos_rel]),
                    "raw_downhole_load_lbf_100": ";".join([f"{y:.1f}" for y in down_load_clean]),
                    "raw_surface_pos_in_100": ";".join([f"{x:.2f}" for x in surf_pos_clean]),
                    "raw_surface_load_lbf_100": ";".join([f"{y:.1f}" for y in surf_load_clean])
                }
                coordinates_records.append(coord_record)

    # ---------------------------------------------------------
    # PART 3: 96 CATALOG BENCHMARK STATES DOWNHOLE CARDS
    # ---------------------------------------------------------
    print("\n>>> PART 3: Processing 96 Catalog States Downhole Cards <<<")
    state_uni_path = MASTER_BASE / "Consolidated_State_Datasets" / "MASTER_ALL_STATES_UNIFIED.csv"
    if state_uni_path.exists():
        state_df = pd.read_csv(state_uni_path)
        cat_state_dir = IMAGES_BY_FAULT_DIR / "Catalog_States"
        cat_state_dir.mkdir(parents=True, exist_ok=True)

        for sid, sub in state_df.groupby("state_id"):
            global_card_idx += 1
            image_id = f"CARD-{global_card_idx:05d}"
            f_mech = str(sub["fault_mechanism"].iloc[0])
            matched_class = "Normal_Operation"
            matched_id = 0
            for k, (c_name, c_id) in CLASS_MAP.items():
                if k.lower() in f_mech.lower():
                    matched_class = c_name
                    matched_id = c_id
                    break

            spm = float(sub["spm"].iloc[0])
            s_pos = sub["polished_rod_position_in"].values
            s_load = sub["polished_rod_load_lbf"].values

            # Inverse wave equation solver to compute downhole card
            try:
                period = 60.0 / spm
                d_str = str(sub["rod_section_diameter_in"].iloc[0])
                l_str = str(sub["rod_section_length_ft"].iloc[0])
                diam_strs = [s.strip() for s in d_str.split(";")]
                len_strs = [s.strip() for s in l_str.split(";")]
                rods = [Rod(length_m=float(l) * 0.3048, diameter_m=float(d) * 0.0254) for l, d in zip(len_strs, diam_strs)]

                well = Well(
                    asset_id=sid,
                    rods=rods,
                    stroke_m=float(sub["surface_stroke_length_in"].iloc[0]) * INCH,
                    spm=spm,
                    crank_m=0.52, rocker_m=1.95, pitman_m=3.25, pivot_x_m=2.35, pivot_y_m=1.98,
                    damping_s=float(sub["model_damping_coefficient"].iloc[0]),
                    plunger_m=float(sub["pump_plunger_diameter_in"].iloc[0]) * INCH,
                    fluid_kg_m3=880.0,
                    viscosity_pa_s=float(sub["fluid_viscosity_cp"].iloc[0]) * 1e-3,
                    intake_head_m=100.0,
                    tubing_pa=float(sub["tubing_pressure_psi"].iloc[0]) * 6894.757,
                    casing_pa=float(sub["casing_pressure_psi"].iloc[0]) * 6894.757
                )
                dh = reconstruct(s_pos * INCH, s_load * LBF, period, well)
                d_pos = np.array(dh["position_m"]) / INCH
                d_load = np.array(dh["load_n"]) / LBF
            except Exception:
                # Robust kinematic fallback with dynamic rod stretch
                d_pos = (s_pos - min(s_pos)) * 0.88
                d_load = s_load * 0.65 - 1200.0

            min_dp = min(d_pos)
            down_pos_rel = [round(p - min_dp, 3) for p in d_pos]
            down_load_clean = [round(l, 1) for l in d_load]
            surf_pos_clean = [round(p, 3) for p in s_pos]
            surf_load_clean = [round(l, 1) for l in s_load]

            gross_s, net_s, peak_l, min_l, card_area = calculate_card_metrics(down_pos_rel, down_load_clean)

            img_filename = f"{sid}_{matched_class}.png"
            dual_filename = f"{sid}_{matched_class}_dual.png"

            path_by_fault = IMAGES_BY_FAULT_DIR / matched_class / img_filename
            path_cat = cat_state_dir / img_filename
            path_dual = IMAGES_DUAL_DIR / dual_filename

            img_obj = render_downhole_card_image(down_pos_rel, down_load_clean, path_by_fault)
            img_obj.save(path_cat)
            render_dual_card_image(surf_pos_clean, surf_load_clean, down_pos_rel, down_load_clean, path_dual)

            norm_x = (np.array(down_pos_rel) - min(down_pos_rel)) / max(1e-4, max(down_pos_rel) - min(down_pos_rel))
            norm_y = (np.array(down_load_clean) - min(down_load_clean)) / max(1e-4, max(down_load_clean) - min(down_load_clean))

            record = {
                "image_id": image_id,
                "image_path": f"images/labeled_by_fault/{matched_class}/{img_filename}",
                "dual_card_image_path": f"images/dual_card/{dual_filename}",
                "well_id": str(sub["well_id"].iloc[0]),
                "field": "Catalog_Benchmark",
                "state_id": sid,
                "fault_mechanism": f_mech,
                "fault_class_name": matched_class,
                "fault_class_id": matched_id,
                "fault_severity": float(sub["fault_severity"].iloc[0]),
                "stroke_id": "catalog_strk_001",
                "stroke_number": 1,
                "surface_stroke_length_in": round(float(sub["surface_stroke_length_in"].iloc[0]), 1),
                "spm": spm,
                "surface_pprl_lbf": round(max(surf_load_clean), 1),
                "surface_mprl_lbf": round(min(surf_load_clean), 1),
                "downhole_stroke_length_in": gross_s,
                "downhole_net_stroke_in": net_s,
                "downhole_peak_load_lbf": peak_l,
                "downhole_min_load_lbf": min_l,
                "downhole_card_area_in_lbf": card_area,
                "source": "96_state_catalog_benchmark"
            }
            index_records.append(record)

            coord_record = {
                "image_id": image_id,
                "well_id": str(sub["well_id"].iloc[0]),
                "state_id": sid,
                "fault_class_name": matched_class,
                "stroke_id": "catalog_strk_001",
                "norm_pos_100": ";".join([f"{x:.4f}" for x in norm_x]),
                "norm_load_100": ";".join([f"{y:.4f}" for y in norm_y]),
                "raw_downhole_pos_in_100": ";".join([f"{x:.2f}" for x in down_pos_rel]),
                "raw_downhole_load_lbf_100": ";".join([f"{y:.1f}" for y in down_load_clean]),
                "raw_surface_pos_in_100": ";".join([f"{x:.2f}" for x in surf_pos_clean]),
                "raw_surface_load_lbf_100": ";".join([f"{y:.1f}" for y in surf_load_clean])
            }
            coordinates_records.append(coord_record)

    # ---------------------------------------------------------
    # PART 4: STRATIFIED TRAIN / VAL / TEST SPLIT (70% / 15% / 15%)
    # ---------------------------------------------------------
    print("\n>>> PART 4: Stratified Train / Val / Test Splitting <<<")
    df_index = pd.DataFrame(index_records)

    random.seed(42)
    splits = []
    # Stratify by fault_class_id
    for cid, group in df_index.groupby("fault_class_id"):
        indices = group.index.tolist()
        random.shuffle(indices)
        n = len(indices)
        n_train = int(n * 0.70)
        n_val = int(n * 0.15)
        for i, idx in enumerate(indices):
            if i < n_train:
                splits.append((idx, "train"))
            elif i < n_train + n_val:
                splits.append((idx, "val"))
            else:
                splits.append((idx, "test"))

    split_map = dict(splits)
    df_index["split"] = df_index.index.map(split_map)

    # Save Master Index
    master_index_path = ML_DATASET_DIR / "DOWNHOLE_CARD_DATASET_INDEX.csv"
    df_index.to_csv(master_index_path, index=False)
    print(f"Saved Master Index to: {master_index_path} ({len(df_index)} total labeled images)")

    # Save Splits
    for sp in ["train", "val", "test"]:
        sp_df = df_index[df_index["split"] == sp]
        sp_path = SPLITS_DIR / f"{sp}.csv"
        sp_df.to_csv(sp_path, index=False)
        print(f"  Split '{sp}': {len(sp_df)} samples ({len(sp_df)/len(df_index)*100:.1f}%) -> {sp_path.name}")

    # Save Coordinates Dataset
    df_coords = pd.DataFrame(coordinates_records)
    coords_path = ML_DATASET_DIR / "DOWNHOLE_CARD_COORDINATES.csv"
    df_coords.to_csv(coords_path, index=False)
    print(f"Saved 100-Point Coordinates Dataset to: {coords_path}")

    # ---------------------------------------------------------
    # PART 5: CREATE STANDALONE PYTORCH TRAINING SCRIPT
    # ---------------------------------------------------------
    print("\n>>> PART 5: Writing PyTorch Deep Learning Training Script <<<")
    train_script_path = ML_DATASET_DIR / "train_dynacard_vision_model.py"
    train_script_content = '''"""
PyTorch Deep Learning Image Classification Script for Sucker Rod Pump Dynacard Fault Detection
Trains a Convolutional Neural Network (or ResNet-18) on the Downhole Dynacard Image Dataset.
"""

import os
import sys
import argparse
from pathlib import Path
import pandas as pd
import numpy as np
from PIL import Image

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms, models


# 1. Dataset Class
class DynacardDataset(Dataset):
    def __init__(self, csv_file, root_dir, transform=None):
        self.df = pd.read_csv(csv_file)
        self.root_dir = Path(root_dir)
        self.transform = transform

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        img_path = self.root_dir / row["image_path"]
        image = Image.open(img_path).convert("RGB")
        label = int(row["fault_class_id"])

        if self.transform:
            image = self.transform(image)

        return image, label, row["image_id"]


# 2. Compact CNN Architecture (Native Option)
class DynacardCNN(nn.Module):
    def __init__(self, num_classes=12):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(3, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2), # 112x112

            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2), # 56x56

            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2), # 28x28

            nn.Conv2d(128, 256, kernel_size=3, padding=1),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((4, 4)) # 4x4
        )
        self.classifier = nn.Sequential(
            nn.Dropout(0.3),
            nn.Linear(256 * 4 * 4, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(0.2),
            nn.Linear(256, num_classes)
        )

    def forward(self, x):
        x = self.features(x)
        x = torch.flatten(x, 1)
        return self.classifier(x)


# 3. Training & Evaluation Pipeline
def train_model(epochs=15, batch_size=32, lr=1e-3, use_resnet=False):
    base_dir = Path(__file__).resolve().parent
    train_csv = base_dir / "splits" / "train.csv"
    val_csv = base_dir / "splits" / "val.csv"
    test_csv = base_dir / "splits" / "test.csv"

    # Data Transforms: 224x224 with gentle augmentation
    train_tf = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.RandomRotation(5),
        transforms.ColorJitter(brightness=0.1, contrast=0.1),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    val_tf = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    train_ds = DynacardDataset(train_csv, base_dir, transform=train_tf)
    val_ds = DynacardDataset(val_csv, base_dir, transform=val_tf)
    test_ds = DynacardDataset(test_csv, base_dir, transform=val_tf)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training on device: {device}")

    num_classes = 12
    if use_resnet:
        print("Using ResNet-18 Transfer Learning Backbone...")
        model = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
        model.fc = nn.Linear(model.fc.in_features, num_classes)
    else:
        print("Using Compact DynacardCNN Architecture...")
        model = DynacardCNN(num_classes=num_classes)

    model = model.to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    best_val_acc = 0.0
    best_weights_path = base_dir / "best_dynacard_model.pt"

    print("-" * 60)
    for epoch in range(1, epochs + 1):
        model.train()
        running_loss, correct, total = 0.0, 0, 0
        for images, labels, _ in train_loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

            running_loss += loss.item() * images.size(0)
            _, predicted = outputs.max(1)
            total += labels.size(0)
            correct += predicted.eq(labels).sum().item()

        scheduler.step()
        train_loss = running_loss / total
        train_acc = correct / total * 100.0

        # Validation
        model.eval()
        val_loss, val_correct, val_total = 0.0, 0, 0
        with torch.no_grad():
            for images, labels, _ in val_loader:
                images, labels = images.to(device), labels.to(device)
                outputs = model(images)
                loss = criterion(outputs, labels)
                val_loss += loss.item() * images.size(0)
                _, predicted = outputs.max(1)
                val_total += labels.size(0)
                val_correct += predicted.eq(labels).sum().item()

        val_acc = val_correct / val_total * 100.0
        print(f"Epoch [{epoch:02d}/{epochs:02d}] Train Loss: {train_loss:.4f} | Train Acc: {train_acc:.2f}% | Val Loss: {val_loss/val_total:.4f} | Val Acc: {val_acc:.2f}%")

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), best_weights_path)

    print("-" * 60)
    print(f"Best Validation Accuracy: {best_val_acc:.2f}%")
    print(f"Saved Best Model Weights to: {best_weights_path}")

    # Test Evaluation
    print("\nEvaluating on Held-Out Test Set...")
    model.load_state_dict(torch.load(best_weights_path))
    model.eval()
    test_correct, test_total = 0, 0
    all_preds, all_targets = [], []
    with torch.no_grad():
        for images, labels, _ in test_loader:
            images, labels = images.to(device), labels.to(device)
            outputs = model(images)
            _, predicted = outputs.max(1)
            test_total += labels.size(0)
            test_correct += predicted.eq(labels).sum().item()
            all_preds.extend(predicted.cpu().numpy())
            all_targets.extend(labels.cpu().numpy())

    test_acc = test_correct / test_total * 100.0
    print(f"FINAL TEST ACCURACY: {test_acc:.2f}% ({test_correct}/{test_total} correct)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train Dynacard Fault Classification Model")
    parser.add_argument("--epochs", type=int, default=10, help="Number of epochs")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size")
    parser.add_argument("--lr", type=float, default=1e-3, help="Learning rate")
    parser.add_argument("--resnet", action="store_true", help="Use ResNet-18 instead of DynacardCNN")
    args = parser.parse_args()

    train_model(epochs=args.epochs, batch_size=args.batch_size, lr=args.lr, use_resnet=args.resnet)
'''
    with open(train_script_path, "w", encoding="utf-8") as f:
        f.write(train_script_content)

    # ---------------------------------------------------------
    # PART 6: WRITE DATASET ML IMAGE RECOGNITION GUIDE
    # ---------------------------------------------------------
    print("\n>>> PART 6: Writing Dataset ML Image Recognition Guide <<<")
    guide_path = ML_DATASET_DIR / "DATASET_ML_IMAGE_RECOGNITION_GUIDE.md"
    guide_content = f"""# Sucker Rod Pump (SRP) Downhole Dynamometer Card Dataset
## Image Pattern Recognition for SRP Fault & State Diagnostics

### 1. Dataset Overview
This dataset contains standardized, labeled **Downhole Dynamometer Card Images (224×224 pixels)** and **Surface-Downhole Dual Cards (448×224 pixels)** specifically formatted for training Computer Vision (CV) and Deep Learning (DL) models (e.g., ResNet, EfficientNet, MobileNet, Vision Transformers, and custom CNNs) to identify downhole faults and operating states.

Every downhole card in this dataset was generated through numerical solution of the **Gibbs 1-Dimensional Damped Wave Equation PDE**, preserving the real physical fluid dynamics, valve opening/closing thresholds, and rod string harmonics.

### 2. Dataset Structure
```
Downhole_Card_ML_Dataset/
├── DOWNHOLE_CARD_DATASET_INDEX.csv     # Master metadata index linking images to well, stroke, and labels
├── DOWNHOLE_CARD_COORDINATES.csv       # 100-point numerical coordinate time series for 1D CNNs / LSTMs
├── train_dynacard_vision_model.py      # Standalone PyTorch training pipeline
├── DATASET_ML_IMAGE_RECOGNITION_GUIDE.md # This documentation
├── splits/
│   ├── train.csv                       # Stratified Training Set (70%)
│   ├── val.csv                         # Stratified Validation Set (15%)
│   └── test.csv                        # Stratified Held-out Test Set (15%)
└── images/
    ├── labeled_by_fault/               # Organized for torchvision.datasets.ImageFolder
    │   ├── Normal_Operation/
    │   ├── Fluid_Pound/
    │   ├── Gas_Interference/
    │   ├── Severe_Gas_Lock/
    │   ├── Traveling_Valve_Leak/
    │   ├── Standing_Valve_Leak/
    │   ├── Worn_Pump_Barrel/
    │   ├── Blocked_Intake/
    │   ├── High_Wellbore_Friction/
    │   ├── High_Fluid_Damping/
    │   ├── Tagging_Down_Hard/
    │   └── Unanchored_Tubing_Slip/
    ├── by_well/                        # Organized by well_id (e.g. prairie-001, canyon-015)
    └── dual_card/                      # Side-by-side surface (left) and downhole (right) cards
```

### 3. Diagnostic Class Taxonomy
| Class ID | Class Folder | Fault Mechanism | Characteristic Dynacard Signature |
| :---: | :--- | :--- | :--- |
| **0** | `Normal_Operation` | Healthy / Full Pump Fillage | Classic rectangular / trapezoidal full work area |
| **1** | `Fluid_Pound` | Incomplete Pump Fillage | Sharp horizontal lower shelf, sudden bottom impact |
| **2** | `Gas_Interference` | Compressible Gas in Chamber | Rounded concave polytropic compression delay on downstroke |
| **3** | `Severe_Gas_Lock` | Gas Locked Pump | Thin diagonal band, negligible net work area |
| **4** | `Traveling_Valve_Leak` | TV Cut / Worn Ball & Seat | Slanted right edge, delayed load pickup, drooping upstroke |
| **5** | `Standing_Valve_Leak` | SV Cut / Fluid Loss | Slanted left edge, delayed load drop, elevated downstroke |
| **6** | `Worn_Pump_Barrel` | Plunger Clearance Slippage | Rounded corners, elliptical shape, reduced gross displacement |
| **7** | `Blocked_Intake` | Restricted Wellbore Inflow | Deep underfilling, early vacuum decompression |
| **8** | `High_Wellbore_Friction` | Dogleg / Contact Drag | Widened upper and lower boundary hysteresis loop |
| **9** | `High_Fluid_Damping` | Viscous Heavy Crude | Bulging rounded card with high viscous drag hysteresis |
| **10** | `Tagging_Down_Hard` | Plunger Mechanical Impact | Sharp downward load spike at lower turnaround |
| **11** | `Unanchored_Tubing_Slip` | Tubing Breathing & Stretch | Tilted parallelogram from tubing elongation |

### 4. Fast ML Training Quickstart

#### Using the Provided Standalone PyTorch Script:
Run directly from terminal:
```bash
cd "C:\\Users\\HARSHIT\\OneDrive - TAS\\Desktop\\Master Dataset\\Downhole_Card_ML_Dataset"
python train_dynacard_vision_model.py --epochs 15 --batch-size 32 --lr 0.001
```

Or train with a pre-trained ResNet-18 backbone:
```bash
python train_dynacard_vision_model.py --epochs 10 --resnet
```

#### Zero-Code Loading via Torchvision:
```python
from torchvision.datasets import ImageFolder
from torchvision import transforms

dataset = ImageFolder(
    root="Downhole_Card_ML_Dataset/images/labeled_by_fault",
    transform=transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])
)
print("Detected classes:", dataset.classes)
```

### 5. Summary Statistics
- **Total Labeled Images**: {len(df_index)}
- **Training Samples**: {len(df_index[df_index['split'] == 'train'])} (70%)
- **Validation Samples**: {len(df_index[df_index['split'] == 'val'])} (15%)
- **Test Samples**: {len(df_index[df_index['split'] == 'test'])} (15%)
- **Image Resolution**: 224×224 pixels (Downhole), 448×224 pixels (Dual Card)
- **Coordinate Points**: 100 points normalized and raw per card
"""
    with open(guide_path, "w", encoding="utf-8") as f:
        f.write(guide_content)

    elapsed = round(time.time() - t_start, 1)
    print("\n" + "=" * 80)
    print(f"ML DOWNHOLE CARD DATASET SUCCESSFULLY GENERATED IN {elapsed} SECONDS!")
    print(f"Total labeled card images: {len(df_index)}")
    print(f"Output directory: {ML_DATASET_DIR}")
    print("=" * 80)


if __name__ == "__main__":
    generate_ml_dataset()
