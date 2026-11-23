import {useMemo,useState} from 'react';

export type OperationsWell={asset_id:string;field?:string|null;state?:string;condition?:string;detail?:string};

const fieldName=(well:OperationsWell)=>well.field||'Unassigned';
const pretty=(value?:string)=>value?.replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase())||'Full pump (normal)';

export function OperationsConsole({wells,selected,onSelect,kind}:{
  wells:OperationsWell[];selected:string;onSelect:(id:string)=>void;kind:'Digital Twin'|'APM';
}){
  const [query,setQuery]=useState(''),[field,setField]=useState('ALL'),[state,setState]=useState('ALL');
  const normalized=useMemo(()=>wells.map((well,index)=>({
    ...well,field:fieldName(well),state:well.state||'Waiting',condition:pretty(well.condition),index
  })),[wells]);
  const fields=useMemo(()=>Array.from(new Set(normalized.map(w=>w.field))),[normalized]);
  const visible=normalized.filter(w=>(field==='ALL'||w.field===field)&&(state==='ALL'||w.state===state)&&
    `${w.field} ${w.asset_id} ${w.condition}`.toLowerCase().includes(query.toLowerCase()));
  const active=normalized.find(w=>w.asset_id===selected)||visible[0]||normalized[0];
  const running=normalized.filter(w=>/running|connected/i.test(w.state)).length;
  return <div className="ops-console">
    <section className="ops-overview">
      <div className="ops-title"><div><span className="ops-kicker">{kind} operations</span><h2>Fleet overview</h2></div><span className="ops-live"><i/> Live</span></div>
      <div className="ops-totals"><div><span>Wells</span><strong>{normalized.length}</strong></div><div><span>Running</span><strong>{running}</strong></div>
        <div><span>Fields</span><strong>{fields.length}</strong></div><div><span>Attention</span><strong>{normalized.length-running}</strong></div></div>
      <details><summary>Automatic condition coverage</summary><p>{new Set(normalized.map(w=>w.condition)).size} monitored conditions across {normalized.length} wells</p></details>
    </section>
    <div className="ops-workspace">
      <section className="ops-directory"><div className="ops-section-title"><h2>Wells</h2><span>{visible.length}</span></div>
        <label className="ops-search"><span>Search fields or wells</span><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search fields or wells"/></label>
        <div className="ops-filters"><label>Field<select value={field} onChange={e=>setField(e.target.value)}><option value="ALL">All fields</option>{fields.map(f=><option key={f}>{f}</option>)}</select></label>
          <label>Run state<select value={state} onChange={e=>setState(e.target.value)}><option value="ALL">All states</option>{Array.from(new Set(normalized.map(w=>w.state))).map(s=><option key={s}>{s}</option>)}</select></label></div>
        <div className="ops-list">{fields.map(f=>{const items=visible.filter(w=>w.field===f);return items.length?<div key={f}><h3>{f}</h3>{items.map(w=><button key={w.asset_id} className={w.asset_id===active?.asset_id?'selected':''} onClick={()=>onSelect(w.asset_id)}>
          <span><strong>{w.asset_id}</strong><small>{w.condition}</small></span><em>{w.state}</em></button>)}</div>:null;})}</div>
      </section>
      <section className="ops-detail">{active?<><div className="ops-well-head"><div><span>{active.field}</span><h2>{active.asset_id}</h2><p>{active.state} · synchronized operational view</p></div><span className="ops-badge">{active.state}</span></div>
        <div className="ops-condition"><span>Pump condition</span><strong>{active.condition}</strong><p>{active.detail||'Live condition monitoring combines telemetry, stroke diagnostics and asset context.'}</p></div>
        <div className="ops-reading-grid"><div><span>Stroke rate</span><strong>— spm</strong></div><div><span>Controller fillage</span><strong>— %</strong></div><div><span>AC input</span><strong>— kW</strong></div><div><span>Mean line current</span><strong>— A</strong></div></div>
        <div className="ops-diagnostics"><div><span>Surface dynacard</span><div className="ops-chart-placeholder">Live stroke trace available in diagnostics</div></div><div><span>Downhole dynacard</span><div className="ops-chart-placeholder">Reconstructed pump card available in diagnostics</div></div></div>
      </>:<p className="note">No wells are registered.</p>}</section>
    </div>
  </div>;
}
