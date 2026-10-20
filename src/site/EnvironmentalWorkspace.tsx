import {useState} from "react";
import {EnvironmentalLab} from "./EnvironmentalLab";
import {EnvironmentalMap} from "./EnvironmentalMap";
import {FloodScenarioPanel} from "./FloodScenarioPanel";
import {GeoRasterWorkbench} from "./GeoRasterWorkbench";
import {EnsoObservatory} from "./EnsoObservatory";
const BASINS:Record<string,string[]>={
 "Cuenca del Plata":["Paraná","Paraguay","Uruguay","Iguazú","Pilcomayo","Bermejo","Salado del Norte","Tercero / Carcarañá","Río de la Plata"],
 "Amazonas":["Amazonas","Solimões","Negro","Madeira","Tapajós","Xingu","Purus","Juruá","Ucayali","Marañón","Napo","Putumayo / Içá","Javari","Trombetas"],
 "Orinoco":["Orinoco","Meta","Apure","Guaviare","Caroní","Arauca","Ventuari"],
 "Tocantins–Araguaia":["Tocantins","Araguaia","Itacaiúnas"],
 "São Francisco":["São Francisco","Das Velhas","Paracatu","Grande"],
 "Magdalena–Cauca":["Magdalena","Cauca","San Jorge","Cesar"],
 "Patagonia y sur":["Colorado","Negro","Limay","Neuquén","Chubut","Santa Cruz","Gallegos","Baker","Biobío"],
 "Vertiente del Pacífico":["Guayas","Esmeraldas","Tumbes","Chira","Santa","Rímac","Maule","Maipo","Loa"],
 "Otras cuencas":["Seleccionar libremente en el mapa"]
};
export function EnvironmentalWorkspace(){
 const [layer,setLayer]=useState("");
 const [guideStep,setGuideStep]=useState(0);
 const [guideBasin,setGuideBasin]=useState("Cuenca del Plata");
 const [guideRiver,setGuideRiver]=useState("Paraná");
 const [guideMode,setGuideMode]=useState<"relieve"|"observado">("relieve");
 const [guideMessage,setGuideMessage]=useState("");
 const steps=["Río","Tramo","Análisis","Ejecutar","Resultados"];
 function advanceGuide(){if(guideStep===1&&(!tramoStart||!tramoEnd)){setGuideMessage("Primero marcá dos puntos sobre el mapa para delimitar el tramo.");setTramoMode(true);return}if(guideStep===3){if(guideMode==="relieve")setTerrainEnabled(true);else setLayer("MODIS_Combined_Flood_3-Day")}setGuideMessage("");setGuideStep(x=>Math.min(4,x+1))}
 const [terrainEnabled,setTerrainEnabled]=useState(false);
 const [terrainLevel,setTerrainLevel]=useState(60);
 const [tramoMode,setTramoMode]=useState(false);
 const [tramoStart,setTramoStart]=useState<[number,number]|null>(null);
 const [tramoEnd,setTramoEnd]=useState<[number,number]|null>(null);
 function selectTramoPoint(a:number,b:number){if(!tramoStart||tramoEnd){setTramoStart([a,b]);setTramoEnd(null)}else{setTramoEnd([a,b]);setTramoMode(false);updatePoint((tramoStart[0]+a)/2,(tramoStart[1]+b)/2)}}
 const [date,setDate]=useState("");
 const [lat,setLat]=useState(-28.507);
 const [lon,setLon]=useState(-59.043);
 const [latInput,setLatInput]=useState("-28.507");
 const [lonInput,setLonInput]=useState("-59.043");
 const [error,setError]=useState("");
 const [cityQuery,setCityQuery]=useState("");
 const [cityLoading,setCityLoading]=useState(false);
 const [cityError,setCityError]=useState("");
 async function findCity(e:React.FormEvent){e.preventDefault();if(cityQuery.trim().length<3){setCityError("Ingresá al menos tres letras.");return}setCityLoading(true);setCityError("");try{const q=encodeURIComponent(cityQuery.trim());const response=await fetch(`https://nominatim.openstreetmap.org/search?format=json&limit=5&q=${q}`,{headers:{"Accept":"application/json"}});if(!response.ok)throw Error("Servicio de búsqueda no disponible");const places=await response.json() as Array<{lat:string;lon:string;display_name:string}>;const p=places[0];if(!p){setCityError("No se encontró esa localidad. Agregá provincia y país.");return}const a=Number(p.lat),b=Number(p.lon);if(!Number.isFinite(a)||!Number.isFinite(b))throw Error("Coordenadas inválidas");updatePoint(a,b);setGuideMessage(`Ubicación encontrada: ${p.display_name}. Marcá los extremos del tramo en el mapa.`)}catch(err){setCityError(err instanceof Error?err.message:"No se pudo buscar la ciudad")}finally{setCityLoading(false)}}
 function updatePoint(a:number,b:number){setLat(a);setLon(b);setLatInput(a.toFixed(5));setLonInput(b.toFixed(5));setError("")}
 function queryPoint(e:React.FormEvent){e.preventDefault();const a=Number(latInput),b=Number(lonInput);if(!latInput.trim()||!lonInput.trim()||!Number.isFinite(a)||!Number.isFinite(b)||a < -90||a>90||b < -180||b>180){setError("Ingresá latitud entre -90 y 90 y longitud entre -180 y 180");return}updatePoint(a,b)}
 return <><section aria-label="Simulación sencilla" style={{background:"#102d3b",color:"#eef6fa",padding:16,borderRadius:12,margin:"12px 0"}}><h2 style={{margin:"0 0 8px"}}>Simulá en 3 pasos</h2><p style={{fontSize:13}}>1. Elegí la cuenca, el río y marcá dos puntos en el mapa. 2. Activá la visualización y mové la cota. 3. Consultá el resultado y el informe debajo del mapa.</p><form onSubmit={findCity} style={{display:"flex",flexWrap:"wrap",gap:8,alignItems:"end",marginBottom:12}}><label>Buscar ciudad o localidad<input value={cityQuery} onChange={e=>setCityQuery(e.target.value)} placeholder="Ej.: Goya, Corrientes, Argentina" style={{display:"block",padding:9,minWidth:240,marginTop:4}}/></label><button type="submit" disabled={cityLoading}>{cityLoading?"Buscando…":"Buscar en el mapa"}</button>{cityError&&<span role="alert">{cityError}</span>}</form><div style={{display:"flex",gap:12,flexWrap:"wrap",alignItems:"end"}}><label>Cuenca<select value={guideBasin} onChange={e=>{setGuideBasin(e.target.value);setGuideRiver(BASINS[e.target.value][0]);setTramoStart(null);setTramoEnd(null);setTramoMode(true)}} style={{display:"block",padding:9,marginTop:4}}>{Object.keys(BASINS).map(b=><option key={b}>{b}</option>)}</select></label><label>Río<select value={guideRiver} onChange={e=>{setGuideRiver(e.target.value);setTramoStart(null);setTramoEnd(null);setTramoMode(true)}} style={{display:"block",padding:9,marginTop:4}}>{BASINS[guideBasin].map(r=><option key={r}>{r}</option>)}</select></label><button type="button" onClick={()=>{setTramoMode(true);setGuideMessage("Marcá el inicio y el final del tramo en el mapa.")}}>1. Marcar tramo</button><button type="button" onClick={()=>{setTerrainEnabled(true);setTramoMode(false);setGuideMessage("Visualización activada: ajustá la cota con el deslizador.")}}>2. Simular zonas bajas</button><button type="button" onClick={()=>{setLayer("MODIS_Combined_Flood_3-Day");setGuideMessage("Capa satelital solicitada: verificá fecha y cobertura.")}}>Ver agua observada (MODIS)</button></div>{guideMessage&&<p role="status" style={{marginBottom:0}}>{guideMessage}</p>}<p style={{fontSize:12,marginBottom:0}}>La simulación de zonas bajas es topográfica, no una predicción de inundación.</p></section><div style={{display:"grid",gridTemplateColumns:"minmax(0,2.2fr) minmax(300px,1fr)",gap:16,alignItems:"start"}} className="dots-environmental-workspace">
  <div style={{minWidth:0}}>
   <details style={{margin:"8px 0"}}><summary>Opciones avanzadas · coordenadas</summary>   <form onSubmit={queryPoint} style={{display:"flex",flexWrap:"wrap",gap:10,alignItems:"end",padding:"12px 0"}}>
    <label>Latitud <input aria-label="Latitud" value={latInput} onChange={e=>setLatInput(e.target.value)} inputMode="decimal" style={{display:"block",width:130,padding:9}}/></label>
    <label>Longitud <input aria-label="Longitud" value={lonInput} onChange={e=>setLonInput(e.target.value)} inputMode="decimal" style={{display:"block",width:130,padding:9}}/></label>
    <button type="submit" style={{padding:10}}>Consultar ubicación</button>
   </form>
   {error&&<p role="alert">{error}</p>}
</details>
   <div style={{display:"flex",gap:10,alignItems:"center",flexWrap:"wrap",margin:"8px 0"}}><button type="button" aria-pressed={tramoMode} onClick={()=>setTramoMode(v=>!v)}>{tramoMode?"Finalizar selección de tramo":"Definir tramo sobre el mapa"}</button><button type="button" onClick={()=>{setTramoStart(null);setTramoEnd(null);setTramoMode(true)}}>Borrar tramo</button><span>{tramoStart?(tramoEnd?"Tramo marcado (línea de referencia)":"Marcá el punto final"):"Sin tramo delimitado"}</span></div>
   <section style={{background:"#142834",color:"#f1f7fb",borderRadius:12,padding:14,margin:"12px 0"}} aria-label="Simulación visual de relieve"><h2 style={{margin:"0 0 8px"}}>Simulación interactiva · zonas bajas</h2><label style={{display:"block"}}><input type="checkbox" checked={terrainEnabled} onChange={e=>setTerrainEnabled(e.target.checked)}/> Mostrar áreas por debajo de una cota topográfica</label><label style={{display:"block",marginTop:12}}>Cota absoluta del terreno: <strong>{terrainLevel} m sobre el nivel del mar</strong><input aria-label="Cota topográfica para explorar zonas bajas" type="range" min="-10" max="200" step="1" value={terrainLevel} onChange={e=>setTerrainLevel(Number(e.target.value))} style={{width:"100%",display:"block"}}/></label><p style={{fontSize:12,marginBottom:0}}>El color azul señala celdas con elevación inferior a la cota elegida. <strong>No es una mancha de inundación ni un pronóstico</strong>: incluye depresiones desconectadas del río y no incorpora diques, caudales ni hidráulica. Fuente de relieve: teselas Terrarium / AWS Terrain Tiles, según disponibilidad. Para comparar con observaciones, activá también una capa MODIS.</p></section>
   <EnvironmentalMap lat={lat} lon={lon} layer={layer} date={date} onPoint={updatePoint} tramoMode={tramoMode} onTramoPoint={selectTramoPoint} tramoStart={tramoStart} tramoEnd={tramoEnd} terrainEnabled={terrainEnabled} terrainLevel={terrainLevel}/>
   <details open style={{margin:"14px 0"}}><summary style={{padding:12,background:"#173743",color:"#fff",borderRadius:8,cursor:"pointer"}}>Observatorio ENSO · NOAA / IRI Columbia · gráficos e informes</summary><EnsoObservatory/></details>
   <FloodScenarioPanel onLayer={setLayer} tramoStart={tramoStart} tramoEnd={tramoEnd} riverName={guideRiver} basinName={guideBasin}/>
   <details style={{marginTop:14}}><summary style={{padding:12,background:"#173743",color:"#fff",borderRadius:8,cursor:"pointer"}}>Laboratorio geoespacial · importar DEM / GeoTIFF</summary><GeoRasterWorkbench basin={guideBasin} river={guideRiver} tramoStart={tramoStart} tramoEnd={tramoEnd}/></details>
   <p>Ubicación seleccionada: {lat.toFixed(5)}, {lon.toFixed(5)} · Capa: {layer||"Mapa base"}</p>
  </div>
  <details style={{minWidth:0}}><summary style={{padding:12,background:"#173743",color:"#fff",borderRadius:8,cursor:"pointer"}}>Opciones avanzadas · capas y variables</summary><EnvironmentalLab lat={lat} lon={lon} activeMapLayer={layer} onSelectMapLayer={setLayer} mapDate={date} onMapDateChange={setDate}/></details>
 </div></>;
}
