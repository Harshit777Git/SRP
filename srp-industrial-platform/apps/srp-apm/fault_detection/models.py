import math

import numpy as np
from shared.contracts import GRAVITY, Well

from surface_dynacard.geometry import area
from fault_detection.suspicions import ranked_causes


def inputs(card):
    surface, downhole = (card[k] for k in ("surface_resampled","downhole"))
    channels = np.array([surface["position_m"],surface["load_n"],
                         downhole["position_m"],downhole["load_n"]])
    features = [card["spm"]]
    for x,f in (channels[:2],channels[2:]):
        direction = np.roll(x,-1)-x > 0
        features.extend([np.ptp(x),np.min(f),np.max(f),area(x,f),
                         np.mean(f[direction])-np.mean(f[~direction]),
                         np.std(np.roll(f,-1)-f), np.std(f)])
    # Fixed engineering scales preserve amplitude, offset and phase.
    return channels / np.array([3,30000,3,30000])[:,None], np.array(features)


def baseline(card):
    if card["downhole"]["status"]!="SOLVED":
        symptom = card["downhole"]["reason"]
    else:
        x = np.array(card["downhole"]["position_m"])
        f = np.array(card["downhole"]["load_n"])
        work = area(x,f)
        symptom = f"Calculated downhole card work {work:.0f} J per stroke"
        if config:=card.get("asset_configuration"):
            well = Well.model_validate(config)
            area_pump = math.pi*well.plunger_m**2/4
            pressure_head = (well.tubing_pa-well.casing_pa
                             + well.fluid_kg_m3*GRAVITY*(well.depth-well.intake_head_m))
            ideal = area_pump*pressure_head*np.ptp(x)
            if ideal>0:
                ratio = work/ideal
                symptom += f", {ratio:.0%} of the ideal hydrostatic work"
                if ratio<.55:
                    symptom += ". Reduced hydraulic work is consistent with incomplete fillage, gas or leakage."
    return dict(label="FAULT_TYPE_UNDETERMINED", confidence=None, evidence=symptom, model_version="rules/1.1",
                suspected_causes=ranked_causes(card),
                status="INSUFFICIENT_EVIDENCE",
                investigation="Review stroke quality, operating trend and downhole reconstruction")


def cnn(classes=3):
    import torch
    from torch import nn

    def branch():
        return nn.Sequential(nn.Conv1d(2,16,7,padding=3),nn.ReLU(),
                             nn.Conv1d(16,32,5,padding=2),nn.ReLU(),
                             nn.AdaptiveAvgPool1d(8),nn.Flatten())

    class DualCard(nn.Module):
        def __init__(self):
            super().__init__()
            self.surface = branch()
            self.downhole = branch()
            self.fusion = nn.Sequential(nn.Linear(512,64),nn.ReLU(),nn.Linear(64,classes))

        def forward(self, x):
            surface = self.surface(x[:,:2])
            downhole = self.downhole(x[:,2:])
            return self.fusion(torch.cat([surface,downhole],dim=1))
    return DualCard()
