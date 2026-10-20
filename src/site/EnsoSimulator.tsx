import {useEffect,useMemo,useState} from "react";
import {calculateEnso,ensoEpisodes,type MonthlyAnomaly} from "../lib/ensoAnalysis";
export function EnsoSimulator(){
 const [raw,setRaw]=useState("");
 const [official,setOfficial]=useState<{month:string;season:string;anomalyC:number}[]>([]);
 const [sourceError,setSourceError]=useState("");
 const [sourceLoading,setSourceLoading]=useState(false);
 const [showOfficial,setShowOfficial]=useState(true);
 useEffect(()=>{const ctrl=new AbortController();setSourceLoading(true);fetch("/api/enso/oni",{signal:ctrl.signal}).then(async r=>{const j=await r.json();if(!r.ok)throw Error(j.error||"NOAA no disponible");return j}).then(j=>{if(!ctrl.signal.aborted)setOfficial(j.points||[])}).catch(e=>{if(!ctrl.signal.aborted)setSourceError((e as Error).message)}).finally(()=>{if(!ctrl.signal.aborted)setSourceLoading(false)});return()=>ctrl.abort()},[]);
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
  <div style={{border:"1px solid #476577",borderRadius:8,padding:8,marginBottom:12}}>
   <h4 style={{margin:"0 0 8px"}}>ONI oficial · NOAA CPC</h4>
   {sourceLoading&&<p>Consultando fuente oficial…</p>}
   {sourceError&&<p role="alert">Fuente oficial no disponible: {sourceError}</p>}
   {official.length>0&&<><p>{official.length} trimestres superpuestos · último: {official[official.length-1].season} {official[official.length-1].month.slice(0,4)} · {official[official.length-1].anomalyC.toFixed(1)} °C</p>
    <button type="button" onClick={()=>setShowOfficial(v=>!v)}>{showOfficial?"Ocultar":"Mostrar"} serie oficial reciente</button>
    {showOfficial&&<div style={{maxHeight:220,overflowY:"auto"}}><table style={{width:"100%",fontSize:12}}><thead><tr><th>Estación</th><th>Mes central</th><th>ONI °C</th></tr></thead><tbody>{official.slice(-36).map(p=><tr key={p.month}><td>{p.season}</td><td>{p.month}</td><td>{p.anomalyC.toFixed(1)}</td></tr>)}</tbody></table></div>}
   </>}
   <p style={{fontSize:12}}>Datos oficiales de <a href="https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt" target="_blank" rel="noreferrer">NOAA CPC</a>. Este índice trimestral no debe volver a promediarse como si fuera una serie mensual de SST.</p>
  </div>
  <label htmlFor="dots-enso-data">Serie propia de anomalías mensuales (AAAA-MM;anomalía en °C)</label>
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
