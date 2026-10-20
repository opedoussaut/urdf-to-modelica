import { useEffect, useRef, useState } from "react";
import { useAudience } from "./audience";
import { request, waitJob, message } from "./studio";
import KinematicSchematic, { schematicApplies } from "./KinematicSchematic";

type Props={model:string;path:string;hash:string;selected?:string;dirty:boolean;onSelect:(name:string)=>void;onOpen:(type:string)=>void};
const color=(v:any, fallback="#253e5a")=>Array.isArray(v)?`rgb(${v.join(',')})`:fallback;
const enumeration=(v:any)=>v?.name?.split('.').at(-1) || v;
const point=(v:any)=>Array.isArray(v)&&v.length===2&&v.every(Number.isFinite);

/** Render evaluated OMC primitives, never arbitrary SVG/HTML from Modelica source. */
function Graphic({g,name}:{g:any;name:string}) {
  const e=g.elements||[];
  if(e[0]===false)return null;
  const line=g.name==='Line';
  const origin=point(e[1])?e[1]:[0,0],rotation=typeof e[2]==='number'?e[2]:0;
  const stroke=color(e[3]),fill=enumeration(e[6])==='None'?'none':color(e[4],'none');
  const common={stroke,strokeWidth:typeof e[line?5:7]==='number'?Math.max(.35,e[line?5:7]):.5,fill};
  const extent=e[g.name==='Rectangle'?9:8];
  const rect=Array.isArray(extent)&&extent.length===2&&extent.every(point)?{
    x:Math.min(extent[0][0],extent[1][0]),y:Math.min(extent[0][1],extent[1][1]),
    width:Math.abs(extent[1][0]-extent[0][0]),height:Math.abs(extent[1][1]-extent[0][1])}:null;
  let shape=null;
  if(g.name==='Rectangle'&&rect)shape=<rect {...rect} {...common} rx={Number(e[10])||0}/>;
  if(g.name==='Ellipse'&&rect)shape=<ellipse cx={rect.x+rect.width/2} cy={rect.y+rect.height/2} rx={rect.width/2} ry={rect.height/2} {...common}/>;
  const points=e[line?6:8];
  if((line||g.name==='Polygon')&&Array.isArray(points)&&points.every(point)) {
    const p=points.map((p:number[])=>p.join(',')).join(' ');
    shape=line?<polyline points={p} fill="none" stroke={stroke} strokeWidth={common.strokeWidth} strokeDasharray={enumeration(e[4])==='Dash'?'3 2':undefined}/>:<polygon points={p} {...common}/>;
  }
  if(g.name==='Text'&&rect) {
    const label=typeof e[9]==='string'?e[9].replaceAll('%name',name):'';
    shape=<text transform={`translate(${rect.x+rect.width/2} ${rect.y+rect.height/2}) scale(1 -1)`} textAnchor="middle" dominantBaseline="middle" fill={color(e[11],stroke)} fontSize={Number(e[10])||Math.min(14,Math.max(7,rect.height*.55))} fontFamily="Arial, sans-serif">{label}</text>;
  }
  return <g transform={`translate(${origin.join(' ')}) rotate(${rotation})`}>{shape}</g>;
}
function Graphics({layer,name}:{layer:any;name:string}) {return <>{(layer?.graphics||[]).map((g:any,i:number)=><Graphic key={i} g={g} name={name}/>)}</>}

/** Pan (drag) and zoom (wheel or buttons) an SVG by its viewBox; Fit restores the whole drawing. */
function ZoomSvg({box,label,children}:{box:number[];label:string;children:React.ReactNode}) {
  const [vb,setVb]=useState(box),svg=useRef<SVGSVGElement>(null),drag=useRef<{x:number;y:number;vb:number[]}|null>(null);
  useEffect(()=>setVb(box),[box.join(',')]);
  const zoom=(f:number,cx=vb[0]+vb[2]/2,cy=vb[1]+vb[3]/2)=>setVb(([x,y,w,h])=>{
    const nw=Math.min(Math.max(w*f,box[2]/40),box[2]*4),k=nw/w;
    return [cx-(cx-x)*k,cy-(cy-y)*k,nw,h*k];
  });
  const toSvg=(e:{clientX:number;clientY:number})=>{
    const r=svg.current!.getBoundingClientRect(),s=Math.max(vb[2]/r.width,vb[3]/r.height);
    const ox=(r.width*s-vb[2])/2,oy=(r.height*s-vb[3])/2;
    return [vb[0]-ox+(e.clientX-r.left)*s,vb[1]-oy+(e.clientY-r.top)*s,s];
  };
  useEffect(()=>{
    const el=svg.current;if(!el)return;
    const wheel=(e:WheelEvent)=>{e.preventDefault();const [cx,cy]=toSvg(e);zoom(e.deltaY>0?1.2:1/1.2,cx,cy)};
    el.addEventListener('wheel',wheel,{passive:false});
    return ()=>el.removeEventListener('wheel',wheel);
  });
  return <div className="wb-zoom">
    <div className="wb-zoom-tools" role="group" aria-label="Zoom">
      <button onClick={()=>zoom(1/1.4)} aria-label="Zoom in">+</button>
      <button onClick={()=>zoom(1.4)} aria-label="Zoom out">−</button>
      <button onClick={()=>setVb(box)}>Fit</button>
      <span>{Math.round(box[2]/vb[2]*100)} %</span>
    </div>
    <svg ref={svg} viewBox={vb.join(' ')} role="img" aria-label={label}
      onPointerDown={e=>{if((e.target as Element).closest('.wb-diagram-component'))return;drag.current={x:e.clientX,y:e.clientY,vb};(e.currentTarget as Element).setPointerCapture(e.pointerId)}}
      onPointerMove={e=>{const d=drag.current;if(!d)return;const s=toSvg(e)[2];setVb([d.vb[0]-(e.clientX-d.x)*s,d.vb[1]-(e.clientY-d.y)*s,d.vb[2],d.vb[3]])}}
      onPointerUp={()=>{drag.current=null}}>
      {children}
    </svg>
  </div>;
}

export default function ModelicaDiagram({model,path,hash,selected,dirty,onSelect,onOpen}:Props) {
  const simple=useAudience()==='simple';
  const [data,setData]=useState<any>(),[error,setError]=useState(''),[busy,setBusy]=useState(false),[pick,setView]=useState<'schematic'|'native'>('schematic');
  // The native annotation preview is a tool-level view for Modelica engineers; Simple mode keeps the schematic.
  const view=simple?'schematic':pick;
  useEffect(()=>{
    let disposed=false;setData(undefined);setError('');
    if(dirty)return;
    setBusy(true);
    request(`/model/${model}/diagram?path=${encodeURIComponent(path)}`,'POST')
      .then(waitJob).then(d=>{if(!disposed)setData(d)})
      .catch(e=>{if(!disposed)setError(message(e))}).finally(()=>{if(!disposed)setBusy(false)});
    return ()=>{disposed=true};
  },[model,path,hash,dirty]);
  const extent=data?.diagram.coordinateSystem?.extent||[[-100,-100],[100,100]];
  const x=extent[0][0]-20,y=-extent[1][1]-20,w=extent[1][0]-extent[0][0]+40,h=extent[1][1]-extent[0][1]+40;
  const routed=data?.connections.filter((c:any)=>c.annotation?.Line)||[];
  return <div className="wb-native-diagram">
    {(() => {
      const applies=!!data&&schematicApplies(data.components,data.connections);
      return <div className="wb-diagram-caption">
        <strong>{applies&&view==='schematic'?'Kinematic schematic':'Modelica annotation preview'}</strong>
        {applies&&!simple&&<span className="wb-diagram-toggle" role="group" aria-label="Diagram view">
          <button aria-pressed={view==='schematic'} className={view==='schematic'?'on':''} onClick={()=>setView('schematic')}>Kinematic schematic</button>
          <button aria-pressed={view==='native'} className={view==='native'?'on':''} onClick={()=>setView('native')}>Native annotations</button>
        </span>}
        <span>READ ONLY · FROM OPENMODELICA</span>
      </div>;
    })()}
    {!dirty&&!busy&&!error&&data&&view==='schematic'&&schematicApplies(data.components,data.connections)?
      <KinematicSchematic components={data.components} connections={data.connections} selected={selected} onSelect={onSelect} onOpen={onOpen}/>
    :dirty?<p className="wb-notice">Save this revision to preview its compiler-evaluated annotations. Your unsaved source is retained.</p>:busy?<p className="wb-notice">OpenModelica is reading component icons, placements and connections…</p>:error?<p className="wb-error" role="alert">{error}</p>:data&&<>
      <ZoomSvg box={[x,y,w,h]} label={`OpenModelica diagram ${data.class_name}`}>
        <g transform="scale(1 -1)">
          <Graphics layer={data.diagram} name={data.class_name}/>
          {routed.map((c:any,i:number)=>{
            const line=c.annotation.Line;
            return <g key={i}><title>{c.from} ↔ {c.to}</title>{line.$kind?<Graphic g={line} name=""/>:Array.isArray(line.points)&&line.points.every(point)?<polyline points={line.points.map((p:number[])=>p.join(',')).join(' ')} fill="none" stroke={color(line.color)} strokeWidth={line.thickness||.5}/>:null}</g>;
          })}
          {data.components.map((c:any)=>{
            const t=c.placement.transformation;if(!t)return null;
            const ext=t.extent||[[-10,-10],[10,10]],origin=t.origin||[0,0];
            const cs=c.icon.coordinateSystem?.extent||[[-100,-100],[100,100]];
            const sx=(ext[1][0]-ext[0][0])/(cs[1][0]-cs[0][0]),sy=(ext[1][1]-ext[0][1])/(cs[1][1]-cs[0][1]);
            return <g key={c.name} role="button" tabIndex={0} aria-label={`Inspect ${c.name}`} className="wb-diagram-component"
              onClick={()=>onSelect(c.name)} onDoubleClick={()=>onOpen(c.type)} onKeyDown={e=>{if(e.key==='Enter')onSelect(c.name)}}
              transform={`translate(${origin.join(' ')}) rotate(${t.rotation||0}) translate(${(ext[0][0]+ext[1][0])/2} ${(ext[0][1]+ext[1][1])/2}) scale(${sx} ${sy}) translate(${-(cs[0][0]+cs[1][0])/2} ${-(cs[0][1]+cs[1][1])/2})`}>
              <title>{c.name} · {c.type} · double-click to open class</title>
              <rect x={cs[0][0]} y={cs[0][1]} width={cs[1][0]-cs[0][0]} height={cs[1][1]-cs[0][1]} fill="transparent" stroke={selected===c.name?'#0d9488':'transparent'} strokeWidth={6}/>
              <Graphics layer={c.icon} name={c.name}/>
            </g>;
          })}
        </g>
      </ZoomSvg>
      <p className="wb-footnote">Drag to pan · wheel or +/− to zoom · {data.method} · revision {data.revision.slice(0,8)} · {routed.length}/{data.connections.length} connections have native routes. Click to inspect; double-click to open a component class.</p>
      <details><summary>Connection inventory and preview limitations</summary><ul>{data.connections.map((c:any,i:number)=><li key={i}><code>{c.from} ↔ {c.to}</code>{!c.annotation?.Line?' · no native Line annotation':''}</li>)}</ul>{data.limitations.map((l:string)=><p key={l}>{l}</p>)}</details>
    </>}
  </div>;
}
