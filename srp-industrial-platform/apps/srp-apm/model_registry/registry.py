import os
import json
from urllib.request import Request, urlopen
from pathlib import Path

from fault_detection.models import baseline, cnn, inputs
from fault_detection.remediation import CONFIDENCE, GATES, SCHEMA, live_inputs

import numpy as np


def gate_passes(metadata):
    evaluation=metadata.get("deployment_evaluation",{})
    return (metadata.get("schema")==SCHEMA and metadata.get("approved_for_deployment") is True
            and metadata.get("origin")=="REAL_FIELD"
            and evaluation.get("independent_well_split") is True
            and all(type(evaluation.get(key)) in (int,float) and evaluation[key]>=threshold
                    for key,threshold in GATES.items()))


class RemoteRegistry:
    def __init__(self, url):
        self.url = url

    def call(self, route, data=None):
        request = Request(self.url+route,data=json.dumps(data).encode() if data is not None else None,
                          headers={"Content-Type":"application/json"})
        with urlopen(request,timeout=1) as response:
            return json.load(response)

    def metadata(self):
        try:
            return self.call("/registry")
        except OSError:
            return dict(status="WORKER_UNAVAILABLE",deployed=False)

    def predict(self, card):
        try:
            fields = ("spm","surface_resampled","downhole","asset_configuration","quality","source","condition_monitor")
            return self.call("/predict",{field:card[field] for field in fields if field in card})
        except OSError:
            return dict(baseline(card),status="WORKER_UNAVAILABLE")


class Registry:
    def __init__(self,path=None,experimental=None):
        path = path or os.getenv("SRP_MODEL_PATH")
        if not path:
            candidates = [
                Path(__file__).resolve().parents[3]/"data/training/dynacard_fault_model.joblib",
                Path(r"C:\Users\HARSHIT\OneDrive - TAS\Desktop\SRP\DH_IMG_PREDICTION_ML_DATASET\dynacard_fault_model.joblib"),
                Path(__file__).resolve().parents[3]/"data/training/downhole_contour.joblib"
            ]
            for c in candidates:
                if c.is_file():
                    path = str(c)
                    break
        self.artifact = self.network = None
        self.experimental = (os.getenv("SRP_ALLOW_EXPERIMENTAL_MODEL")=="1" if experimental is None else experimental)
        self.rejection = None
        if path and Path(path).is_file():
            if Path(path).suffix==".pt":
                import torch
                torch.set_num_threads(1)
                self.artifact = torch.load(path,map_location="cpu",weights_only=True)
                self.network = cnn(len(self.artifact["metadata"]["classes"]))
                self.network.load_state_dict(self.artifact["weights"])
                self.network.eval()
            else:
                import joblib
                self.artifact = joblib.load(path)
            metadata=self.artifact.get("metadata",{})
            from fault_detection.advanced_dynacard import SCHEMA as ADVANCED_SCHEMA
            supported=("calibrator" not in self.artifact or metadata.get("schema") in (SCHEMA, ADVANCED_SCHEMA))
            if not supported or (not self.experimental and not (metadata.get("schema")==ADVANCED_SCHEMA or gate_passes(metadata))):
                self.rejection="Artifact requires a compatible feature contract and independent field approval"
                self.artifact=self.network=None

    def metadata(self):
        if self.artifact:
            return self.artifact["metadata"]
        return dict(model_version="rules/1.1",status="INSUFFICIENT_EVIDENCE",
                    deployed=True,origin="engineering features",field_validated=False,artifact_rejection=self.rejection)

    def preview(self,card):
        if card.get("source")!="SIMULATOR" or not self.artifact:
            return None
        result=self.predict(card,all_scores=True)
        if not result.get("in_training_spm_range"):
            return None
        return dict(model_version=result["model_version"],scores=result["candidate_scores"])

    def predict(self, card,all_scores=False):
        result = baseline(card)
        if not self.artifact or card.get("downhole",{}).get("status")!="SOLVED":
            return result
        from datetime import datetime, timezone
        metadata=self.metadata()
        if metadata.get("origin")=="SIMULATED" and card.get("source")!="SIMULATOR":
            return dict(result,model_evaluation="Synthetic artifact requires simulated telemetry")
        from fault_detection.advanced_dynacard import SCHEMA as ADVANCED_SCHEMA, predict as predict_advanced
        if metadata.get('schema')==ADVANCED_SCHEMA or 'model' in self.artifact:
            try:
                prediction=predict_advanced(self.artifact,card,all_scores=True)
            except Exception as error:
                return dict(result,model_evaluation=str(error))
            return dict(result,**prediction,timestamp=datetime.now(timezone.utc).isoformat())
        from fault_detection.contour import SCHEMA as CONTOUR_SCHEMA,predict as predict_contour
        if metadata.get('schema')==CONTOUR_SCHEMA:
            try:
                prediction=predict_contour(self.artifact,card)
            except (TypeError,ValueError,KeyError) as error:
                return dict(result,model_evaluation=str(error))
            return dict(result,**prediction,timestamp=datetime.now(timezone.utc).isoformat(),
                probability_preview=dict(model_version=metadata['model_version'],scores=prediction['candidate_scores']))
        try:
            channels,features=(live_inputs(card) if metadata.get("schema")==SCHEMA else inputs(card))
        except (TypeError,ValueError,KeyError) as error:
            return dict(result,model_evaluation=str(error))
        if self.network is not None:
            import torch
            with torch.inference_mode():
                logits = self.network(torch.as_tensor(channels[None],dtype=torch.float32))[0]
                probabilities = torch.softmax(logits/self.artifact["temperature"],dim=0).numpy()
            classes = self.artifact["metadata"]["classes"]
        else:
            estimator = self.artifact["estimator"]
            probabilities = estimator.predict_proba([features])[0]
            classes = estimator.classes_
            if calibrator:=self.artifact.get("calibrator"):
                probabilities=calibrator.predict_proba(np.log(probabilities[None].clip(1e-6)))[0]
                classes=calibrator.classes_
        index = probabilities.argmax()
        confidence = float(probabilities[index])
        limits = self.artifact["domain"]
        in_domain = limits[0]-.03 <= card["spm"] <= limits[1]+.03
        return dict(result,label=str(classes[index]) if in_domain and confidence>=CONFIDENCE else "FAULT_TYPE_UNDETERMINED",
                    candidate_scores=[dict(label=str(classes[i]),score=float(probabilities[i]))
                                      for i in np.argsort(probabilities)[-(len(classes) if all_scores else 3):][::-1]],
                    confidence=confidence, model_version=metadata["model_version"],
                    provenance=metadata["dataset"],status=metadata["status"],in_training_spm_range=in_domain,
                    timestamp=datetime.now(timezone.utc).isoformat())
