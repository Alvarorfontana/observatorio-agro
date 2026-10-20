import {useState} from "react";
export function FloodScenarioPanel({onLayer,tramoStart,tramoEnd,riverName,basinName}:{onLayer:(id:string)=>void;tramoStart:[number,number]|null;tramoEnd:[number,number]|null;riverName:string;basinName:string}){

 const [base,setBase]=useState("4");
 const [rise,setRise]=useState(1);
 const [threshold,setThreshold]=useState("6");
 const [source,setSource]=useState("");
 const [date,setDate]=useState(new Date().toISOString().slice(0,10));
 const selected={name:riverName,note:"El tramo de referencia es el que marcaste en el mapa."};
 const b=Number(base),t=Number(threshold);
 const valid=base.trim()!==""&&threshold.trim()!==""&&Number.isFinite(b)&&Number.isFinite(t)&&b>=0&&t>=0;
 const hypothetical=b+rise;
 const above=valid&&hypothetical>=t;
 function printReport(){
  const esc=(v:string)=>v.replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]||c));
  const fmt=(n:number)=>n.toLocaleString("es-AR",{minimumFractionDigits:2,maximumFractionDigits:2});
  const pos=(p:[number,number]|null)=>p?p.map(n=>n.toFixed(5)).join(", "):"No delimitado";
  const delta=hypothetical-t;
  const distance=tramoStart&&tramoEnd?(()=>{
   const rad=Math.PI/180,dLat=(tramoEnd[0]-tramoStart[0])*rad,dLon=(tramoEnd[1]-tramoStart[1])*rad;
   const h=Math.sin(dLat/2)**2+Math.cos(tramoStart[0]*rad)*Math.cos(tramoEnd[0]*rad)*Math.sin(dLon/2)**2;
   return 12742*Math.asin(Math.min(1,Math.sqrt(h)));
  })():null;
  const row=(name:string,value:string)=>`<tr><th>${esc(name)}</th><td>${esc(value)}</td></tr>`;
  const rows=[
   row("Cuenca seleccionada",basinName),
   row("Río seleccionado",selected.name),
   row("Inicio marcado (latitud, longitud)",pos(tramoStart)),
   row("Fin marcado (latitud, longitud)",pos(tramoEnd)),
   row("Distancia geodésica entre puntos",distance===null?"No calculable sin ambos extremos":fmt(distance)+" km en línea recta; no equivale a longitud del cauce"),
   row("Fecha declarada del dato",date),
   row("Procedencia declarada",source.trim()||"Sin fuente declarada; valor ingresado manualmente"),
   row("Altura hidrométrica inicial",fmt(b)+" m (referencia vertical no documentada)"),
   row("Incremento supuesto", "+"+fmt(rise)+" m"),
   row("Altura del escenario",fmt(hypothetical)+" m"),
   row("Umbral definido por el usuario",fmt(t)+" m"),
   row("Diferencia escenario menos umbral",(delta>=0?"+":"")+fmt(delta)+" m")
  ].join("");
  const completeness=[source.trim()?"Fuente declarada por el usuario; no verificada":"Falta identificar organismo, estación, URL y publicación original",
    tramoStart&&tramoEnd?"Dos extremos cartográficos identificados; trazado hidráulico del cauce no delimitado":"Falta delimitar inicio y fin del tramo",
    "Falta confirmar datum vertical y escala de la estación para interpretar las alturas",
    "No hay series oficiales de nivel o caudal ni incertidumbre asociada",
    "No se ha ejecutado modelo hidráulico 1D/2D ni validación contra extensión observada",
    "No se dispone de inventario de exposición de población, viviendas, caminos o infraestructura"].map(x=>`<li>${esc(x)}</li>`).join("");
  const w=window.open("","_blank");
  if(!w){window.alert("Habilitá las ventanas emergentes para generar el informe.");return}
  const report=`<!doctype html><html lang="es"><head><meta charset="utf-8"><title>DOTS Campo | Informe técnico de escenario fluvial</title>
  <style>@page{size:A4;margin:17mm 16mm}body{font:11pt/1.5 Arial,Helvetica,sans-serif;color:#182a35;max-width:900px;margin:0 auto}header{border-bottom:4px solid #b82332;padding:12px 0 18px}header strong{font-size:14pt;color:#b82332;letter-spacing:.04em}h1{font-size:23pt;line-height:1.15;margin:10px 0}h2{font-size:14pt;border-bottom:1px solid #cbd5dd;padding-bottom:5px;margin-top:25px}p,li{orphans:3;widows:3}table{border-collapse:collapse;width:100%;font-size:10pt}td,th{padding:8px;border-bottom:1px solid #d8e1e6;text-align:left;vertical-align:top}th{width:43%;background:#f1f5f7}.lead{font-size:12pt}.note{border-left:4px solid #cc9230;padding:10px 14px;background:#fff7e8}.metric{font-size:18pt;font-weight:700}.meta{color:#5a6a75;font-size:9pt}.footer{margin-top:30px;border-top:1px solid #ddd;padding-top:10px;font-size:9pt}@media print{button{display:none}h2{break-after:avoid}table{break-inside:avoid}}</style></head><body>
  <header><strong>DOTS CAMPO | OBSERVATORIO AGROAMBIENTAL</strong><h1>Informe técnico de escenario de crecida fluvial</h1><div class="meta">Documento de exploración de escenario · Emitido ${esc(new Date().toLocaleString("es-AR"))} · Sin validación hidrodinámica</div></header>
  <h2>1. Objeto y alcance</h2><p class="lead">Evaluar aritméticamente un incremento hipotético de altura hidrométrica para ${esc(selected.name)}, comparándolo con un umbral definido por el usuario. El análisis se limita al escenario numérico y a los puntos cartográficos declarados; no estima extensión, profundidad ni tiempo de llegada de una inundación.</p>
  <h2>2. Localización y delimitación espacial</h2><p>Referencia territorial: cuenca ${esc(basinName)}, río ${esc(selected.name)}. Inicio del tramo: ${esc(pos(tramoStart))}; final del tramo: ${esc(pos(tramoEnd))}.</p>
  <p>${distance===null?"No se puede determinar la separación entre extremos porque el tramo no está completamente marcado.":`La distancia geodésica entre extremos es ${fmt(distance)} km. Es una línea recta entre coordenadas, no la longitud real del río ni un dominio hidráulico validado.`}</p>
  <h2>3. Datos de entrada y trazabilidad</h2><table>${rows}</table>
  <p class="note"><strong>Advertencia de referencia vertical.</strong> Una altura hidrométrica de escala local no equivale a la elevación absoluta del terreno en metros sobre el nivel del mar. No se ha comprobado que la altura inicial y el umbral correspondan a la misma estación y datum. Si no son comparables, la comparación numérica carece de interpretación hidrológica válida.</p>
  <h2>4. Procedimiento de cálculo reproducible</h2><p>Se aplicó exclusivamente la relación <strong>H escenario = H inicial + ΔH</strong>. Con los valores ingresados: ${fmt(b)} m + ${fmt(rise)} m = <strong>${fmt(hypothetical)} m</strong>. La diferencia frente al umbral es H escenario − H umbral = ${fmt(hypothetical)} − ${fmt(t)} = <strong>${(delta>=0?"+":"")+fmt(delta)} m</strong>. No se calculó propagación de caudal, almacenamiento, pendiente de lámina de agua ni flujo lateral.</p>
  <h2>5. Resultados del escenario</h2><div class="metric">${fmt(hypothetical)} m</div><p>Altura resultante bajo el supuesto ingresado. El escenario ${above?"alcanza o supera":"permanece por debajo de"} el umbral numérico definido por ${fmt(Math.abs(delta))} m ${above?"(diferencia no negativa)":"(déficit respecto del umbral)"}.</p>
  <p>Este resultado <strong>no permite concluir</strong> que se inundará una localidad, que una defensa será sobrepasada ni que un inmueble estará afectado. La clasificación sólo es válida como comparación matemática de entradas, sujeta a la compatibilidad de escalas.</p>
  <h2>6. Lectura de capas satelitales y topográficas</h2><p>NASA GIBS / MODIS puede aportar evidencia de agua observada en fechas y productos disponibles. Esa observación no constituye una proyección del escenario. El filtro topográfico Terrarium, si se utiliza en el mapa, selecciona celdas por elevación absoluta y puede incluir depresiones sin conexión hidráulica. <strong>Ni la detección satelital ni el filtro de cotas se incorporan al cálculo numérico de este informe.</strong> No se adjunta un área inundada estimada porque no se ha calculado.</p>
  <h2>7. Incertidumbres y control de calidad</h2><ul>${completeness}</ul><p>El valor de incremento es una hipótesis elegida por el usuario; no es un intervalo de confianza ni un pronóstico de organismos oficiales. No se cuantificaron errores de medición, resolución espacial, tiempos de respuesta, efectos de afluentes ni operación de embalses.</p>
  <h2>8. Información requerida para un estudio de inundación</h2><ol><li>Identificar estaciones oficiales, datum, series temporales y curvas de gasto pertinentes al tramo.</li><li>Delimitar el cauce y planicie de inundación mediante topografía/batimetría y estructuras hidráulicas.</li><li>Establecer condiciones de borde aguas arriba y abajo y ejecutar un modelo hidráulico apropiado.</li><li>Calibrar niveles y extensión con observaciones históricas, incluidos productos radar y ópticos cuando correspondan.</li><li>Calcular mapas de profundidad, velocidad, duración y exposición con incertidumbre documentada.</li></ol>
  <h2>9. Conclusión técnica</h2><p>Para ${esc(selected.name)}, la variación hipotética de +${fmt(rise)} m produce una altura aritmética de ${fmt(hypothetical)} m, situada ${fmt(Math.abs(delta))} m ${above?"por encima o al nivel":"por debajo"} del umbral proporcionado. Esta conclusión es <strong>condicional</strong> a la validez y comparabilidad de los datos manuales. No se emite evaluación de riesgo territorial ni alerta hidrológica.</p>
  <h2>10. Fuentes y referencias de consulta</h2><p><strong>Entrada utilizada:</strong> ${esc(source.trim()||"sin fuente documental consignada")}. <strong>Fuentes para contrastación futura, no consultadas automáticamente en este cálculo:</strong> Instituto Nacional del Agua (INA); NASA Global Imagery Browse Services (GIBS); AWS Terrain Tiles (Terrarium); servicios hidrometeorológicos competentes según jurisdicción.</p>
  <div class="footer">DOTS Campo · Informe generado desde el navegador con parámetros introducidos por el usuario. Uso exploratorio; no apto para decisiones de emergencia, ordenamiento territorial ni certificación de riesgo sin validación técnica independiente.</div></body></html>`;
  w.document.open();w.document.write(report);w.document.close();w.focus();w.print();
 }

 return <section aria-label="Simulación de crecidas" style={{background:"#142834",color:"#edf5f8",borderRadius:12,padding:16,marginTop:14}}>
  <h2>Escenario interactivo de crecida</h2>
  <p style={{fontSize:13}}>Usá el río y el tramo seleccionados en el mapa para probar una variación hipotética de nivel. Los valores iniciales son ejemplos editables, no lecturas oficiales.</p>
  <p><strong>Cuenca:</strong> {basinName} · <strong>Río:</strong> {riverName}</p>
  <button type="button" onClick={()=>onLayer("MODIS_Combined_Flood_3-Day")}>Ver capa de agua MODIS</button>
  <p style={{fontSize:12}}>{selected.note}</p>
  <p><strong>Tramo delimitado:</strong> {tramoStart&&tramoEnd?`Inicio ${tramoStart[0].toFixed(4)}, ${tramoStart[1].toFixed(4)} · Fin ${tramoEnd[0].toFixed(4)}, ${tramoEnd[1].toFixed(4)}`:"Usá «Definir tramo sobre el mapa» y marcá dos puntos."}</p>
  <p style={{fontSize:12}}>La línea entre los puntos es una referencia geométrica, no el recorrido real del cauce. Todavía no se calcula la superficie inundable.</p>
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
