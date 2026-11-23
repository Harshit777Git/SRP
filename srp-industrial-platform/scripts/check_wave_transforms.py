"""Manufactured periodic solution tests independent of simulator fault labels."""
import json,math
import numpy as np
from context import ROOT
from shared.contracts import Well,Rod
from wave_equation.solver import reconstruct,submerged_rod_weight,reconstruct_everitt_jennings
from surface_dynacard.geometry import describe

results=[]
for lengths in ([450],[650,550],[800,750,650]):
    well=Well(asset_id='VERIFY',rods=[Rod(length_m=l,diameter_m=.0286-i*.0032) for i,l in enumerate(lengths)])
    n=200;period=10.;phase=np.arange(n)*math.tau/n
    bottom_x=.8*(1-np.cos(phase))+.02*np.sin(2*phase)
    bottom_f=3000+800*np.sin(phase)+200*np.cos(2*phase)
    u=np.fft.rfft(bottom_x);force=np.fft.rfft(bottom_f);omega=math.tau*np.arange(len(u))/period
    # Exact upward solution; inverse of the continuous rod transfer matrix.
    for rod in reversed(well.rods):
        ea=rod.modulus*math.pi*rod.diameter_m**2/4
        k=np.sqrt((omega**2-1j*well.damping_s*omega)*rod.density/rod.modulus)
        c=np.cos(k*rod.length_m);s=rod.length_m*np.sinc(k*rod.length_m/np.pi)
        u,force=c*u+s*force/ea,-ea*k*k*s*u+c*force
    surface_x=np.fft.irfft(u,n=n);surface_f=np.fft.irfft(force,n=n)+submerged_rod_weight(well)
    solution=reconstruct(surface_x,surface_f,period,well)
    target=bottom_x-bottom_x.min()
    position_error=float(np.sqrt(np.mean((np.asarray(solution['position_m'])-target)**2)))
    load_error=float(np.sqrt(np.mean((np.asarray(solution['load_n'])-bottom_f)**2)))
    dc_error=abs(float(np.mean(solution['load_n']))-float(np.mean(bottom_f)))
    checks=dict(depth_m=well.depth,position_rmse_m=position_error,load_rmse_n=load_error,dc_load_error_n=dc_error,
        solver_quality=solution['solver_quality'],passed=position_error<.005 and load_error<30 and dc_error<1)
    assert checks['passed'],checks
    features=solution['features'];fo=(well.tubing_pa-well.casing_pa+well.fluid_kg_m3*9.80665*(well.depth-well.intake_head_m))*math.pi*well.plunger_m**2/4
    assert abs(features['fluid_load_fo_n']-fo)<1e-6
    assert features['ept_m'] is None or 0<=features['ept_m']<=features['mpt_m']
    results.append(checks);print(checks,flush=True)
rectangle=describe(np.array([0.,1,1,0]),np.array([0.,0,100,100]),True,None)
assert abs(rectangle['area_j']-100)<1e-9
assert all(v is None for v in rectangle['limits'].values())
assert rectangle['submerged_rod_weight_lbf'] is None
assert describe(np.array([0.,1]),np.array([100.,200]),False,None)['area_j'] is None
(ROOT/'reports/WAVE_SOLVER_VERIFICATION.json').write_text(json.dumps(dict(manufactured_solutions=results,surface_area_and_missing_metadata='PASS'),indent=2))
print('PASS: independent periodic solutions, DC force preservation, fluid-load equation, geometry and missing metadata')
