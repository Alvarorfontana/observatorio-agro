import React,{useEffect,useRef,useState} from "react";
import L from "leaflet";
import * as echarts from "echarts";
type Collection={id:string;title?:string};
type Scene={id:string;collection:string;geometry?:{type:string;coordinates:unknown};properties:{datetime?:string;"eo:cloud_cover"?:number};links:{href:string;rel:string}[]};
export function CopernicusModule({embedded=false,lat,lon,polygon=[]}:{embedded?:boolean;lat?:number;lon?:number;polygon?:[number,number][]}){
 const mapElement=useRef<HTMLDivElement|null>(null);
 const mapInstance=useRef<L.Map|null>(null);
 const baseLayer=useRef<L.TileLayer|null>(null);
 const [mapStyle,setMapStyle]=useState<"satellite"|"streets">("satellite");
 const [outline,setOutline]=useState<[number,number][]>([]);
 const [drawMode,setDrawMode]=useState(false);
 const drawing=useRef(false);
 useEffect(()=>{drawing.current=drawMode},[drawMode]);
 useEffect(()=>{if(polygon.length>=3)setOutline(polygon)},[polygon]);
 const [collections,setCollections]=useState<Collection[]>([]);
 const [catalogError,setCatalogError]=useState("");
 const [catalogLoading,setCatalogLoading]=useState(true);
 const [collection,setCollection]=useState("sentinel-2-l2a");
 const [bbox,setBbox]=useState(()=>lat!==undefined&&lon!==undefined?[lon-0.06,lat-0.06,lon+0.06,lat+0.06].map(x=>x.toFixed(4)).join(","):"-59.10,-28.56,-58.98,-28.44");
 useEffect(()=>{if(outline.length>=3){const ys=outline.map(p=>p[0]),xs=outline.map(p=>p[1]);setBbox([Math.min(...xs),Math.min(...ys),Math.max(...xs),Math.max(...ys)].map(v=>v.toFixed(6)).join(","))}},[outline]);
 useEffect(()=>{if(!mapElement.current||mapInstance.current)return;const m=L.map(mapElement.current).setView([lat??-28.507,lon??-59.043],12);mapInstance.current=m;m.on("click",e=>{if(drawing.current)setOutline(p=>[...p,[e.latlng.lat,e.latlng.lng]])});setTimeout(()=>m.invalidateSize(),100);return ()=>{m.remove();mapInstance.current=null}},[]);
 useEffect(()=>{const m=mapInstance.current;if(!m)return; if(baseLayer.current)m.removeLayer(baseLayer.current); const satellite=mapStyle==="satellite"; const layer=L.tileLayer(satellite?"https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}":"https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",{attribution:satellite?"Imagery © Esri, Maxar, Earthstar Geographics and contributors":"© OpenStreetMap contributors",maxZoom:19});layer.addTo(m);layer.bringToBack();baseLayer.current=layer;return ()=>{if(m.hasLayer(layer))m.removeLayer(layer)}},[mapStyle]);
 useEffect(()=>{const m=mapInstance.current;if(!m)return;const group=L.featureGroup().addTo(m);if(outline.length){L.polyline(outline,{color:"#35b3cf",weight:3}).addTo(group);outline.forEach(p=>L.circleMarker(p,{radius:4,color:"#fff",fillColor:"#35b3cf",fillOpacity:1}).addTo(group));if(outline.length>=3){L.polygon(outline,{color:"#35b3cf",fillOpacity:.13}).addTo(group);m.fitBounds(L.latLngBounds(outline),{padding:[24,24]})}}return ()=>{group.remove()}},[outline]);
 const [start,setStart]=useState("2026-09-01");
 const [end,setEnd]=useState("2026-10-22");
 const [scenes,setScenes]=useState<Scene[]>([]);
 const [error,setError]=useState("");
 const [resultsQuery,setResultsQuery]=useState("");

 const resultsCurrent=resultsQuery===JSON.stringify({bbox,start,end,collection});
 const validScenes=resultsCurrent?scenes:[];
 const [loading,setLoading]=useState(false);
 const [pdfBusy,setPdfBusy]=useState(false);
 const [mapIndex,setMapIndex]=useState<MapKind>("ndvi");
 const [compareStart,setCompareStart]=useState("2025-09-01");
 const [compareEnd,setCompareEnd]=useState("2025-10-22");
 useEffect(()=>{const back=(d:string)=>{const x=new Date(d+"T12:00:00Z");if(isNaN(x.getTime()))return d;x.setUTCFullYear(x.getUTCFullYear()-1);return x.toISOString().slice(0,10)};setCompareStart(back(start));setCompareEnd(back(end))},[start,end]);
 const [thematicUrl,setThematicUrl]=useState("");
 const [thematicBlob,setThematicBlob]=useState<Blob|null>(null);
 const [thematicError,setThematicError]=useState("");
 const [thematicBusy,setThematicBusy]=useState(false);
 const [mapReading,setMapReading]=useState<MapReading|null>(null);
 const [mapDay,setMapDay]=useState("");
 useEffect(()=>{setMapDay("")},[start,end]);
 const [reportTitle,setReportTitle]=useState("Informe territorial Copernicus");
 const [reportNotes,setReportNotes]=useState("");
 const [includeScenes,setIncludeScenes]=useState(true);
 async function generateThematic(){if(outline.length<3)return;setThematicBusy(true);setThematicError("");setThematicUrl("");setThematicBlob(null);setMapReading(null);try{const r=await fetch("/api/copernicus/map",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({polygon:outline,index:mapIndex,start:mapDay||start,end:mapDay||end,compare_start:compareStart,compare_end:compareEnd})});if(!r.ok){const j=await r.json();throw Error(j.detail||j.error||"No se pudo generar el mapa")}const blob=await r.blob();setMapReading(decodeReading(r.headers.get("X-DOTS-Reading")));setThematicBlob(blob);setThematicUrl(URL.createObjectURL(blob))}catch(e){setThematicError(e instanceof Error?e.message:String(e))}finally{setThematicBusy(false)}}
 useEffect(()=>{setThematicUrl("");setThematicBlob(null);setThematicError("");setMapReading(null)},[outline,start,end,mapIndex,compareStart,compareEnd,mapDay]);
 function downloadGeoJSON(){if(outline.length<3){setError("Dibujá una parcela con al menos tres vértices para exportar GeoJSON.");return;}const ring=[...outline.map(([latitude,longitude])=>[longitude,latitude]),[outline[0][1],outline[0][0]]];const geojson={type:"FeatureCollection",features:[{type:"Feature",properties:{source:"DOTS - delimitacion del usuario",collection,start,end},geometry:{type:"Polygon",coordinates:[ring]}},...validScenes.filter(x=>x.geometry).map(x=>({type:"Feature",properties:{id:x.id,collection:x.collection,...x.properties},geometry:(x as any).geometry}))]};const url=URL.createObjectURL(new Blob([JSON.stringify(geojson,null,2)],{type:"application/geo+json"}));const a=document.createElement("a");a.href=url;a.download="DOTS_Copernicus_area.geojson";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
 async function downloadReport(){if(outline.length<3){setError("Dibujá una parcela con al menos tres vértices para generar PDF.");return;}setPdfBusy(true);setError("");try{const r=await fetch("/api/copernicus/report",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({polygon:outline,scenes:includeScenes?validScenes:[],collection,start,end,title:reportTitle,notes:reportNotes,map_png:thematicBlob?await new Promise<string>((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(",")[1]||"");reader.onerror=()=>reject(Error("No se pudo leer el mapa"));reader.readAsDataURL(thematicBlob)}):undefined,map_index:thematicBlob?mapIndex:undefined,map_reading:thematicBlob&&mapReading?mapReading:undefined})});if(!r.ok){const j=await r.json();throw Error(j.detail||j.error||"No se pudo generar el PDF")}const blob=await r.blob();const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;a.download="DOTS_Copernicus_catalogo.pdf";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}catch(e){setError(e instanceof Error?e.message:String(e))}finally{setPdfBusy(false)}}
 useEffect(()=>{let active=true;setCatalogLoading(true);fetch("/api/copernicus/collections").then(async r=>{const j=await r.json();if(!r.ok)throw Error(j.detail||j.error||"Catálogo no disponible");const c:Collection[]=(j.collections||[]).filter((x:Collection)=>x.id&&(/sentinel/i.test(x.id)||/sentinel/i.test(x.title||"")));if(!c.length)throw Error("El catálogo no devolvió colecciones Sentinel compatibles. Se mantiene Sentinel-2 L2A como opción manual, su disponibilidad se comprobará al buscar.");if(!active)return;setCollections(c);setCollection(current=>c.some(x=>x.id===current)?current:(c.find(x=>/sentinel-2/i.test(x.id))||c[0]).id);setCatalogError("")}).catch(e=>{if(active)setCatalogError(e instanceof Error?e.message:String(e))}).finally(()=>{if(active)setCatalogLoading(false)});return ()=>{active=false}},[]);
 async function search(e:React.FormEvent){e.preventDefault();if(!collection){setError("No hay colección Sentinel seleccionada. Revisá la conexión con el catálogo.");return}if(outline.length<3){setError("Delimitá primero una parcela con al menos tres puntos sobre el mapa.");return}setError("");setScenes([]);setResultsQuery("");setLoading(true);try{
 const q=new URLSearchParams({bbox,start,end,collection,limit:"25"});
 const r=await fetch("/api/copernicus/scenes?"+q);const j=await r.json();if(!r.ok)throw Error(typeof j.detail==="string"?j.detail:JSON.stringify(j.detail||j.error||"Consulta fallida"));setScenes(j.features||[]);setResultsQuery(JSON.stringify({bbox,start,end,collection}));
 }catch(e){setError(e instanceof Error?e.message:String(e))}finally{setLoading(false)}}
 return <main style={{maxWidth:embedded?"100%":1180,margin:"auto",padding:embedded?"12px 4px":"32px 22px",fontFamily:"IBM Plex Sans, sans-serif",color:"#e5edf2",background:"#101c25",minHeight:embedded?0:"100vh"}}>
 {!embedded&&<a href="/" style={{color:"#8bd3ef"}}>← DOTS · Inicio</a>}<p style={{letterSpacing:2,color:"#78bfd7",marginTop:40}}>NUEVO MÓDULO · COPERNICUS 2026</p>
 <h1 style={{fontSize:"clamp(32px,5vw,58px)",margin:"8px 0"}}>DOTS amplía su capacidad de análisis satelital con Copernicus</h1>
 <p style={{fontSize:19,maxWidth:840}}>Explorá imágenes oficiales del programa Copernicus y prepará análisis de parcelas, vegetación, agua, temperatura y atmósfera. Los mapas se calculan en vivo sobre píxeles reales del servicio oficial de Copernicus, con rangos de lectura e interpretación.</p>
 <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(220px,1fr))",gap:14,margin:"28px 0"}}>
 {[
 ["Sentinel-1","Radar: agua sobre el terreno, aun con nubes · disponible"],
 ["Sentinel-2","NDVI, NDWI, color natural y cambio entre campañas · disponible"],
 ["Sentinel-3","Temperatura superficial diurna, 1 km · disponible"],
 ["Sentinel-5P","Humo, aerosoles y NO₂ regionales · disponible"],
 ["Google Earth Timelapse","Mosaicos anuales 1984–2022 para la historia del lote · disponible"],
 ["IA geoespacial","TerraMind / TESSERA · en evaluación"]
 ].map(([name,desc])=><article key={name} style={{border:"1px solid #38505d",borderRadius:12,padding:18,background:"#192b36"}}><h2 style={{fontSize:19,margin:"0 0 8px"}}>{name}</h2><p style={{margin:0,color:"#b7c9d1"}}>{desc}</p></article>)}</div>
 <section aria-label="Aplicaciones prácticas" style={{margin:"28px 0"}}><h2>¿Para qué sirve en la práctica?</h2><p>DOTS amplía sus capacidades de análisis incorporando fuentes de Copernicus. No es una plataforma separada: sus imágenes y productos se relacionan con los módulos de cultivos, parcelas, agua y clima que ya ofrece DOTS.</p><div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(230px,1fr))",gap:14}}>{[
 {t:"Producción agrícola",d:"Comparar campañas y reconocer sectores de vegetación menos vigorosa. Ayuda a decidir dónde inspeccionar un lote antes de intervenir.",url:"#mapas-tematicos",link:"Generar NDVI o cambio de NDVI"},
 {t:"Crecidas e inundaciones",d:"Revisar imágenes de radar para reconocer agua sobre el terreno, incluso cuando las nubes impiden una fotografía óptica.",url:"#mapas-tematicos",link:"Generar agua por radar"},
 {t:"Temperaturas y sequías",d:"Contrastar temperaturas superficiales y cambios en vegetación para investigar períodos de estrés térmico e hídrico.",url:"#mapas-tematicos",link:"Generar temperatura superficial"},
 {t:"Historia del territorio",d:"Ver el lote año por año desde 1984 con Google Earth Timelapse, y comparar NDVI entre campañas: avance agrícola, pérdida de monte y cambios en pastizales.",url:"#historia-territorio",link:"Ver historia del lote"},
 {t:"Calidad atmosférica",d:"Consultar productos regionales de gases y humo para contextualizar episodios ambientales, sin atribuir emisiones a una parcela individual.",url:"#mapas-tematicos",link:"Generar humo o NO₂"},
 {t:"Informes técnicos",d:"Un PDF con la delimitación del lote, el mapa generado, sus rangos de lectura, la interpretación y las imágenes usadas con su enlace oficial para verificarlas.",url:"#generador-informes-copernicus",link:"Armar el informe"}
 ].map(x=><article key={x.t} style={{padding:18,background:"#192b36",border:"1px solid #38505d",borderRadius:12}}><h3>{x.t}</h3><p style={{color:"#bfd0d9"}}>{x.d}</p><a style={{color:"#8bd3ef"}} href={x.url}>{x.link} →</a></article>)}</div></section>
 <section style={{background:"#192b36",border:"1px solid #38505d",padding:22,borderRadius:14}}>
 <h2>Delimitar y analizar una parcela</h2><p>Seleccioná un polígono del Observatorio o dibujá uno nuevo. Sin delimitación no se habilita la consulta.</p>
 <div style={{display:"flex",gap:8,alignItems:"center",marginBottom:10,flexWrap:"wrap"}}><strong>Mapa base</strong><button type="button" onClick={()=>setMapStyle("satellite")} aria-pressed={mapStyle==="satellite"} style={{...action,background:mapStyle==="satellite"?"#087f9e":"#234454"}}>Imagen satelital</button><button type="button" onClick={()=>setMapStyle("streets")} aria-pressed={mapStyle==="streets"} style={{...action,background:mapStyle==="streets"?"#087f9e":"#234454"}}>Mapa de calles</button></div><p style={{color:"#b7c9d1"}}>La imagen de fondo es cartografía de referencia; no corresponde necesariamente a la fecha de búsqueda Copernicus ni constituye un mapa NDVI.</p>
 <div ref={mapElement} style={{height:340,width:"100%",borderRadius:10,marginBottom:12}} aria-label="Mapa interactivo para delimitar el área de estudio"/>
 <div style={{display:"flex",gap:8,flexWrap:"wrap",marginBottom:12}}><button type="button" onClick={()=>setDrawMode(v=>!v)} style={action}>{drawMode?"Terminar dibujo":"Dibujar polígono"}</button><button type="button" onClick={()=>{setOutline([]);setScenes([]);setDrawMode(true)}} style={action}>Borrar delimitación</button><span style={{alignSelf:"center"}}>{outline.length>=3?"Área delimitada · "+outline.length+" vértices":outline.length+" puntos · mínimo 3"}</span></div>
 <p style={{color:"#b7c9d1"}}>El rectángulo de búsqueda se calcula automáticamente desde el polígono. La búsqueda devuelve escenas que intersectan el área; todavía no recorta píxeles ni calcula índices dentro del lote.</p>
 <form onSubmit={search} style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(180px,1fr))",gap:12}}>
 <label>Colección<select required value={collection} onChange={e=>setCollection(e.target.value)} style={field}>{collections.length===0&&<option value="sentinel-2-l2a">{catalogLoading?"Cargando catálogo…":"Sentinel-2 L2A (consulta directa)"}</option>}{collections.map(c=><option key={c.id} value={c.id}>{c.title||c.id}</option>)}</select>{catalogError&&<span role="alert" style={{display:"block",color:"#ffb5a7",marginTop:6}}>No se pudo cargar el catálogo: {catalogError}. Podés intentar una búsqueda directa con Sentinel-2 L2A.</span>}</label>
 <label>Extensión de búsqueda (automática)<input readOnly value={outline.length>=3?bbox:"Delimitá el lote primero"} style={field}/></label>
 <label>Desde<input required type="date" value={start} onChange={e=>setStart(e.target.value)} style={field}/></label>
 <label>Hasta<input required type="date" value={end} onChange={e=>setEnd(e.target.value)} style={field}/></label>
 <button disabled={loading||!collection||outline.length<3} type="submit" style={{background:"#35b3cf",color:"#071820",fontWeight:700,border:0,borderRadius:8,padding:12,cursor:"pointer"}}>{loading?"Consultando…":"Buscar imágenes"}</button>
 </form>
 {error&&<p role="alert" style={{color:"#ffb5a7"}}>{error}</p>}
 <section id="mapas-tematicos" style={{margin:"22px 0",padding:16,border:"1px solid #54717f",borderRadius:10}}><h3>Mapas temáticos Copernicus · datos reales</h3><p>Calculá productos sobre los píxeles reales de la zona delimitada, con el período elegido arriba. Las imágenes se procesan en el servicio oficial de Copernicus; no se generan resultados de ejemplo.</p><label>Producto<select value={mapIndex} onChange={e=>setMapIndex(e.target.value as MapKind)} style={field}>{MAP_GROUPS.map(g=><optgroup key={g.label} label={g.label}>{g.items.map(([v,l])=><option key={v} value={v}>{l}</option>)}</optgroup>)}</select></label><p style={{color:"#b7c9d1",fontSize:14,margin:"8px 0 0"}}>{MAP_HINTS[mapIndex]}</p>{mapDay&&<p style={{margin:"8px 0 0"}}><span style={{padding:"3px 10px",borderRadius:20,background:"#234454"}}>Usando solo la imagen del {mapDay.split("-").reverse().join("/")}</span> <button type="button" onClick={()=>setMapDay("")} style={{...action,padding:"3px 9px",fontSize:13}}>Volver al período completo</button></p>}{mapIndex==="ndvi_change"&&<div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(180px,1fr))",gap:12,marginTop:10}}><label>Comparar contra · desde<input type="date" value={compareStart} onChange={e=>setCompareStart(e.target.value)} style={field}/></label><label>Comparar contra · hasta<input type="date" value={compareEnd} onChange={e=>setCompareEnd(e.target.value)} style={field}/></label></div>}<button type="button" disabled={thematicBusy||outline.length<3} onClick={generateThematic} style={{...action,marginTop:12}}>{thematicBusy?"Procesando píxeles…":"Generar mapa temático"}</button>{thematicError&&<p role="alert" style={{color:"#ffb5a7"}}>{thematicError}</p>}{thematicUrl&&<div style={{marginTop:14}}><img src={thematicUrl} alt={"Mapa satelital "+mapIndex+" calculado sobre la parcela"} style={{maxWidth:"100%",maxHeight:520,borderRadius:8}}/><p style={{color:"#b7c9d1"}}>Fuente: {mapReading?.source||"Copernicus"} · {mapDay?"imagen del "+mapDay:"período "+start+" a "+end}.</p><a href={thematicUrl} download={"DOTS_Copernicus_"+mapIndex+".png"} style={{color:"#8bd3ef"}}>Descargar mapa PNG</a>{mapReading&&<MapReadingPanel reading={mapReading}/>}</div>}</section>
 <section id="generador-informes-copernicus" style={{margin:"24px 0",padding:18,border:"1px solid #54717f",borderRadius:10}}><h3>Generador de informes técnicos · PDF</h3><p>Configurá el documento para la parcela delimitada. Se incluyen solamente datos disponibles y verificados del catálogo.</p><label>Título del informe<input value={reportTitle} onChange={e=>setReportTitle(e.target.value)} maxLength={120} style={field}/></label><label>Observaciones técnicas<textarea value={reportNotes} onChange={e=>setReportNotes(e.target.value)} maxLength={1200} rows={3} style={{...field,resize:"vertical"}}/></label><label style={{display:"flex",alignItems:"center",gap:8,margin:"12px 0"}}><input type="checkbox" checked={includeScenes} onChange={e=>setIncludeScenes(e.target.checked)}/> Incluir listado de escenas consultadas ({validScenes.length})</label><p style={{color:"#b7c9d1"}}>Incluye: mapa esquemático del polígono, coordenadas, período, colección y metodología. NDVI, humedad e inundaciones no se calcularán sin procesamiento satelital real.</p></section>
 <button type="button" onClick={downloadGeoJSON} disabled={outline.length<3} style={action}>Exportar mapa y delimitación GeoJSON</button>{" "}<button type="button" onClick={downloadReport} disabled={pdfBusy||outline.length<3} style={action}>{pdfBusy?"Generando PDF…":"Descargar informe PDF del área delimitada"}</button><p style={{color:"#b7c9d1"}}>El PDF documenta el polígono y las escenas consultadas; no incluye todavía índices de vegetación calculados.</p>
 <p role="status">{validScenes.length?validScenes.length+" escenas encontradas":loading?"Buscando en Copernicus…":"Los resultados aparecerán aquí. No se muestran datos simulados."}</p>
 <TerritoryHistory outline={outline}/>
 <section id="graficos-copernicus" style={{marginTop:22}}><h3>Módulos gráficos · monitoreo satelital</h3><p style={{color:"#b7c9d1"}}>Los gráficos se generan exclusivamente con metadatos de las escenas devueltas por Copernicus. No representan mediciones de vegetación ni agua dentro de la parcela.</p>{scenes.length>0?<><div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(300px,1fr))",gap:14}}><SceneChart title="Escenas por fecha" kind="dates" scenes={validScenes}/><SceneChart title="Cobertura nubosa por imagen" kind="cloud" scenes={validScenes}/><SceneChart title="Distribución de nubosidad" kind="distribution" scenes={validScenes}/></div><ReadingBox title="Lectura de los gráficos" lines={interpretScenes(validScenes)}/></>:<p style={{padding:20,border:"1px dashed #54717f",borderRadius:9}}>Delimitá el área y consultá imágenes para activar los tres gráficos.</p>}</section>
 <ScenesList scenes={validScenes} onUse={day=>{setMapDay(day);document.getElementById("mapas-tematicos")?.scrollIntoView({behavior:"smooth",block:"start"})}}/>
 </section>
 <p style={{color:"#9cb2bd",marginTop:22}}>Fuentes: Copernicus Data Space Ecosystem / ESA. Los productos no son mediciones de campo. El acceso al agente openEO alfa requiere autorización; DOTS no declara habilitados procesos que aún no fueron configurados.</p>
 </main>
}
const action:React.CSSProperties={padding:"9px 13px",borderRadius:7,border:"1px solid #54717f",background:"#234454",color:"#fff",cursor:"pointer"};
const field:React.CSSProperties={display:"block",width:"100%",padding:11,borderRadius:7,border:"1px solid #647d89",background:"#0d1b25",color:"#fff",marginTop:7,boxSizing:"border-box"};

type SceneChartKind="dates"|"cloud"|"distribution";
function SceneChart({title,kind,scenes}:{title:string;kind:SceneChartKind;scenes:Scene[]}){
 const el=useRef<HTMLDivElement|null>(null);
 useEffect(()=>{
  if(!el.current)return;
  const chart=echarts.init(el.current);
  const dated=scenes.filter(x=>x.properties.datetime).slice().sort((a,b)=>(a.properties.datetime||"").localeCompare(b.properties.datetime||""));
  const daily=new Map<string,number>();
  for(const scene of dated){const day=(scene.properties.datetime||"").slice(0,10);daily.set(day,(daily.get(day)||0)+1)}
  const clouds=dated.filter(x=>typeof x.properties["eo:cloud_cover"]==="number");
  const buckets=[0,0,0,0,0];
  for(const scene of clouds){const n=scene.properties["eo:cloud_cover"]!;buckets[Math.min(4,Math.max(0,Math.floor(n/20)))]+=1}
  const axisColor="#b7c9d1";
  const labels=kind==="dates"?[...daily.keys()]:kind==="cloud"?clouds.map(x=>(x.properties.datetime||"").slice(0,10)):["0–19%","20–39%","40–59%","60–79%","80–100%"];
  const values=kind==="dates"?[...daily.values()]:kind==="cloud"?clouds.map(x=>x.properties["eo:cloud_cover"]):buckets;
  chart.setOption({backgroundColor:"#192b36",tooltip:{trigger:"axis"},grid:{left:48,right:18,top:30,bottom:80},xAxis:{type:"category",data:labels,axisLabel:{color:axisColor,rotate:labels.length>5?45:0}},yAxis:{type:"value",min:0,max:kind==="cloud"?100:undefined,name:kind==="cloud"?"Nubes (%)":"Escenas",nameTextStyle:{color:axisColor},axisLabel:{color:axisColor}},series:[{name:title,type:kind==="cloud"?"line":"bar",data:values,itemStyle:{color:"#35b3cf"},lineStyle:{color:"#35b3cf"}}]});
  const observer=new ResizeObserver(()=>chart.resize());observer.observe(el.current);
  return ()=>{observer.disconnect();chart.dispose()};
 },[kind,scenes,title]);
 const noData=kind==="cloud"&&!scenes.some(x=>typeof x.properties["eo:cloud_cover"]==="number");
 return <article style={{border:"1px solid #38505d",borderRadius:10,padding:14,background:"#192b36"}}><h4 style={{margin:"0 0 8px"}}>{title}</h4>{noData&&<p>Esta colección no proporciona porcentajes de nubosidad.</p>}<div ref={el} style={{width:"100%",height:270}} role="img" aria-label={title}/></article>
}

type MapReading={name:string;source?:string;lines:string[];stats:{valid_pixels:number|null;classes:{range:string;label:string;color:string;pct:number}[]}};
function decodeReading(h:string|null):MapReading|null{if(!h)return null;try{const bytes=Uint8Array.from(atob(h),c=>c.charCodeAt(0));return JSON.parse(new TextDecoder().decode(bytes))}catch{return null}}
function ReadingBox({title,lines}:{title:string;lines:string[]}){if(!lines.length)return null;return <div style={{marginTop:14,padding:14,border:"1px solid #38505d",borderRadius:10,background:"#14252f"}}><h4 style={{margin:"0 0 8px"}}>{title}</h4>{lines.map((l,i)=><p key={i} style={{margin:"6px 0",color:"#d7e3e8"}}>{l}</p>)}</div>}
function MapReadingPanel({reading}:{reading:MapReading}){const cls=reading.stats?.classes||[];return <div style={{marginTop:14}}>{cls.length>0&&<table style={{width:"100%",borderCollapse:"collapse",fontSize:14}}><thead><tr style={{textAlign:"left",color:"#b7c9d1"}}><th></th><th>Rango</th><th>Lectura</th><th style={{textAlign:"right"}}>% del lote</th></tr></thead><tbody>{cls.map(c=><tr key={c.range} style={{borderTop:"1px solid #38505d"}}><td style={{width:22,padding:"6px 0"}}><span style={{display:"inline-block",width:14,height:14,borderRadius:3,background:c.color}}/></td><td>{c.range}</td><td>{c.label}</td><td style={{textAlign:"right"}}><b>{c.pct.toFixed(1)}%</b></td></tr>)}</tbody></table>}<ReadingBox title={"Interpretación · "+reading.name} lines={reading.lines}/></div>}
function interpretScenes(scenes:Scene[]):string[]{if(!scenes.length)return [];const dates=[...new Set(scenes.map(s=>(s.properties.datetime||"").slice(0,10)).filter(d=>d.length===10))].sort();const out=[`Se encontraron ${scenes.length} escenas en ${dates.length} fechas distintas.`];if(dates.length>=2){const span=(Date.parse(dates[dates.length-1])-Date.parse(dates[0]))/864e5;out.push(`En promedio hay una pasada cada ${Math.round(span/(dates.length-1))} días, lo que alcanza para seguir cambios semanales del lote.`)}const clouds=scenes.map(s=>s.properties["eo:cloud_cover"]).filter((c):c is number=>typeof c==="number");if(clouds.length){const clear=clouds.filter(c=>c<20).length;out.push(`${clear} de ${clouds.length} escenas tienen menos de 20% de nubes y son las más confiables para medir índices.`);if(!clear)out.push("Ninguna escena está despejada: los índices ópticos pueden estar afectados. Para agua conviene usar radar Sentinel-1, que atraviesa las nubes.")}else out.push("Esta colección no informa nubosidad (por ejemplo radar o productos atmosféricos).");return out}

type MapKind="ndvi"|"ndwi"|"truecolor"|"ndvi_change"|"s1_water"|"lst"|"co"|"no2"|"aerosol";
const MAP_GROUPS:{label:string;items:[MapKind,string][]}[]=[
 {label:"Sentinel-2 · producción agrícola e historia",items:[["ndvi","NDVI · vigor vegetal"],["ndwi","NDWI · índice de agua"],["truecolor","Color natural"],["ndvi_change","Cambio de NDVI entre dos períodos"]]},
 {label:"Sentinel-1 · crecidas e inundaciones",items:[["s1_water","Agua por radar (funciona con nubes)"]]},
 {label:"Sentinel-3 · temperaturas y sequías",items:[["lst","Temperatura superficial diurna"]]},
 {label:"Sentinel-5P · calidad atmosférica",items:[["co","Monóxido de carbono · humo de quemas"],["aerosol","Aerosoles · humo y polvo"],["no2","Dióxido de nitrógeno"]]},
];
const MAP_HINTS:Record<MapKind,string>={
 ndvi:"Vigor de la vegetación dentro del lote, a 10 m.",
 ndwi:"Agua en superficie y suelo encharcado dentro del lote, a 10 m.",
 truecolor:"Imagen como la vería el ojo, para reconocer el terreno.",
 ndvi_change:"Compara el período elegido arriba contra otro período; por defecto, el mismo del año anterior para comparar campañas.",
 s1_water:"Usa la pasada de radar más reciente del período. Ve el agua aunque esté nublado.",
 lst:"Pasada de la mañana, 1 km por píxel: muestra la zona alrededor del lote, marcado en blanco.",
 co:"Promedio del período (máximo 31 días), unos 5 km por píxel: muestra la región alrededor del lote.",
 aerosol:"Promedio del período (máximo 31 días), unos 5 km por píxel: muestra la región alrededor del lote.",
 no2:"Promedio del período (máximo 31 días), unos 5 km por píxel: muestra la región alrededor del lote.",
};

const HISTORY_YEARS=[1985,1990,1995,2000,2005,2010,2015,2020,2022];
function TerritoryHistory({outline}:{outline:[number,number][]}){
 const [yearA,setYearA]=useState(1985);
 const [yearB,setYearB]=useState(2022);
 const [images,setImages]=useState<Record<number,string>>({});
 const [busy,setBusy]=useState<number[]>([]);
 const [error,setError]=useState("");
 const [showGrid,setShowGrid]=useState(false);
 const key=JSON.stringify(outline);
 useEffect(()=>{setImages(prev=>{Object.values(prev).forEach(u=>URL.revokeObjectURL(u));return {}});setShowGrid(false);setError("")},[key]);
 async function load(year:number){
  if(images[year]||busy.includes(year))return;
  setBusy(b=>[...b,year]);
  try{const r=await fetch("/api/historia/timelapse",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({polygon:outline,year})});
   if(!r.ok){const j=await r.json().catch(()=>({}));throw Error([j.error,j.detail].filter(Boolean).join(": ")||"No se pudo obtener el mosaico")}
   const url=URL.createObjectURL(await r.blob());setImages(m=>({...m,[year]:url}));setError("")}
  catch(e){setError(e instanceof Error?e.message:String(e))}
  finally{setBusy(b=>b.filter(y=>y!==year))}
 }
 async function compare(){await Promise.all([load(yearA),load(yearB)])}
 async function evolution(){setShowGrid(true);for(const y of HISTORY_YEARS){await load(y)}}
 const years=Array.from({length:2022-1984+1},(_,i)=>1984+i);
 const ready=outline.length>=3;
 const frame=(y:number)=><figure key={y} style={{margin:0}}>{images[y]?<img src={images[y]} alt={"Mosaico anual "+y+" alrededor del lote"} style={{width:"100%",borderRadius:8,display:"block"}}/>:<div style={{aspectRatio:"4/3",borderRadius:8,background:"#0d1b25",display:"grid",placeItems:"center",color:"#78939f"}}>{busy.includes(y)?"Cargando…":"Sin cargar"}</div>}<figcaption style={{marginTop:6,fontWeight:600}}>{y}</figcaption></figure>;
 return <section id="historia-territorio" style={{margin:"22px 0",padding:16,border:"1px solid #54717f",borderRadius:10}}>
  <h3>Historia del territorio · 1984 a 2022</h3>
  <p>Mosaicos anuales sin nubes de Google Earth Timelapse, a 30 m, con tu lote marcado en blanco. Sirven para ver cómo cambió el campo y su entorno a lo largo de casi 40 años.</p>
  {!ready?<p style={{padding:16,border:"1px dashed #54717f",borderRadius:9}}>Dibujá el lote en el mapa para ver su historia.</p>:<>
  <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(150px,1fr))",gap:12,alignItems:"end"}}>
   <label>Año A<select value={yearA} onChange={e=>setYearA(+e.target.value)} style={field}>{years.map(y=><option key={y}>{y}</option>)}</select></label>
   <label>Año B<select value={yearB} onChange={e=>setYearB(+e.target.value)} style={field}>{years.map(y=><option key={y}>{y}</option>)}</select></label>
   <button type="button" onClick={compare} style={action}>Comparar los dos años</button>
   <button type="button" onClick={evolution} style={action}>Ver evolución cada 5 años</button>
  </div>
  {error&&<p role="alert" style={{color:"#ffb5a7"}}>{error}</p>}
  {(images[yearA]||images[yearB]||busy.includes(yearA)||busy.includes(yearB))&&<div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(260px,1fr))",gap:14,marginTop:14}}>{frame(yearA)}{frame(yearB)}</div>}
  {showGrid&&<div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(170px,1fr))",gap:12,marginTop:16}}>{HISTORY_YEARS.map(frame)}</div>}
  <ReadingBox title="Cómo leer estas imágenes" lines={[
   "Verde oscuro es monte o vegetación densa; verde claro, pasturas o cultivos en crecimiento; marrón o beige, suelo arado, rastrojo o pastizal seco; azul oscuro o negro, agua.",
   "Compará los dos años buscando monte que desaparece, lotes nuevos con formas rectas, lagunas que se secan o aparecen y cambios en el cauce de los ríos.",
   "Cada mosaico combina imágenes de todo el año para quitar las nubes: muestra cómo estaba el lugar ese año, no un día puntual. Hasta 2014 son imágenes Landsat; desde 2015 se suman las de Sentinel-2.",
   "Es una imagen para mirar, no para medir: para cifras de cobertura usá el cambio de NDVI o el análisis de deforestación de DOTS.",
  ]}/>
  </>}
  <p style={{color:"#8fa6b0",fontSize:13,marginTop:10}}>Fuente: Google Earth Timelapse (Google, Landsat, Copernicus) · CC-BY 4.0. Contiene datos modificados de Copernicus Sentinel (2015 en adelante).</p>
 </section>
}

function cloudTag(c:number|undefined){if(typeof c!=="number")return {text:"Sin dato de nubes",color:"#8fa6b0",bg:"#22343f"};if(c<20)return {text:"Útil · "+c.toFixed(0)+"% nubes",color:"#0e2a17",bg:"#7fd18b"};if(c<50)return {text:"Regular · "+c.toFixed(0)+"% nubes",color:"#3a2a00",bg:"#f2cf6b"};return {text:"Nublada · "+c.toFixed(0)+"% nubes",color:"#fff",bg:"#8a3b33"}}
function ScenesList({scenes,onUse}:{scenes:Scene[];onUse:(day:string)=>void}){
 if(!scenes.length)return null;
 const sorted=scenes.slice().sort((a,b)=>(a.properties["eo:cloud_cover"]??999)-(b.properties["eo:cloud_cover"]??999));
 const useful=scenes.filter(s=>(s.properties["eo:cloud_cover"]??999)<20).length;
 return <details style={{marginTop:14,border:"1px solid #38505d",borderRadius:10,padding:"10px 14px",background:"#14252f"}}>
  <summary style={{cursor:"pointer",fontWeight:600}}>Ver imágenes usadas ({scenes.length}) · {useful} útiles para medir</summary>
  <p style={{color:"#b7c9d1",fontSize:14}}>Ordenadas de menos a más nubes. «Usar esta fecha» acota el período a ese día para que el mapa temático use esa imagen. El enlace oficial permite a cualquiera verificar el dato en Copernicus.</p>
  <div style={{display:"grid",gap:6}}>{sorted.map(s=>{const day=(s.properties.datetime||"").slice(0,10);const tag=cloudTag(s.properties["eo:cloud_cover"]);const self=s.links.find(l=>l.rel==="self");
   return <article key={s.id} style={{display:"flex",flexWrap:"wrap",gap:10,alignItems:"center",borderTop:"1px solid #2c4350",padding:"8px 0"}}>
    <b style={{minWidth:96}}>{day?day.split("-").reverse().join("/"):"Sin fecha"}</b>
    <span style={{padding:"2px 8px",borderRadius:20,fontSize:13,background:tag.bg,color:tag.color}}>{tag.text}</span>
    <span style={{color:"#8fa6b0",fontSize:13,flex:"1 1 200px",overflowWrap:"anywhere"}}>{s.collection} · {s.id}</span>
    {day&&<button type="button" onClick={()=>onUse(day)} style={{...action,padding:"5px 10px",fontSize:13}}>Usar esta fecha</button>}
    {self&&<a href={self.href} target="_blank" rel="noreferrer" style={{color:"#8bd3ef",fontSize:13}}>Ficha oficial ↗</a>}
   </article>})}</div>
 </details>
}
