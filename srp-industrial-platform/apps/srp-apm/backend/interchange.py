import csv
import hashlib
import io
import json
from datetime import datetime, timedelta, timezone

import numpy as np
from pydantic import AwareDatetime, TypeAdapter

from shared.contracts import ASSET_PATTERN, INCH, LBF, Sample, Well
import re
from surface_dynacard.geometry import describe


UTC = TypeAdapter(AwareDatetime)
EXPORT_NAMES = dict(raw="srp_raw_telemetry.csv",surface="srp_surface_dynacard.csv",
                    downhole="srp_downhole_dynacard.csv",configuration="srp_well_configuration.csv",
                    diagnostics="srp_fault_diagnostics.csv",synchronized="srp_synchronized_stroke.csv")
UNITS = {"m": 1., "in": INCH, "ft": .3048, "N": 1., "kN": 1000., "lbf": LBF}


def csv_text(fields, rows):
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def timestamp(start, offset):
    return (UTC.validate_python(start)+timedelta(seconds=offset)).isoformat()


def card_rows(card, kind, raw=()):
    identity = dict(well_id=card["asset_id"],stroke_id=card["stroke_id"])
    if kind=="configuration":
        config=Well.model_validate(card["asset_configuration"])
        yield dict(well_id=config.asset_id,unit_system="SI",pump_setting_depth_m=config.depth,
                   **config.model_dump(exclude={"rods","asset_id"}),
                   rods_json=json.dumps([rod.model_dump() for rod in config.rods]))
        return
    if kind=="diagnostics":
        d=card["diagnosis"]
        yield dict(identity,timestamp=d.get("timestamp",card["timestamp"]),predicted_class=d["label"],
                   confidence=d.get("confidence"),severity=d.get("severity"),evidence=d.get("evidence"),
                   model_version=d.get("model_version"),dataset_provenance=d.get("provenance"),
                   fault_status=d.get("status"),quality=card["quality"])
        return
    if kind=="raw":
        for r in raw:
            values=r.model_dump(mode="json",exclude={"schema_version","asset_id","run_id","sequence","stroke_id"})
            fields=("timestamp","sample_index","crank_angle_deg","polished_rod_position_in",
                    "polished_rod_load_lbf","spm","quality","source","sensor_id",
                    "calibration_id","calibration_date","load_uncertainty_lbf",
                    "position_uncertainty_in","acquisition_method")
            yield dict(identity,**{key:values[key] for key in fields})
        return
    if kind not in ("surface","downhole","synchronized"):
        raise ValueError("Unknown export type")
    series=card["surface_resampled" if kind=="synchronized" else kind]
    if "time_s" not in series:
        raise ValueError("Stroke has no verified sample timebase")
    for index,(time,x,f) in enumerate(zip(series["time_s"],series["position_m"],series["load_n"],strict=True)):
        row=dict(identity,timestamp=timestamp(card["timestamp"],time),sample_index=index)
        if kind=="surface":
            yield dict(row,position_in=x/INCH,load_lbf=f/LBF,stroke_phase=series["direction"][index],source=card["source"])
        elif kind=="downhole":
            yield dict(row,plunger_position_in=x/INCH,pump_load_lbf=f/LBF,solver_version=series["solver_version"],quality=card["quality"])
        else:
            p=card["downhole"]
            yield dict(row,position_in=x/INCH,load_lbf=f/LBF,
                       plunger_position_in=p["position_m"][index]/INCH,pump_load_lbf=p["load_n"][index]/LBF)


def rows_from_csv(content):
    if not isinstance(content,str) or not content.strip():
        raise ValueError("Choose a nonempty CSV file")
    content=content.lstrip("\ufeff")
    try:
        dialect=csv.Sniffer().sniff(content[:4096],delimiters=",;\t|")
    except csv.Error as error:
        raise ValueError("Unable to determine the CSV delimiter") from error
    reader=csv.DictReader(io.StringIO(content),dialect=dialect)
    rows=list(reader)
    if not rows or len(rows)>15000 or len(set(reader.fieldnames))!=len(reader.fieldnames) or any(None in r or None in r.values() for r in rows):
        raise ValueError("Expected 1–15,000 rows with unique headers and a constant column count")
    return reader.fieldnames, rows


def import_file(body):
    content=body.get("content","")
    kind=body.get("kind")
    filename=str(body.get("filename",""))
    if filename.lower().endswith(".tam_exp"):
        raise ValueError("TAM native interchange requires a verified adapter. Use a numerical export.")
    if filename.lower().endswith(".dyn"):
        if kind!="surface":
            raise ValueError("Select surface for a supported Echometer DYN record")
        return import_dyn(body,filename,content)
    if kind=="configuration":
        if filename.lower().endswith(".json"):
            well=Well.model_validate_json(content)
        else:
            _,rows=rows_from_csv(content)
            if len(rows)!=1:
                raise ValueError("Expected one well configuration per file")
            record={k:v for k,v in rows[0].items() if v!=""}
            if record.get("unit_system")!="SI":
                raise ValueError("Engineering configuration CSV must use SI")
            well=Well.model_validate(dict(record,asset_id=record["well_id"],rods=json.loads(record["rods_json"])))
        return dict(kind=kind, configuration=well.model_dump())
    if kind not in {"raw","surface","downhole"}:
        raise ValueError("Select raw telemetry, surface card, downhole card or configuration")
    headers, rows=rows_from_csv(content)
    mapping=body.get("mapping") or {}
    canonical={"raw":("polished_rod_position_in","polished_rod_load_lbf"),
               "surface":("position_in","load_lbf"),"downhole":("plunger_position_in","pump_load_lbf")}
    pos,load=canonical[kind]
    pos_col,load_col=mapping.get("position",pos),mapping.get("load",load)
    pos_unit,load_unit=body.get("position_unit","in"),body.get("load_unit","lbf")
    if pos_col not in headers or load_col not in headers:
        raise ValueError("Map the position and load columns")
    if pos_unit not in ("in","ft","m") or load_unit not in ("lbf","N","kN"):
        raise ValueError("Select position and load units")
    groups={}
    for line,row in enumerate(rows):
        asset=row.get(mapping.get("well","well_id")) or body.get("well_id")
        stroke=row.get(mapping.get("stroke","stroke_id")) or body.get("stroke_id")
        if not isinstance(asset,str) or not re.fullmatch(ASSET_PATTERN,asset) or stroke is None or stroke=="":
            raise ValueError("Supply the source well and stroke identity")
        if int(stroke)<0:
            raise ValueError("Stroke ID must be nonnegative")
        groups.setdefault((asset,int(stroke)),[]).append((line,row))
    cards=[]
    for (asset,stroke),group in groups.items():
        samples=[]
        for order,(_,row) in enumerate(group):
            index=int(row.get(mapping.get("index","sample_index"),order))
            observed=row.get(mapping.get("timestamp","timestamp"))
            dt=UTC.validate_python(observed).astimezone(timezone.utc) if observed else None
            x=float(row[pos_col])*UNITS[pos_unit]
            f=float(row[load_col])*UNITS[load_unit]
            if not np.isfinite([x,f]).all():
                raise ValueError("Position and load must be finite")
            samples.append((index,dt,x,f,row))
        samples.sort(key=lambda point:point[0])
        indices,times,x,f,source_rows=map(list,zip(*samples))
        if len(set(indices))!=len(indices) or len(indices)<2:
            raise ValueError("A stroke needs at least two samples with unique indices")
        time_s=None
        if any(t is not None for t in times):
            if any(t is None for t in times) or any(b<=a for a,b in zip(times,times[1:])):
                raise ValueError("Sample timestamps must be complete and strictly increasing")
            time_s=[(t-times[0]).total_seconds() for t in times]
        if indices[0]<0:
            raise ValueError("Sample indices must be nonnegative")
        if kind=="raw":
            if time_s is None:
                raise ValueError("Raw telemetry requires timestamped samples")
            for i,row in enumerate(source_rows):
                Sample.model_validate(dict(asset_id=asset,run_id="offline-import",stroke_id=stroke,
                    sample_index=indices[i],sequence=i,timestamp=times[i],source=row.get("source"),
                    quality=row.get("quality"),crank_angle_deg=row.get("crank_angle_deg"),
                    spm=row.get("spm"),polished_rod_position_in=x[i]/INCH,polished_rod_load_lbf=f[i]/LBF,
                    sensor_id=row.get("sensor_id") or None,calibration_id=row.get("calibration_id") or None,
                    calibration_date=row.get("calibration_date") or None,
                    load_uncertainty_lbf=row.get("load_uncertainty_lbf") or None,
                    position_uncertainty_in=row.get("position_uncertainty_in") or None,
                    acquisition_method=row.get("acquisition_method") or None))
        gaps=any(b-a!=1 for a,b in zip(indices,indices[1:]))
        warnings=(["Sample indices contain gaps"] if gaps else [])+([] if time_s else ["No timestamp alignment"])
        details=describe(np.array(x),np.array(f),not gaps)
        cards.append(dict(asset_id=asset,stroke_id=stroke,sample_index=indices,kind=kind,
                          timestamp=times[0].isoformat() if time_s else None,time_s=time_s,
                          quality="DEGRADED" if warnings or any(r.get("quality","GOOD")!="GOOD" for r in source_rows) else "GOOD",
                          warnings=warnings,source=source_rows[0].get("source") or body.get("provenance") or "EXTERNAL",
                          original_rows=source_rows if kind=="raw" else None,**details))
    digest=hashlib.sha256(json.dumps([kind,content,mapping,pos_unit,load_unit,body.get("well_id"),
                                      body.get("stroke_id"),body.get("provenance")],sort_keys=True).encode()).hexdigest()
    return dict(dataset_id=digest,kind=kind,filename=filename,provenance=body.get("provenance",""),
                headers=headers,records=len(rows),cards=cards)


def import_dyn(body,filename,content):
    lines=content.lstrip("\ufeff").splitlines()
    try:
        count=int(lines[0].strip())
    except (IndexError,ValueError) as error:
        raise ValueError("Expected an Echometer DYN sample-count header") from error
    if not 2<=count<=15000 or len(lines)<count+1:
        raise ValueError("DYN sample count is invalid or incomplete")
    pairs=[]
    for line in lines[1:count+1]:
        fields=line.split(",")
        if len(fields)!=2:
            raise ValueError("DYN point must contain two comma-separated numerical fields")
        x,f=map(float,fields)
        if not np.isfinite([x,f]).all():
            raise ValueError("DYN points must be finite")
        pairs.append(dict(position_in=x,load_lbf=f))
    mapping=body.get("mapping") or {}
    if mapping:
        raise ValueError("DYN uses its fixed two-column surface point block")
    result=import_file(body|dict(content=csv_text(["position_in","load_lbf"],pairs),filename=filename+".csv"))
    result.update(filename=filename, vendor_format="Echometer counted ASCII point block",
                  opaque_trailer_lines=len(lines)-1-count,
                  original_sha256=hashlib.sha256(content.encode()).hexdigest())
    result["dataset_id"]=hashlib.sha256((result["original_sha256"]+result["dataset_id"]).encode()).hexdigest()
    return result


def benchmark(reference, candidate, origin, confirmed):
    if reference["quality"]!="GOOD":
        raise ValueError("Use a complete operating stroke")
    if candidate["kind"]=="raw" or candidate["area_j"] is None:
        raise ValueError("Comparison requires an ordered surface or downhole card")
    series=reference[candidate["kind"]]
    if "time_s" not in series:
        raise ValueError("Operating stroke has no verified timestamps")
    a=describe(np.array(series["position_m"]),np.array(series["load_n"]),True)
    result=dict(reference=dict(asset=reference["asset_id"],run=reference["run_id"],stroke=reference["stroke_id"],
                    source=reference.get("source"),configuration=reference.get("asset_configuration")),
        external=dict(asset=candidate["asset_id"],stroke=candidate["stroke_id"],source=origin,kind=candidate["kind"]),
        peak_load_difference_pct=100*(candidate["max_load_n"]-a["max_load_n"])/abs(a["max_load_n"]) if a["max_load_n"] else None,
        minimum_load_difference_n=candidate["min_load_n"]-a["min_load_n"],
        stroke_length_difference_m=candidate["stroke_m"]-a["stroke_m"],
        area_difference_j=candidate["area_j"]-a["area_j"])
    if not confirmed or not candidate["time_s"] or candidate["quality"]!="GOOD":
        return dict(result,alignment="GEOMETRY_ONLY", reason="Time metrics require complete timestamps and confirmation of comparable cycle and equipment",
                    rmse_n=None,mae_n=None,normalized_rmse=None,correlation=None,fundamental_phase_deg=None)
    t=np.array(series["time_s"]); u=np.array(candidate["time_s"])
    if abs(u[-1]-t[-1])>max(t[-1]*.03,.05):
        raise ValueError("Stroke times differ by more than 3%; phase comparison is invalid")
    common=np.linspace(0,min(t[-1],u[-1]),200)
    load=np.interp(common,t,series["load_n"])
    other=np.interp(common,u,candidate["load_n"])
    difference=other-load
    span=float(np.ptp(load))
    coeff=np.fft.rfft(load)[1]; other_coeff=np.fft.rfft(other)[1]
    return dict(result,alignment="TIME_ALIGNED_FROM_CONFIRMED_ORIGIN",
        comparison_window_s=float(common[-1]),rmse_n=float(np.sqrt(np.mean(difference**2))),
        mae_n=float(np.mean(abs(difference))),normalized_rmse=float(np.sqrt(np.mean(difference**2))/span) if span else None,
        correlation=float(np.corrcoef(load,other)[0,1]) if span and np.ptp(other) else None,
        fundamental_phase_deg=float(np.angle(other_coeff/coeff,deg=True)) if abs(coeff)>1e-8 and abs(other_coeff)>1e-8 else None)
