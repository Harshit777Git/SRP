"""Label-blind contour image encoding shared by training and live inference."""
import numpy as np
from PIL import Image,ImageDraw

SCHEMA='paired-contour-image/3.0'

def encode(position,load):
    x=np.asarray(position,dtype=float);f=np.asarray(load,dtype=float)
    if len(x)!=len(f) or len(x)<32 or not np.isfinite(x).all() or not np.isfinite(f).all():raise ValueError('invalid paired contour')
    if np.ptp(x)<1e-8 or np.ptp(f)<1e-8:raise ValueError('degenerate contour')
    raw=[np.ptp(x)/3,np.min(f)/30000,np.max(f)/30000]
    x=(x-x.min())/np.ptp(x);f=(f-f.min())/np.ptp(f)
    canvas=Image.new('L',(128,128),0)
    points=[(4+float(a)*119,123-float(b)*119) for a,b in zip(x,f)]
    ImageDraw.Draw(canvas).line(points+[points[0]],fill=255,width=3,joint='curve')
    raster=np.asarray(canvas.resize((32,32),Image.Resampling.LANCZOS),dtype=np.float32)/255
    start=int(np.argmin(x));xx=np.roll(x,-start);ff=np.roll(f,-start)
    phase=np.arange(len(x))/len(x);target=np.arange(128)/128
    motion=np.interp(target,phase,xx,period=1);force=np.interp(target,phase,ff,period=1)
    work=abs(np.sum((np.roll(x,-1)-x)*(np.roll(f,-1)+f)/2))
    return np.r_[raster.reshape(-1),motion,force,raw,work].astype(np.float32)

def predict(artifact,card):
    # Strict feature allowlist: these two arrays are the complete model input.
    downhole=card.get('downhole',{})
    if card.get('quality')!='GOOD' or downhole.get('status')!='SOLVED':raise ValueError('complete good-quality reconstructed stroke required')
    if downhole.get('solver_quality',{}).get('status')=='SUSPECT':raise ValueError('solver quality is suspect')
    surface=card.get('surface_resampled') or card.get('surface',{})
    vector=np.r_[encode(surface['position_m'],surface['load_n']),encode(downhole['position_m'],downhole['load_n'])]
    scores=artifact['estimator'].predict_proba([vector])[0]
    classes=artifact['estimator'].classes_;best=int(np.argmax(scores))
    reference=artifact['reference_vectors']
    distance=float(np.sqrt(np.mean((reference-vector)**2,axis=1)).min())
    in_domain=distance<=artifact['distance_limit']
    accepted=in_domain and float(scores[best])>=artifact['threshold']
    return dict(label=str(classes[best]) if accepted else 'FAULT_TYPE_UNDETERMINED',confidence=float(scores[best]),
        candidate_scores=[dict(label=str(classes[i]),score=float(scores[i])) for i in np.argsort(scores)[::-1]],
        in_training_spm_range=True,in_domain=in_domain,contour_distance=distance,
        model_version=artifact['metadata']['model_version'],status='HELD_OUT_SYNTHETIC_EVALUATION',
        evidence='Prediction uses only paired surface/downhole traces encoded as contour images and morphology. Scores are model estimates, not field-calibrated probabilities.',
        investigation='Compare with the separate Digital Twin ground truth; review solver quality and domain coverage',
        field_validated=False)
