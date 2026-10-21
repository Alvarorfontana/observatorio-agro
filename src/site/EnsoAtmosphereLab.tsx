import {useEffect,useState} from "react";
type Series={months:string[];values:(number|null)[]};
type Payload={baseline:string;status:Record<string,string>;products:Record<string,Series>;sources:Record<string,string>;data_kind:string};
const labels:Record<string,string>={
 olr_pacific:"OLR: radiación saliente del Pacífico tropical",
 trade_winds_850:"Viento zonal 850 hPa: alisios",
 walker_shear_200_minus_850:"Circulación Walker: diferencia u200−u850",
 tahiti_minus_darwin_slp_anomaly:"Presión Tahití−Darwin: anomalía no estandarizada",
 soil_argentina:"Humedad del suelo: anomalía Argentina"
};
export function EnsoAtmosphereLab(){
 const [data,setData]=useState<Payload|null>(null),[error,setError]=useState(""),[selected,setSelected]=useState("");
 useEffect(()=>{const ctrl=new AbortController();fetch("/data/enso-atmosphere.json",{signal:ctrl.signal}).then(async r=>{if(!r.ok)throw Error("El conjunto atmosférico NOAA aún no fue procesado");return await r.json() as Payload}).then(d=>{if(!ctrl.signal.aborted)setData(d)}).catch(e=>{if(!ctrl.signal.aborted)setError(String(e))});return()=>ctrl.abort()},[]);
 const available=Object.keys(data?.products||{}),key=available.includes(selected)?selected:available[0];
 const s=key?data?.products[key]:undefined;
 const v=s?.values||[],finite=v.filter((n):n is number=>n!==null&&Number.isFinite(n));
 const lo=Math.min(-1,...finite),hi=Math.max(1,...finite),span=hi-lo||1;
 const paths:string[]=[];let path="";
 v.forEach((n,i)=>{if(n!==null&&Number.isFinite(n)){path+=(path?" L":"M")+(40+i*710/Math.max(1,v.length-1)).toFixed(1)+" "+(170-(n-lo)*145/span).toFixed(1)}else if(path){paths.push(path);path=""}});
 if(path)paths.push(path);
 return <section aria-label="Laboratorio atmosférico ENSO" style={{marginTop:18,padding:14,background:"#183743",borderRadius:10}}>
 <h3>Atmósfera, circulación Walker y humedad del suelo · NOAA/NCEP</h3>
 <p>Series mensuales con anomalías respecto de 1991–2020. La presión Tahití−Darwin es una diferencia regional, no el índice SOI oficial.</p>
 {!data&&<p role="status">{error||"Cargando productos atmosféricos…"}</p>}
 {data&&<><label>Variable <select value={key} onChange={e=>setSelected(e.target.value)}>{available.map(k=><option value={k} key={k}>{labels[k]||k}</option>)}</select></label>
 {s?<><svg viewBox="0 0 800 205" role="img" aria-label={labels[key]||key} style={{width:"100%",background:"#092733",marginTop:12}}>
 <line x1="40" x2="750" y1={170-(0-lo)*145/span} y2={170-(0-lo)*145/span} stroke="#e3eef2" strokeDasharray="4 5"/>
 {paths.map((p,i)=><path key={i} d={p} fill="none" stroke="#7bdbea" strokeWidth="2"/>)}
 <text x="40" y="194" fontSize="12" fill="#fff">{s.months[0]}</text>
 <text x="675" y="194" fontSize="12" fill="#fff">{s.months[s.months.length-1]}</text></svg>
 <p style={{fontSize:13}}>Lectura científica: la línea horizontal indica anomalía cero frente a 1991–2020. OLR informa sobre radiación saliente y convección; u850, sobre viento zonal; u200−u850, sobre cizalladura vertical; Tahití−Darwin no es el SOI oficial; humedad del suelo es una estimación modelada, no una medición de campo. Las asociaciones con ENSO no prueban causalidad local.</p>
 <p>{finite.length} observaciones válidas · {s.months[0]} a {s.months[s.months.length-1]}</p></>:<p>No hay productos procesados disponibles.</p>}
 <p style={{fontSize:12}}>Estado de fuentes: {Object.entries(data.status).map(([k,v])=>k+": "+v).join(" · ")||"sin fuentes procesadas"}. Los archivos sin cobertura válida no se sustituyen por valores sintéticos.</p>
 <p style={{fontSize:12}}>{Object.entries(data.sources).map(([k,url],i)=><span key={k}>{i>0?" · ":""}<a href={url} target="_blank" rel="noreferrer" style={{color:"#a7e4ff"}}>{k.toUpperCase()} NOAA</a></span>)}</p>
 </>}
 </section>;
}
