"""Rank investigations by observed evidence without assigning causal probabilities."""


def ranked_causes(card):
    observed=card.get("condition_monitor",{})
    symptom=observed.get("symptom")
    if card.get("quality")!="GOOD":
        return []
    if observed.get("status")=="STROKE_RATE_CHANGE":
        reason=f"Observed {observed['current_spm']:.4g} SPM versus {observed['reference_spm']:.4g} SPM reference"
        ordered=("Drive or operating setpoint change","Speed measurement scaling or timebase error")
    elif symptom=="MEASURED_TRAVEL_CHANGE":
        reason=f"Polished-rod travel changed by {observed['surface_travel_delta_m']:+.4f} m"
        ordered=("Position sensing or scale change","Actual pumping-unit travel change")
    elif symptom=="POLISHED_ROD_LOAD_OFFSET":
        reason=f"Mean surface load shifted by {observed['surface_load_delta_n']:+.0f} N with waveform shape retained"
        ordered=("Load-cell zero or tare shift","Actual static load change")
    elif symptom=="DELAYED_PUMP_UNLOADING":
        reason=f"Late downstroke load exceeded reference by {observed['late_downstroke_excess_n']:.0f} N"
        ordered=("Incomplete liquid fillage or restricted supply","Gas interference")
    elif symptom=="PUMP_STROKE_WORK_CHANGE":
        delta=observed["downhole_work_delta_j"]
        reason=f"Reconstructed stroke work changed by {delta:+.0f} J"
        ordered=(("Increased rod or pump friction","Changed hydraulic load") if delta>0 else
                 ("Reduced liquid fillage or gas interference","Leakage or reduced hydraulic load"))
    elif observed.get("status")=="DYNACARD_CHANGE" and observed.get("surface"):
        s=observed["surface"]
        reason=f"Measured surface load waveform deviation {s['change_fraction']:.1%} (threshold {s['threshold_fraction']:.1%})"
        ordered=("Changed pump or valve loading","Changed rod loading or load measurement")
    else:
        return []
    return [dict(cause=cause,evidence=reason,basis="ENGINEERING_HYPOTHESIS") for cause in ordered]

