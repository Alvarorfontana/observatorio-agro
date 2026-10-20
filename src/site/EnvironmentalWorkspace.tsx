import {useState} from "react";
import {EnvironmentalLab} from "./EnvironmentalLab";
import {EnvironmentalMap} from "./EnvironmentalMap";
import {FloodScenarioPanel} from "./FloodScenarioPanel";
export function EnvironmentalWorkspace(){
 const [layer,setLayer]=useState("");
 const [guideStep,setGuideStep]=useState(0);
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
 function selectTramoPoint(a:number,b:number){if(!tramoStart||tramoEnd){setTramoStart([a,b]);setTramoEnd(null)}else setTramoEnd([a,b])}
 const [date,setDate]=useState("");
 const [lat,setLat]=useState(-28.507);
 const [lon,setLon]=useState(-59.043);
 const [latInput,setLatInput]=useState("-28.507");
 const [lonInput,setLonInput]=useState("-59.043");
 const [error,setError]=useState("");
 function updatePoint(a:number,b:number){setLat(a);setLon(b);setLatInput(a.toFixed(5));setLonInput(b.toFixed(5));setError("")}
 function queryPoint(e:React.FormEvent){e.preventDefault();const a=Number(latInput),b=Number(lonInput);if(!latInput.trim()||!lonInput.trim()||!Number.isFinite(a)||!Number.isFinite(b)||a < -90||a>90||b < -180||b>180){setError("Ingresá latitud entre -90 y 90 y longitud entre -180 y 180");return}updatePoint(a,b)}
 return <><section aria-label="Procedimiento guiado de simulación" style={{background:"#102d3b",color:"#eef6fa",padding:18,borderRadius:14,margin:"14px 0"}}><h2 style={{margin:"0 0 8px"}}>Procedimiento guiado para el usuario</h2><p style={{fontSize:13}}>Seguí los pasos para configurar una exploración territorial. Los resultados no constituyen un pronóstico hidráulico.</p><div style={{display:"flex",flexWrap:"wrap",gap:8,marginBottom:12}}>{steps.map((name,i)=><button key={name} type="button" onClick={()=>{setGuideStep(i);setGuideMessage("")}} aria-current={guideStep===i?"step":undefined} style={{padding:"9px 12px",background:guideStep===i?"#0b7f91":"#244653",color:"white",border:"1px solid #6e9ca8",borderRadius:8}}>{i+1}. {name}</button>)}</div>{guideStep===0?<label>Seleccioná el río <select value={guideRiver} onChange={e=>setGuideRiver(e.target.value)} style={{display:"block",padding:9,marginTop:5}}><option>Paraná</option><option>Paraguay</option><option>Uruguay</option></select></label>:guideStep===1?<p>Activá «Definir tramo sobre el mapa» y marcá dos puntos del {guideRiver}. {tramoStart&&tramoEnd?"Ya hay dos puntos definidos.":"Falta completar la delimitación."}</p>:guideStep===2?<fieldset style={{border:"1px solid #6e9ca8",borderRadius:8}}><legend>Tipo de exploración</legend><label style={{marginRight:16}}><input type="radio" checked={guideMode==="relieve"} onChange={()=>setGuideMode("relieve")}/> Zonas bajas según relieve</label><label><input type="radio" checked={guideMode==="observado"} onChange={()=>setGuideMode("observado")}/> Agua observada (MODIS)</label></fieldset>:guideStep===3?<p>{guideMode==="relieve"?"Al ejecutar se activa la capa de elevación. Ajustá la cota con el deslizador situado encima del mapa.":"Al ejecutar se selecciona la capa MODIS. Elegí la fecha en el panel de capas y verificá su disponibilidad."}</p>:<p>Resultado configurado: {guideRiver} · {guideMode==="relieve"?"exploración topográfica":"observación satelital"} · {tramoStart&&tramoEnd?"tramo con dos puntos definidos":"tramo sin delimitar"}. Revisá el mapa y los controles. El informe de escenario está debajo del mapa y sólo documenta niveles hipotéticos, no extensión inundada.</p>}{guideMessage&&<p role="alert" style={{color:"#ffda8d"}}>{guideMessage}</p>}<div style={{display:"flex",gap:10,marginTop:14}}><button type="button" disabled={guideStep===0} onClick={()=>{setGuideStep(x=>Math.max(0,x-1));setGuideMessage("")}}>Anterior</button><button type="button" disabled={guideStep===4} onClick={advanceGuide}>{guideStep===3?"Ejecutar visualización":guideStep===4?"Finalizado":"Siguiente"}</button></div></section><div style={{display:"grid",gridTemplateColumns:"minmax(0,2.2fr) minmax(300px,1fr)",gap:16,alignItems:"start"}} className="dots-environmental-workspace">
  <div style={{minWidth:0}}>
   <form onSubmit={queryPoint} style={{display:"flex",flexWrap:"wrap",gap:10,alignItems:"end",padding:"12px 0"}}>
    <label>Latitud <input aria-label="Latitud" value={latInput} onChange={e=>setLatInput(e.target.value)} inputMode="decimal" style={{display:"block",width:130,padding:9}}/></label>
    <label>Longitud <input aria-label="Longitud" value={lonInput} onChange={e=>setLonInput(e.target.value)} inputMode="decimal" style={{display:"block",width:130,padding:9}}/></label>
    <button type="submit" style={{padding:10}}>Consultar ubicación</button>
   </form>
   {error&&<p role="alert">{error}</p>}
   <div style={{display:"flex",gap:10,alignItems:"center",flexWrap:"wrap",margin:"8px 0"}}><button type="button" aria-pressed={tramoMode} onClick={()=>setTramoMode(v=>!v)}>{tramoMode?"Finalizar selección de tramo":"Definir tramo sobre el mapa"}</button><button type="button" onClick={()=>{setTramoStart(null);setTramoEnd(null);setTramoMode(true)}}>Borrar tramo</button><span>{tramoStart?(tramoEnd?"Tramo marcado (línea de referencia)":"Marcá el punto final"):"Sin tramo delimitado"}</span></div>
   <section style={{background:"#142834",color:"#f1f7fb",borderRadius:12,padding:14,margin:"12px 0"}} aria-label="Simulación visual de relieve"><h2 style={{margin:"0 0 8px"}}>Simulación interactiva · zonas bajas</h2><label style={{display:"block"}}><input type="checkbox" checked={terrainEnabled} onChange={e=>setTerrainEnabled(e.target.checked)}/> Mostrar áreas por debajo de una cota topográfica</label><label style={{display:"block",marginTop:12}}>Cota absoluta del terreno: <strong>{terrainLevel} m sobre el nivel del mar</strong><input aria-label="Cota topográfica para explorar zonas bajas" type="range" min="-10" max="200" step="1" value={terrainLevel} onChange={e=>setTerrainLevel(Number(e.target.value))} style={{width:"100%",display:"block"}}/></label><p style={{fontSize:12,marginBottom:0}}>El color azul señala celdas con elevación inferior a la cota elegida. <strong>No es una mancha de inundación ni un pronóstico</strong>: incluye depresiones desconectadas del río y no incorpora diques, caudales ni hidráulica. Fuente de relieve: teselas Terrarium / AWS Terrain Tiles, según disponibilidad. Para comparar con observaciones, activá también una capa MODIS.</p></section>
   <EnvironmentalMap lat={lat} lon={lon} layer={layer} date={date} onPoint={updatePoint} tramoMode={tramoMode} onTramoPoint={selectTramoPoint} tramoStart={tramoStart} tramoEnd={tramoEnd} terrainEnabled={terrainEnabled} terrainLevel={terrainLevel}/>
   <FloodScenarioPanel onPoint={updatePoint} onLayer={setLayer} tramoStart={tramoStart} tramoEnd={tramoEnd}/>
   <p>Ubicación seleccionada: {lat.toFixed(5)}, {lon.toFixed(5)} · Capa: {layer||"Mapa base"}</p>
  </div>
  <EnvironmentalLab lat={lat} lon={lon} activeMapLayer={layer} onSelectMapLayer={setLayer} mapDate={date} onMapDateChange={setDate}/>
 </div></>;
}
