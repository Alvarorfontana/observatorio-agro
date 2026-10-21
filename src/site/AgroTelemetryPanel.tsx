import {useEffect,useState} from "react";

type ResponseData = {
  provider:string;
  source:string;
  data_kind:string;
  period:{start:string;end:string};
  daily:Record<string, Array<string|number|null>>;
  daily_units:Record<string,string>;
  limitations:string[];
  omitted_variables?:string[];
};
const labels:Record<string,string>={
  temperature_2m_mean:"Temperatura media",
  relative_humidity_2m_mean:"Humedad relativa",
  precipitation_sum:"Precipitación",
  et0_fao_evapotranspiration:"Evapotranspiración ET0",
  shortwave_radiation_sum:"Radiación solar",
  wind_speed_10m_max:"Viento máximo",
  soil_moisture_0_to_7cm_mean:"Humedad del suelo 0-7 cm",
  soil_moisture_7_to_28cm_mean:"Humedad del suelo 7-28 cm"
};
export function AgroTelemetryPanel({lat,lon}:{lat:number;lon:number}){
  const [days,setDays]=useState(30);
  const [reload,setReload]=useState(0);
  const [data,setData]=useState<ResponseData|null>(null);
  const [variable,setVariable]=useState("precipitation_sum");
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(false);
  useEffect(()=>{
    const controller=new AbortController();
    const end=new Date();
    end.setUTCDate(end.getUTCDate()-8);
    const start=new Date(end);
    start.setUTCDate(start.getUTCDate()-days+1);
    const query=new URLSearchParams({
      lat:String(lat),lon:String(lon),
      start:start.toISOString().slice(0,10),
      end:end.toISOString().slice(0,10)
    });
    setLoading(true);setError("");setData(null);
    fetch("/api/agro/telemetria?"+query,{signal:controller.signal})
      .then(async response=>{
        const result=await response.json();
        if(!response.ok)throw Error(result.error||"No se obtuvieron datos");
        return result as ResponseData;
      })
      .then(result=>{if(!controller.signal.aborted)setData(result)})
      .catch(err=>{if(!controller.signal.aborted)setError(String(err))})
      .finally(()=>{if(!controller.signal.aborted)setLoading(false)});
    return ()=>controller.abort();
  },[lat,lon,days,reload]);
  const available=Object.keys(labels).filter(k=>data?.daily[k]?.some(v=>typeof v==="number"));
  const selected=available.includes(variable)?variable:available[0];
  const dates=data?.daily.time||[];
  const observations=(selected?data?.daily[selected]:[])||[];
  const valid=observations.filter((v):v is number=>typeof v==="number"&&Number.isFinite(v));
  const minimum=Math.min(0,...valid),maximum=Math.max(1,...valid);
  const coords=observations.map((v,i)=>typeof v==="number"&&Number.isFinite(v)
    ? {x:35+i*720/Math.max(1,observations.length-1),y:175-(v-minimum)*145/(maximum-minimum)}:null);
  const segments:string[]=[];
  let segment="";
  coords.forEach(p=>{
    if(p){segment+=(segment?" L":"M")+p.x.toFixed(1)+" "+p.y.toFixed(1)}
    else if(segment){segments.push(segment);segment=""}
  });
  if(segment)segments.push(segment);
  function downloadCsv(){
    if(!data)return;
    const keys=available;
    const rows=[["fecha",...keys].join(","),...dates.map((d,i)=>[d,...keys.map(k=>data.daily[k][i]??"")].join(","))];
    const url=URL.createObjectURL(new Blob([rows.join("\n")],{type:"text/csv;charset=utf-8"}));
    const a=document.createElement("a");a.href=url;a.download="dots-telemetria-agricola.csv";a.click();URL.revokeObjectURL(url);
  }
  return <section aria-label="Telemetría agroclimática" style={{background:"#102b37",color:"#eef6fa",padding:16,borderRadius:12,margin:"14px 0"}}>
    <h2>Telemetría agroclimática · parcela seleccionada</h2>
    <p>Coordenadas: {lat.toFixed(4)}, {lon.toFixed(4)}. Datos modelados; no equivalen a mediciones de sensores instalados.</p>
    <label>Histórico <select value={days} onChange={e=>setDays(Number(e.target.value))}>
      <option value={30}>30 días</option><option value={90}>90 días</option><option value={365}>365 días</option>
    </select></label>{" "}
    <button type="button" onClick={()=>setReload(v=>v+1)}>Actualizar</button>{" "}
    <button type="button" onClick={downloadCsv} disabled={!data||!available.length}>Exportar CSV</button>
    {loading&&<p role="status">Consultando Open-Meteo…</p>}
    {error&&<p role="alert">{error}</p>}
    {data&&<><p>Período: {data.period.start} a {data.period.end} · <a href={data.source} target="_blank" rel="noreferrer" style={{color:"#9de6fa"}}>{data.provider}</a></p>
      {selected?<><label>Variable <select value={selected} onChange={e=>setVariable(e.target.value)}>
        {available.map(k=><option key={k} value={k}>{labels[k]}</option>)}
      </select></label>
      <svg viewBox="0 0 800 210" role="img" aria-label={"Serie histórica "+labels[selected]} style={{width:"100%",background:"#163c49",borderRadius:8,marginTop:10}}>
        {segments.map((path,i)=><path key={i} d={path} fill="none" stroke="#7ad8e9" strokeWidth={2}/>)}
        <text x={35} y={198} fontSize={13} fill="#fff">{dates[0]}</text>
        <text x={660} y={198} fontSize={13} fill="#fff">{dates[dates.length-1]}</text>
      </svg>
      <p>{valid.length} valores · {data.daily_units[selected]||"Unidad no informada"} · Último: {valid.length?valid[valid.length-1]:"Sin dato"}</p>
      </>:<p>No se recibieron series numéricas para este período.</p>}
      {Boolean(data.omitted_variables?.length)&&<p role="status">La fuente no ofrece humedad del suelo para esta consulta; se muestran las variables meteorológicas disponibles.</p>}
      <p style={{fontSize:12}}>{data.data_kind}. {data.limitations.join(". ")}.</p>
    </>}
  </section>;
}
