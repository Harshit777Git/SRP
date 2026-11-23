import {useEffect,useState} from 'react';
import {Action,Panel,fmt} from '../../ui/components';

export type TimedCard={position_m:number[];load_n:number[];time_s?:number[]};
export type PlaybackStroke={crank_origin_deg?:number;sampled_spm?:number;source?:string;run_id:string;stroke_id:number;timestamp:string;period_s:number;
  surface:TimedCard;surface_resampled?:TimedCard;downhole:Partial<TimedCard>&{status:string};
  diagnosis?:{label:string;evidence:string};
  asset_configuration?:{plunger_m:number;stroke_m:number;tubing_pa:number;casing_pa:number;fluid_kg_m3:number;intake_head_m:number;rods:{length_m:number;diameter_m:number}[]}};
type Point={x:number;f:number};
type Timed=TimedCard & {time_s:number[]};
const strokeKey=(stroke:PlaybackStroke)=>`${stroke.run_id}/${stroke.stroke_id}`;

export function interpolate(series:Timed,t:number,period:number):Point {
  const end=series.time_s.length-1;
  let hi=series.time_s.findIndex(time=>time>t);
  const lo=hi<0?end:Math.max(0,hi-1);
  const last=hi<0;
  if(last)hi=0;
  const fraction=(t-series.time_s[lo])/Math.max(1e-8,(last?period:series.time_s[hi])-series.time_s[lo]);
  const at=(values:number[])=>values[lo]+fraction*(values[hi]-values[lo]);
  return {x:at(series.position_m),f:at(series.load_n)};
}

function CardCursor({title,series,point,onSeek,overlay}:{title:string;series:Timed;point:Point;onSeek:(t:number)=>void;overlay?:TimedCard}){
  const [hover,setHover]=useState<Point>();
  const xAll=[...series.position_m,...(overlay?.position_m??[])], yAll=[...series.load_n,...(overlay?.load_n??[])];
  const minX=Math.min(...xAll),maxX=Math.max(...xAll),minY=Math.min(...yAll),maxY=Math.max(...yAll);
  const px=(x:number)=>60+278*(x-minX)/Math.max(maxX-minX,1e-8);
  const py=(y:number)=>226-190*(y-minY)/Math.max(maxY-minY,1e-8);
  const poly=(s:TimedCard)=>s.position_m.map((x,i)=>`${px(x)},${py(s.load_n[i])}`).join(' ');
  function nearest(event:React.PointerEvent<SVGSVGElement>|React.MouseEvent<SVGSVGElement>){
    const matrix=event.currentTarget.getScreenCTM();
    if(!matrix)return 0;
    const pointer=new DOMPoint(event.clientX,event.clientY).matrixTransform(matrix.inverse());
    let picked=0,distance=Infinity;
    series.position_m.forEach((x,i)=>{
      const d=Math.hypot(pointer.x-px(x),pointer.y-py(series.load_n[i]));
      if(d<distance){picked=i;distance=d;}
    });
    return picked;
  }
  return <Panel title={title} meta="Shared stroke clock">
    <svg viewBox="0 0 360 280" role="img" aria-label={title} style={{width:'100%',minHeight:240,touchAction:'manipulation'}}
      onPointerMove={e=>{const i=nearest(e);setHover({x:series.position_m[i],f:series.load_n[i]});}}
      onPointerLeave={()=>setHover(undefined)} onClick={e=>onSeek(series.time_s[nearest(e)])}>
      {[0,1,2,3,4].map(i=><g key={i} fill="var(--muted)" fontSize="10">
        <path d={`M60 ${226-47.5*i}H338 M${60+69.5*i} 36V226`} stroke="var(--line)"/>
        <text x="54" y={230-47.5*i} textAnchor="end">{fmt((minY+(maxY-minY)*i/4)/1000,2)}</text>
        <text x={60+69.5*i} y="242" textAnchor="middle">{fmt(minX+(maxX-minX)*i/4,2)}</text>
      </g>)}
      <text x="6" y="20" fill="var(--muted)" fontSize="11">Load (kN)</text>
      <text x="200" y="266" textAnchor="middle" fill="var(--muted)" fontSize="11">Displacement (m)</text>
      {overlay&&<polyline points={poly(overlay)} stroke="var(--secondary)" strokeDasharray="4 4" fill="none"/>}
      <polyline points={poly(series)} stroke="var(--accent)" strokeWidth="2" fill="none"/>
      <circle data-testid={title+' cursor'} cx={px(point.x)} cy={py(point.f)} r="5" fill="var(--text)">
        <title>{fmt(point.x,4)} m, {fmt(point.f/1000,3)} kN</title></circle>
    </svg>
    <p className="note">{hover?'Hovered sample · ':''}{fmt((hover??point).x,4)} m · {fmt((hover??point).f/1000,3)} kN</p>
  </Panel>;
}

function Pump({point,limits,config,simulated}:{point:Point;limits:[number,number];config?:PlaybackStroke['asset_configuration'];simulated:boolean}){
  const travel=limits[1]-limits[0];
  const y=246-128*(point.x-limits[0])/Math.max(travel,1e-8);
  const area=config?Math.PI*config.plunger_m**2/4:undefined;
  const swept=area===undefined?undefined:area*(point.x-limits[0])*1000;
  const estimatedChamber=simulated&&config&&area!==undefined
    ? area*(config.stroke_m+Math.max(-.8*config.stroke_m,point.x))*1000:undefined;
  const depth=config?.rods.reduce((sum,r)=>sum+r.length_m,0);
  const intake=simulated&&config?(config.casing_pa+config.fluid_kg_m3*9.80665*config.intake_head_m)/1000:undefined;
  const discharge=simulated&&config&&depth?(config.tubing_pa+config.fluid_kg_m3*9.80665*depth)/1000:undefined;
  return <Panel title="Pump cross-section" meta="Reconstructed motion">
    <svg viewBox="0 0 300 335" role="img" aria-label="Pump cross-section" style={{width:'100%',maxHeight:340}}>
      <path d="M96 20V302H204V20" fill="none" stroke="var(--muted)" strokeWidth="5"/>
      <rect x="113" y="28" width="74" height="267" fill="var(--accent)" opacity=".08"/>
      <rect x="116" y={y+10} width="68" height={280-y} fill="var(--accent)" opacity=".25"/>
      <path d="M113 78V292H187V78" stroke="var(--text)" strokeWidth="4" fill="none"/>
      <line x1="150" y1="18" x2="150" y2={y} stroke="var(--text)" strokeWidth="8"/>
      <g data-testid="pump-plunger" transform={`translate(0 ${y})`}>
        <rect x="116" y="-9" width="68" height="19" fill="var(--secondary)" rx="3"/>
        <path d="M143 4h14m-12-3h10" stroke="var(--text)" strokeWidth="1.4"/>
      </g>
      <path d="M136 288h28l-14-10z" fill="var(--muted)"/>
      <g fill="var(--muted)" fontSize="10">
        <text x="158" y="18">Rod string</text><text x="208" y="47">Tubing</text><text x="193" y="87">Pump barrel</text>
        <text x="194" y={y+2}>Traveling valve</text><text x="171" y="281">Standing valve</text>
        <text x="8" y="263">Pump chamber</text><text x="8" y="57">Fluid column</text>
        <text x="150" y="325" textAnchor="middle">Valve and flow state unavailable</text>
      </g>
    </svg>
    <details><summary>Pump measurements and estimates</summary>
      <p className="note">Reconstructed plunger {fmt(point.x,4)} m · {fmt(point.f/1000,2)} kN · effective travel {fmt(travel,3)} m</p>
      <p className="note">Swept volume from lower reversal {fmt(swept,3)} L · nominal displacement {fmt(area===undefined?undefined:area*travel*1000,3)} L/stroke</p>
      <p className="note">Model estimated chamber volume {fmt(estimatedChamber,3)} L</p>
      <p className="note">Model estimated nominal intake {fmt(intake)} kPa · discharge {fmt(discharge)} kPa</p>
      <p className="note">Chamber pressure, fillage, valve state, flow direction and actual production unavailable from this reconstruction.</p>
    </details>
  </Panel>;
}

export function PumpPlayback({stroke,history,select,exportUrl,historical,liveTime}:{stroke?:PlaybackStroke;history:PlaybackStroke[];
  select:(stroke?:PlaybackStroke)=>void;exportUrl:string;historical:boolean;liveTime?:number}){
  const [playing,setPlaying]=useState(false),[speed,setSpeed]=useState(1),[time,setTime]=useState(0);
  const [overlayKey,setOverlayKey]=useState(''),[annotation,setAnnotation]=useState('');
  const key=stroke?strokeKey(stroke):'';
  const period=stroke?.period_s??0;
  const cursorTime=!historical&&!playing ? liveTime??time : time;
  useEffect(()=>{setTime(0);setAnnotation(key?localStorage.getItem('srp-stroke-note/'+key)??'':'');},[key]);
  useEffect(()=>{
    if(!playing||period<=0)return;
    let previous=performance.now(),frame=0;
    const step=(now:number)=>{const dt=(now-previous)/1000;previous=now;
      setTime(t=>(t+dt*speed)%period);frame=requestAnimationFrame(step);};
    frame=requestAnimationFrame(step);
    return ()=>cancelAnimationFrame(frame);
  },[playing,period,speed,key]);
  const surface=stroke?.surface_resampled, downhole=stroke?.downhole;
  const selected=history.findIndex(item=>strokeKey(item)===key);
  const overlay=history.find(item=>strokeKey(item)===overlayKey);
  function seek(t:number){if(!historical&&stroke)select(stroke);setPlaying(false);setTime(t);}
  const s=surface as Timed|undefined,p=downhole as Timed|undefined;
  const aligned=!!s?.time_s?.length&&!!p?.time_s?.length&&s.time_s.length===p.time_s.length
    && s.time_s.every((t,i)=>t===p.time_s[i]);
  return <>
    {aligned&&s&&p&&stroke ? <div className="playback-grid">
      <Pump point={interpolate(p,cursorTime,period)} limits={[Math.min(...p.position_m),Math.max(...p.position_m)]}
        config={stroke.asset_configuration} simulated={stroke.source==='SIMULATOR'}/>
      <CardCursor title="Surface playback card" series={s} point={interpolate(s,cursorTime,period)} onSeek={seek} overlay={overlay?.surface_resampled}/>
      <CardCursor title="Downhole playback card" series={p} point={interpolate(p,cursorTime,period)} onSeek={seek}
        overlay={overlay?.downhole.status==='SOLVED'?overlay.downhole as TimedCard:undefined}/>
    </div>:<Panel title="Synchronized stroke unavailable"><p className="note">Wait for a completed stroke with a verified shared timebase and solved downhole card.</p></Panel>}
    <Panel title="Stroke playback" meta={stroke?`${historical?'HISTORICAL':'LIVE · latest completed'} · Stroke ${stroke.stroke_id} · ${stroke.source==='SIMULATOR'?'SIMULATED':stroke.source==='FIELD'?'MEASURED':'SOURCE UNAVAILABLE'}`:undefined}>
      <div className="actions">
        <Action primary disabled={!aligned} onClick={()=>{if(!historical&&stroke)select(stroke);setPlaying(!playing);}}>{playing?'Pause playback':'Play stroke'}</Action>
        <Action disabled={!stroke} onClick={()=>{select(stroke);setTime(cursorTime);setPlaying(false);}}>Freeze stroke</Action>
        <Action disabled={selected<0||selected+1>=history.length} onClick={()=>select(history[selected+1])}>Previous stroke</Action>
        <Action disabled={selected<=0} onClick={()=>select(history[selected-1])}>Next stroke</Action>
        <Action onClick={()=>{setPlaying(false);select(undefined);}}>Follow live phase</Action>
        <label className="field">Speed<select value={speed} onChange={e=>setSpeed(+e.target.value)}>{[.25,.5,1,2].map(v=><option key={v} value={v}>{v}×</option>)}</select></label>
        <label className="field">Historical stroke<select aria-label="Historical stroke" value={selected<0?'':key} onChange={e=>select(history.find(item=>strokeKey(item)===e.target.value))}>
          <option value="">Latest completed</option>{history.map(item=><option key={strokeKey(item)} value={strokeKey(item)}>{item.stroke_id} · {new Date(item.timestamp).toLocaleTimeString()}</option>)}</select></label>
        <label className="field">Overlay stroke<select aria-label="Overlay stroke" value={overlayKey} onChange={e=>setOverlayKey(e.target.value)}>
          <option value="">No overlay</option>{history.map(item=><option key={strokeKey(item)} value={strokeKey(item)}>{item.stroke_id} · {new Date(item.timestamp).toLocaleTimeString()}</option>)}</select></label>
        {aligned&&<a href={exportUrl+'&format=engineering&kind=synchronized'} download="srp_synchronized_stroke.csv">Export synchronized samples</a>}
      </div>
      <label className="field">Stroke time · {fmt(cursorTime,3)} / {fmt(period,3)} s
        <input aria-label="Stroke time" type="range" min="0" max={period||1} step=".001" value={Math.min(cursorTime,period||1)} onChange={e=>seek(+e.target.value)} disabled={!aligned}/></label>
      {stroke&&<details><summary>Diagnostics and stroke annotation</summary>
        <p className="note">{stroke.diagnosis?.label??'Diagnosis unavailable'} · {stroke.diagnosis?.evidence}</p>
        <label className="field">Local annotation<textarea value={annotation} onChange={e=>{
          setAnnotation(e.target.value);localStorage.setItem('srp-stroke-note/'+key,e.target.value);
        }}/></label>
      </details>}
    </Panel>
  </>;
}
