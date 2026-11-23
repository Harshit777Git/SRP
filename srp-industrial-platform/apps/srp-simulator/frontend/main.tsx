import {useEffect,useState} from 'react';
import {createRoot} from 'react-dom/client';
import {Action,Chart,Metrics,Panel,Shell,Status,api,fmt,request,useStream} from '../../ui/components';
import {OperationsConsole} from '../../ui/operations-console';

type Config = {asset_id:string;spm:number;stroke_m:number;dynamometer_hz:number;rods:{length_m:number}[]} & Record<string,unknown>;
type State = Record<string,number> & {linkage:number[][]};
type Mqtt = {connected:boolean;sent:number;queued:number;retry_failures:number;dropped:number;ack_lag_s:number;topics:string[]};
type Snapshot = {mode:string;run_id:string;configuration:Config;state?:State;history:State[];mqtt:Mqtt;fault?:{kind:string;severity:number;onset_s:number;duration_s:number;ramp_s:number}};
type ReferenceCard = {id:string;source:string;name:string;kind:string;label:null;provenance:string;points:number;position_m:number[];load_n:number[]};
const base=api(8001);
const tabs=['Fleet / Well Setup','Live Pumping Unit','Virtual Sensors','Fault Laboratory','MQTT Monitor','Reference Cards','Fleet Overview','U.S. Site Groups','Operations Console'];
type Fleet = {wells:{asset_id:string;site_id:string|null;mode:string;run_id:string|null;ground_truth?:{kind:string;active_severity:number};calibration?:{accepted:boolean;source_condition:string}}[];site_ids:string[]};
const signals:[string,string,string][]=[
  ['load_n','Polished-rod load','N'],['position_m','Polished-rod position','m'],
  ['crank_angle_deg','Crank angle','deg'],['current_a','Motor current','A'],
  ['tubing_pa','Tubing pressure','Pa'],['casing_pa','Casing pressure','Pa'],['spm','Stroke rate','SPM']
];
const faults=['healthy','incomplete_fillage','gas_interference','traveling_valve_leak','standing_valve_leak','rod_friction',
  'pump_wear','restricted_inflow','load_cell_drift','position_sensor_fault','abnormal_speed'];

function Pump({state}: {state?:State}) {
  const coords=state?.linkage.map(([x,y])=>[73+62*x,230-62*y]) ?? [];
  const line=(a:number,b:number,stroke:string,width:number)=><line x1={coords[a][0]} y1={coords[a][1]}
    x2={coords[b][0]} y2={coords[b][1]} stroke={stroke} strokeWidth={width} strokeLinecap="round"/>;
  const plunger=284-12*(state?.pump_position_m??0);
  return <svg viewBox="0 0 470 325" role="img" aria-label="Calculated pumpjack linkage and plunger" style={{width:'100%',height:330}}>
    <defs><pattern id="grid" width="23" height="23" patternUnits="userSpaceOnUse"><path d="M23 0H0V23" fill="none" stroke="var(--line)"/></pattern></defs>
    <rect x="0" y="0" width="470" height="325" fill="url(#grid)" opacity=".57"/>
    <line x1="18" x2="452" y1="242" y2="242" stroke="var(--muted)" opacity=".65"/>
    {!!coords.length && <>
      <path d={`M ${coords[3][0]-33} 242 L ${coords[3].join(' ')} L ${coords[3][0]+33} 242 Z`} fill="var(--line)"/>
      <circle cx={coords[0][0]} cy={coords[0][1]} r={37} stroke="var(--muted)" strokeDasharray="4 5" fill="none"/>
      {line(0,1,'var(--secondary)',8)}{line(1,2,'var(--muted)',5)}{line(2,4,'var(--accent)',8)}
      {coords.slice(0,4).map(([x,y],i)=><circle key={i} cx={x} cy={y} r={i===3?8:5} fill="var(--text)"/>)}
      <line x1={coords[4][0]} x2={coords[4][0]} y1={coords[4][1]} y2={plunger} stroke="var(--accent)" strokeWidth="2"/>
      <rect x={coords[4][0]-10} y={250} width="20" height="61" rx="3" fill="none" stroke="var(--muted)"/>
      <rect x={coords[4][0]-9} y={plunger-4} width="18" height="8" rx="2" fill="var(--accent)"/>
      <text x="20" y="22" fill="var(--muted)" fontSize="11">FOUR-BAR LINKAGE</text>
      <text x="20" y="269" fill="var(--muted)" fontSize="11">PLUNGER · SCHEMATIC DEPTH</text>
    </>}
    {!coords.length && <text x="235" y="157" textAnchor="middle" fill="var(--muted)" fontSize="14">Start a simulation to view the linkage</text>}
  </svg>;
}

function App(){
  const [tab,setTab]=useState(tabs[tabs.length-1]),[asset,setAsset]=useState('SRP_001'),[configs,setConfigs]=useState<Config[]>([]);
  const [configText,setConfigText]=useState(''),[error,setError]=useState(''),[speed,setSpeed]=useState(1);
  const [submitting,setSubmitting]=useState(false),[confirmation,setConfirmation]=useState('');
  const [fault,setFault]=useState('incomplete_fillage'),[severity,setSeverity]=useState(80);
  const [delay,setDelay]=useState(0),[duration,setDuration]=useState(120),[ramp,setRamp]=useState(2);
  const [references,setReferences]=useState<ReferenceCard[]>([]),[referenceId,setReferenceId]=useState('');
  const [fleet,setFleet]=useState<Fleet>({wells:[],site_ids:[]}),[selectedSite,setSelectedSite]=useState('US_TX_MIDLAND');
  const {data,online}=useStream<Snapshot>(`${base}/stream?asset=${asset}`);
  const refresh=()=>request<Config[]>(`${base}/assets`).then(list=>{
    setConfigs(list);setAsset(current=>list.some(item=>item.asset_id===current)?current:list[0]?.asset_id??current);
  }).catch(e=>setError(e.message));
  useEffect(()=>{void refresh();},[]);
  useEffect(()=>{const update=()=>request<Fleet>(`${base}/fleet`).then(setFleet).catch(()=>{});update();const timer=setInterval(update,3000);return ()=>clearInterval(timer);},[]);
  useEffect(()=>{request<ReferenceCard[]>(`${base}/reference-cards`).then(cards=>{setReferences(cards);setReferenceId(cards[0]?.id??'');}).catch(e=>setError(e.message));},[]);
  useEffect(()=>{const config=configs.find(c=>c.asset_id===asset);if(config)setConfigText(JSON.stringify(config,null,2));},[asset,configs]);
  const action=(name:string,payload:unknown={})=>{setError('');return request(`${base}/assets/${asset}/${name}`,payload).catch(e=>setError(e.message));};
  const updateSpeed=(value:number)=>{if(value<.1||value>20||!Number.isFinite(value))return;setSpeed(value);void request(`${base}/fleet/speed`,{speed:value}).catch(e=>setError(e.message));};
  const groupAction=async(path:string)=>{try{await request(`${base}/${path}`,{speed});setFleet(await request<Fleet>(`${base}/fleet`));setError('');}catch(e){setError((e as Error).message);}};
  const save=async()=>{try{const config=await request<Config>(`${base}/assets`,JSON.parse(configText));await refresh();setAsset(config.asset_id);setError('');}catch(e){setError((e as Error).message);}};
  const s=data?.state,m=data?.mqtt,h=data?.history??[];
  const livePeriod=60/(s?.spm||data?.configuration.spm||1);
  const liveCard=h.filter(p=>p.simulation_time_s>=(s?.simulation_time_s??0)-livePeriod);
  useEffect(()=>setConfirmation(''),[asset,data?.run_id]);
  const scheduled=data?.fault;
  const elapsed=(s?.simulation_time_s??0)-(scheduled?.onset_s??0);
  const faultStatus=!online?'Status unavailable':!scheduled||scheduled.kind==='healthy'||scheduled.severity===0?'No fault active'
    :data?.mode==='stopped'?'Scenario stopped':elapsed>=scheduled.duration_s?'Scenario completed'
    :data?.mode==='paused'?'Scenario paused':elapsed<0?'Scenario scheduled':'Scenario active';
  const effective=scheduled&&elapsed>=0&&elapsed<scheduled.duration_s
    ? scheduled.severity*(scheduled.ramp_s>0?Math.min(1,elapsed/scheduled.ramp_s,(scheduled.duration_s-elapsed)/scheduled.ramp_s):1):0;
  async function schedule(){
    setSubmitting(true);setConfirmation('');setError('');
    try {
      const result=await request<{waiting_for_reference:boolean}>(`${base}/assets/${asset}/fault`,
        {kind:fault,severity:severity/100,onset_s:delay,duration_s:duration,ramp_s:ramp,wait_for_reference:true});
      setConfirmation(result.waiting_for_reference?'Scenario scheduled after the initial reference strokes.'
        :fault==='healthy'?'Healthy scenario accepted.':'Scenario accepted by simulator.');
    } catch (e) {setError((e as Error).message);}
    finally {setSubmitting(false);}
  }
  const plot=([key,label,unit]:[string,string,string])=><Panel key={key} title={label} meta={unit}><Chart height={205} label={label}
    series={[{x:h.map(p=>p.simulation_time_s),y:h.map(p=>p[key])}]} xLabel="Simulation time (s)" yLabel={unit}/></Panel>;
  return <div style={{display:'flex',flexDirection:'column',minHeight:'100vh'}}>
    <header style={{
      minHeight: 52,
      background: '#102c27',
      borderBottom: '1px solid #1f4e42',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '10px 18px',
      flexWrap: 'wrap',
      gap: 10,
      position: 'sticky',
      top: 0,
      zIndex: 1000
    }}>
      <div style={{display: 'flex', alignItems: 'center', gap: 14,flexWrap:'wrap'}}>
        <div style={{
          background: '#ffffff',
          color: '#102c27',
          fontWeight: 800,
          fontSize: 13,
          letterSpacing: '0.12em',
          padding: '4px 12px',
          borderRadius: 6,
          boxShadow: '0 1px 3px rgba(0,0,0,0.3)',
          display: 'flex',
          alignItems: 'center',
          gap: 6
        }}>
          <span style={{background: '#137c61', color: '#fff', borderRadius: 4, padding: '1px 5px', fontSize: 11, fontWeight: 900}}>TAS</span>
          <span>SRP TWIN</span>
        </div>
        <span style={{color: '#d6eee0', fontWeight: 600, fontSize: 13, letterSpacing: '0.04em'}}>
          TAS DIGITAL TWIN · SRP SIMULATION PLATFORM
        </span>
      </div>

      <div style={{display: 'flex', alignItems: 'center', gap: 12,flexWrap:'wrap'}}>
        <div style={{
          background: '#042713',
          border: '1px solid #14532d',
          color: m?.connected?'#72ddb1':'#ffcc80',
          fontFamily: 'monospace',
          fontSize: 11,
          fontWeight: 600,
          padding: '4px 10px',
          borderRadius: 9999,
          display: 'flex',
          alignItems: 'center',
          gap: 6
        }}>
          <span style={{width: 6, height: 6, borderRadius: '50%', background: '#22c55e', boxShadow: '0 0 6px #22c55e'}}/>
          <span>{m?.connected?'MQTT connected':'MQTT disconnected'} · {fleet.wells.filter(w=>w.mode==='running').length}/{fleet.wells.length} wells running</span>
        </div>
        <label style={{fontSize:11,color:'#d6eee0'}}>Well <select aria-label="Header well" value={asset} onChange={e=>setAsset(e.target.value)}>{configs.map(c=><option key={c.asset_id}>{c.asset_id}</option>)}</select></label>
        <label style={{fontSize:11,color:'#d6eee0'}}>Speed × <input aria-label="Header simulation speed" type="number" min=".1" max="20" step=".1" value={speed} onChange={e=>updateSpeed(+e.target.value)} style={{width:60}}/></label>
        <a style={{fontSize:12,color:'#d6eee0'}} href={location.protocol+'//'+location.hostname+':3002/?asset='+encodeURIComponent(asset)} target="_blank" rel="noreferrer">View in APM ↗</a>
      </div>
    </header>
    <Shell product="Digital Twin Simulator" title={tab} description="Configure virtual wells, operate the pumping unit and inspect simulated sensor telemetry."
    tabs={tabs} selected={tab} select={setTab}>
    <div className="toolbar"><div className="actions"><label className="field">Well<select aria-label="Well" value={asset} onChange={e=>setAsset(e.target.value)}>
      {(configs.length?configs.map(c=>c.asset_id):['SRP_001']).map(id=><option key={id}>{id}</option>)}</select></label>
      <Status good={online}>{online?(data?.mode??'Connected'):'API disconnected'}</Status>
      <Status good={!!m?.connected}>{m?.connected?'MQTT connected':'MQTT disconnected'}</Status></div>
      <div className="actions"><label className="field">Speed ×<input type="number" min=".1" max="20" step=".1" value={speed} onChange={e=>updateSpeed(+e.target.value)} style={{width:75}}/></label>
        <Action primary onClick={()=>void action('start',{speed})}>Start</Action>
        <Action onClick={()=>void action('pause')} disabled={!s}>Pause</Action><Action onClick={()=>void action('stop')} disabled={!s}>Stop</Action>
        <Action onClick={()=>void action('reset',{speed})}>Reset</Action></div></div>
    {error&&<p role="alert" className="error">{error}</p>}
    {tab===tabs[tabs.length-1]&&<OperationsConsole kind="Digital Twin" selected={asset} onSelect={setAsset} wells={fleet.wells.map(w=>({asset_id:w.asset_id,field:w.site_id,state:w.mode,
      condition:w.ground_truth&&w.ground_truth.active_severity>0?w.ground_truth.kind:'healthy',
      detail:'Private simulator ground truth. '+(w.calibration?.accepted===false?'Source condition '+w.calibration.source_condition+' is not reproduced by this engine.':'Compare this operating condition with the independent APM prediction.')}))}/>}
    {tab===tabs[0]&&<><Panel title="Synthetic well configurations"><div className="scroll"><table><thead><tr><th>Well</th><th>Depth (m)</th><th>Stroke (m)</th><th>SPM</th><th>Dynamometer (Hz)</th></tr></thead>
      <tbody>{configs.map(c=><tr key={c.asset_id}><td><button onClick={()=>setAsset(c.asset_id)}>{c.asset_id}</button></td><td>{c.rods.reduce((a,r)=>a+r.length_m,0)}</td><td>{c.stroke_m}</td><td>{c.spm}</td><td>{c.dynamometer_hz}</td></tr>)}</tbody></table></div></Panel>
      <Panel title="Equipment and sensor configuration"><label className="field">Well configuration JSON<textarea value={configText} onChange={e=>setConfigText(e.target.value)}/></label>
      <p className="note">Use a new asset ID to create a well. Reset a running well to apply saved changes.</p><Action primary onClick={()=>void save()}>Save well configuration</Action></Panel></>}
    {tab===tabs[1]&&<><Metrics items={[[ 'Polished-rod load',`${fmt(s&&s.load_n/1000,2)} kN`],['Rod position',`${fmt(s?.position_m,3)} m`],
      ['Stroke rate',`${fmt(s?.spm)} SPM`],['Motor current',`${fmt(s?.current_a)} A`]]}/>
      <div className="columns simgrid"><Panel title="Pumping unit" meta="SIMULATED"><Pump state={s}/></Panel>
      <Panel title="Live polished-rod load" meta={`${data?.configuration.dynamometer_hz??50} Hz configured`}><Chart height={330} label="Live polished-rod load"
        series={[{x:h.map(p=>p.simulation_time_s),y:h.map(p=>p.load_n/1000)}]} xLabel="Simulation time (s)" yLabel="Load (kN)"/></Panel></div>
      <Metrics items={[[ 'Crank angle',`${fmt(s?.crank_angle_deg)}°`],['Plunger displacement',`${fmt(s?.pump_position_m,3)} m`],
      ['Tubing pressure',`${fmt(s&&s.tubing_pa/1000)} kPa`],['Net delivery',`${fmt(s?.net_delivered_m3,3)} m³`]]}/></>}
    {tab===tabs[2]&&<div className="columns">{signals.map(plot)}</div>}
    {tab===tabs[3]&&<Panel title="Inject a simulated operating condition" meta="Simulator only">
      <div className="formgrid"><label className="field">Scenario<select value={fault} onChange={e=>setFault(e.target.value)}>{faults.map(f=><option key={f} value={f}>{f.replaceAll('_',' ')}</option>)}</select></label>
      <label className="field">Severity (%)<input type="number" min="0.1" max="100" step="0.1" value={severity} onChange={e=>setSeverity(+e.target.value)}/></label>
      <label className="field">Delay (s)<input type="number" min="0" value={delay} onChange={e=>setDelay(+e.target.value)}/></label>
      <label className="field">Duration (s)<input type="number" min=".1" value={duration} onChange={e=>setDuration(+e.target.value)}/></label>
      <label className="field">Ramp (s)<input type="number" min="0" value={ramp} onChange={e=>setRamp(+e.target.value)}/></label></div>
      <div className="actions">
        <Action primary disabled={!online||data?.mode!=='running'||submitting||severity<.1||severity>100} onClick={()=>void schedule()}>{submitting?'Sending…':'Start scenario'}</Action>
        <span role="status"><Status good={faultStatus==='Scenario active'}>{faultStatus}</Status></span>
      </div>
      {confirmation&&<p role="status">{confirmation}</p>}
      {scheduled&&scheduled.kind!=='healthy'&&<p className="note">
        {scheduled.kind.replaceAll('_',' ')} · {elapsed<0?`starts in ${fmt(-elapsed)} s`
          :elapsed<scheduled.duration_s?`${fmt(effective*100,0)}% applied severity · ${fmt(scheduled.duration_s-elapsed)} s remaining`
          :'Injection window ended'} · simulation time
      </p>}
      {data?.mode!=='running'&&<p className="note">Run or resume the selected well to start a scenario.</p>}</Panel>}
    {tab===tabs[4]&&<><Metrics items={[[ 'Acknowledged',m?.sent??0],['Queued',m?.queued??0],['Retries',m?.retry_failures??0],
      ['Dropped',m?.dropped??0],['Ack lag (s)',fmt(m?.ack_lag_s,3)],['Dynamometer (Hz)',data?.configuration.dynamometer_hz??'—']]}/>
      <Panel title="Published MQTT topics"><pre>{m?.topics.join('\n')||'No topic acknowledgements yet'}</pre></Panel></>}
    {tab===tabs[5]&&<Panel title="Echometer demonstration surface cards" meta="REFERENCE ONLY">
      <p className="note">Numerical vendor examples for geometry comparison. Fault labels, timestamps, well identity and training permission are unverified. These cards are not injected into live telemetry or used as ML ground truth.</p>
      {references.length?<><label className="field">Card<select value={referenceId} onChange={e=>setReferenceId(e.target.value)}>
        {references.map(c=><option key={c.id} value={c.id}>{c.name} · {c.points} points</option>)}</select></label>
        {references.filter(c=>c.id===referenceId).map(c=><div key={c.id}>
          <Metrics items={[[ 'Source',c.source],['Trace',c.kind],['Points',c.points],['Fault label','Unverified']]}/>
          <Chart height={380} label="Reference and live synthetic surface dynacards" series={[
            {x:c.position_m,y:c.load_n.map(v=>v/1000)},
            ...(liveCard.length>10?[{x:liveCard.map(p=>p.position_m),y:liveCard.map(p=>p.load_n/1000),secondary:true}]:[])]}
            xLabel="Polished-rod displacement (m)" yLabel="Polished-rod load (kN)"/>
          <p className="note">Solid: vendor reference. Dashed: current synthetic well, latest stroke. Original vendor point order is preserved; inches and lbf were converted to SI. Different well geometry can produce different ranges.</p>
        </div>)}</>:<p>No supported numerical reference cards found in the local vendor archives.</p>}
    </Panel>}
    {tab===tabs[6]&&<><Metrics items={[["Configured fleet wells",fleet.wells.filter(w=>w.site_id).length],
      ["Running",fleet.wells.filter(w=>w.site_id&&w.mode==='running').length],["Site groups",fleet.site_ids.length],
      ["MQTT queued",m?.queued??'—'],["MQTT dropped",m?.dropped??'—']]}/>
      <Panel title="Fleet controls" meta="FICTIONAL SYNTHETIC ASSETS"><div className="actions">
        <Action primary onClick={()=>void groupAction('fleet/start')}>Start all</Action>
        <Action onClick={()=>void groupAction('fleet/pause')}>Pause all</Action>
        <Action onClick={()=>void groupAction('fleet/resume')}>Resume all</Action>
        <Action onClick={()=>void groupAction('fleet/stop')}>Stop all</Action></div>
        <p className="note">Engineering validation is synthetic self-consistency only. Watch the MQTT queue before sustained fleet operation.</p></Panel>
      <Panel title="Wells by site"><div className="scroll"><table><thead><tr><th>Site</th><th>Well</th><th>State</th><th>Run</th></tr></thead><tbody>
        {fleet.wells.filter(w=>w.site_id).map(w=><tr key={w.asset_id}><td>{w.site_id}</td><td><button onClick={()=>{setAsset(w.asset_id);setTab(tabs[1]);}}>{w.asset_id}</button></td><td>{w.mode}</td><td>{w.run_id?.slice(0,8)??'—'}</td></tr>)}
      </tbody></table></div></Panel></>}
    {tab===tabs[7]&&<><Panel title="Site controls" meta="ORGANIZATIONAL REGIONS"><div className="actions">
      <label className="field">Site<select value={selectedSite} onChange={e=>setSelectedSite(e.target.value)}>{fleet.site_ids.map(id=><option key={id}>{id}</option>)}</select></label>
      <Action primary onClick={()=>void groupAction(`sites/${selectedSite}/start`)}>Start site</Action>
      <Action onClick={()=>void groupAction(`sites/${selectedSite}/pause`)}>Pause site</Action>
      <Action onClick={()=>void groupAction(`sites/${selectedSite}/resume`)}>Resume site</Action>
      <Action onClick={()=>void groupAction(`sites/${selectedSite}/stop`)}>Stop site</Action></div></Panel>
      <Panel title="Site wells"><div className="scroll"><table><thead><tr><th>Well</th><th>State</th><th>Run</th></tr></thead><tbody>
      {fleet.wells.filter(w=>w.site_id===selectedSite).map(w=><tr key={w.asset_id}><td><button onClick={()=>{setAsset(w.asset_id);setTab(tabs[1]);}}>{w.asset_id}</button></td><td>{w.mode}</td><td>{w.run_id?.slice(0,8)??'—'}</td></tr>)}</tbody></table></div></Panel></>}
    </Shell>
  </div>;
}
createRoot(document.getElementById('root')!).render(<App/>);
