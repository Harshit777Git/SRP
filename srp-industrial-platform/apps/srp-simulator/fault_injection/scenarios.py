from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


FaultName = Literal["healthy", "incomplete_fillage", "gas_interference", "gas_lock",
                    "traveling_valve_leak", "standing_valve_leak", "rod_friction", "pump_wear",
                    "restricted_inflow", "unanchored_tubing", "tagging_down", "tagging_up",
                    "rod_parting", "load_cell_drift", "position_sensor_fault", "abnormal_speed"]


class Fault(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    kind: FaultName = "healthy"
    onset_s: float = Field(default=0, ge=0)
    duration_s: float = Field(default=3600, gt=0)
    ramp_s: float = Field(default=2, ge=0)
    severity: float = Field(default=0, ge=0, le=1)

    def at(self, time, kind):
        elapsed = time - self.onset_s
        if kind != self.kind or elapsed < 0 or elapsed >= self.duration_s:
            return 0.
        if self.ramp_s == 0:
            return self.severity
        return self.severity * min(1., elapsed / self.ramp_s, (self.duration_s-elapsed) / self.ramp_s)
