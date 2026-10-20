import {useMemo,useState} from "react";
import {calculateEnso,ensoEpisodes,type MonthlyAnomaly} from "../lib/ensoAnalysis";
export function EnsoSimulator(){
 const [raw,setRaw]=useState("");
 const result=useMemo(()=>{
  try{
   if(!raw.trim())return {points:[],episodes:[],error:""};
   const rows:MonthlyAnomaly[]=raw.trim().split(/\r?\n/).map(line=>{
    const parts=line.split(/[;\t]/).map(v=>v.trim());
    if(parts.length!==2)throw Error("Formato: AAAA-MM;anomalía °C");
    const anomalyC=Number(parts[1].replace(",","."));
    return {month:parts[0],anomalyC,source:"Serie de anomalías ingresada por el usuario"};
   });
   const points=calculateEnso(rows);
   return {points,episodes:ensoEpisodes(points),error:""};
  }catch(e){return {points:[],episodes:[],error:(e as Error).message}}
 },[raw]);
 return <section style={{background:"#172935",padding:12,borderRadius:10,marginTop:12}}>
  <h3>El Niño / La Niña · análisis Niño 3.4</h3>
  <p style={{fontSize:12}}>Ingresá anomalías mensuales de temperatura del mar ya calculadas para Niño 3.4, con climatología y fuente identificadas. El módulo calcula una media móvil de tres meses y episodios consecutivos; no afirma reproducir el ONI oficial.</p>
  <label htmlFor="dots-enso-data">Serie mensual (AAAA-MM;anomalía en °C)</label>
  <textarea id="dots-enso-data" rows={5} value={raw} onChange={e=>setRaw(e.target.value)} placeholder={"2023-01;-0.2\n2023-02;-0.1\n2023-03;0.1"} style={{width:"100%",boxSizing:"border-box",padding:8,background:"#20313d",color:"white"}}/>
  {result.error&&<p role="alert">{result.error}</p>}
  {result.points.length>0&&<><p>{result.points.length} meses procesados · {result.episodes.length} episodios de cinco o más meses detectados</p>
   <div style={{maxHeight:240,overflowY:"auto"}}>
    <table style={{width:"100%",fontSize:12}}><thead><tr><th>Mes</th><th>Anomalía</th><th>Media 3 meses</th><th>Fase indicativa</th></tr></thead><tbody>{result.points.map(p=><tr key={p.month}><td>{p.month}</td><td>{p.anomalyC.toFixed(2)} °C</td><td>{p.threeMonthMean===null?"—":p.threeMonthMean.toFixed(2)+" °C"}</td><td>{p.phase==="warm"?"Cálida":p.phase==="cold"?"Fría":p.phase==="neutral"?"Neutra":"Insuficiente"}</td></tr>)}</tbody></table>
   </div>
   {result.episodes.map(e=><p key={e.start}>{e.phase==="warm"?"Fase cálida":"Fase fría"}: {e.start} a {e.end} ({e.months} meses)</p>)}
  </>}
  <p style={{fontSize:12,color:"#ffd38d"}}>ENSO es un condicionante climático, no una relación determinista con una crecida. El análisis de impacto regional exige contrastar lluvia, cuencas, estaciones y desfases temporales.</p>
 </section>;
}
