import { useMemo, useState } from "react";
import { ENVIRONMENTAL_CATALOG, modulesByGroup } from "../lib/environmentalCatalog";
import type { EnvironmentalModule } from "../lib/environmentalCatalog";
import { makeTimeline } from "../lib/environmentalTimeline";
import { INITIAL_VARIABLES } from "../lib/environmentalVariables";
import type { TemporalFrame, ObservationKind } from "../lib/environmentalTimeline";

type Props = { frames?: readonly TemporalFrame[]; onSelectFrame?: (frame: TemporalFrame) => void; onSelectMapLayer?: (layer: string) => void; activeMapLayer?: string };
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
export function EnvironmentalLab({frames=[],onSelectFrame,onSelectMapLayer,activeMapLayer=""}:Props) {
 const [id,setId]=useState("flood");
 const [search,setSearch]=useState("");
 const [kind,setKind]=useState<ObservationKind>("observed");
 const [index,setIndex]=useState(0);
 const module = ENVIRONMENTAL_CATALOG.find(m=>m.id===id) ?? ENVIRONMENTAL_CATALOG[0];
 const timeline=useMemo(()=>makeTimeline(frames,id as TemporalFrame["variable"],kind),[frames,id,kind]);
 const frame=timeline[Math.min(index,timeline.length-1)];
 function changeModule(value:string){setId(value);setIndex(0);}
 function changeKind(value:ObservationKind){setKind(value);setIndex(0);}
 return <section aria-label="Laboratorio ambiental" className="dots-lab" style={{padding:16,background:"#101c24",color:"#e8f2f7",borderRadius:12,maxWidth:460}}>
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
  <p style={{fontSize:12,color:"#aac7d5"}}>Las capas disponibles muestran el último producto servido por NASA GIBS. Su cobertura y fecha efectiva dependen de cada satélite; no son pronósticos ni simulaciones.</p>
  <label htmlFor="dots-lab-search">Buscar entre {INITIAL_VARIABLES.length} variables registradas</label>
  <input id="dots-lab-search" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Ej.: caudal, NDVI, humedad..." style={{display:"block",width:"100%",boxSizing:"border-box",padding:10,margin:"8px 0",background:"#20313d",color:"white"}}/>
  {search.trim() && <div style={{maxHeight:160,overflowY:"auto",padding:8,background:"#192b35"}}>{INITIAL_VARIABLES.filter(v=>(v.label+" "+v.id+" "+v.unit).toLocaleLowerCase("es").includes(search.toLocaleLowerCase("es"))).map(v=><p key={v.id} style={{margin:"5px 0"}}>{v.label} · {v.unit} <small>({v.support})</small></p>)}</div>}
  <p><strong>Variables:</strong> {module.parameters.join(" · ")}</p>
  <p><strong>Fuentes candidatas:</strong> {module.sources.join(" · ")}</p>
  <p><strong>Producto:</strong> {module.output}</p>
  <p style={{color:"#f3ca8b"}}>{module.caveat}</p>
  <label htmlFor="dots-lab-kind">Tipo de información</label>
  <select id="dots-lab-kind" value={kind} onChange={e=>changeKind(e.target.value as ObservationKind)} style={{display:"block",padding:9,margin:"8px 0 12px",background:"#20313d",color:"white"}}>
   {(Object.keys(labels) as ObservationKind[]).map(k=><option key={k} value={k}>{labels[k]}</option>)}
  </select>
  {timeline.length===0 ? <p role="status">No hay escenas verificadas cargadas para este módulo y tipo. No se generan imágenes simuladas.</p> : <>
   <label htmlFor="dots-lab-time">Fecha de adquisición ({timeline.length} escenas)</label>
   <input id="dots-lab-time" type="range" min={0} max={timeline.length-1} value={Math.min(index,timeline.length-1)} onChange={e=>setIndex(Number(e.target.value))} style={{width:"100%"}}/>
   <p>{frame.acquiredAt} · {frame.source} · {frame.resolutionMeters ? frame.resolutionMeters+" m" : "resolución no declarada"}</p>
   {frame.qualityNote && <p>{frame.qualityNote}</p>}
   <button type="button" disabled={!onSelectFrame} onClick={()=>frame&&onSelectFrame?.(frame)}>Mostrar escena en mapa</button>
  </>}
 </section>;
}
