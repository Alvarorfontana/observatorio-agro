import {EnsoHistoricalLab} from "./EnsoHistoricalLab";
import {useEffect,useMemo,useState} from "react";
import {ENSO_SOURCES} from "../lib/ensoSourceRegistry";
type Point={month:string;season:string;anomalyC:number};
const panels=[
 {title:"Temperatura superficial del Pacífico ecuatorial",src:"https://ftp.cpc.ncep.noaa.gov/CPC/li.xu/enso/ssta_last-4weeks.png",desc:"NOAA CPC · anomalías de temperatura superficial, últimas cuatro semanas"},
 {title:"Temperatura subsuperficial",src:"https://ftp.cpc.ncep.noaa.gov/CPC/li.xu/enso/zlon_last.png",desc:"NOAA CPC · sección vertical ecuatorial de anomalías oceánicas"},
 {title:"Contenido de calor oceánico",src:"https://ftp.cpc.ncep.noaa.gov/CPC/li.xu/enso/heat-last-year.png",desc:"NOAA CPC · evolución del contenido térmico subsuperficial"},
 {title:"Vientos ecuatoriales a 850 hPa",src:"https://ftp.cpc.ncep.noaa.gov/CPC/li.xu/enso/uv850_last30days.png",desc:"NOAA CPC · circulación atmosférica"},
 {title:"Radiación saliente OLR",src:"https://ftp.cpc.ncep.noaa.gov/CPC/li.xu/enso/olra_last30days.png",desc:"NOAA CPC · convección tropical"},
 {title:"Probabilidades oficiales de ENSO",src:"https://ftp.cpc.ncep.noaa.gov/CPC/li.xu/enso/CPCoffprobs.png",desc:"NOAA CPC · pronóstico probabilístico; fecha y período en la figura"},
 {title:"Pronóstico de intensidad",src:"https://ftp.cpc.ncep.noaa.gov/CPC/li.xu/enso/CPCstrengthprobs.png",desc:"NOAA CPC · distribución probabilística de intensidad"},
 {title:"Anomalía relativa Niño 3.4",src:"https://ftp.cpc.ncep.noaa.gov/CPC/li.xu/enso/roni.png",desc:"NOAA CPC · indicador relativo, no idéntico al ONI"}
];
type TeleObservation={month:string;value:number};
type TelePayload={provider:string;stale?:boolean;status:Record<string,string>;indices:Record<string,{source:string;observations:TeleObservation[]}>};
const teleLabels:Record<string,string>={soi:"Oscilación del Sur (SOI)",pna:"Pacífico–Norteamérica (PNA)",aao:"Oscilación Antártica (AAO)",nao:"Oscilación del Atlántico Norte (NAO)",ao:"Oscilación Ártica (AO)",tni:"Índice Trans-Niño (TNI)",oni:"ONI (serie PSL; contrastar con CPC)"};
function TeleconnectionsPanel(){
 const [data,setData]=useState<TelePayload|null>(null);
 const [loading,setLoading]=useState(true);
 const [error,setError]=useState("");
 const [selected,setSelected]=useState("soi");
 useEffect(()=>{const controller=new AbortController();fetch("/api/enso/teleconnections",{signal:controller.signal})
 .then(async response=>{const json=await response.json();if(!response.ok)throw Error(json.error||"Fuente NOAA no disponible");return json as TelePayload})
 .then(json=>{if(!controller.signal.aborted)setData(json)})
 .catch(e=>{if(!controller.signal.aborted)setError(String(e))})
 .finally(()=>{if(!controller.signal.aborted)setLoading(false)});
 return ()=>controller.abort()},[]);
 const available=Object.keys(data?.indices||{});
 const key=available.includes(selected)?selected:available[0];
 const series=(key&&data?.indices[key]?.observations||[]).slice(-120);
 const values=series.map(p=>p.value);
 const lo=Math.min(-1,...values),hi=Math.max(1,...values),span=hi-lo||1;
 const points=series.map((p,i)=>`${30+i*730/Math.max(1,series.length-1)},${175-(p.value-lo)*145/span}`).join(" ");
 return <section aria-label="Teleconexiones NOAA" style={{marginTop:18,padding:14,background:"#183744",borderRadius:10}}>
 <h3>Índices atmosféricos y oceánicos · NOAA PSL</h3>
 <p>Series mensuales observadas, independientes del ONI trimestral oficial. No se generan valores sintéticos.</p>
 {loading&&<p role="status">Consultando índices NOAA…</p>}
 {error&&<p role="alert">{error}</p>}
 {data?.stale&&<p role="status">Datos en caché: no se pudo actualizar la fuente.</p>}
 {available.length>0&&<><label>Índice <select value={key} onChange={e=>setSelected(e.target.value)}>{available.map(k=><option key={k} value={k}>{teleLabels[k]||k}</option>)}</select></label>
 <svg viewBox="0 0 800 205" role="img" aria-label={`Serie mensual NOAA de ${teleLabels[key]||key}`} style={{width:"100%",marginTop:12,background:"#0c2834",borderRadius:8}}>
 <line x1="30" x2="760" y1={175-(0-lo)*145/span} y2={175-(0-lo)*145/span} stroke="#a2bbc7" strokeDasharray="4 5"/>
 <polyline points={points} fill="none" stroke="#71d6eb" strokeWidth="2"/>
 <text x="30" y="195" fontSize="13" fill="#e3eef3">{series[0]?.month||""}</text>
 <text x="685" y="195" fontSize="13" fill="#e3eef3">{series[series.length-1]?.month||""}</text></svg>
 <p>Último dato disponible: <strong>{series[series.length-1]?.month||"Sin datos"} · {series[series.length-1]?.value ?? "—"}</strong>. Ventana: hasta 120 meses.</p>
 <a href={data!.indices[key].source} target="_blank" rel="noreferrer" style={{color:"#a7e4ff"}}>Consultar archivo original NOAA PSL ↗</a></>}
 {!loading&&data&&available.length===0&&<p>No hay series disponibles en este momento.</p>}
 </section>
}

export function EnsoObservatory(){
 const [points,setPoints]=useState<Point[]>([]),[error,setError]=useState(""),[loading,setLoading]=useState(true);
 const [sourceFilter,setSourceFilter]=useState("Todas");
 const [count,setCount]=useState(72),[selected,setSelected]=useState(0),[play,setPlay]=useState(false);
 useEffect(()=>{const ctrl=new AbortController();fetch("/api/enso/oni",{signal:ctrl.signal}).then(async r=>{const j=await r.json();if(!r.ok)throw Error(j.error||"Fuente no disponible");return j}).then(j=>{if(!ctrl.signal.aborted){setPoints(j.points||[]);setSelected(Math.max(0,(j.points||[]).length-1))}}).catch(e=>{if(!ctrl.signal.aborted)setError(String(e))}).finally(()=>{if(!ctrl.signal.aborted)setLoading(false)});return()=>ctrl.abort()},[]);
 const data=useMemo(()=>points.slice(-count),[points,count]);
 useEffect(()=>{if(!play||data.length<2)return;const timer=window.setInterval(()=>setSelected(i=>(i+1)%data.length),700);return()=>window.clearInterval(timer)},[play,data.length]);
 useEffect(()=>{setSelected(Math.max(0,data.length-1))},[count,points.length]);
 const current=data[Math.min(selected,data.length-1)];
 const min=-3.5,max=3.5,chartWidth=800,chartHeight=240;
 const coords=data.map((p,i)=>({x:50+(i/Math.max(1,data.length-1))*720,y:25+(max-Math.max(min,Math.min(max,p.anomalyC)))/(max-min)*175}));
 const path=coords.map((p,i)=>(i?"L":"M")+p.x.toFixed(1)+" "+p.y.toFixed(1)).join(" ");
 function exportCsv(){const rows=["mes,estacion,oni_c",...data.map(p=>[p.month,p.season,p.anomalyC].join(","))];const blob=new Blob([rows.join("\n")],{type:"text/csv;charset=utf-8"});const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;a.download="dots-enso-noaa-oni.csv";a.click();URL.revokeObjectURL(url)}
 function report(){const latest=points[points.length-1];const w=window.open("","_blank");if(!w)return;const escape=(v:string)=>v.replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]||c));w.document.write('<!doctype html><html lang="es"><head><meta charset="utf-8"><title>DOTS · Informe ENSO</title><style>body{font:15px Arial;max-width:800px;margin:45px auto;line-height:1.6}h1{color:#16475d}small{color:#555}</style></head><body><h1>DOTS Campo · Informe técnico ENSO</h1><p>Emisión: '+escape(new Date().toISOString().slice(0,10))+'</p><h2>Última observación ONI disponible</h2><p>'+ (latest?escape(latest.season+" "+latest.month+": "+latest.anomalyC.toFixed(1)+" °C"):"No disponible")+'</p><h2>Interpretación</h2><p>El ONI es un índice de anomalías trimestrales superpuestas. Un único valor no confirma por sí solo un episodio ENSO ni permite predecir efectos locales.</p><h2>Fuentes</h2><p>NOAA CPC: https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt</p><p>IRI Columbia: https://iri.columbia.edu/our-expertise/climate/forecasts/enso/current/</p><h2>Limitaciones</h2><p>Las imágenes oceánicas y atmosféricas deben interpretarse con su propia fecha de actualización. Las proyecciones no son observaciones ni garantizan impactos sobre cuencas particulares.</p><small>Documento generado automáticamente por DOTS Campo. Verificar fecha y consistencia de los productos oficiales.</small></body></html>');w.document.close();w.print()}
 return <section aria-label="Observatorio ENSO NOAA IRI" style={{background:"#102631",color:"#eff7fa",padding:16,borderRadius:12,margin:"14px 0"}}>
 <h2 style={{marginTop:0}}>Observatorio ENSO · NOAA / IRI Columbia</h2>
 <p>Monitoreo oceánico-atmosférico, índice ONI histórico y paneles oficiales actualizables. Los productos mantienen su autoría y fecha de emisión.</p>
 {loading&&<p role="status">Consultando serie oficial NOAA…</p>}{error&&<p role="alert">No se pudo cargar la serie ONI: {error}</p>}
 {points.length>0&&<><div style={{display:"flex",gap:14,flexWrap:"wrap",alignItems:"center"}}><strong>Último ONI: {points[points.length-1].anomalyC.toFixed(1)} °C · {points[points.length-1].season} {points[points.length-1].month}</strong><label>Ventana histórica <select value={count} onChange={e=>setCount(Number(e.target.value))}><option value={24}>24 trimestres</option><option value={72}>72 trimestres</option><option value={144}>144 trimestres</option><option value={9999}>Toda la serie</option></select></label></div>
 <div style={{overflowX:"auto"}}><svg viewBox={"0 0 "+chartWidth+" "+chartHeight} role="img" aria-label="Evolución temporal del índice ONI de NOAA" style={{width:"100%",minWidth:450,background:"#192f3a",borderRadius:8,marginTop:12}}>
 {[0.5,0,-0.5].map(v=><g key={v}><line x1={50} x2={770} y1={25+(max-v)/(max-min)*175} y2={25+(max-v)/(max-min)*175} stroke={v===0?"#c5d6dc":"#67828e"} strokeDasharray="5 5"/><text x={9} y={30+(max-v)/(max-min)*175} fontSize={13} fill="#e7f0f5">{v.toFixed(1)}</text></g>)}
 <path d={path} fill="none" stroke="#6fd3ef" strokeWidth={2.5}/>{current&&coords[Math.min(selected,coords.length-1)]&&<circle cx={coords[Math.min(selected,coords.length-1)].x} cy={coords[Math.min(selected,coords.length-1)].y} r={6} fill="#ffce73" stroke="#fff" strokeWidth={2}/>}<text x={50} y={224} fill="#d8e9ef" fontSize={12}>{data[0]?.month}</text><text x={690} y={224} fill="#d8e9ef" fontSize={12}>{data[data.length-1]?.month}</text></svg></div>
 <label style={{display:"block",marginTop:8}}>Recorrer observaciones <input type="range" min={0} max={Math.max(0,data.length-1)} value={Math.min(selected,Math.max(0,data.length-1))} onChange={e=>{setPlay(false);setSelected(Number(e.target.value))}} style={{width:"100%"}}/></label><p>{current?.season} · {current?.month} · <strong>{current?.anomalyC.toFixed(1)} °C</strong></p>
 <div style={{display:"flex",flexWrap:"wrap",gap:8}}><button type="button" onClick={()=>setPlay(v=>!v)}>{play?"Pausar":"▶ Animar serie"}</button><button type="button" onClick={exportCsv}>Exportar CSV</button><button type="button" onClick={report}>Informe técnico / imprimir PDF</button></div>
 <p style={{fontSize:12}}>Fuente de la serie: <a href="https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt" target="_blank" rel="noreferrer" style={{color:"#a7e4ff"}}>NOAA CPC · ONI</a>. La animación recorre datos observados; no es una simulación ni un pronóstico.</p></>}
 <section aria-label="Interpretación del ONI" style={{background:"#1a3a47",padding:14,borderRadius:10,marginTop:16}}>
 <h3 style={{marginTop:0}}>Interpretación científica de la observación seleccionada</h3>
 {current?(()=>{const v=current.anomalyC;const phase=v>=0.5?"calentamiento compatible con condiciones de El Niño":v<=-0.5?"enfriamiento compatible con condiciones de La Niña":"condiciones térmicas cercanas a la neutralidad";const previous=data[Math.max(0,Math.min(selected,data.length-1)-1)];const delta=previous&&previous!==current?v-previous.anomalyC:null;return <><p><strong>{current.season} · {current.month}:</strong> ONI de {v.toFixed(1)} °C, indicativo de {phase}.</p><p>{delta===null?"No hay observación anterior en la ventana elegida para estimar la variación.":`Respecto del trimestre superpuesto anterior, la anomalía ${delta>0?"aumentó":delta<0?"disminuyó":"no cambió"} ${Math.abs(delta).toFixed(1)} °C.`}</p><p><strong>Lectura:</strong> {v>=1.5?"Anomalía cálida elevada.":v>=0.5?"Anomalía cálida sobre el umbral orientativo.":v<=-1.5?"Anomalía fría pronunciada.":v<=-0.5?"Anomalía fría bajo el umbral orientativo.":"El índice está dentro de la banda neutral orientativa."} Para identificar un episodio oficial se requiere persistencia y corroboración atmosférica; este panel no declara automáticamente episodios ni predice lluvias o crecidas.</p></>})():<p>La interpretación se habilita cuando se carga la serie NOAA.</p>}
 <p style={{fontSize:12,color:"#c6dbe5"}}>El ONI resume anomalías de temperatura superficial en Niño 3.4 mediante trimestres superpuestos. Los cambios consecutivos no son observaciones independientes. Para el diagnóstico completo contrastá SOI, vientos alisios, OLR, temperatura subsuperficial y pronósticos IRI.</p>
 </section>
 <TeleconnectionsPanel/>
 <EnsoHistoricalLab/>
 <h3>Diagnóstico oceánico y atmosférico · productos NOAA CPC</h3>
 <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(min(100%,290px),1fr))",gap:12}}>{panels.map(p=><figure key={p.title} style={{margin:0,background:"#fff",color:"#172d38",padding:10,borderRadius:9}}><img src={p.src} alt={p.desc} loading="lazy" style={{width:"100%",height:"auto"}}/><figcaption><strong>{p.title}</strong><div style={{fontSize:12}}>{p.desc}</div><a href={p.src} target="_blank" rel="noreferrer">Ver figura oficial y fecha</a></figcaption></figure>)}</div>
 <h3>Catálogo de variables y productos verificables</h3>
 <p>Este inventario identifica variables, unidades, frecuencia y acceso a sus fuentes. <strong>Registro no significa ingesta automática:</strong> por ahora el ONI es la serie conectada; los demás productos requieren conectores y validación por separado.</p>
 <label>Filtrar por categoría <select value={sourceFilter} onChange={e=>setSourceFilter(e.target.value)}>{["Todas",...Array.from(new Set(ENSO_SOURCES.map(v=>v.group)))].map(g=><option key={g}>{g}</option>)}</select></label>
 <div style={{overflowX:"auto",maxHeight:460,overflowY:"auto",marginTop:10}}><table style={{width:"100%",fontSize:12,borderCollapse:"collapse"}}><thead><tr><th>Variable / producto</th><th>Origen</th><th>Tipo</th><th>Unidad</th><th>Frecuencia</th><th>Estado</th></tr></thead><tbody>{ENSO_SOURCES.filter(v=>sourceFilter==="Todas"||v.group===sourceFilter).map(v=><tr key={v.id} style={{borderBottom:"1px solid #49606c"}}><td style={{padding:8}}><a href={v.url} target="_blank" rel="noreferrer" style={{color:"#a7e4ff"}}>{v.name} ↗</a></td><td>{v.provider}</td><td>{v.kind}</td><td>{v.unit}</td><td>{v.frequency}</td><td>{v.id==="oni"?"Serie conectada":"Fuente catalogada"}</td></tr>)}</tbody></table></div>
  <h3>Pronósticos IRI · Universidad de Columbia</h3><p>El pronóstico multimodelo, la distribución de probabilidades y los boletines de NOAA son productos distintos. Para evitar reproducir números desactualizados, se consultan en sus páginas oficiales.</p>
 <div style={{display:"flex",flexWrap:"wrap",gap:12}}><a href="https://iri.columbia.edu/our-expertise/climate/forecasts/enso/current/" target="_blank" rel="noreferrer" style={{color:"#a7e4ff"}}>IRI · pronóstico y pluma de modelos</a><a href="https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc.shtml" target="_blank" rel="noreferrer" style={{color:"#a7e4ff"}}>NOAA · diagnóstico oficial</a><a href="https://www.cpc.ncep.noaa.gov/data/indices/" target="_blank" rel="noreferrer" style={{color:"#a7e4ff"}}>NOAA · catálogo de índices</a></div>
 <p style={{fontSize:12,color:"#ffd59b"}}>No se calculan probabilidades locales de sequía o crecida a partir del ONI. Esas evaluaciones requieren datos regionales, validación y modelos específicos. Las imágenes externas dependen de la disponibilidad del proveedor.</p>
 </section>;
}
