import {useEffect,useState} from "react";
import {FloodRadarConnected} from "./FloodRadarConnected";
type Forecast={status:string;source:string;units:string;dates:string[];river_discharge:(number|null)[];river_discharge_min?:(number|null)[];river_discharge_max?:(number|null)[];limitations?:string[];model_grid?:{lat:number;lon:number}};
export function FloodLiveSources({lat,lon,polygon}:{lat:number;lon:number;polygon:number[][]}){
 const [data,setData]=useState<Forecast|null>(null),[error,setError]=useState(""),[loading,setLoading]=useState(false),[refresh,setRefresh]=useState(0);
 useEffect(()=>{
  if(!Number.isFinite(lat)||!Number.isFinite(lon))return;
  const ctrl=new AbortController();setLoading(true);setError("");setData(null);
  fetch("/api/pronostico-crecidas?"+new URLSearchParams({lat:String(lat),lon:String(lon)}),{signal:ctrl.signal})
   .then(async r=>{const j=await r.json();if(!r.ok)throw Error(j.error||"Pronóstico no disponible");return j as Forecast})
   .then(j=>{if(!ctrl.signal.aborted)setData(j)})
   .catch(e=>{if(!ctrl.signal.aborted)setError(e instanceof Error?e.message:"Error de conexión")})
   .finally(()=>{if(!ctrl.signal.aborted)setLoading(false)});
  return ()=>ctrl.abort();
 },[lat,lon,refresh]);
 const vals=data?.river_discharge?.map((v,i)=>({date:data.dates[i],value:v})).filter((x):x is {date:string;value:number}=>Number.isFinite(x.value))||[];
 const min=Math.min(...vals.map(v=>v.value)),max=Math.max(...vals.map(v=>v.value)),span=max-min||1;
 const w=460,h=190,p=32;
 const px=(i:number)=>p+(vals.length>1?i/(vals.length-1):0)*(w-2*p);
 const py=(v:number)=>h-p-(v-min)/span*(h-2*p);
 return <div style={{marginTop:14}}>
  <h3>Caudal modelado · GloFAS / Copernicus</h3>
  <button type="button" onClick={()=>setRefresh(v=>v+1)} disabled={loading}>{loading?"Consultando…":"Actualizar pronóstico"}</button>
  {error&&<p role="alert">Sin datos: {error}</p>}
  {vals.length>0&&<><svg viewBox={`0 0 ${w} ${h}`} role="img" aria-label="Pronóstico de caudal fluvial por fecha" style={{width:"100%",background:"#132733"}}>
   <line x1={p} y1={h-p} x2={w-p} y2={h-p} stroke="#a5b8c5"/>
   <path d={vals.map((v,i)=>`${i?"L":"M"}${px(i).toFixed(1)},${py(v.value).toFixed(1)}`).join(" ")} fill="none" stroke="#5bdaeb" strokeWidth={3}/>
   {vals.map((v,i)=><circle key={i} cx={px(i)} cy={py(v.value)} r={4} fill="#5bdaeb"><title>{v.date}: {v.value.toFixed(1)} {data?.units}</title></circle>)}
   <text x={p} y={p-10} fill="white" fontSize={11}>{max.toFixed(1)} {data?.units}</text>
   <text x={p} y={h-7} fill="white" fontSize={11}>{min.toFixed(1)} {data?.units}</text>
  </svg><p style={{fontSize:12}}>Pronóstico: {vals[0]?.date} a {vals[vals.length-1]?.date}. Fuente: {data?.source}. Celda de modelo: {data?.model_grid?.lat??"—"}, {data?.model_grid?.lon??"—"}.</p></>}
  <p style={{fontSize:12,color:"#ffd38d"}}>Pronóstico de caudal en una celda del modelo; no equivale a nivel hidrométrico ni a extensión de inundación. No sustituye alertas oficiales.</p>
  <h3>Radar Sentinel-1 · cambio de agua en el lote</h3>
  {polygon.length>=3?<FloodRadarConnected polygon={polygon} lat={lat} lon={lon} location="Polígono seleccionado"/>:<p>Para ejecutar el análisis radar de agua, dibujá un polígono en el mapa principal de DOTS. El radar compara escenas reales y reporta disponibilidad o errores.</p>}
 </div>;
}
