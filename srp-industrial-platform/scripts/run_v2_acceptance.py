from contextlib import ExitStack
import io
import json
import os
import time
import uuid
from urllib.request import urlopen
from zipfile import ZipFile

from context import ROOT
from run_acceptance import http, local, wait_for
from evaluate_wave import compare as compare_with_truth

import numpy as np
from playwright.sync_api import expect, sync_playwright


SIM="http://127.0.0.1:18201"
APM="http://127.0.0.1:18202"
SIM_UI="http://127.0.0.1:13201"
APM_UI="http://127.0.0.1:13202"
EVIDENCE=ROOT/"data/evaluation/v2"


def run(report,stack):
    from pathlib import Path
    model=Path(os.getenv("SRP_V2_ACCEPTANCE_MODEL",str(ROOT/"data/training/cnn.pt"))).resolve()
    if not model.is_file():
        raise ValueError(f"Acceptance model not found: {model}")
    _,_,env=local(stack,model,18201,18202,13201,13202,18885,
          scope="v2/"+uuid.uuid4().hex[:8])
    for service in (SIM,APM):
        wait_for(lambda:http(service,"/health")["connected"],f"MQTT at {service}")
    for service in (SIM_UI,APM_UI):
        wait_for(lambda:urlopen(service,timeout=2).status==200,service)
    asset="SRP_001"
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=os.getenv("PLAYWRIGHT_BROWSER_PATH"),headless=True)
        page=browser.new_page(viewport=dict(width=1920,height=1080),accept_downloads=True)
        page.goto(SIM_UI)
        page.get_by_label("Speed ×").fill("5")
        page.get_by_role("button",name="Start",exact=True).click()
        def get_card(status):
            card=http(APM,f"/snapshot?asset={asset}").get("card")
            if card and card.get("condition_monitor",{}).get("status")==status:
                return card
        healthy=wait_for(lambda:get_card("WITHIN_REFERENCE"),"reference stroke")
        (EVIDENCE/"reference_stroke.json").write_text(json.dumps(healthy))
        page.goto(APM_UI)
        page.get_by_role("button",name="Animated Pump Analysis").click()
        expect(page.get_by_role("img",name="Pump cross-section")).to_be_visible(timeout=15000)
        page.get_by_role("button",name="Freeze stroke").click()
        cursors=[page.get_by_test_id(name) for name in ("pump-plunger","Surface playback card cursor","Downhole playback card cursor")]
        attrs=["transform","cx","cx"]
        def positions():
            return [c.get_attribute(attr) for c,attr in zip(cursors,attrs)]
        before=positions()
        page.get_by_role("slider",name="Stroke time").fill(str(healthy["period_s"]*.33))
        wait_for(lambda:all(a!=b for a,b in zip(before,positions())),"three synchronized view updates")
        frozen=positions()
        time.sleep(.25)
        assert positions()==frozen
        page.get_by_role("combobox").filter(has=page.get_by_role("option",name="2×",exact=True)).select_option("2")
        page.get_by_role("button",name="Play stroke").click()
        wait_for(lambda:all(a!=b for a,b in zip(frozen,positions())),"playback advances all three views")
        page.get_by_role("button",name="Pause playback").click()
        page.screenshot(path=EVIDENCE/"animated_pump.png",full_page=True)
        report["playback"]="PASS"

        def url(card,kind):
            return f'{APM}/cards/{card["run_id"]}/{card["stroke_id"]}?asset={asset}&format=engineering&kind={kind}'
        for kind in ("raw","surface","downhole","configuration","diagnostics","synchronized"):
            with urlopen(url(healthy,kind)) as result:
                (EVIDENCE/f"srp_{kind}.csv").write_bytes(result.read())
        page.get_by_role("button",name="Import / Export Center").click()
        with page.expect_download() as surface_download:
            page.get_by_role("link",name="surface CSV",exact=True).click()
        assert surface_download.value.suggested_filename=="srp_surface_dynacard.csv"
        surface_download.value.save_as(EVIDENCE/"srp_surface.csv")
        page.get_by_label("Data file").set_input_files(str(EVIDENCE/"srp_surface.csv"))
        page.get_by_role("button",name="Preview import").click()
        expect(page.get_by_role("img",name="Imported stroke preview")).to_be_visible()
        page.get_by_role("button",name="Save dataset").click()
        expect(page.get_by_text("Dataset saved.",exact=False)).to_be_visible()
        page.get_by_role("button",name="Engineering Benchmark Laboratory").click()
        select=page.get_by_role("combobox",name="Imported dataset")
        expect(select.locator("option").nth(1)).to_have_text("srp_surface.csv · surface")
        select.select_option(index=1)
        expect(page.get_by_role("img",name="Engineering card overlay")).to_be_visible()
        page.get_by_role("checkbox").check()
        page.get_by_role("button",name="Calculate comparison").click()
        expect(page.get_by_text("normalized_rmse",exact=False)).to_be_visible()
        page.screenshot(path=EVIDENCE/"engineering_benchmark.png",full_page=True)
        with page.expect_download() as downloaded:
            page.get_by_role("button",name="Download comparison report").click()
        downloaded.value.save_as(EVIDENCE/"engineering_comparison.json")
        report["comparison_browser"]="PASS"
        if vendor:=os.getenv("SRP_VENDOR_EXAMPLE_ARCHIVE"):
            with ZipFile(vendor) as archive:
                member=next(name for name in archive.namelist() if "/Overtravel_DYN_" in name)
                filename=member.rsplit("/",1)[-1]
                buffer=archive.read(member)
            page.get_by_role("button",name="Import / Export Center").click()
            page.get_by_label("Data file").set_input_files(dict(name=filename,mimeType="text/plain",buffer=buffer))
            page.get_by_text("Map nonstandard columns and units").click()
            page.get_by_label("Fallback source well").fill("OVERTRAVEL")
            page.get_by_label("Source / provenance").fill("Echometer Session 20 training example")
            page.get_by_role("button",name="Preview import").click()
            expect(page.get_by_text("132 rows",exact=False)).to_be_visible()
            page.get_by_role("button",name="Save dataset").click()
            expect(page.get_by_text("Dataset saved.",exact=False)).to_be_visible()
            page.get_by_role("button",name="Engineering Benchmark Laboratory").click()
            page.get_by_role("combobox",name="Imported dataset").select_option(label=filename+" · surface")
            expect(page.get_by_role("img",name="Engineering card overlay")).to_be_visible()
            page.get_by_role("button",name="Calculate comparison").click()
            expect(page.get_by_text("GEOMETRY_ONLY",exact=False)).to_be_visible()
            page.screenshot(path=EVIDENCE/"external_dyn_benchmark.png",full_page=True)
            with page.expect_download() as external_report:
                page.get_by_role("button",name="Download comparison report").click()
            external_report.value.save_as(EVIDENCE/"external_dyn_comparison.json")
            report["vendor_browser_comparison"]="PASS (geometry only)"

        page.goto(SIM_UI)
        page.get_by_role("button",name="Fault Laboratory").click()
        page.get_by_label("Scenario",exact=False).first.select_option("traveling_valve_leak")
        page.get_by_role("button",name="Start scenario").click()
        expect(page.get_by_text("Scenario active",exact=True)).to_be_visible(timeout=12000)
        fault=wait_for(lambda:get_card("DYNACARD_CHANGE"),"altered card observed",timeout=45)
        report["fault_evidence"]={k:fault[k] for k in ("run_id","stroke_id","condition_monitor","diagnosis")}
        assert fault["diagnosis"]["model_version"].startswith(("cnn/","cnn-v2/"))
        page.goto(APM_UI)
        expect(page.get_by_text("Dynacard change detected",exact=False)).to_be_visible(timeout=15000)
        page.screenshot(path=EVIDENCE/"fault_diagnosis.png",full_page=True)
        page.get_by_role("button",name="Animated Pump Analysis").click()
        expect(page.get_by_role("img",name="Pump cross-section")).to_be_visible()
        page.get_by_role("button",name="Freeze stroke").click()
        page.get_by_role("slider",name="Stroke time").fill("2")
        page.screenshot(path=EVIDENCE/"fault_pump_playback.png",full_page=True)

        # Offline acceptance only. APM has no access to this simulator file.
        simulator_truth=[]
        truth_path=Path(env["SIM_DATA"])/f'{fault["run_id"]}.jsonl'
        for line in truth_path.read_text().splitlines():
            try:
                simulator_truth.append(json.loads(line))
            except ValueError:
                continue
        report["offline_pump_truth"]=[]
        for label,card in (("healthy",healthy),("leak",fault)):
            first,last=card["raw_sequence"]
            truth=[dict(time=item["timestamp_unix_s"],x=item["pump_position_m"],f=item["pump_load_n"])
                   for item in simulator_truth if first<=item["sequence"]<=last]
            assert len(truth)==card["sample_count"]
            report["offline_pump_truth"].append(dict(label=label,**compare_with_truth(card,truth)))
        assert any(item["fault"]=="traveling_valve_leak" and item["severity"]>0
                   for item in simulator_truth if fault["raw_sequence"][0]<=item["sequence"]<=fault["raw_sequence"][1])

        roundtrips=[]
        for label,card in (("healthy",healthy),("leak",fault)):
            for kind in ("surface","downhole"):
                with urlopen(url(card,kind)) as response:
                    csv_bytes=response.read()
                (EVIDENCE/f"{label}_{kind}.csv").write_bytes(csv_bytes)
                imported=http(APM,"/interchange",dict(content=csv_bytes.decode(),kind=kind,filename=f"{label}.csv",
                                                     provenance="synthetic acceptance run",save=True))
                series=imported["cards"][0]
                assert series["asset_id"]==card["asset_id"] and series["stroke_id"]==card["stroke_id"]
                diffs={k:float(np.max(abs(np.asarray(series[k])-card[kind][k]))) for k in ("position_m","load_n")}
                assert max(diffs.values())<1e-9
                result=http(APM,"/benchmark",dict(asset=asset,run=card["run_id"],stroke=card["stroke_id"],
                    dataset_id=imported["dataset_id"],index=0,confirmed=True))
                assert result["rmse_n"]<.05 and abs(result["area_difference_j"])<1e-8
                roundtrips.append(dict(label=label,kind=kind,max_error=diffs,report=result))
        for kind in ("raw","configuration"):
            exported=(EVIDENCE/f"srp_{kind}.csv").read_text()
            preview=http(APM,"/interchange",dict(content=exported,kind=kind,filename=f"{kind}.csv"))
            assert preview["kind"]==kind
            if kind=="configuration":
                assert preview["configuration"]["asset_id"]==asset
            else:
                assert preview["records"]==healthy["sample_count"]
        report["roundtrips"]=roundtrips
        browser.close()
    report["pipeline"]="PASS"


if __name__=="__main__":
    EVIDENCE.mkdir(parents=True,exist_ok=True)
    results={}
    try:
        with ExitStack() as stack:
            run(results,stack)
    except Exception as e:
        results.update(pipeline="FAIL",error=str(e))
        raise
    finally:
        (EVIDENCE/"acceptance.json").write_text(json.dumps(results,indent=2))
        print(json.dumps({"pipeline":results.get("pipeline"),"roundtrips":len(results.get("roundtrips",[])),
                          "error":results.get("error")},indent=2),flush=True)
