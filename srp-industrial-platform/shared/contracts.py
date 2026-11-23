from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


ASSET_PATTERN = r"^[A-Za-z0-9_-]{1,48}$"


class Rod(BaseModel):
    length_m: float = Field(ge=20, le=2500)
    diameter_m: float = Field(ge=.012, le=.06)
    density: float = Field(default=7850, ge=7000, le=8500)
    modulus: float = Field(default=205e9, ge=150e9, le=230e9)


class Well(BaseModel):
    asset_id: str = Field(pattern=ASSET_PATTERN)
    rods: list[Rod] = Field(min_length=1, max_length=8)
    stroke_m: float = Field(default=2.1, ge=.5, le=4)
    spm: float = Field(default=6, ge=2, le=15)
    crank_m: float = Field(default=.6, ge=.2, le=.8)
    rocker_m: float = Field(default=2, ge=1.6, le=2.6)
    pitman_m: float = Field(default=3.4, ge=3, le=4)
    pivot_x_m: float = Field(default=2.4, ge=2, le=3)
    pivot_y_m: float = Field(default=2.1, ge=1.6, le=2.7)
    mechanism: Literal["four_bar", "sinusoidal_test"] = "four_bar"
    damping_s: float = Field(default=.6, ge=.05, le=5)
    rod_contact_friction_n_m: float = Field(default=0, ge=0, le=20)
    structural_load_limit_lbf: float | None = Field(default=None, gt=0)
    rod_yield_limit_lbf: float | None = Field(default=None, gt=0)
    minimum_load_limit_lbf: float | None = Field(default=None)
    plunger_m: float = Field(default=.04445, ge=.025, le=.09)
    # Illustrative pump-fit defaults. Replace with measured pump dimensions for
    # field-calibrated runs; radial clearance is not inferable from card data.
    plunger_length_m: float = Field(default=.9, ge=.1, le=3)
    plunger_radial_clearance_m: float = Field(default=38.1e-6, ge=0, le=.001)
    pump_wear_clearance_growth_m: float = Field(default=76.2e-6, ge=0, le=.003)
    fluid_kg_m3: float = Field(default=880, ge=650, le=1300)
    chamber_gas_fraction: float = Field(default=.015, ge=.001, le=.2)
    viscosity_pa_s: float = Field(default=.015, gt=0, le=2)
    intake_head_m: float = Field(default=100, ge=5, le=500)
    tubing_pa: float = Field(default=350000, ge=100000, le=4e6)
    casing_pa: float = Field(default=150000, ge=100000, le=4e6)
    voltage_v: float = Field(default=480, ge=100, le=1000)
    gear_ratio: float = Field(default=100, ge=10, le=500)
    running_efficiency: float = Field(default=.85, ge=.4, le=1)
    physics_step_s: float = Field(default=.002, ge=.0001, le=.01)
    dynamometer_hz: int = Field(default=50, ge=20, le=100)
    electrical_hz: int = Field(default=10, ge=1, le=20)
    pressure_hz: int = Field(default=1, ge=1, le=5)
    noise_position_m: float = Field(default=0, ge=0, le=.02)
    noise_load_n: float = Field(default=0, ge=0, le=1000)
    position_bias_m: float = Field(default=0, ge=-.1, le=.1)
    load_bias_n: float = Field(default=0, ge=-5000, le=5000)
    sensor_latency_s: float = Field(default=0, ge=0, le=2)
    missing_probability: float = Field(default=0, ge=0, le=.2)
    seed: int = 42

    @model_validator(mode="after")
    def check_depth(self):
        if self.depth > 3000 or self.depth <= self.intake_head_m:
            raise ValueError("depth must exceed intake head and be at most 3000 m")
        return self

    @property
    def depth(self):
        return sum(rod.length_m for rod in self.rods)


class Sample(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    schema_version: Literal["1.0"] = "1.0"
    asset_id: str = Field(pattern=ASSET_PATTERN)
    site_id: str | None = Field(default=None, pattern=ASSET_PATTERN)
    source: Literal["SIMULATOR", "FIELD"]
    timestamp: AwareDatetime
    run_id: str = Field(min_length=1, max_length=80)
    physics_model_version: str | None = Field(default=None, min_length=1, max_length=80)
    sequence: int = Field(ge=0, le=2**63-1)
    stroke_id: int = Field(ge=0, le=2**63-1)
    sample_index: int = Field(ge=0, le=4000)
    polished_rod_position_in: float = Field(ge=-300, le=300)
    polished_rod_load_lbf: float = Field(ge=-10000, le=200000)
    crank_angle_deg: float = Field(ge=0, lt=360)
    spm: float = Field(gt=0, le=30)
    quality: Literal["GOOD", "DEGRADED", "BAD"]
    # Optional acquisition metadata. Empty values mean unrecorded; never infer
    # these values from simulator configuration or curve appearance.
    sensor_id: str | None = Field(default=None, min_length=1, max_length=80)
    calibration_id: str | None = Field(default=None, min_length=1, max_length=80)
    calibration_date: AwareDatetime | None = None
    load_uncertainty_lbf: float | None = Field(default=None, gt=0, le=10000)
    position_uncertainty_in: float | None = Field(default=None, gt=0, le=10)
    acquisition_method: str | None = Field(default=None, min_length=1, max_length=80)
    units: dict[str, str] = Field(default_factory=lambda: {
        "polished_rod_position_in": "in", "polished_rod_load_lbf": "lbf",
        "crank_angle_deg": "deg", "spm": "stroke/min"})


def topic(asset_id: str, stream: str):
    return f"srp/v1/{asset_id}/{stream}"


INCH = .0254
LBF = 4.4482216152605
GRAVITY = 9.80665
