import {useState} from "react";
import {EnvironmentalLab} from "./EnvironmentalLab";
import {EnvironmentalMap} from "./EnvironmentalMap";
import {FloodScenarioPanel} from "./FloodScenarioPanel";
export function EnvironmentalWorkspace(){
 const [layer,setLayer]=useState("");
 const [date,setDate]=useState("");
 const [lat,setLat]=useState(-28.507);
 const [lon,setLon]=useState(-59.043);
 const [latInput,setLatInput]=useState("-28.507");
 const [lonInput,setLonInput]=useState("-59.043");
 const [error,setError]=useState("");
 function updatePoint(a:number,b:number){setLat(a);setLon(b);setLatInput(a.toFixed(5));setLonInput(b.toFixed(5));setError("")}
 function queryPoint(e:React.FormEvent){e.preventDefault();const a=Number(latInput),b=Number(lonInput);if(!latInput.trim()||!lonInput.trim()||!Number.isFinite(a)||!Number.isFinite(b)||a < -90||a>90||b < -180||b>180){setError("Ingresá latitud entre -90 y 90 y longitud entre -180 y 180");return}updatePoint(a,b)}
 return <div style={{display:"grid",gridTemplateColumns:"minmax(0,2.2fr) minmax(300px,1fr)",gap:16,alignItems:"start"}} className="dots-environmental-workspace">
  <div style={{minWidth:0}}>
   <form onSubmit={queryPoint} style={{display:"flex",flexWrap:"wrap",gap:10,alignItems:"end",padding:"12px 0"}}>
    <label>Latitud <input aria-label="Latitud" value={latInput} onChange={e=>setLatInput(e.target.value)} inputMode="decimal" style={{display:"block",width:130,padding:9}}/></label>
    <label>Longitud <input aria-label="Longitud" value={lonInput} onChange={e=>setLonInput(e.target.value)} inputMode="decimal" style={{display:"block",width:130,padding:9}}/></label>
    <button type="submit" style={{padding:10}}>Consultar ubicación</button>
   </form>
   {error&&<p role="alert">{error}</p>}
   <EnvironmentalMap lat={lat} lon={lon} layer={layer} date={date} onPoint={updatePoint}/>
   <FloodScenarioPanel onPoint={updatePoint} onLayer={setLayer}/>
   <p>Ubicación seleccionada: {lat.toFixed(5)}, {lon.toFixed(5)} · Capa: {layer||"Mapa base"}</p>
  </div>
  <EnvironmentalLab lat={lat} lon={lon} activeMapLayer={layer} onSelectMapLayer={setLayer} mapDate={date} onMapDateChange={setDate}/>
 </div>;
}
