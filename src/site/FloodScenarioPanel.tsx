import {useState} from "react";
type River={id:string;name:string;lat:number;lon:number;note:string};
const RIVERS:River[]=[
{id:"parana",name:"Paraná · Corrientes",lat:-27.47,lon:-58.84,note:"Punto de referencia cartográfico; no equivale a una estación oficial"},
{id:"paraguay",name:"Paraguay · Formosa",lat:-26.18,lon:-58.17,note:"Punto de referencia cartográfico; no equivale a una estación oficial"},
{id:"uruguay",name:"Uruguay · Concordia",lat:-31.39,lon:-58.02,note:"Punto de referencia cartográfico; no equivale a una estación oficial"}
];
export function FloodScenarioPanel({onPoint,onLayer}:{onPoint:(lat:number,lon:number)=>void;onLayer:(id:string)=>void}){
 const [river,setRiver]=useState(RIVERS[0].id);
 const [base,setBase]=useState("4");
 const [rise,setRise]=useState(1);
 const [threshold,setThreshold]=useState("6");
 const [source,setSource]=useState("");
 const [date,setDate]=useState(new Date().toISOString().slice(0,10));
 const selected=RIVERS.find(r=>r.id===river)!;
 const b=Number(base),t=Number(threshold);
 const valid=base.trim()!==""&&threshold.trim()!==""&&Number.isFinite(b)&&Number.isFinite(t)&&b>=0&&t>=0;
 const hypothetical=b+rise;
 const above=valid&&hypothetical>=t;
 function printReport(){
  const safe=(v:string)=>v.replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]||c));
  const w=window.open("","_blank");
  if(!w){window.alert("Habilitá las ventanas emergentes para imprimir el informe.");return}
  w.document.write(`<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Informe de escenario DOTS</title><style>body{font:15px Arial;max-width:800px;margin:48px auto;line-height:1.6}h1{border-bottom:4px solid #b72230;padding-bottom:15px}small{color:#555}</style></head><body><h1>DOTS Campo · Informe de escenario fluvial</h1><p><b>Tramo de referencia:</b> ${safe(selected.name)}</p><p><b>Fecha de análisis:</b> ${safe(date)}</p><p><b>Fuente de la altura base:</b> ${safe(source||"No declarada — dato ingresado manualmente")}</p><p><b>Altura base ingresada:</b> ${b.toFixed(2)} m</p><p><b>Variación hipotética:</b> +${rise.toFixed(2)} m</p><p><b>Altura del escenario:</b> ${hypothetical.toFixed(2)} m</p><p><b>Umbral ingresado:</b> ${t.toFixed(2)} m</p><p><b>Resultado:</b> ${above?"Supera o iguala el umbral ingresado":"Por debajo del umbral ingresado"}</p><h2>Alcance y limitaciones</h2><p>Este cálculo es hipotético y utiliza valores manuales. No es un pronóstico, no calcula extensión inundable, velocidad del agua, superficie afectada ni daños. Los niveles sólo son comparables cuando corresponden a la misma estación y referencia vertical. No reemplaza información oficial de INA, organismos hidrológicos ni defensa civil.</p><small>Generado localmente desde DOTS Campo. Guardar como PDF desde la opción Imprimir del navegador.</small></body></html>`);
  w.document.close();w.focus();w.print();
 }
 return <section aria-label="Simulación de crecidas" style={{background:"#142834",color:"#edf5f8",borderRadius:12,padding:16,marginTop:14}}>
  <h2>Escenario interactivo de crecida</h2>
  <p style={{fontSize:13}}>Elegí un río y probá una variación hipotética de nivel. Los valores iniciales son ejemplos editables, no lecturas oficiales.</p>
  <label style={{display:"block",marginBottom:10}}>Río y tramo
   <select value={river} onChange={e=>{const id=e.target.value;setRiver(id);const r=RIVERS.find(x=>x.id===id)!;onPoint(r.lat,r.lon)}} style={{display:"block",width:"100%",padding:10,marginTop:5}}>
    {RIVERS.map(r=><option key={r.id} value={r.id}>{r.name}</option>)}
   </select>
  </label>
  <button type="button" onClick={()=>onPoint(selected.lat,selected.lon)}>Centrar mapa en el tramo</button>{" "}
  <button type="button" onClick={()=>onLayer("MODIS_Combined_Flood_3-Day")}>Ver capa de agua MODIS</button>
  <p style={{fontSize:12}}>{selected.note}</p>
  <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(145px,1fr))",gap:10}}>
   <label>Altura base (m)<input type="number" min="0" step="0.1" value={base} onChange={e=>setBase(e.target.value)} style={{display:"block",width:"95%",padding:8}}/></label>
   <label>Umbral de referencia (m)<input type="number" min="0" step="0.1" value={threshold} onChange={e=>setThreshold(e.target.value)} style={{display:"block",width:"95%",padding:8}}/></label>
   <label>Fecha del dato<input type="date" value={date} onChange={e=>setDate(e.target.value)} style={{display:"block",padding:8}}/></label>
  </div>
  <label style={{display:"block",marginTop:12}}>Fuente de la altura ingresada<input value={source} onChange={e=>setSource(e.target.value)} placeholder="Ej.: INA, estación y fecha" style={{display:"block",width:"100%",boxSizing:"border-box",padding:9}}/></label>
  <label style={{display:"block",marginTop:14}}>Incremento hipotético: <strong>+{rise.toFixed(1)} m</strong><input type="range" min="0" max="8" step="0.1" value={rise} onChange={e=>setRise(Number(e.target.value))} style={{display:"block",width:"100%"}}/></label>
  {valid?<div role="status" style={{padding:12,background:"#24404e",borderRadius:8}}><strong>Escenario: {hypothetical.toFixed(2)} m</strong><p style={{marginBottom:0}}>{above?"El escenario alcanza o supera el umbral que ingresaste.":"El escenario está por debajo del umbral ingresado."} Diferencia respecto del umbral: {(hypothetical-t).toFixed(2)} m.</p></div>:<p role="alert">Ingresá alturas y umbrales válidos.</p>}
  <p style={{fontSize:12,color:"#ffdb99"}}>La capa MODIS muestra detecciones satelitales de agua según disponibilidad histórica: no representa la inundación futura del escenario. Para calcular una mancha inundable se requiere topografía hidráulica, cotas de referencia y un modelo calibrado.</p>
  <button type="button" disabled={!valid} onClick={printReport} style={{padding:11,marginTop:5}}>Generar informe · Imprimir / Guardar PDF</button>
 </section>;
}
