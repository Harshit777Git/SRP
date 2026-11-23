import {useEffect,useState} from 'react';
import {Action,Panel,fmt,request} from '../../ui/components';

type Curve={position_in:number[];load_lbf:number[];status?:string};
type Reference={asset_id:string;display_name:string;version:string;estimated_period_s:number;
  timebase_status:string;source_sha256:string;surface:Curve;vendor_downhole:Curve;apm_downhole:Curve;
  metrics:Record<string,number|string>;assumptions:Record<string,unknown>};

function Card({title,curve,index,overlay}:{title:string;curve:Curve;index:number;overlay?:Curve}){
  const xs=[...curve.position_in,...(overlay?.position_in??[])];
  const ys=[...curve.load_lbf,...(overlay?.load_lbf??[])];
  const xmin=Math.min(...xs),xmax=Math.max(...xs),ymin=Math.min(...ys),ymax=Math.max(...ys);
  const px=(v:number)=>35+285*(v-xmin)/Math.max(1e-9,xmax-xmin);
  const py=(v:number)=>225-190*(v-ymin)/Math.max(1e-9,ymax-ymin);
  const line=(c:Curve)=>c.position_in.map((x,i)=>`${px(x)},${py(c.load_lbf[i])}`).join(' ');
  return <Panel title={title} meta={`${curve.position_in.length} ordered samples`}>
    <svg viewBox="0 0 350 260" role="img" aria-label={title} style={{width:'100%'}}>
      <polyline points={line(curve)} fill="none" stroke="var(--accent)" strokeWidth="2"/>
      {overlay&&<polyline points={line(overlay)} fill="none" stroke="var(--secondary)" strokeDasharray="5 4" strokeWidth="2"/>}
      <circle cx={px(curve.position_in[index])} cy={py(curve.load_lbf[index])} r="5" fill="var(--text)"/>
      <text x="10" y="250" fill="var(--muted)" fontSize="11">Displacement (in) / load (lbf)</text>
    </svg>
    <p className="note">Sample {index+1}: {fmt(curve.position_in[index],3)} in, {fmt(curve.load_lbf[index],1)} lbf</p>
  </Panel>;
}

export function HistoricalReference({base}:{base:string}){
  const [record,setRecord]=useState<Reference>();
  const [error,setError]=useState('');
  const [index,setIndex]=useState(0),[playing,setPlaying]=useState(false),[speed,setSpeed]=useState(1);
  const [overlay,setOverlay]=useState(true);
  useEffect(()=>{request<Reference>(`${base}/historical-references/STATE-077/1`).then(setRecord).catch(e=>setError(e.message));},[base]);
  const count=record?.surface.position_in.length??0;
  useEffect(()=>{
    if(!playing||!record||count===0)return;
    const interval=window.setInterval(()=>setIndex(i=>(i+1)%count),record.estimated_period_s*1000/(count*speed));
    return()=>window.clearInterval(interval);
  },[playing,record,count,speed]);
  if(error)return <Panel title="STATE-077 historical reference"><p className="error">{error}</p><p className="note">Start the APM with APM_DATA=state/state93, then reload this view.</p></Panel>;
  if(!record)return <Panel title="STATE-077 historical reference"><p>Loading persisted reference...</p></Panel>;
  const x=record.apm_downhole.position_in[index];
  const low=Math.min(...record.apm_downhole.position_in), high=Math.max(...record.apm_downhole.position_in);
  const y=210-140*(x-low)/Math.max(1e-9,high-low);
  const pointError=record.apm_downhole.load_lbf[index]-record.vendor_downhole.load_lbf[index];
  function exportComparison(){
    const rows=['sample_index,surface_position_in,surface_load_lbf,tam_position_in,tam_load_lbf,apm_position_in,apm_load_lbf'];
    for(let i=0;i<count;i++)rows.push([i,record!.surface.position_in[i],record!.surface.load_lbf[i],record!.vendor_downhole.position_in[i],record!.vendor_downhole.load_lbf[i],record!.apm_downhole.position_in[i],record!.apm_downhole.load_lbf[i]].join(','));
    const url=URL.createObjectURL(new Blob([rows.join('\n')],{type:'text/csv'}));
    const a=document.createElement('a');a.href=url;a.download='STATE-077-comparison.csv';a.click();URL.revokeObjectURL(url);
  }
  return <>
    <Panel title="STATE-077 historical vendor demonstration" meta={`Version ${record.version}`}>
      <p className="note">Ordered source samples; playback timing ESTIMATED from {fmt(60/record.estimated_period_s,3)} SPM. TAM pump card is vendor calculated; APM pump card is reconstructed.</p>
      <div className="actions">
        <Action onClick={()=>setPlaying(!playing)}>{playing?'Pause':'Play'}</Action>
        <Action onClick={()=>{setPlaying(false);setIndex(i=>(i-1+count)%count);}}>Step back</Action>
        <Action onClick={()=>{setPlaying(false);setIndex(i=>(i+1)%count);}}>Step forward</Action>
        <label className="field">Speed<select value={speed} onChange={e=>setSpeed(+e.target.value)}>{[.25,.5,1,2].map(v=><option key={v} value={v}>{v}x</option>)}</select></label>
        <label className="field"><input type="checkbox" checked={overlay} onChange={e=>setOverlay(e.target.checked)}/> TAM overlay</label>
        <Action onClick={exportComparison}>Export comparison CSV</Action>
      </div>
      <input aria-label="Stroke sample" type="range" min="0" max={count-1} value={index} onChange={e=>{setPlaying(false);setIndex(+e.target.value);}} style={{width:'100%'}}/>
    </Panel>
    <div className="playback-grid">
      <Panel title="Pump cross-section" meta="APM reconstructed movement">
        <svg viewBox="0 0 220 270" role="img" aria-label="STATE-077 pump cross-section" style={{width:'100%',maxHeight:300}}>
          <path d="M55 20V245H165V20" fill="none" stroke="var(--muted)" strokeWidth="5"/>
          <rect x="76" y="25" width="68" height="215" fill="var(--accent)" opacity=".12"/>
          <line x1="110" y1="12" x2="110" y2={y} stroke="var(--text)" strokeWidth="7"/>
          <rect data-testid="state077-plunger" x="78" y={y} width="64" height="16" fill="var(--secondary)"/>
          <text x="7" y="260" fill="var(--muted)" fontSize="10">Valve and fillage states unavailable</text>
        </svg>
        <p className="note">Plunger {fmt(x,3)} in · model motion. Valve and fillage estimates are unavailable.</p>
      </Panel>
      <Card title="Surface Dynacard" curve={record.surface} index={index}/>
      <Card title="APM downhole / TAM reference" curve={record.apm_downhole} index={index} overlay={overlay?record.vendor_downhole:undefined}/>
    </div>
    <Panel title="Pointwise comparison">
      <p>Sample {index+1}: TAM {fmt(record.vendor_downhole.position_in[index],3)} in / {fmt(record.vendor_downhole.load_lbf[index],1)} lbf; APM {fmt(x,3)} in / {fmt(record.apm_downhole.load_lbf[index],1)} lbf.</p>
      <p className="note">Load difference {fmt(pointError,1)} lbf · displacement difference {fmt(x-record.vendor_downhole.position_in[index],3)} in</p>
      <p className="note">Load RMSE {fmt(Number(record.metrics.load_rmse_lbf),1)} lbf · displacement RMSE {fmt(Number(record.metrics.displacement_rmse_in),3)} in · area error {fmt(Number(record.metrics.card_area_error_percent),2)}%</p>
      <details><summary>Provenance and assumptions</summary><pre>{JSON.stringify({source_sha256:record.source_sha256,solver:record.apm_downhole.status,assumptions:record.assumptions},null,2)}</pre></details>
    </Panel>
  </>;
}
