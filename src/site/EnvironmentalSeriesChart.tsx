import { useMemo, useState } from "react";
type Datum={date:string;value:number};
type Props={title:string;unit:string;description?:string};
const parse=(input:string):Datum[]=>{
 const rows=input.trim().split(/\r?\n/).map(s=>s.trim()).filter(Boolean);
 if(rows.length>5000)throw Error("Máximo 5000 registros");
 const data=rows.map(row=>{
  const parts=row.split(/[;,\t]/).map(v=>v.trim());
  if(parts.length!==2||!/^\d{4}-\d{2}-\d{2}$/.test(parts[0])||!Number.isFinite(Date.parse(parts[0]+"T00:00:00Z")))throw Error("Formato: AAAA-MM-DD;valor");
  const value=Number(parts[1].replace(",","."));
  if(!Number.isFinite(value))throw Error("Hay valores no numéricos");
  return {date:parts[0],value};
 });
 return data.sort((a,b)=>a.date.localeCompare(b.date));
};
/** Grafica únicamente series aportadas por el usuario, sin datos sintéticos. */
export function EnvironmentalSeriesChart({title,unit,description}:Props){
 const [raw,setRaw]=useState("");
 const [threshold,setThreshold]=useState("");
 const [scenario,setScenario]=useState("0");
 const [error,setError]=useState("");
 const series=useMemo(()=>{try{return parse(raw)}catch{return []}},[raw]);
 const limit=threshold.trim()===""?null:Number(threshold);
 const delta=Number(scenario);
 const goodScenario=Number.isFinite(delta)&&Math.abs(delta)<100000;
 const values=series.flatMap(d=>[d.value,...(goodScenario?[d.value+delta]:[]),...(limit!==null&&Number.isFinite(limit)?[limit]:[])]);
 const low=values.length?Math.min(...values):0, high=values.length?Math.max(...values):1;
 const span=high-low||1;
 const w=550,h=230,p=35;
 const x=(i:number)=>p+(series.length<2?0:i/(series.length-1))*(w-p*2);
 const y=(v:number)=>h-p-(v-low)/span*(h-p*2);
 const line=(offset:number)=>series.map((d,i)=>`${i?"L":"M"}${x(i).toFixed(2)},${y(d.value+offset).toFixed(2)}`).join(" ");
 return <section style={{padding:12,background:"#172935",borderRadius:10,marginTop:12}}>
  <h3 style={{margin:"0 0 6px"}}>{title} · gráfico interactivo</h3>
  {description&&<p style={{fontSize:12}}>{description}</p>}
  <label htmlFor="dots-data">Ingresar observaciones verificadas (una por línea: fecha;valor)</label>
  <textarea id="dots-data" rows={4} value={raw} onChange={e=>{setRaw(e.target.value);setError("");}} placeholder={"2026-01-01;3.42\n2026-01-02;3.56"} style={{width:"100%",boxSizing:"border-box",background:"#20313d",color:"white",padding:8}}/>
  <div style={{display:"flex",gap:8,flexWrap:"wrap"}}>
   <label>Umbral ({unit}) <input value={threshold} onChange={e=>setThreshold(e.target.value)} inputMode="decimal" style={{width:90}}/></label>
   <label>Variación hipotética ({unit}) <input value={scenario} onChange={e=>setScenario(e.target.value)} inputMode="decimal" style={{width:90}}/></label>
  </div>
  <button type="button" onClick={()=>{try{parse(raw);setError("");}catch(e){setError((e as Error).message);}}}>Validar datos</button>
  {error&&<p role="alert">{error}</p>}
  {series.length>0&&goodScenario?<><svg viewBox={`0 0 ${w} ${h}`} role="img" aria-label={`Serie observada y escenario hipotético de ${title}`} style={{width:"100%",marginTop:8,background:"#10202b"}}>
   <line x1={p} y1={h-p} x2={w-p} y2={h-p} stroke="#9aaeb9"/>
   <line x1={p} y1={p} x2={p} y2={h-p} stroke="#9aaeb9"/>
   {limit!==null&&Number.isFinite(limit)&&<line x1={p} x2={w-p} y1={y(limit)} y2={y(limit)} stroke="#ffbc60" strokeDasharray="5 4"/>}
   <path d={line(0)} fill="none" stroke="#49d2e6" strokeWidth={3}/>
   {delta!==0&&<path d={line(delta)} fill="none" stroke="#ffb86b" strokeDasharray="7 4" strokeWidth={2}/>}
   <text x={p+4} y={p-9} fontSize={11} fill="white">{high.toFixed(2)} {unit}</text>
   <text x={p+4} y={h-8} fontSize={11} fill="white">{low.toFixed(2)} {unit}</text>
  </svg><p style={{fontSize:12}}>Azul: valores ingresados · Naranja: desplazamiento hipotético constante · Línea punteada horizontal: umbral. Registros: {series.length}. Desde {series[0].date} hasta {series[series.length-1].date}.</p></>:<p>No hay una serie cargada. No se fabrican mediciones.</p>}
  <p style={{fontSize:12,color:"#ffd38d"}}>El escenario es una prueba matemática de sensibilidad, no un pronóstico. No estima extensión de inundación, velocidades ni daños; eso requiere modelo hidrodinámico, topografía y calibración.</p>
 </section>;
}
