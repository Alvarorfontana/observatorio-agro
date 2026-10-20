import { useMemo, useState } from "react";
import { ENVIRONMENTAL_CATALOG, modulesByGroup } from "../lib/environmentalCatalog";
import type { EnvironmentalModule } from "../lib/environmentalCatalog";
import { makeTimeline } from "../lib/environmentalTimeline";
import { INITIAL_VARIABLES } from "../lib/environmentalVariables";
import { EnvironmentalSeriesChart } from "./EnvironmentalSeriesChart";
import { FloodLiveSources } from "./FloodLiveSources";
import { EnsoSimulator } from "./EnsoSimulator";
import type { TemporalFrame, ObservationKind } from "../lib/environmentalTimeline";

type Props = { frames?: readonly TemporalFrame[]; onSelectFrame?: (frame: TemporalFrame) => void; onSelectMapLayer?: (layer: string) => void; activeMapLayer?: string; mapDate?: string; onMapDateChange?: (date:string)=>void; lat?:number; lon?:number; polygon?:number[][] };
const MAP_LAYERS = [
 {id:"MODIS_Combined_Flood_3-Day",label:"Agua detectada · MODIS",variable:"flood",source:"NASA GIBS · MODIS"},
 {id:"VIIRS_Combined_Flood_3-Day",label:"Agua detectada · VIIRS",variable:"flood",source:"NASA GIBS · VIIRS"},
 {id:"MODIS_Terra_NDVI_8Day",label:"Vegetación · NDVI",variable:"vegetation",source:"NASA GIBS · MODIS"},
 {id:"SMAP_L4_Analyzed_Surface_Soil_Moisture",label:"Humedad del suelo",variable:"drought",source:"NASA GIBS · SMAP"},
 {id:"IMERG_Precipitation_Rate",label:"Lluvia · IMERG",variable:"storms",source:"NASA GIBS · GPM"},
 {id:"GOES-East_ABI_Band13_Clean_Infrared",label:"Nubes infrarrojas · GOES",variable:"storms",source:"NASA GIBS · GOES"},
 {id:"MODIS_Terra_Land_Surface_Temp_Day",label:"Temperatura superficial",variable:"temperature",source:"NASA GIBS · MODIS"},
 {id:"VIIRS_NOAA20_Thermal_Anomalies_375m_All",label:"Focos térmicos · VIIRS",variable:"fire",source:"NASA GIBS · VIIRS"},
] as const;
const labels: Record<ObservationKind,string> = { observed:"Observaciones", forecast:"Pronósticos", scenario:"Escenarios" };
const status: Record<EnvironmentalModule["status"],string> = { visualizacion:"Capa / visualización", analisis:"Análisis por validar", "requiere-modelo":"Requiere modelo calibrado" };
/** Panel conectable al mapa Leaflet existente: no crea mapas ficticios ni solicita datos sin endpoint verificado. */
export function EnvironmentalLab({frames=[],onSelectFrame,onSelectMapLayer,activeMapLayer="",mapDate="",onMapDateChange,lat,lon,polygon=[]}:Props) {
 const [id,setId]=useState("flood");
 const [search,setSearch]=useState("");
 const today=new Date().toISOString().slice(0,10);
 const historicalStart="2000-01-01";
 const dated=Boolean(mapDate);
 const shiftDay=(amount:number)=>{const current=new Date((mapDate||today)+"T12:00:00Z");current.setUTCDate(current.getUTCDate()+amount);const next=current.toISOString().slice(0,10);if(next>=historicalStart&&next<=today)onMapDateChange?.(next);};
 const [kind,setKind]=useState<ObservationKind>("observed");
 const [index,setIndex]=useState(0);
 const module = ENVIRONMENTAL_CATALOG.find(m=>m.id===id) ?? ENVIRONMENTAL_CATALOG[0];
 const timeline=useMemo(()=>makeTimeline(frames,id as TemporalFrame["variable"],kind),[frames,id,kind]);
 const frame=timeline[Math.min(index,timeline.length-1)];
 function changeModule(value:string){setId(value);setIndex(0);}
 function changeKind(value:ObservationKind){setKind(value);setIndex(0);}
 return <section aria-label="Laboratorio ambiental" className="dots-lab" style={{padding:16,background:"#101c24",color:"#e8f2f7",borderRadius:12,width:"100%",boxSizing:"border-box"}}>
  <h2 style={{marginTop:0}}>Laboratorio ambiental · DOTS Campo</h2>
  <label htmlFor="dots-lab-variable">Variable ambiental</label>
  <select id="dots-lab-variable" value={id} onChange={e=>changeModule(e.target.value)} style={{display:"block",width:"100%",padding:10,margin:"8px 0 14px",background:"#20313d",color:"white"}}>
   {Object.entries(modulesByGroup()).map(([group,items])=><optgroup label={group} key={group}>{items.map(m=><option value={m.id} key={m.id}>{m.title}</option>)}</optgroup>)}
  </select>
  <p><strong>Estado:</strong> {status[module.status]}</p>
  <label htmlFor="dots-lab-layer">Capas satelitales disponibles en el mapa DOTS</label>
  <select id="dots-lab-layer" value={MAP_LAYERS.some(l=>l.id===activeMapLayer)?activeMapLayer:""} onChange={e=>onSelectMapLayer?.(e.target.value)} disabled={!onSelectMapLayer} style={{display:"block",width:"100%",padding:10,margin:"8px 0 10px",background:"#20313d",color:"white"}}>
   <option value="">Sin capa adicional</option>
   {MAP_LAYERS.map(l=><option key={l.id} value={l.id}>{l.label} · {l.source}</option>)}
  </select>
  <div style={{display:"grid",gap:8,margin:"12px 0"}}>
   <label htmlFor="dots-lab-date">Fecha satelital solicitada</label>
   <input id="dots-lab-date" type="date" min={historicalStart} max={today} value={mapDate} onChange={e=>onMapDateChange?.(e.target.value)} disabled={!onMapDateChange} style={{padding:10,background:"#20313d",color:"white"}}/>
   <div style={{display:"flex",gap:8}}>
    <button type="button" onClick={()=>shiftDay(-1)} disabled={!onMapDateChange}>◀ Día anterior</button>
    <button type="button" onClick={()=>shiftDay(1)} disabled={!onMapDateChange||mapDate===today}>Día siguiente ▶</button>
    <button type="button" onClick={()=>onMapDateChange?.("")} disabled={!onMapDateChange||!dated}>Última disponible</button>
   </div>
  </div>
  <p style={{fontSize:12,color:"#aac7d5"}}>NASA GIBS recibe la fecha elegida mediante WMS TIME. Una solicitud no garantiza una escena válida ese día: cada producto tiene fechas, resolución y cobertura propias. El control no interpola imágenes ni genera pronósticos.</p>
  <label htmlFor="dots-lab-search">Buscar entre {INITIAL_VARIABLES.length} variables registradas</label>
  <input id="dots-lab-search" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Ej.: caudal, NDVI, humedad..." style={{display:"block",width:"100%",boxSizing:"border-box",padding:10,margin:"8px 0",background:"#20313d",color:"white"}}/>
  <div style={{maxHeight:260,overflowY:"auto",padding:8,background:"#192b35"}}>{INITIAL_VARIABLES.filter(v=>(v.label+" "+v.id+" "+v.unit).toLocaleLowerCase("es").includes(search.toLocaleLowerCase("es"))).map(v=><div key={v.id} style={{padding:"8px 0",borderBottom:"1px solid #34505d"}}><strong>{v.label}</strong> · {v.unit}<div style={{fontSize:12,color:"#bbd4e0"}}>{v.sourceIds.join(" · ")} · {v.support}</div></div>)}</div>}
  {id==="flood"&&<div style={{padding:10,border:"1px solid #42687d",borderRadius:10}}>
   <h3 style={{marginTop:0}}>Crecidas e inundaciones · dos análisis</h3>
   <p><strong>1. Crecida:</strong> serie de niveles o caudales, umbrales y variaciones hipotéticas. <strong>2. Inundación:</strong> comparación de las máscaras satelitales MODIS/VIIRS por fecha, mediante el selector del mapa.</p>
   <p style={{fontSize:12,color:"#ffd38d"}}>La extensión futura de agua aún no se calcula: requiere un modelo hidrodinámico calibrado y datos topográficos.</p>
  </div>}
  <p><strong>Variables:</strong> {module.parameters.join(" · ")}</p>
  <p><strong>Fuentes candidatas:</strong> {module.sources.join(" · ")}</p>
  <p><strong>Producto:</strong> {module.output}</p>
  <p style={{color:"#f3ca8b"}}>{module.caveat}</p>
  <label htmlFor="dots-lab-kind">Tipo de información</label>
  <select id="dots-lab-kind" value={kind} onChange={e=>changeKind(e.target.value as ObservationKind)} style={{display:"block",padding:9,margin:"8px 0 12px",background:"#20313d",color:"white"}}>
   {(Object.keys(labels) as ObservationKind[]).map(k=><option key={k} value={k}>{labels[k]}</option>)}
  </select>
  {id==="flood"&&lat!==undefined&&lon!==undefined&&<FloodLiveSources lat={lat} lon={lon} polygon={polygon}/>}
  {id==="enso"&&<EnsoSimulator/>}
  <EnvironmentalSeriesChart key={id} title={id==="flood"?"Crecida · altura hidrométrica":module.title} unit={id==="flood"?"m":INITIAL_VARIABLES.find(v=>v.id===id)?.unit??"unidad declarada"} description={id==="flood"?"Cargá una serie oficial de una misma estación y con la misma referencia vertical. El desplazamiento hipotético no representa una mancha de inundación.":"Gráfico reutilizable: ingresá observaciones de la misma variable y unidad, con fecha y fuente verificables."}/>
  {timeline.length===0 ? <p role="status">No hay escenas verificadas cargadas para este módulo y tipo. No se generan imágenes simuladas.</p> : <>
   <label htmlFor="dots-lab-time">Fecha de adquisición ({timeline.length} escenas)</label>
   <input id="dots-lab-time" type="range" min={0} max={timeline.length-1} value={Math.min(index,timeline.length-1)} onChange={e=>setIndex(Number(e.target.value))} style={{width:"100%"}}/>
   <p>{frame.acquiredAt} · {frame.source} · {frame.resolutionMeters ? frame.resolutionMeters+" m" : "resolución no declarada"}</p>
   {frame.qualityNote && <p>{frame.qualityNote}</p>}
   <button type="button" disabled={!onSelectFrame} onClick={()=>frame&&onSelectFrame?.(frame)}>Mostrar escena en mapa</button>
  </>}
 </section>;
}
