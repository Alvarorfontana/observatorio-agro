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
 const [collection,setCollection]=useState("");
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
 const [mapIndex,setMapIndex]=useState<"ndvi"|"ndwi"|"truecolor">("ndvi");
 const [thematicUrl,setThematicUrl]=useState("");
 const [thematicError,setThematicError]=useState("");
 const [thematicBusy,setThematicBusy]=useState(false);
 const [reportTitle,setReportTitle]=useState("Informe territorial Copernicus");
 const [reportNotes,setReportNotes]=useState("");
 const [includeScenes,setIncludeScenes]=useState(true);
 async function generateThematic(){if(outline.length<3)return;setThematicBusy(true);setThematicError("");setThematicUrl("");try{const r=await fetch("/api/copernicus/map",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({polygon:outline,index:mapIndex,start,end})});if(!r.ok){const j=await r.json();throw Error(j.detail||j.error||"No se pudo generar el mapa")}const blob=await r.blob();setThematicUrl(URL.createObjectURL(blob))}catch(e){setThematicError(e instanceof Error?e.message:String(e))}finally{setThematicBusy(false)}}
 useEffect(()=>{setThematicUrl("");setThematicError("")},[outline,start,end,mapIndex]);
 function downloadGeoJSON(){if(outline.length<3)return;const ring=[...outline.map(([latitude,longitude])=>[longitude,latitude]),[outline[0][1],outline[0][0]]];const geojson={type:"FeatureCollection",features:[{type:"Feature",properties:{source:"DOTS - delimitacion del usuario",collection,start,end},geometry:{type:"Polygon",coordinates:[ring]}},...validScenes.filter(x=>x.geometry).map(x=>({type:"Feature",properties:{id:x.id,collection:x.collection,...x.properties},geometry:(x as any).geometry}))]};const url=URL.createObjectURL(new Blob([JSON.stringify(geojson,null,2)],{type:"application/geo+json"}));const a=document.createElement("a");a.href=url;a.download="DOTS_Copernicus_area.geojson";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
 async function downloadReport(){if(outline.length<3)return;setPdfBusy(true);setError("");try{const r=await fetch("/api/copernicus/report",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({polygon:outline,scenes:includeScenes?validScenes:[],collection,start,end,title:reportTitle,notes:reportNotes})});if(!r.ok){const j=await r.json();throw Error(j.detail||j.error||"No se pudo generar el PDF")}const blob=await r.blob();const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;a.download="DOTS_Copernicus_catalogo.pdf";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}catch(e){setError(e instanceof Error?e.message:String(e))}finally{setPdfBusy(false)}}
 useEffect(()=>{let active=true;setCatalogLoading(true);fetch("/api/copernicus/collections").then(async r=>{const j=await r.json();if(!r.ok)throw Error(j.detail||j.error||"Catálogo no disponible");const c:Collection[]=(j.collections||[]).filter((x:Collection)=>x.id&&/^sentinel-[1235]/i.test(x.id));if(!c.length)throw Error("El catálogo no devolvió colecciones Sentinel compatibles.");if(!active)return;setCollections(c);setCollection(current=>c.some(x=>x.id===current)?current:(c.find(x=>/sentinel-2/i.test(x.id))||c[0]).id);setCatalogError("")}).catch(e=>{if(active)setCatalogError(e instanceof Error?e.message:String(e))}).finally(()=>{if(active)setCatalogLoading(false)});return ()=>{active=false}},[]);
 async function search(e:React.FormEvent){e.preventDefault();if(!collection){setError("No hay colección Sentinel seleccionada. Revisá la conexión con el catálogo.");return}if(outline.length<3){setError("Delimitá primero una parcela con al menos tres puntos sobre el mapa.");return}setError("");setScenes([]);setResultsQuery("");setLoading(true);try{
 const q=new URLSearchParams({bbox,start,end,collection,limit:"25"});
 const r=await fetch("/api/copernicus/scenes?"+q);const j=await r.json();if(!r.ok)throw Error(typeof j.detail==="string"?j.detail:JSON.stringify(j.detail||j.error||"Consulta fallida"));setScenes(j.features||[]);setResultsQuery(JSON.stringify({bbox,start,end,collection}));
 }catch(e){setError(e instanceof Error?e.message:String(e))}finally{setLoading(false)}}
 return <main style={{maxWidth:embedded?"100%":1180,margin:"auto",padding:embedded?"12px 4px":"32px 22px",fontFamily:"IBM Plex Sans, sans-serif",color:"#e5edf2",background:"#101c25",minHeight:embedded?0:"100vh"}}>
 {!embedded&&<a href="/" style={{color:"#8bd3ef"}}>← DOTS · Inicio</a>}<p style={{letterSpacing:2,color:"#78bfd7",marginTop:40}}>NUEVO MÓDULO · COPERNICUS 2026</p>
 <h1 style={{fontSize:"clamp(32px,5vw,58px)",margin:"8px 0"}}>DOTS amplía su capacidad de análisis satelital con Copernicus</h1>
 <p style={{fontSize:19,maxWidth:840}}>Explorá imágenes oficiales del programa Copernicus y prepará análisis de parcelas, vegetación, agua, temperatura y atmósfera. Consulta del catálogo en vivo; los cálculos avanzados se incorporarán progresivamente.</p>
 <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(220px,1fr))",gap:14,margin:"28px 0"}}>
 {[
 ["Sentinel-1","Radar y superficies inundadas"],
 ["Sentinel-2","Vegetación y cambios agrícolas"],
 ["Sentinel-3","Temperatura superficial"],
 ["Sentinel-5P","Composición atmosférica"],
 ["openEO","Procesamiento remoto · pendiente de conexión"],
 ["IA geoespacial","TerraMind / TESSERA · en evaluación"]
 ].map(([name,desc])=><article key={name} style={{border:"1px solid #38505d",borderRadius:12,padding:18,background:"#192b36"}}><h2 style={{fontSize:19,margin:"0 0 8px"}}>{name}</h2><p style={{margin:0,color:"#b7c9d1"}}>{desc}</p></article>)}</div>
 <section aria-label="Aplicaciones prácticas" style={{margin:"28px 0"}}><h2>¿Para qué sirve en la práctica?</h2><p>DOTS amplía sus capacidades de análisis incorporando fuentes de Copernicus. No es una plataforma separada: sus imágenes y productos se relacionan con los módulos de cultivos, parcelas, agua y clima que ya ofrece DOTS.</p><div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(230px,1fr))",gap:14}}>{[
 {t:"Producción agrícola",d:"Comparar campañas y reconocer sectores de vegetación menos vigorosa. Ayuda a decidir dónde inspeccionar un lote antes de intervenir.",url:"/cultivos",link:"Ir a cultivos"},
 {t:"Crecidas e inundaciones",d:"Revisar imágenes de radar para reconocer agua sobre el terreno, incluso cuando las nubes impiden una fotografía óptica.",url:"/nino-crecidas",link:"Ir a crecidas"},
 {t:"Temperaturas y sequías",d:"Contrastar temperaturas superficiales y cambios en vegetación para investigar períodos de estrés térmico e hídrico.",url:"/simulador-ambiental",link:"Ir al simulador"},
 {t:"Historia del territorio",d:"Comparar coberturas de distintas fechas para estudiar avance agrícola, pérdida de monte y cambios en pastizales.",url:"/observatorio",link:"Abrir mapa principal"},
 {t:"Calidad atmosférica",d:"Consultar productos regionales de gases y humo para contextualizar episodios ambientales, sin atribuir emisiones a una parcela individual.",url:"/capas",link:"Ver capas"},
 {t:"Informes técnicos",d:"Usar las fuentes verificadas como respaldo de análisis de parcelas; los nuevos informes automáticos Copernicus aún están en desarrollo.",url:"/modulos",link:"Ver informes"}
 ].map(x=><article key={x.t} style={{padding:18,background:"#192b36",border:"1px solid #38505d",borderRadius:12}}><h3>{x.t}</h3><p style={{color:"#bfd0d9"}}>{x.d}</p><a style={{color:"#8bd3ef"}} href={x.url}>{x.link} →</a></article>)}</div></section>
 <section style={{background:"#192b36",border:"1px solid #38505d",padding:22,borderRadius:14}}>
 <h2>Delimitar y analizar una parcela</h2><p>Seleccioná un polígono del Observatorio o dibujá uno nuevo. Sin delimitación no se habilita la consulta.</p>
 <div style={{display:"flex",gap:8,alignItems:"center",marginBottom:10,flexWrap:"wrap"}}><strong>Mapa base</strong><button type="button" onClick={()=>setMapStyle("satellite")} aria-pressed={mapStyle==="satellite"} style={{...action,background:mapStyle==="satellite"?"#087f9e":"#234454"}}>Imagen satelital</button><button type="button" onClick={()=>setMapStyle("streets")} aria-pressed={mapStyle==="streets"} style={{...action,background:mapStyle==="streets"?"#087f9e":"#234454"}}>Mapa de calles</button></div><p style={{color:"#b7c9d1"}}>La imagen de fondo es cartografía de referencia; no corresponde necesariamente a la fecha de búsqueda Copernicus ni constituye un mapa NDVI.</p>
 <div ref={mapElement} style={{height:340,width:"100%",borderRadius:10,marginBottom:12}} aria-label="Mapa interactivo para delimitar el área de estudio"/>
 <div style={{display:"flex",gap:8,flexWrap:"wrap",marginBottom:12}}><button type="button" onClick={()=>setDrawMode(v=>!v)} style={action}>{drawMode?"Terminar dibujo":"Dibujar polígono"}</button><button type="button" onClick={()=>{setOutline([]);setScenes([]);setDrawMode(true)}} style={action}>Borrar delimitación</button><span style={{alignSelf:"center"}}>{outline.length>=3?"Área delimitada · "+outline.length+" vértices":outline.length+" puntos · mínimo 3"}</span></div>
 <p style={{color:"#b7c9d1"}}>El rectángulo de búsqueda se calcula automáticamente desde el polígono. La búsqueda devuelve escenas que intersectan el área; todavía no recorta píxeles ni calcula índices dentro del lote.</p>
 <form onSubmit={search} style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(180px,1fr))",gap:12}}>
 <label>Colección<select required value={collection} onChange={e=>setCollection(e.target.value)} style={field}><option value="" disabled>{catalogLoading?"Cargando colecciones…":"Seleccionar colección"}</option>{collections.map(c=><option key={c.id} value={c.id}>{c.title||c.id}</option>)}</select>{catalogError&&<span role="alert" style={{display:"block",color:"#ffb5a7",marginTop:6}}>No se pudo cargar el catálogo: {catalogError}. Recargá la página para reintentar.</span>}</label>
 <label>Extensión de búsqueda (automática)<input readOnly value={outline.length>=3?bbox:"Delimitá el lote primero"} style={field}/></label>
 <label>Desde<input required type="date" value={start} onChange={e=>setStart(e.target.value)} style={field}/></label>
 <label>Hasta<input required type="date" value={end} onChange={e=>setEnd(e.target.value)} style={field}/></label>
 <button disabled={loading||!collection||outline.length<3} type="submit" style={{background:"#35b3cf",color:"#071820",fontWeight:700,border:0,borderRadius:8,padding:12,cursor:"pointer"}}>{loading?"Consultando…":"Buscar imágenes"}</button>
 </form>
 {error&&<p role="alert" style={{color:"#ffb5a7"}}>{error}</p>}
 <section style={{margin:"22px 0",padding:16,border:"1px solid #54717f",borderRadius:10}}><h3>Mapas temáticos Sentinel-2 · datos reales</h3><p>Calculá índices sobre los píxeles de la zona delimitada. Requiere credenciales CDSE de procesamiento configuradas en el servidor. Las imágenes se obtienen del servicio oficial; no se generan resultados de ejemplo.</p><label>Producto<select value={mapIndex} onChange={e=>setMapIndex(e.target.value as "ndvi"|"ndwi"|"truecolor")} style={field}><option value="ndvi">NDVI · vigor vegetal</option><option value="ndwi">NDWI · índice de agua</option><option value="truecolor">Composición RGB · color natural</option></select></label><button type="button" disabled={thematicBusy||outline.length<3} onClick={generateThematic} style={{...action,marginTop:12}}>{thematicBusy?"Procesando píxeles…":"Generar mapa temático"}</button>{thematicError&&<p role="alert" style={{color:"#ffb5a7"}}>{thematicError}</p>}{thematicUrl&&<div style={{marginTop:14}}><img src={thematicUrl} alt={"Mapa satelital "+mapIndex+" calculado sobre la parcela"} style={{maxWidth:"100%",maxHeight:520,borderRadius:8}}/><p style={{color:"#b7c9d1"}}>Fuente: Copernicus Sentinel-2 L2A · período {start} a {end} · índice {mapIndex.toUpperCase()}. El raster se enmascara al polígono; la imagen corresponde a un mosaico de menor nubosidad, no necesariamente a una única fecha.</p><a href={thematicUrl} download={"DOTS_Sentinel2_"+mapIndex+".png"} style={{color:"#8bd3ef"}}>Descargar mapa PNG</a></div>}</section>
 <section id="generador-informes-copernicus" style={{margin:"24px 0",padding:18,border:"1px solid #54717f",borderRadius:10}}><h3>Generador de informes técnicos · PDF</h3><p>Configurá el documento para la parcela delimitada. Se incluyen solamente datos disponibles y verificados del catálogo.</p><label>Título del informe<input value={reportTitle} onChange={e=>setReportTitle(e.target.value)} maxLength={120} style={field}/></label><label>Observaciones técnicas<textarea value={reportNotes} onChange={e=>setReportNotes(e.target.value)} maxLength={1200} rows={3} style={{...field,resize:"vertical"}}/></label><label style={{display:"flex",alignItems:"center",gap:8,margin:"12px 0"}}><input type="checkbox" checked={includeScenes} onChange={e=>setIncludeScenes(e.target.checked)}/> Incluir listado de escenas consultadas ({validScenes.length})</label><p style={{color:"#b7c9d1"}}>Incluye: mapa esquemático del polígono, coordenadas, período, colección y metodología. NDVI, humedad e inundaciones no se calcularán sin procesamiento satelital real.</p></section>
 <button type="button" onClick={downloadGeoJSON} disabled={outline.length<3} style={action}>Exportar mapa y delimitación GeoJSON</button>{" "}<button type="button" onClick={downloadReport} disabled={pdfBusy||outline.length<3} style={action}>{pdfBusy?"Generando PDF…":"Descargar informe PDF del área delimitada"}</button><p style={{color:"#b7c9d1"}}>El PDF documenta el polígono y las escenas consultadas; no incluye todavía índices de vegetación calculados.</p>
 <p role="status">{validScenes.length?validScenes.length+" escenas encontradas":loading?"Buscando en Copernicus…":"Los resultados aparecerán aquí. No se muestran datos simulados."}</p>
 <section id="graficos-copernicus" style={{marginTop:22}}><h3>Módulos gráficos · monitoreo satelital</h3><p style={{color:"#b7c9d1"}}>Los gráficos se generan exclusivamente con metadatos de las escenas devueltas por Copernicus. No representan mediciones de vegetación ni agua dentro de la parcela.</p>{scenes.length>0?<div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(300px,1fr))",gap:14}}><SceneChart title="Escenas por fecha" kind="dates" scenes={validScenes}/><SceneChart title="Cobertura nubosa por imagen" kind="cloud" scenes={validScenes}/><SceneChart title="Distribución de nubosidad" kind="distribution" scenes={validScenes}/></div>:<p style={{padding:20,border:"1px dashed #54717f",borderRadius:9}}>Delimitá el área y consultá imágenes para activar los tres gráficos.</p>}</section>
 <div style={{display:"grid",gap:8}}>{validScenes.map(s=><article key={s.id} style={{borderTop:"1px solid #38505d",padding:"12px 0"}}><strong>{s.id}</strong><p>{s.collection} · {s.properties.datetime||"Fecha no informada"} · Nubes: {s.properties["eo:cloud_cover"]??"sin dato"}%</p>{s.links.find(l=>l.rel==="self")&&<a href={s.links.find(l=>l.rel==="self")!.href} target="_blank" rel="noreferrer" style={{color:"#8bd3ef"}}>Metadatos oficiales ↗</a>}</article>)}</div>
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
