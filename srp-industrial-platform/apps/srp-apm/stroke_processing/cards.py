from datetime import timezone

import numpy as np

from shared.contracts import INCH, LBF
from surface_dynacard.geometry import describe
from wave_equation.solver import reconstruct


CARD_VERSION = "crank-periodic/1.1"


def build(samples, closing_sample, well, points=200):
    if not samples:
        return None
    first = samples[0]
    time = np.array([(s.timestamp-first.timestamp).total_seconds() for s in samples])
    angle = np.array([s.crank_angle_deg for s in samples])
    x = np.array([s.polished_rod_position_in*INCH for s in samples])
    f = np.array([s.polished_rod_load_lbf*LBF for s in samples])
    period = (closing_sample.timestamp-first.timestamp).total_seconds()
    steps = np.diff([s.sequence for s in samples]+[closing_sample.sequence])
    index_gaps = np.diff([s.sample_index for s in samples])
    gap = float(np.diff(np.r_[time, period]).max())
    expected = max(1, closing_sample.sequence-first.sequence+first.sample_index)
    completeness = min(1.,len(samples)/expected)
    monotonic = (np.diff(time)>0).all() and (np.diff(angle)>0).all()
    identity_ok = all((s.asset_id,s.run_id,s.stroke_id)==
                      (first.asset_id,first.run_id,first.stroke_id) for s in samples)
    identity_ok = identity_ok and (closing_sample.asset_id,closing_sample.run_id)==(first.asset_id,first.run_id)
    identity_ok = identity_ok and closing_sample.stroke_id==first.stroke_id+1
    good = (len(samples)>=32 and first.sample_index==0 and first.crank_angle_deg<15
            and closing_sample.crank_angle_deg<15 and angle[-1]>345 and monotonic
            and (steps==1).all() and (index_gaps==1).all() and gap<.25
            and all(s.quality=="GOOD" and s.source==first.source for s in samples)
            and np.ptp(x)>.02 and identity_ok)
    result = dict(asset_id=first.asset_id, run_id=first.run_id, stroke_id=first.stroke_id,
                  timestamp=first.timestamp.astimezone(timezone.utc).isoformat(), raw_sequence=[first.sequence,samples[-1].sequence],
                  sample_count=len(samples), completeness=completeness, largest_gap_s=gap,
                  quality="GOOD" if good else "DEGRADED", period_s=period,
                  spm=60/period if period>0 else None, card_version=CARD_VERSION,
                  source=first.source, identity_consistent=bool(identity_ok), crank_origin_deg=first.crank_angle_deg,
                  sampled_spm=float(np.median([sample.spm for sample in samples])),
                  surface=describe(x,f,good,well))
    result["surface"]["time_s"] = time.tolist()
    result['surface']['markers']['SOS']['sample_number']=first.sample_index+1
    can_reconstruct = bool(well and len(samples) >= 20 and np.ptp(x) > 0.02 and period > 0)
    reason = "insufficient samples" if not can_reconstruct else ("degraded stroke" if not good else None)
    result["downhole"] = dict(status="DOWNHOLE CARD UNAVAILABLE", reason=reason or "reconstruction pending")
    if can_reconstruct:
        # Keep actual paired samples in surface; maintain original movement phase in the grid.
        phase = time/period
        grid = np.arange(points)/points
        position = np.interp(grid,phase,x,period=1)
        load = np.interp(grid,phase,f,period=1)
        result["asset_configuration"] = well.model_dump()
        try:
            result["downhole"] = reconstruct(position,load,period,well)
            result["downhole"]["time_s"] = (grid*period).tolist()
            result["surface_resampled"] = dict(position_m=position.tolist(),load_n=load.tolist(),time_s=(grid*period).tolist())
        except Exception as error:
            result["downhole"] = dict(status="DOWNHOLE CARD UNAVAILABLE", reason=str(error))
    return result
