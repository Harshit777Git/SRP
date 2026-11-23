"""Create reproducible, fictional engineering configurations for the Phase 3 fleet."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shared.contracts import Rod, Well

SITES = [
    ("US_TX_MIDLAND", "TX-MID"), ("US_NM_DELAWARE", "NM-DEL"),
    ("US_ND_WILLISTON", "ND-WIL"), ("US_OK_ANADARKO", "OK-ANA"),
    ("US_CO_DJ", "CO-DJ"), ("US_TX_EAGLEFORD", "TX-EAG"),
]


def build():
    result = []
    for site_index, (site_id, prefix) in enumerate(SITES):
        for index in range(5):
            n = site_index * 5 + index
            depth = 720 + site_index * 170 + index * 115
            upper_fraction = .43 + .025 * (index % 3)
            rods = [Rod(length_m=round(depth * upper_fraction, 3), diameter_m=.0286 if n % 3 == 0 else .0254),
                    Rod(length_m=round(depth * (1 - upper_fraction), 3), diameter_m=.0222 if n % 2 else .01905)]
            well = Well(asset_id=f"{prefix}-{index+1:03d}", rods=rods,
                        stroke_m=round(1.45 + .18 * index + .08 * site_index, 3),
                        spm=round(5.0 + .55 * ((n * 3) % 7), 3),
                        crank_m=round(.42 + .025 * (n % 6), 3),
                        rocker_m=round(1.85 + .04 * (n % 6), 3),
                        pitman_m=round(3.25 + .045 * (n % 7), 3),
                        pivot_x_m=round(2.25 + .035 * (n % 6), 3),
                        pivot_y_m=round(1.95 + .035 * (n % 5), 3),
                        damping_s=round(.45 + .08 * (n % 6), 3),
                        plunger_m=round(.0381 + .003 * (n % 6), 4),
                        fluid_kg_m3=820 + 17 * (n % 9),
                        chamber_gas_fraction=round(.01 + .008 * (n % 8), 3),
                        viscosity_pa_s=round(.012 + .004 * (n % 9), 3),
                        intake_head_m=70 + 12 * (n % 8),
                        tubing_pa=260000 + 25000 * (n % 7),
                        casing_pa=120000 + 8000 * (n % 6),
                        gear_ratio=95 + 4 * (n % 7),
                        running_efficiency=round(.78 + .02 * (n % 7), 3),
                        physics_step_s=.0067,
                        seed=20261117 + n)
            result.append(dict(site_id=site_id, identity_status="FICTIONAL",
                               validation_status="UNVALIDATED", well=well.model_dump()))
    return result


if __name__ == "__main__":
    target = ROOT / "config/fleet/us_srp_30_wells.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(dict(schema_version="phase3.1", origin="SYNTHETIC",
                                      regional_labels_are_organizational=True,
                                      wells=build()), indent=2) + "\n")
    print(target)
