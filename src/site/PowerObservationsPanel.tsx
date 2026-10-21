import {useEffect,useState} from "react";
import {DotsReportExport} from "./DotsReportExport";
type Power={type:string;geometry:{coordinates:number[]};properties:{parameter:Record<string,Record<string,number>>}};
const variables:Record<string,string>={T2M:"Temperatura a 2 m (°C)",PRECTOTCORR:"Precipitación corregida (mm/h)",RH2M:"Humedad relativa (%)",WS2M:"Velocidad del viento a 2 m (m/s)"};
export function PowerObservationsPanel({lat:mapLat,lon:mapLon}:{lat:number;lon:number}){
 const [lat,setLat]=useState(String(mapLat)),[lon,setLon]=useState(String(mapLon)),[days,setDays]=useState("7"),[data,setData]=useState<Power|null>(null),[error,setError]=useState(""),[loading,setLoading]=useState(false),[selected,setSelected]=useState("T2M");
 async function load(){
  const latitude=Number(lat),longitude=Number(lon),count=Number(days);
  if(!lat.trim()||!lon.trim()||!Number.isFinite(latitude)||!Number.isFinite(longitude)||Math.abs(latitude)>90||Math.abs(longitude)>180){setError("Coordenadas inválidas");return}
  setLoading(true);setError("");setData(null);
  const end=new Date();end.setUTCDate(end.getUTCDate()-2);
  const start=new Date(end);start.setUTCDate(start.getUTCDate()-count+1);
  const fmt=(d:Date)=>d.toISOString().slice(0,10).replaceAll("-","");
  const params=new URLSearchParams({parameters:"T2M,PRECTOTCORR,RH2M,WS2M",community:"AG",longitude:String(longitude),latitude:String(latitude),start:fmt(start),end:fmt(end),format:"JSON",time_standard:"UTC"});
  try{const r=await fetch("https://power.larc.nasa.gov/api/temporal/hourly/point?"+params);if(!r.ok)throw Error("NASA POWER no respondió: HTTP "+r.status);const j=await r.json() as Power;if(!j.properties?.parameter)throw Error("Respuesta sin observaciones");setData(j)}catch(e){setError(String(e))}finally{setLoading(false)}
 }
 useEffect(()=>{setLat(String(mapLat));setLon(String(mapLon))},[mapLat,mapLon]);
 const series=data?.properties.parameter[selected]||{},points=Object.entries(series).filter(([,v])=>typeof v==="number"&&Number.isFinite(v)&&v>-900);
 const values=points.map(([,v])=>v),min=Math.min(...values),max=Math.max(...values),span=max-min||1;
 const path=points.map(([,v],i)=>(i?"L":"M")+(40+i*710/Math.max(1,points.length-1)).toFixed(1)+","+(165-(v-min)/span*130).toFixed(1)).join(" ");
 return <section style={{padding:18,background:"#15323e",color:"#eaf3f5",borderRadius:12,marginTop:18}}>
  <h3>Observaciones meteorológicas · NASA POWER</h3>
  <p>Consulta horaria de un punto geográfico. No es un promedio regional ni una estimación de cobertura nacional. Fuente: <a href="https://power.larc.nasa.gov/" target="_blank" rel="noreferrer">NASA POWER</a>.</p>
  <div style={{display:"flex",gap:12,flexWrap:"wrap",alignItems:"end"}}>
   <label>Latitud <input aria-label="Latitud NASA POWER" value={lat} onChange={e=>setLat(e.target.value)}/></label>
   <label>Longitud <input aria-label="Longitud NASA POWER" value={lon} onChange={e=>setLon(e.target.value)}/></label>
   <label>Días <select value={days} onChange={e=>setDays(e.target.value)}><option value="7">7</option><option value="14">14</option><option value="30">30</option></select></label>
   <button disabled={loading} onClick={()=>void load()}>{loading?"Consultando…":"Consultar NASA"}</button>
  </div>
  {error&&<p role="alert">{error}. Si el navegador bloquea la consulta, debe habilitarse el acceso a la API NASA POWER.</p>}
  {data&&<><p>Coordenadas consultadas: {data.geometry.coordinates[1]}°, {data.geometry.coordinates[0]}°. Horario UTC; valores faltantes -999 excluidos.</p>
   <label>Variable <select value={selected} onChange={e=>setSelected(e.target.value)}>{Object.keys(data.properties.parameter).map(k=><option key={k} value={k}>{variables[k]||k}</option>)}</select></label>
   {points.length>1?<DotsReportExport title={"DOTS · "+(variables[selected]||selected)} source="NASA POWER · https://power.larc.nasa.gov/" description={"Observaciones horarias UTC del punto "+lat+", "+lon+"; datos faltantes excluidos."} filename={"dots-power-"+selected.toLowerCase()} headers={["fecha_hora_utc",selected]} rows={points.map(([t,v])=>[t,v])}><svg viewBox="0 0 800 195" style={{width:"100%",background:"#09232d"}} role="img" aria-label={"Serie temporal de "+(variables[selected]||selected)}><path d={path} fill="none" stroke="#5ccee3" strokeWidth="2"/><text x="12" y="20" fill="white">{max.toFixed(2)}</text><text x="12" y="174" fill="white">{min.toFixed(2)}</text></svg><p>{points.length} observaciones válidas · Desde {points[0][0]} hasta {points[points.length-1][0]} UTC</p></DotsReportExport>:<p>No hay observaciones válidas para esta variable.</p>}
  </>}
 </section>
}
