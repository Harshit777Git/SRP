import {useEffect,useState} from 'react';
import {Action,Chart,Panel,request} from '../../ui/components';
import {PlaybackStroke,TimedCard} from './playback';

type Imported=TimedCard & {asset_id:string;stroke_id:number;kind:string;warnings:string[];source:string;quality:string};
type Dataset={dataset_id:string;filename:string;kind:string;records:number;cards?:Imported[];configuration?:unknown;headers?:string[]};
export function Engineering({base,asset,stroke,exportUrl,benchmarkOnly}:{base:string;asset:string;stroke?:PlaybackStroke;exportUrl:string;benchmarkOnly:boolean}){
  const [content,setContent]=useState(''),[filename,setFilename]=useState(''),[kind,setKind]=useState('surface');
  const [mapping,setMapping]=useState<Record<string,string>>({}),[positionUnit,setPositionUnit]=useState('in'),[loadUnit,setLoadUnit]=useState('lbf');
  const [provenance,setProvenance]=useState(''),[well,setWell]=useState(''),[strokeId,setStrokeId]=useState('1');
  const [error,setError]=useState(''),[status,setStatus]=useState(''),[preview,setPreview]=useState<Dataset>();
  const [datasets,setDatasets]=useState<Dataset[]>([]),[dataset,setDataset]=useState<Dataset>(),[index,setIndex]=useState(0);
  const [confirmed,setConfirmed]=useState(false),[report,setReport]=useState<unknown>();
  const refresh=()=>request<Dataset[]>(base+'/interchange').then(setDatasets).catch(e=>setError(e.message));
  useEffect(()=>{void refresh();},[base,benchmarkOnly]);
  useEffect(()=>{setReport(undefined);setConfirmed(false);},[asset,stroke?.run_id,stroke?.stroke_id,dataset?.dataset_id,index]);
  async function chooseFile(file?:File){
    if(!file)return;
    setPreview(undefined);setStatus('');setError('');
    try{
      if(file.size>1600000)throw new Error('Select a file smaller than 1.6 MB.');
      const bytes=new Uint8Array(await file.arrayBuffer());
      let text:string;
      if(bytes[0]===255&&bytes[1]===254)text=new TextDecoder('utf-16le').decode(bytes);
      else if(bytes[0]===254&&bytes[1]===255)text=new TextDecoder('utf-16be').decode(bytes);
      else {try{text=new TextDecoder('utf-8',{fatal:true}).decode(bytes);}
        catch{text=new TextDecoder('windows-1252').decode(bytes);}}
      setContent(text);setFilename(file.name);
    }catch(e){setError((e as Error).message);}
  }
  async function parse(save:boolean){
    setError('');setStatus('');
    try{
      const result=await request<Dataset>(base+'/interchange',{filename,content,kind,mapping:Object.fromEntries(
        Object.entries(mapping).filter(([,value])=>value.trim())),position_unit:positionUnit,load_unit:loadUnit,
        well_id:well,stroke_id:strokeId,provenance,save});
      setPreview(result);
      if(save){setStatus('Dataset saved. Identical imports use the same dataset ID.');void refresh();}
    }catch(e){setError((e as Error).message);}
  }
  async function selectDataset(id:string){
    setDataset(undefined);setIndex(0);setReport(undefined);setError('');
    if(!id)return;
    try{setDataset(await request<Dataset>(base+'/interchange/'+id));}
    catch(e){setError((e as Error).message);}
  }
  async function compare(){
    if(!stroke||!dataset)return;
    setError('');
    try{setReport(await request(base+'/benchmark',{asset,run:stroke.run_id,stroke:stroke.stroke_id,
      dataset_id:dataset.dataset_id,index,confirmed}));}
    catch(e){setReport(undefined);setError((e as Error).message);}
  }
  function download(){
    const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'}));
    const a=document.createElement('a');a.href=url;a.download='srp_comparison.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  const candidate=dataset?.cards?.[index];
  const operating=candidate?.kind==='downhole'?stroke?.downhole:stroke?.surface;
  const series=(card?:Partial<TimedCard>,secondary=false)=>({x:card?.position_m??[],y:card?.load_n?.map(f=>f/1000)??[],secondary});
  const types=['raw','surface','downhole','configuration','diagnostics','synchronized'];
  return <>
    {error&&<p role="alert" className="error">{error}</p>}
    {status&&<p role="status">{status}</p>}
    {!benchmarkOnly?<><Panel title="Export selected stroke" meta={stroke?`Stroke ${stroke.stroke_id}`:undefined}>
      <div className="actions">{stroke?.asset_configuration&&<a href={exportUrl+'&format=configuration-json'}>configuration JSON</a>}
        {exportUrl?types.filter(name=>!['synchronized','downhole'].includes(name)||stroke?.downhole.status==='SOLVED')
        .map(name=><a key={name} href={exportUrl+'&format=engineering&kind='+name} download={'srp_'+name+'.csv'}>{name} CSV</a>)
        :<p className="note">Select a completed stroke to export.</p>}</div>
    </Panel><Panel title="Import numerical data">
      <div className="formgrid">
        <label className="field">Data file<input type="file" accept=".csv,.tsv,.txt,.json,.dyn" onChange={e=>void chooseFile(e.target.files?.[0])}/></label>
        <label className="field">Record type<select value={kind} onChange={e=>{setKind(e.target.value);setPreview(undefined);}}>
          {types.slice(0,4).map(t=><option key={t}>{t}</option>)}</select></label>
        <label className="field">Source / provenance<input value={provenance} onChange={e=>setProvenance(e.target.value)} placeholder="e.g. TAM Well 17 export"/></label>
      </div>
      {kind!=='configuration'&&<details><summary>Map nonstandard columns and units</summary>
        <p className="note">Enter exact column headers. Leave a field blank for the SRP contract name. Supply well and stroke identity if the file lacks these columns.</p>
        {content&&<p className="mono">{content.split(/\r?\n/)[0]}</p>}
        <div className="formgrid">
          {['position','load','index','timestamp','well','stroke'].map(field=><label className="field" key={field}>{field} column
            <input value={mapping[field]??''} onChange={e=>setMapping({...mapping,[field]:e.target.value})}/></label>)}
          <label className="field">Position unit<select value={positionUnit} onChange={e=>setPositionUnit(e.target.value)}>{['in','ft','m'].map(u=><option key={u}>{u}</option>)}</select></label>
          <label className="field">Load unit<select value={loadUnit} onChange={e=>setLoadUnit(e.target.value)}>{['lbf','N','kN'].map(u=><option key={u}>{u}</option>)}</select></label>
          <label className="field">Fallback source well<input value={well} onChange={e=>setWell(e.target.value)}/></label>
          <label className="field">Fallback source stroke<input type="number" value={strokeId} onChange={e=>setStrokeId(e.target.value)}/></label>
        </div>
      </details>}
      <div className="actions"><Action primary disabled={!content} onClick={()=>void parse(false)}>Preview import</Action>
        <Action disabled={!preview?.cards} onClick={()=>void parse(true)}>Save dataset</Action></div>
      {preview?.configuration!==undefined?<pre>{JSON.stringify(preview.configuration,null,2)}</pre>:preview?.cards&&
        <><p className="note">{preview.records} rows · {preview.cards.length} strokes · {preview.filename}</p>
          <ul>{preview.cards.slice(0,8).map(c=><li key={c.asset_id+'/'+c.stroke_id}>{c.asset_id} / {c.stroke_id} · {c.quality} · {c.warnings.join(', ')||'Validated sample ordering'}</li>)}</ul>
          <Chart label="Imported stroke preview" xLabel="Displacement (m)" yLabel="Load (kN)" series={[series(preview.cards[0])]}/></>}
    </Panel></>:<Panel title="Compare operating and imported strokes" meta={stroke?`Operating stroke ${stroke.stroke_id}`:undefined}>
      <div className="formgrid">
        <label className="field">Imported dataset<select aria-label="Imported dataset" value={dataset?.dataset_id??''} onChange={e=>void selectDataset(e.target.value)}>
          <option value="">Select a saved dataset</option>{datasets.map(d=><option key={d.dataset_id} value={d.dataset_id}>{d.filename} · {d.kind}</option>)}</select></label>
        <label className="field">Imported stroke<select value={index} onChange={e=>setIndex(+e.target.value)}>
          {dataset?.cards?.map((c,i)=><option key={i} value={i}>{c.asset_id} · {c.stroke_id} · {c.source}</option>)}</select></label>
      </div>
      {candidate&&<Chart label="Engineering card overlay" xLabel="Displacement (m)" yLabel="Load (kN)" series={[series(operating),series(candidate,true)]}/>}
      <p className="note">Solid line shows the selected APM stroke. Dashed line shows imported data in SI units. Use Historical Analytics to pin an operating stroke.</p>
      <label><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>
        Equipment, operating conditions, and cycle origin are comparable.</label>
      <div className="actions"><Action primary disabled={!stroke||!candidate} onClick={()=>void compare()}>Calculate comparison</Action>
        <Action disabled={!report} onClick={download}>Download comparison report</Action></div>
      {report!==undefined&&<pre>{JSON.stringify(report,null,2)}</pre>}
    </Panel>}
  </>;
}
