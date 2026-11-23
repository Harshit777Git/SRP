"""Shared feature contract for archived training strokes and live candidates."""
import math

import numpy as np

from fault_detection.models import inputs
from shared.contracts import GRAVITY
from surface_dynacard.geometry import area


SCHEMA = "srp-physical-pair/1.0"
POINTS = 200
CONFIDENCE = .70
GATES = dict(macro_f1=.90,minimum_recall=.85,minimum_precision=.85,
             minimum_coverage=.70,minimum_real_test_wells=10)


def live_inputs(card):
    if card.get("quality")!="GOOD" or card["downhole"]["status"]!="SOLVED":
        raise ValueError("Complete surface and solved downhole stroke required")
    surface=card.get("surface_resampled",{})
    downhole=card["downhole"]
    time=np.asarray(surface.get("time_s",[]))
    if (time.shape!=(POINTS,) or not np.isfinite(time).all() or
            not np.all(np.diff(time)>0) or not np.array_equal(time,downhole.get("time_s"))):
        raise ValueError("Candidate requires a shared 200-point timebase")
    if not card.get("asset_configuration"):
        raise ValueError("Equipment configuration is required")
    channels,_=inputs(card)
    return physical_inputs(channels,card["asset_configuration"],card["spm"])


def physical_inputs(channels, well, spm):
    channels=np.asarray(channels,dtype=float)
    if channels.shape!=(4,POINTS) or not np.isfinite(channels).all():
        raise ValueError("Four finite 200-point paired channels required")
    s_x,s_f,p_x,p_f=channels*np.array([3,30000,3,30000])[:,None]
    rods=well["rods"]
    depth=sum(r["length_m"] for r in rods)
    stroke=well["stroke_m"]
    hydro=max(100.,math.pi*well["plunger_m"]**2/4*(well["tubing_pa"]-well["casing_pa"]+
              well["fluid_kg_m3"]*GRAVITY*(depth-well["intake_head_m"])))
    weight=sum(r["length_m"]*math.pi*r["diameter_m"]**2/4*(r["density"]-well["fluid_kg_m3"])*GRAVITY for r in rods)
    sx=(s_x-s_x.min())/stroke
    px=(p_x-p_x.min())/stroke
    sf=(s_f-weight)/hydro
    pf=p_f/hydro
    # Common shift keeps the surface-to-pump phase relationship intact.
    start=int(sx.argmax())
    channels=np.roll([sx,sf,px,pf],-start,axis=1)
    features=[]
    for x,f in (channels[:2],channels[2:]):
        travel=float(np.ptp(x))
        features.extend([travel,float(np.mean(f)),float(np.min(f)),float(np.max(f)),area(x,f),
                         float(np.mean(f[20:50])),float(np.mean(f[55:90])),
                         float(np.mean(f[115:155])),float(np.mean(f[155:190]))])
        spectrum=np.fft.rfft(f)/len(f)
        features.extend(np.abs(spectrum[1:13]))
        features.extend(spectrum[1:7].real)
        features.extend(spectrum[1:7].imag)
    # Preserve the engineering scales separately from the dimensionless observables.
    features.extend([spm,depth,stroke,hydro,weight,well["plunger_m"],well["viscosity_pa_s"]])
    return channels,np.asarray(features)

