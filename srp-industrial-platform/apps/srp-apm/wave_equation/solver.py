"""Periodic vertical-rod inverse transforms. SI internally; no force re-zeroing.
EJ-style spatial finite differences with configured damping; independent Gibbs check.
"""
import math
import numpy as np
from shared.contracts import GRAVITY, INCH, LBF

SOLVER_VERSION_EJ='EJ-spatial-FD/3.0'
SOLVER_VERSION_GIBBS='Gibbs-harmonic/2.0'

def submerged_rod_weight(well):
    return sum(math.pi*r.diameter_m**2/4*r.length_m*(r.density-well.fluid_kg_m3)*GRAVITY for r in well.rods)

def gibbs_traverse(displacement,tension,omega,rods,damping):
    for rod in rods:
        rigidity=rod.modulus*math.pi*rod.diameter_m**2/4
        k=np.sqrt((omega**2-1j*damping*omega)*rod.density/rod.modulus)
        c=np.cos(k*rod.length_m);s=rod.length_m*np.sinc(k*rod.length_m/np.pi)
        displacement,tension=c*displacement-s*tension/rigidity,rigidity*k*k*s*displacement+c*tension
    return displacement,tension
traverse=gibbs_traverse

def _filtered(values,harmonics,size=None):
    values=np.asarray(values,dtype=float);size=size or len(values)
    coefficients=np.fft.rfft(values);end=min(harmonics+1,len(coefficients))
    out=np.zeros(size//2+1,dtype=complex);out[:end]=coefficients[:end]
    return np.fft.irfft(out,n=size)*size/len(values)

def reconstruct_gibbs(position,load,period,well,harmonics=16):
    n=len(position);end=min(harmonics+1,n//2)
    omega=math.tau*np.arange(end)/period
    xf=np.fft.rfft(position);ff=np.fft.rfft(np.asarray(load)-submerged_rod_weight(well))
    u,t=gibbs_traverse(xf[:end],ff[:end],omega,well.rods,well.damping_s)
    x=np.fft.irfft(np.pad(u,(0,n//2+1-end)),n=n)
    f=np.fft.irfft(np.pad(t,(0,n//2+1-end)),n=n)
    return dict(position_m=x.tolist(),load_n=f.tolist(),harmonics=end-1,
        discarded_load_fraction=float(np.linalg.norm(ff[end:])/max(1.,np.linalg.norm(ff[1:]))),
        dynamic_load_gain=float(np.linalg.norm(t[1:])/max(1.,np.linalg.norm(ff[1:end]))),solver_version=SOLVER_VERSION_GIBBS)

def reconstruct_everitt_jennings(position,load,period,well,points=200,harmonics=16,spatial_step_m=20.):
    n=len(position);work=max(1024,4*n);dt=period/work
    u=_filtered(position,harmonics,work)
    force=_filtered(np.asarray(load)-submerged_rod_weight(well),harmonics,work)
    contact=getattr(well,'rod_contact_friction_n_m',0.)
    nodes=0
    for rod in well.rods:
        area=math.pi*rod.diameter_m**2/4;ea=rod.modulus*area;a2=rod.modulus/rod.density
        count=max(2,math.ceil(rod.length_m/min(spatial_step_m,.5*math.sqrt(a2)*dt)))
        h=rod.length_m/count;nodes+=count
        def operator(v):
            velocity=(np.roll(v,-1)-np.roll(v,1))/(2*dt)
            return (np.roll(v,-1)-2*v+np.roll(v,1))/dt**2+well.damping_s*velocity+contact/(rod.density*area)*np.tanh(velocity/.01)
        # Centered Neumann boundary F=-EA du/dz; displacement/force continuous at tapers.
        previous=u+h*force/ea+.5*h*h/a2*operator(u)
        for _ in range(count):
            following=2*u-previous+h*h/a2*operator(u)
            previous,u=u,following
        ghost=2*u-previous+h*h/a2*operator(u)
        force=-ea*(ghost-previous)/(2*h)
    grid=np.arange(n)/n;work_grid=np.arange(work)/work
    return dict(position_m=np.interp(grid,work_grid,u,period=1).tolist(),
        load_n=np.interp(grid,work_grid,force,period=1).tolist(),harmonics=harmonics,
        spatial_nodes=nodes,temporal_points=work,solver_version=SOLVER_VERSION_EJ)

def extract_downhole_features(position_m,load_n,well,spm,surface_stroke_m=None):
    x=np.asarray(position_m);f=np.asarray(load_n);n=len(x);dt=60/spm/n
    velocity=(np.roll(x,-1)-np.roll(x,1))/(2*dt)
    derivative=(np.roll(f,-1)-np.roll(f,1))/(2*dt)
    tos=int(np.argmax(x));bos=int(np.argmin(x));span=float(np.ptp(x))
    def point(i,method=None):
        if i is None:return None
        return dict(index=int(i),sample_number=int(i)+1,position_in=float(x[i]/INCH),load_lbf=float(f[i]/LBF),estimated=True,method=method)
    discharge=well.tubing_pa+well.fluid_kg_m3*GRAVITY*well.depth
    intake=well.casing_pa+well.fluid_kg_m3*GRAVITY*well.intake_head_m
    area=math.pi*well.plunger_m**2/4;fo=max(0.,discharge-intake)*area
    def crossing(level,rising):
        before=np.roll(f,1)
        mask=((f>=level)&(before<level)&(velocity>0)) if rising else ((f<=level)&(before>level)&(velocity<0))
        ids=np.flatnonzero(mask)
        return int(ids[0]) if len(ids) else None
    svo=crossing(.75*fo,True) if fo>0 else None
    tvo=crossing(.25*fo,False) if fo>0 else None
    down=np.flatnonzero(velocity<0)
    tp=int(down[np.argmin(derivative[down])]) if len(down) else None
    reliable=bool(tp is not None and span>1e-5 and fo>0 and np.ptp(f)>.1*fo and derivative[tp]<-.1*fo/(60/spm))
    tp=tp if reliable else None
    ept=float(np.clip(x[tp]-x.min(),0,span)) if tp is not None else None
    fillage=100*ept/span if ept is not None else None
    work=float(abs(np.sum((np.roll(x,-1)-x)*(np.roll(f,-1)+f)/2)))
    surface=well.stroke_m if surface_stroke_m is None else surface_stroke_m
    return dict(mpt_in=span/INCH,mpt_m=span,ept_in=ept/INCH if ept is not None else None,ept_m=ept,
        fillage_pct=fillage,load_transfer_point=point(tp,'largest downstroke load-drop derivative'),
        fluid_load_fo_lbf=fo/LBF,fluid_load_fo_n=fo,upper_fluid_reference_lbf=fo/LBF,lower_fluid_reference_lbf=0.,
        valves=dict(SVO=point(svo,'estimated 75% fluid-load upstroke crossing'),
            SVC=point(tos,'ideal-valve turnaround proxy; not a measured valve event'),
            TVO=point(tvo,'estimated 25% fluid-load downstroke crossing'),
            TVC=point(bos,'ideal-valve turnaround proxy; not a measured valve event')),
        markers=dict(TOS=point(tos),BOS=point(bos),MAX_LOAD=point(int(np.argmax(f))),MIN_LOAD=point(int(np.argmin(f)))),
        area_j=work,area_lbf_in=work/(LBF*INCH),stroke_loss_in=(surface-ept)/INCH if ept is not None else None,
        surface_minus_mpt_in=(surface-span)/INCH,
        displacement_bpd=area*ept*spm*1440/.158987294928 if ept is not None else None,
        gross_displacement_bpd=area*span*spm*1440/.158987294928,
        pip_psi=intake/6894.757293,pip_provenance='estimated from configured casing pressure, liquid density and submergence; consistent pressure basis assumed',
        estimate_status='ESTIMATED' if reliable else 'TRANSFER_NOT_IDENTIFIABLE',
        assumptions=['vertical axial rod model','valve events inferred from load and kinematics, not measured',
            'EPT is transfer-point displacement above cycle minimum','displacement is theoretical; no slippage or formation-volume-factor correction',
            'stroke loss is measured surface travel minus estimated effective pump travel; signed'],
        diagnostic_region=dict(detected=bool(fillage is not None and fillage<85),point=point(tp),
            description='Delayed unloading; gas compression and incomplete fillage are not uniquely distinguishable from this estimate'),
        fluid_pound=dict(detected=False,severity='UNDETERMINED',description='Fault-specific fluid-pound annotation requires independent evidence'))

def reconstruct(position,load,period,well,harmonics=16):
    x=np.asarray(position,dtype=float);f=np.asarray(load,dtype=float)
    if period<=0 or len(x)!=len(f) or len(x)<32 or not np.isfinite(x).all() or not np.isfinite(f).all():
        raise ValueError('invalid periodic surface boundary conditions')
    harmonics=min(harmonics,len(x)//2-1)
    ej=reconstruct_everitt_jennings(x,f,period,well,harmonics=harmonics)
    gibbs=reconstruct_gibbs(x,f,period,well,harmonics)
    ex=np.asarray(ej['position_m']);ef=np.asarray(ej['load_n']);gx=np.asarray(gibbs['position_m']);gf=np.asarray(gibbs['load_n'])
    if not all(np.isfinite(a).all() for a in (ex,ef,gx,gf)):raise ValueError('nonfinite inverse wave solution')
    ex-=ex.min();gx-=gx.min()
    xr=float(np.sqrt(np.mean((ex-gx)**2)));fr=float(np.sqrt(np.mean((ef-gf)**2)))
    agreement=xr/max(float(np.ptp(gx)),1e-5)<.03 and fr/max(float(np.ptp(gf)),1.)<.05
    return dict(status='SOLVED',solver_version=SOLVER_VERSION_EJ,verification_version=SOLVER_VERSION_GIBBS,
        position_m=ex.tolist(),load_n=ef.tolist(),gibbs_position_m=gx.tolist(),gibbs_load_n=gf.tolist(),
        displacement_rmse_in=xr/INCH,load_rmse_lbf=fr/LBF,harmonics=harmonics,
        discarded_load_fraction=gibbs['discarded_load_fraction'],dynamic_load_gain=gibbs['dynamic_load_gain'],
        spatial_nodes=ej['spatial_nodes'],temporal_points=ej['temporal_points'],
        features=extract_downhole_features(ex,ef,well,60/period,float(np.ptp(x))),
        solver_quality=dict(status='VALID' if agreement and gibbs['discarded_load_fraction']<.15 else 'SUSPECT',
            agreement_passed=bool(agreement),field_validated=False,
            damping_source='configured/calibrated viscous coefficient',coulomb_contact_n_m=getattr(well,'rod_contact_friction_n_m',0.)),
        load_convention='net axial pump tension; buoyant rod weight removed once; no arbitrary force re-zeroing',
        position_reference='cycle minimum',validation_status='NUMERICALLY_RECONSTRUCTED',
        model_assumptions=['periodic complete paired surface samples','vertical axial rods','continuous displacement/tension at tapers','configured viscous damping'])
