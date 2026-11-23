import { ReactNode, useEffect, useRef, useState } from 'react';
import Button from '@mui/material/Button';
import CssBaseline from '@mui/material/CssBaseline';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import './style.css';

export function api(port: number) {
  return (import.meta.env as Record<string,string|undefined>).VITE_API_URL
    || `${location.protocol}//${location.hostname}:${port}`;
}

export async function request<T>(url: string, body?: unknown): Promise<T> {
  const response = await fetch(url, body === undefined ? undefined : {
    method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body)
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || response.statusText);
  return result;
}

export function useStream<T>(url: string) {
  const [data,setData] = useState<T>();
  const [online,setOnline] = useState(false);
  useEffect(() => {
    setData(undefined);
    const source = new EventSource(url);
    source.onmessage = event => {setData(JSON.parse(event.data)); setOnline(true);};
    source.onerror = () => setOnline(false);
    return () => source.close();
  },[url]);
  return {data,online};
}

export function Shell({product,title,description,tabs,selected,select,children}:{
  product:string; title:string; description:string; tabs:string[]; selected:string;
  select:(tab:string)=>void; children:ReactNode;
}) {
  const [dark,setDark] = useState(localStorage.getItem('srp-reference-theme')==='dark');
  const theme = createTheme({palette:{mode:dark?'dark':'light',primary:{main:dark?'#54e4c5':'#087967'}},
    typography:{fontFamily:'system-ui, sans-serif',button:{textTransform:'none',fontWeight:700}}});
  return <ThemeProvider theme={theme}><CssBaseline/>
    <div className="shell" data-theme={dark?'dark':'light'}>
      <aside><div className="brand"><div className="mark">⍲</div><div>SRP Industrial<small>{product}</small></div></div>
        <nav>{tabs.map((tab,index)=><button key={tab} aria-current={tab===selected?'page':undefined}
          className={tab===selected?'active':''} onClick={()=>select(tab)}>
          <span aria-hidden>{['◈','⌁','▥','◇','⛶','◷','▤'][index]}</span>{tab}</button>)}</nav>
        <button className="theme" onClick={()=>{localStorage.setItem('srp-reference-theme',dark?'light':'dark');setDark(!dark);}}>
          {dark?'☀ Light theme':'☾ Dark theme'}</button>
      </aside>
      <main><header className="heading"><div className="eyebrow">{product}</div><h1>{title}</h1>
        <p>{description}</p></header>{children}</main>
    </div>
  </ThemeProvider>;
}

export function Panel({title,meta,children}: {title:string;meta?:string;children:ReactNode}) {
  return <section className="panel"><div className="panelHead"><h2>{title}</h2>{meta&&<span>{meta}</span>}</div>{children}</section>;
}

export function Status({good,children}:{good:boolean;children:ReactNode}) {
  return <span className={good?'status good':'status'}><i/>{children}</span>;
}

export function Metrics({items}:{items:[string,string|number][]}) {
  return <div className="metrics">{items.map(([label,value])=><div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>;
}

export function Action({children,onClick,primary=false,disabled=false}:{
  children:ReactNode;onClick:()=>void;primary?:boolean;disabled?:boolean;
}) {
  return <Button size="small" variant={primary?'contained':'outlined'} onClick={onClick} disabled={disabled}>{children}</Button>;
}

export const fmt = (n?:number,digits=1) => n===undefined || !Number.isFinite(n)?'—':n.toLocaleString(undefined,{maximumFractionDigits:digits});

export type Series = {x:number[];y:number[];secondary?:boolean};
export function Chart({series,label,xLabel,yLabel,height=275,marker}:{
  series:Series[];label:string;xLabel:string;yLabel:string;height?:number;marker?:{x:number;y:number};
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(()=>{
    const canvas=ref.current;
    if (!canvas) return;
    function draw() {
      const c=ref.current!;
      const width=c.clientWidth;
      if (!width) return;
      const scale=devicePixelRatio;
      c.width=width*scale;c.height=height*scale;
      const ctx=c.getContext('2d')!;
      ctx.scale(scale,scale);
      const styles=getComputedStyle(c);
      const available=series.filter(s=>s.x.length>=2&&s.y.length===s.x.length);
      const xs=available.flatMap(s=>s.x),ys=available.flatMap(s=>s.y);
      if(marker){xs.push(marker.x);ys.push(marker.y);}
      const minX=xs.length?Math.min(...xs):0,maxX=xs.length?Math.max(...xs):1;
      const minY=ys.length?Math.min(...ys):0,maxY=ys.length?Math.max(...ys):1;
      const left=58,top=20,right=width-17,bottom=height-42;
      const x=(v:number)=>left+(v-minX)/Math.max(1e-8,maxX-minX)*(right-left);
      const y=(v:number)=>bottom-(v-minY)/Math.max(1e-8,maxY-minY)*(bottom-top);
      ctx.font='11px IBM Plex Mono, monospace';
      ctx.fillStyle=styles.getPropertyValue('--muted');
      for(let i=0;i<=4;i++){
        const gx=left+(right-left)*i/4, gy=bottom-(bottom-top)*i/4;
        ctx.strokeStyle=styles.getPropertyValue('--line');
        ctx.beginPath();ctx.moveTo(left,gy);ctx.lineTo(right,gy);ctx.moveTo(gx,bottom);ctx.lineTo(gx,top);ctx.stroke();
        ctx.textAlign='right';ctx.fillText(fmt(minY+(maxY-minY)*i/4,1),left-7,gy+4);
        ctx.textAlign='center';ctx.fillText(fmt(minX+(maxX-minX)*i/4,1),gx,bottom+16);
      }
      ctx.textAlign='center';ctx.fillText(xLabel,(left+right)/2,height-6);
      ctx.save();ctx.translate(12,(top+bottom)/2);ctx.rotate(-Math.PI/2);ctx.fillText(yLabel,0,0);ctx.restore();
      for (const line of available) {
        ctx.strokeStyle=styles.getPropertyValue(line.secondary?'--secondary':'--accent');
        ctx.lineWidth=line.secondary?1.4:2.3;
        ctx.setLineDash(line.secondary?[4,4]:[]);
        ctx.beginPath();
        line.x.forEach((v,i)=>i?ctx.lineTo(x(v),y(line.y[i])):ctx.moveTo(x(v),y(line.y[i])));
        ctx.stroke();
      }
      if(marker){
        ctx.fillStyle=styles.getPropertyValue('--text');
        ctx.beginPath();ctx.arc(x(marker.x),y(marker.y),4,0,2*Math.PI);ctx.fill();
      }
      if (!available.length&&!marker) ctx.fillText('Waiting for samples',(left+right)/2,(top+bottom)/2);
    }
    draw();const resize=new ResizeObserver(draw);resize.observe(canvas);
    return ()=>resize.disconnect();
  },[series,height,xLabel,yLabel,marker]);
  return <canvas role="img" aria-label={label} ref={ref} style={{height,width:'100%',display:'block'}}/>;
}
