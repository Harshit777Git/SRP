import numpy as np

from surface_dynacard.geometry import area


VERSION = "dynacard-change/1.3"
REFERENCE_COUNT = 3


def late_downstroke_load(card):
    series=card["downhole"]
    loads=np.asarray(series["load_n"])
    reversal=int(np.argmax(series["position_m"]))
    offsets=np.arange(int(.18*len(loads)),int(.25*len(loads)))
    return float(np.mean(loads[(reversal+offsets)%len(loads)]))


def aligned_load(card,key):
    series=card[key]
    loads=np.asarray(series["load_n"])
    if "crank_origin_deg" not in card or "time_s" not in series:
        return loads
    # Compare the observed phase, compensating for sample-clock quantization at the wrap.
    phase=card["crank_origin_deg"]/360+np.asarray(series["time_s"])*card["sampled_spm"]/60
    return np.interp(np.arange(len(loads))/len(loads),phase,loads,period=1)


def deviation(value, reference, minimum):
    center=float(np.median(reference))
    return value-center, max(minimum,4*float(np.max(np.abs(np.asarray(reference)-center))))


def work(card):
    series=card["downhole"]
    return area(series["position_m"],series["load_n"])


def compare_stroke(card, reference):
    result = dict(status="AWAITING_REFERENCE", version=VERSION, reference_count=len(reference))
    if len(reference) < REFERENCE_COUNT:
        return result
    if card["quality"]!="GOOD":
        return dict(result,status="STROKE_UNAVAILABLE")

    result["reference_strokes"]=[item["stroke_id"] for item in reference]
    rates=[item.get("sampled_spm",item["spm"]) for item in reference]
    speed=float(np.median(rates))
    observed_rate=card.get("sampled_spm",card["spm"])
    rate_limit=.002 if card.get("source")=="SIMULATOR" and all("sampled_spm" in item for item in reference) else .05*speed
    rate_delta,rate_threshold=deviation(observed_rate,rates,rate_limit)
    readings=result["measurements"]=[dict(label="Stroke rate",delta=rate_delta,threshold=rate_threshold,unit="SPM")]
    if abs(rate_delta)>rate_threshold:
        return dict(result,status="STROKE_RATE_CHANGE",reference_spm=speed,current_spm=observed_rate)

    surface=card["surface"]
    spans=[item["surface"]["stroke_m"] for item in reference]
    span_shift,span_limit=deviation(surface["stroke_m"],spans,max(.001,.002*float(np.median(spans))))
    readings.append(dict(label="Surface travel",delta=span_shift,threshold=span_limit,unit="m"))
    if abs(span_shift)>span_limit:
        return dict(result,status="DYNACARD_CHANGE",symptom="MEASURED_TRAVEL_CHANGE",surface_travel_delta_m=span_shift)

    mean_loads=[float(np.mean(item["surface"]["load_n"])) for item in reference]
    load_range=float(np.median([np.ptp(item["surface"]["load_n"]) for item in reference]))
    load_shift,load_limit=deviation(float(np.mean(surface["load_n"])),mean_loads,max(.003*load_range,10.))
    readings.append(dict(label="Mean surface load",delta=load_shift,threshold=load_limit,unit="N"))
    surface_center=np.median([aligned_load(item,"surface_resampled") for item in reference],axis=0)
    if "surface_resampled" in card:
        delta=aligned_load(card,"surface_resampled")-surface_center
        shape_rms=float(np.std(delta))
        if abs(load_shift)>load_limit and shape_rms<.25*abs(load_shift):
            return dict(result,status="DYNACARD_CHANGE",symptom="POLISHED_ROD_LOAD_OFFSET",surface_load_delta_n=load_shift)
    if card["downhole"]["status"]!="SOLVED":
        return dict(result,status="STROKE_UNAVAILABLE")

    changes = {}
    for key, name in (("surface_resampled","surface"),("downhole","downhole")):
        loads=np.array([aligned_load(item,key) for item in reference])
        center=np.median(loads,axis=0)
        scale=max(float(np.ptp(center)),100.)
        noise=float(np.max(np.sqrt(np.mean((loads-center)**2,axis=1))))/scale
        difference=float(np.sqrt(np.mean((aligned_load(card,key)-center)**2)))/scale
        changes[name]=dict(change_fraction=difference,threshold_fraction=max(.015,4*noise))

    reference_work=[work(item) for item in reference]
    work_delta,work_limit=deviation(work(card),reference_work,max(25.,.04*float(np.median(reference_work))))
    readings.append(dict(label="Downhole stroke work",delta=work_delta,threshold=work_limit,unit="J"))
    surface_changed=changes["surface"]["change_fraction"]>changes["surface"]["threshold_fraction"]
    downhole_changed=changes["downhole"]["change_fraction"]>changes["downhole"]["threshold_fraction"]
    # A clear change in measured load is evidence even when the inverse estimate is noisier.
    changed=surface_changed or abs(work_delta)>work_limit
    result.update(status="DYNACARD_CHANGE" if changed else "WITHIN_REFERENCE",
                  downhole_work_delta_j=work_delta,**changes)
    if result["status"]=="DYNACARD_CHANGE":
        retained=[late_downstroke_load(item) for item in reference]
        load_span=float(np.ptp(np.median([item["downhole"]["load_n"] for item in reference],axis=0)))
        excess,threshold=deviation(late_downstroke_load(card),retained,max(.25*load_span,200.))
        if excess>threshold:
            result.update(symptom="DELAYED_PUMP_UNLOADING",late_downstroke_excess_n=excess)
        elif abs(work_delta)>work_limit:
            result.update(symptom="PUMP_STROKE_WORK_CHANGE")
        elif surface_changed and not downhole_changed:
            result.update(symptom="SURFACE_WAVEFORM_CHANGE")
    return result
