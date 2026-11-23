"""Measured loop geometry; ratings come from equipment configuration only."""
import math
import numpy as np
from shared.contracts import INCH,LBF,GRAVITY

def area(position_m,load_n):
    x=np.asarray(position_m);f=np.asarray(load_n)
    return float(abs(np.sum((np.roll(x,-1)-x)*(np.roll(f,-1)+f)/2)))
area_joules=area

def describe(position_m,load_n,complete=True,well=None):
    x=np.asarray(position_m,dtype=float);f=np.asarray(load_n,dtype=float);n=len(x)
    if not n or len(f)!=n or not np.isfinite(x).all() or not np.isfinite(f).all():raise ValueError('invalid surface samples')
    dx=np.gradient(x) if n>1 else np.zeros(n)
    direction=['UP' if v>=0 else 'DOWN' for v in dx]
    def point(i):return dict(index=int(i),position_in=float(x[i]/INCH),load_lbf=float(f[i]/LBF))
    weight=(sum(math.pi*r.diameter_m**2/4*r.length_m*(r.density-well.fluid_kg_m3)*GRAVITY for r in well.rods) if well else None)
    limits={key:getattr(well,attribute,None) if well else None for key,attribute in
        [('structural_limit_lbf','structural_load_limit_lbf'),('rod_yield_limit_lbf','rod_yield_limit_lbf'),('min_load_limit_lbf','minimum_load_limit_lbf')]}
    differences=[]
    up=np.flatnonzero(dx>0);down=np.flatnonzero(dx<0)
    if len(up)>2 and len(down)>2:
        grid=np.linspace(float(x.min()+.1*np.ptp(x)),float(x.max()-.1*np.ptp(x)),10)
        def branch(ids):
            ids=ids[np.argsort(x[ids])];positions,unique=np.unique(x[ids],return_index=True)
            return np.interp(grid,positions,f[ids][unique])
        uf,df=branch(up),branch(down)
        differences=[dict(position_in=float(p/INCH),delta_lbf=float((u-d)/LBF)) for p,u,d in zip(grid,uf,df)]
    work=area(x,f) if (complete or (len(x) > 10 and np.ptp(x) > 0.02)) else None
    return dict(position_m=x.tolist(),load_n=f.tolist(),position_in=(x/INCH).tolist(),load_lbf=(f/LBF).tolist(),
        direction=direction,min_load_n=float(f.min()),max_load_n=float(f.max()),stroke_m=float(np.ptp(x)),stroke_in=float(np.ptp(x)/INCH),
        pprl_lbf=float(f.max()/LBF),mprl_lbf=float(f.min()/LBF),area_j=work,area_lbf_in=work/(LBF*INCH) if work is not None else None,
        complete=bool(complete),submerged_rod_weight_lbf=weight/LBF if weight is not None else None,limits=limits,
        markers=dict(SOS=dict(point(0),sample_number=1),TOS=point(np.argmax(x)),BOS=point(np.argmin(x)),PPRL=point(np.argmax(f)),MPRL=point(np.argmin(f))),
        load_differences=differences,load_difference_method='principal branch interpolation at matched positions')
