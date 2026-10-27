const $=id=>document.getElementById(id);
const number=(v,digits=0)=>v==null?'Sin dato':new Intl.NumberFormat('es-AR',{maximumFractionDigits:digits}).format(v);
const make=(tag,text)=>{const e=document.createElement(tag);e.textContent=text;return e;};
const colors={area:'#246fa6',hazard:'#b76d27',intersection:'#bc3647'};
let map=null,layers={},draw=null,rectMode=false,vertices=[],draft=null,last=null,token=null,busy=false,generation=0;
let worldpopReady=null,localPopulationAvailable=false;
let floodMap=null,floodRequest=0;
const today=new Date();$('event-date').value=`${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`;
function status(text){$('status').textContent=text;}
function clearResult(){last=null;token=null;generation++;$('resume').hidden=true;
  for(const id of ['total','exposed','percent','surface'])$(id).textContent='—';
  for(const id of ['export-json','export-csv','print','pdf'])$(id).disabled=true;
  $('population-year').textContent='Esperando cálculo';$('event-label').textContent='Sin área analizada';
  $('details').replaceChildren(make('h3','Resultados con trazabilidad'),make('p','La consulta se actualiza al calcular. Las cifras anteriores se eliminan cuando cambian los parámetros.'));
  if(map&&layers.intersection){map.removeLayer(layers.intersection);delete layers.intersection;}
}
function geometry(id,optional){const raw=$(id).value.trim();if(!raw){if(optional)return null;throw new Error(id==='area'?'Falta dibujar la zona de estudio (azul).':'Falta dibujar el área de amenaza (naranja).');}let value;try{value=JSON.parse(raw);}catch{throw new Error('El GeoJSON pegado no es válido.');}return value.type==='Feature'?value.geometry:value;}
function setShape(id,value){
  if(!['Polygon','MultiPolygon'].includes(value?.type))throw new Error('Se requiere Polygon o MultiPolygon.');
  const changed=$(id).value!==JSON.stringify(value,null,2);
  $(id).value=JSON.stringify(value,null,2);
  if(map){if(layers[id])map.removeLayer(layers[id]);layers[id]=L.geoJSON(value,{interactive:false,style:{color:colors[id],weight:2,fillOpacity:.13}}).addTo(map);}
  if(id==='area'&&changed)barriosEnArea(value);
}
// ---- Barrios populares dentro de la zona dibujada (RENABAP) ----
let barriosArea=null,barriosAreaReq=0;
async function barriosEnArea(area){
  const box=$('area-barrios');if(!box)return;const req=++barriosAreaReq;box.hidden=false;
  box.replaceChildren(make('h3','Barrios populares en la zona dibujada'),make('p','Buscando los barrios del RENABAP dentro de la zona…'));
  if(map&&layers.barrios){map.removeLayer(layers.barrios);delete layers.barrios;}
  try{const d=await jsonFetch('/api/poblacion/barrios/en-area',{area});if(req!==barriosAreaReq)return;barriosArea={area,data:d};drawBarriosArea(d);}
  catch(e){if(req!==barriosAreaReq)return;barriosArea=null;box.replaceChildren(make('h3','Barrios populares en la zona dibujada'),make('p','No se pudieron consultar: '+e.message));}
}
function drawBarriosArea(d){
  const box=$('area-barrios');box.replaceChildren(make('h3','Barrios populares en la zona dibujada'));
  if(map){if(layers.barrios)map.removeLayer(layers.barrios);
    const fam=d.lista.map(b=>b.familias||0),mx=Math.max(1,...fam);
    layers.barrios=L.geoJSON({type:'FeatureCollection',features:d.lista.map(b=>({type:'Feature',geometry:b.geometry,properties:b}))},{
      style:f=>({color:'#8a3fb5',weight:1.5,fillColor:'#8a3fb5',fillOpacity:.18+.5*Math.sqrt((f.properties.familias||0)/mx)}),
      onEachFeature:(f,l)=>{const p=f.properties;l.bindPopup(`<b>${(p.nombre||'Sin nombre').replace(/[<>&]/g,'')}</b><br>${p.localidad?String(p.localidad).replace(/[<>&]/g,'')+'<br>':''}Familias: ${p.familias==null?'sin dato':number(p.familias)}<br>Superficie: ${number(p.ha,1)} ha${p.parte_en_area<.99?'<br>En la zona: '+number(100*p.parte_en_area)+' %':''}`);}}).addTo(map);}
  const grid=make('div','');grid.className='flood-grid';
  const card=(label,val,sub,cls)=>{const a=make('article','');if(cls)a.className=cls;a.append(make('span',label),make('strong',val),make('span',sub));return a;};
  grid.append(card('Barrios del RENABAP',number(d.barrios),d.completos+' enteros, el resto cortado por el borde'),
    card('Familias en la zona',number(d.familias),'estimación del registro','warn'),
    card('Superficie de barrios',number(d.superficie_ha,1)+' ha','dentro de la zona de '+number(d.area_km2,1)+' km²'));
  box.append(grid);
  if(!d.barrios){box.append(make('p','El RENABAP no registra barrios populares dentro de la zona dibujada.'));}
  else{const t=make('table','');t.className='var-tabla';const hr=make('tr','');for(const h of ['Barrio','Localidad','Familias','En la zona'])hr.append(make('th',h));t.append(hr);
    for(const b of d.lista.slice(0,15)){const tr=make('tr','');tr.append(make('td',b.nombre||'Sin nombre'),make('td',b.localidad||''),make('td',b.familias==null?'—':number(b.familias)),make('td',number(100*b.parte_en_area)+' %'));
      tr.style.cursor='pointer';tr.addEventListener('click',()=>{if(map&&b.lat!=null)map.setView([b.lat,b.lon],15);});t.append(tr);}
    const w=make('div','');w.style.cssText='overflow-x:auto';w.append(t);box.append(w);
    if(d.lista.length>15){const q=make('p',`Se muestran los 15 con más familias de ${number(d.barrios)}. Todos están dibujados en el mapa en violeta: tocalos para ver su nombre.`);q.className='hint';box.append(q);}}
  const n=make('p',d.nota+' Fuente: '+d.fuente+'.');n.className='hint';box.append(n);
  const row=make('div','');row.className='exports';row.style.padding='0';
  const b=make('button','Descargar informe de barrios de esta zona (PDF)');b.type='button';b.className='primary';
  b.addEventListener('click',async()=>{const t=b.textContent;b.disabled=true;b.textContent='Generando informe PDF…';
    try{const r=await fetch('/api/poblacion/barrios/informe-area',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({area:barriosArea.area,poblacion:last||null}),signal:AbortSignal.timeout(90000)});
      if(!r.ok){const j=await r.json().catch(()=>({}));throw new Error(j.error||'Error HTTP '+r.status);}
      const pdf=await r.blob();const u=URL.createObjectURL(pdf),a=make('a','');a.href=u;a.download='DOTS-barrios-populares-zona.pdf';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),5000);}
    catch(e){status('No se pudo generar el informe de barrios: '+e.message);}finally{b.disabled=false;b.textContent=t;}});
  row.append(b);box.append(row);
}
function fit(){if(!map)return;const available=Object.values(layers).filter(Boolean);if(available.length)map.fitBounds(L.featureGroup(available).getBounds(),{padding:[30,30],maxZoom:14});}
function initialiseMap(){
  if(!window.L){$('map-fallback').hidden=false;status('Mapa no disponible. Podés importar ambas geometrías en el formulario.');return;}
  map=L.map('map').setView([-27.47,-58.83],11);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap contributors'}).addTo(map).on('tileerror',()=>{$('map-fallback').hidden=false;});
  map.on('click',e=>{if(!draw)return;vertices.push([e.latlng.lng,e.latlng.lat]);
    if(rectMode&&vertices.length===2){const [[x1,y1],[x2,y2]]=vertices;if(x1===x2||y1===y2){vertices=[vertices[0]];return;}
      vertices=[[x1,y1],[x2,y1],[x2,y2],[x1,y2]];finishShape();return;}
    if(draft)map.removeLayer(draft);
    draft=(rectMode?L.circleMarker([e.latlng.lat,e.latlng.lng],{radius:5,color:colors[draw],interactive:false}):L.polyline(vertices.map(([x,y])=>[y,x]),{color:colors[draw],dashArray:'5 5',interactive:false})).addTo(map);
    status(rectMode?'Ahora marcá la esquina opuesta del rectángulo.':`${vertices.length} vértices. Doble clic o “Cerrar polígono” para terminar (mínimo tres).`);
  });
  map.on('dblclick',e=>{if(!draw||rectMode)return;L.DomEvent.stop(e);vertices.pop();if(vertices.length>=3)finishShape();});
}
if(document.readyState==='complete')initialiseMap();else window.addEventListener('load',initialiseMap,{once:true});
function cancelDraw(){draw=null;rectMode=false;vertices=[];if(map&&draft)map.removeLayer(draft);draft=null;if(map)map.doubleClickZoom.enable();$('map').classList.remove('drawing');}
function startDraw(id,rect){if(!map){status('Usá la importación GeoJSON: el mapa no cargó.');return;}cancelDraw();draw=id;rectMode=rect;map.doubleClickZoom.disable();$('map').classList.add('drawing');
  status(rect?`Rectángulo de ${id==='area'?'la zona':'la amenaza'}: marcá una esquina en el mapa.`:`Marcá los vértices de ${id==='area'?'la zona':'la amenaza'} en el mapa. Doble clic para terminar.`);}
for(const id of ['area','hazard']){$('draw-'+id).addEventListener('click',()=>startDraw(id,false));const r=$('rect-'+id);if(r)r.addEventListener('click',()=>startDraw(id,true));}
function finishShape(){const id=draw;setShape(id,{type:'Polygon',coordinates:[[...vertices,vertices[0]]]});cancelDraw();clearResult();
  status(id==='area'?(layers.hazard?'Zona guardada. Ya podés calcular.':'Zona guardada. Podés calcular ya la población de la zona, o dibujar un área de amenaza para saber cuántos quedan expuestos.'):(layers.area?'Amenaza guardada. Tocá “Calcular población expuesta”.':'Amenaza guardada. Falta dibujar la zona de estudio.'));}
$('cancel').addEventListener('click',()=>{cancelDraw();status('Dibujo cancelado.');});
$('finish').addEventListener('click',()=>{if(!draw||rectMode||vertices.length<3){status(rectMode?'En modo rectángulo se cierra solo con la segunda esquina.':'Marcá al menos tres vértices antes de cerrar.');return;}finishShape();});
$('apply').addEventListener('click',()=>{try{clearResult();setShape('area',geometry('area'));const h=geometry('hazard',true);if(h)setShape('hazard',h);fit();status('Geometrías importadas. El servidor validará su forma antes de calcular.');}catch(e){status(e.message);}});
for(const id of ['area','hazard','year','dataset','kind','category','event-date','event-source','enso'])$(id).addEventListener('input',()=>{clearResult();status('Parámetros modificados. Volvé a calcular para actualizar los resultados.');});

async function jsonFetch(path,payload){const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),50000);
  try{const r=await fetch(path,{method:payload?'POST':'GET',headers:payload?{'Content-Type':'application/json'}:{},body:payload?JSON.stringify(payload):undefined,signal:controller.signal});
    const contentType=r.headers.get('content-type')||'';
    if(!contentType.toLowerCase().includes('json'))throw new Error(`El servidor respondió ${contentType||'sin tipo de contenido'} en lugar de JSON${r.redirected?' (posible redirección a inicio de sesión)':''}. Revisá el acceso al API o la protección de Vercel.`);
    let data;try{data=await r.json();}catch{throw new Error(`La respuesta del servidor no es JSON válido (HTTP ${r.status}).`);}
    if(!r.ok)throw new Error(data.error||`La consulta no pudo completarse (HTTP ${r.status}).`);return data;
  }finally{clearTimeout(timer);}}
async function poll(startGeneration,note){
  for(let i=0;i<30;i++){
    if(generation!==startGeneration)return;
    const result=await jsonFetch('/api/poblacion/resultado',{token});
    if(generation!==startGeneration)return;
    if(result.status!=='pending'){show(result,note);token=null;return;}
    status(`WorldPop está procesando la zona. Consulta ${i+1}/30…`);
    await new Promise(resolve=>setTimeout(resolve,3000));
  }
  status('El cálculo sigue pendiente en WorldPop. Podés continuar la consulta sin iniciar otro trabajo.');$('resume').hidden=false;
}
function updatePopulationAvailability(){
  const localSelected=$('dataset').value!=='worldpop-api';
  const unavailable=worldpopReady===false&&!localSelected;
  $('calculate').disabled=busy||unavailable;
  const note=$('population-availability');
  if(unavailable)note.textContent='No se puede calcular con WorldPop: falta configurar la clave de firma en el servidor. Contactá al administrador; no se iniciaron consultas.';
  else if(worldpopReady===false&&localPopulationAvailable)note.textContent=localSelected?'Fuente local seleccionada; los cálculos usan solo el dataset indicado.':'WorldPop no está configurado. Elegí una fuente local para habilitar el cálculo.';
  else if(worldpopReady===true)note.textContent='Servicio de población disponible. El cálculo consulta WorldPop al enviar el análisis.';
}
function setBusy(value){busy=value;$('resume').disabled=value;updatePopulationAvailability();}
async function run(year,current,note){
  const hz=geometry('hazard',true);
  const payload={area:geometry('area'),...(hz?{hazard:hz}:{}),year,dataset:$('dataset').value,
    event:{kind:$('kind').value,category:$('category').value,source:$('event-source').value,date:$('event-date').value,enso:$('enso').value}};
  setShape('area',payload.area);if(hz)setShape('hazard',hz);fit();status(note||(hz?'Consultando población en WorldPop…':'Sin área de amenaza: se calcula sólo la población de la zona…'));
  const data=await jsonFetch('/api/poblacion/exposicion',payload);if(generation!==current)return;
  if(data.status==='pending'){token=data.token;await poll(current,note);}else show(data,note);
}
$('analysis').addEventListener('submit',async e=>{
  e.preventDefault();if(busy)return;clearResult();setBusy(true);const current=generation;const year=Number($('year').value);
  try{await run(year,current);}
  catch(error){
    if(generation!==current)return;
    status(error.name==='AbortError'?'El servidor excedió el tiempo de respuesta.':'No se pudo completar: '+error.message);if(token)$('resume').hidden=false;}
  finally{setBusy(false);}
});
$('resume').addEventListener('click',async()=>{if(!token||busy)return;setBusy(true);try{await poll(generation);}catch(e){status(e.message);}finally{setBusy(false);}});

function show(data,note){
  last=data;if(note)data.notes=[note,...(data.notes||[])];$('resume').hidden=true;
  $('total').textContent=number(data.population_total);$('exposed').textContent=data.hazard_given===false?'Sin amenaza':number(data.population_exposed);
  $('percent').textContent=data.exposed_percent==null?'Sin dato':number(data.exposed_percent,1)+'%';
  $('surface').textContent=number(data.hazard_in_area_km2,2)+' km²';
  $('population-year').textContent=`${data.source.provider} · ${data.year} · ${data.population_group}`;
  $('event-label').textContent=`${data.event.kind} · ${data.event.date}`;
  if(map&&data.intersection){layers.intersection=L.geoJSON(data.intersection,{interactive:false,style:{color:colors.intersection,weight:3,fillOpacity:.3}}).addTo(map);}
  const rows=[['Fuente de población',data.source.provider],['Grupo',data.population_group],['Año de población',String(data.year)],
    ['Densidad',number(data.density_per_km2,1)+' personas/km²'],['Tipo de amenaza',data.event.category],
    ['Fuente de amenaza',data.event.source],['Contexto ENOS',data.event.enso],
    ['Cobertura ráster',data.coverage_percent==null?'No informada por API de agregación':number(data.coverage_percent,1)+'%'],
    ['Método',data.method],['Calculado',data.calculated_at]];
  $('details').replaceChildren(make('h3',data.status==='partial_coverage'?'Resultado con cobertura parcial':data.status==='no_data'?'Sin cobertura poblacional':'Resultado del análisis'));
  const dl=make('dl','');for(const [key,val]of rows)dl.append(make('dt',key),make('dd',val));$('details').append(dl,make('p',data.interpretation));
  for(const note of data.notes||[])$('details').append(make('p',note));
  status(note?note+' Consulta completada.':data.status==='complete'?'Consulta completada. Podés descargar el informe en PDF.':data.status==='no_data'?'No hay datos válidos para esta zona; no equivale a población cero.':'La cobertura es parcial; las cifras corresponden al sector con datos.');
  for(const id of ['export-json','export-csv','print','pdf'])$(id).disabled=false;
  document.dispatchEvent(new CustomEvent('dots:population-result',{detail:data}));
}
function save(name,text,type){const url=URL.createObjectURL(new Blob([text],{type}));const a=make('a','');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}
$('export-json').addEventListener('click',()=>{if(last)save('DOTS-poblacion-exposicion.json',JSON.stringify(last,null,2),'application/json');});
function csvValue(value){let text=value==null?'':String(value);if(/^[=+@\-\t\r]/.test(text))text="'"+text;return '"'+text.replaceAll('"','""')+'"';}
$('export-csv').addEventListener('click',()=>{if(!last)return;const d=last;const rows=[['variable','valor'],['fuente',d.source.provider],['grupo',d.population_group],['anio_poblacion',d.year],['poblacion_zona',d.population_total],['poblacion_expuesta',d.population_exposed],['porcentaje',d.exposed_percent],['superficie_amenaza_km2',d.hazard_in_area_km2],['cobertura_porcentaje',d.coverage_percent],['fuente_amenaza',d.event.source],['fecha_amenaza',d.event.date],['contexto_enso',d.event.enso],['metodo',d.method],['interpretacion',d.interpretation]];save('DOTS-poblacion-exposicion.csv','\ufeff'+rows.map(row=>row.map(csvValue).join(',')).join('\r\n'),'text/csv;charset=utf-8');});
function drawReport(){
  const section=$('print-report');section.replaceChildren(make('p','DOTS / POBLACIÓN Y RIESGO CLIMÁTICO'),make('h1','Informe de exposición poblacional'));
  section.append(make('p',last.interpretation));
  const table=make('table','');const pairs=[['Población estimada en zona',number(last.population_total)],['Población estimada expuesta',number(last.population_exposed)],['Porcentaje',last.exposed_percent==null?'Sin dato':number(last.exposed_percent,1)+'%'],['Superficie de intersección',number(last.hazard_in_area_km2,2)+' km²'],['Fuente / año / grupo',`${last.source.provider} / ${last.year} / ${last.population_group}`],['Amenaza / fecha',`${last.event.kind} / ${last.event.date}`],['Fuente y categoría de amenaza',`${last.event.source} / ${last.event.category}`],['Cobertura',last.coverage_percent==null?'No informada por API':number(last.coverage_percent,1)+'%'],['Estado',last.status],['Método',last.method],['Fecha de cálculo',last.calculated_at]];
  for(const [key,val]of pairs){const tr=make('tr','');tr.append(make('th',key),make('td',val));table.append(tr);}section.append(table);
  const geometries={area:last.area,intersection:last.intersection};
  const ns='http://www.w3.org/2000/svg';const svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 760 330');svg.setAttribute('role','img');svg.setAttribute('aria-label','Esquema de zona e intersección de amenaza');
  const rings=g=>g.type==='Polygon'?g.coordinates:g.coordinates.flat();
  const coords=rings(last.area).flat(),xs=coords.map(p=>p[0]),ys=coords.map(p=>p[1]);
  const x0=Math.min(...xs),x1=Math.max(...xs),y0=Math.min(...ys),y1=Math.max(...ys),scale=Math.min(700/(x1-x0),270/(y1-y0));
  for(const [key,g]of Object.entries(geometries)){if(!g)continue;const path=document.createElementNS(ns,'path');path.setAttribute('d',rings(g).map(r=>r.map(([x,y],i)=>`${i?'L':'M'} ${30+(x-x0)*scale} ${300-(y-y0)*scale}`).join(' ')+' Z').join(' '));path.setAttribute('fill',colors[key]);path.setAttribute('fill-opacity','.22');path.setAttribute('stroke',colors[key]);path.setAttribute('stroke-width','2');path.setAttribute('fill-rule','evenodd');svg.append(path);}section.append(svg,make('p','Esquema de geometrías: azul = zona de estudio; rojo = intersección con amenaza. Coordenadas geográficas, sin mapa base. Norte hacia arriba.'));
  for(const note of last.notes||[])section.append(make('p',note));
  section.append(make('p','Atribución de población: '+(last.source.attribution||last.source.provider)+'. Contexto ENOS: '+last.event.enso+'.'));
}
$('print').addEventListener('click',()=>{if(last){drawReport();window.print();}});
window.dotsPopulation={setStudyArea(value){clearResult();setShape('area',value.type==='Feature'?value.geometry:value);fit();},
  setHazard(value,event={}){clearResult();setShape('hazard',value.type==='Feature'?value.geometry:value);
    for(const [key,id]of Object.entries({kind:'kind',category:'category',source:'event-source',date:'event-date',enso:'enso'}))if(event[key])$(id).value=event[key];fit();}};
document.addEventListener('dots:population-area',e=>window.dotsPopulation.setStudyArea(e.detail));
document.addEventListener('dots:population-hazard',e=>window.dotsPopulation.setHazard(e.detail.geometry,e.detail.event));
async function loadPopulationAvailability(){
  try{
    const state=await jsonFetch('/api/poblacion/estado');
    worldpopReady=state.worldpop==='ready';
  }catch(error){
    worldpopReady=null;
    $('population-availability').textContent='No se pudo verificar la disponibilidad de población: '+error.message+'. El botón permitirá intentar la consulta y mostrará el error del servidor si persiste.';
  }
  try{
    const data=await jsonFetch('/api/poblacion/datasets');
    for(const d of data.datasets.filter(x=>x.id!=='worldpop-api')){
      const o=make('option',`${d.provider} · ${d.group} · ${d.year}`);
      o.value=d.id;
      $('dataset').append(o);
      localPopulationAvailable=true;
    }
  }catch(error){
    $('population-availability').textContent='No se pudo cargar el catálogo de fuentes: '+error.message;
  }
  updatePopulationAvailability();
}
$('dataset').addEventListener('change',updatePopulationAvailability);
void loadPopulationAvailability();

$('pdf').addEventListener('click',async()=>{if(!last)return;const b=$('pdf');b.disabled=true;const t=b.textContent;b.textContent='Generando PDF…';
  try{const r=await fetch('/api/poblacion/informe',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(last)});
    if(!r.ok){const j=await r.json().catch(()=>({}));throw new Error(j.error||'No se pudo generar el PDF.');}
    const pdf=await r.blob();if(!pdf.size||!pdf.type.toLowerCase().includes('pdf'))throw new Error('El servidor no devolvió un archivo PDF válido.');const url=URL.createObjectURL(pdf);const a=make('a','');a.href=url;a.download=`DOTS-poblacion-expuesta-${(last.event?.date||'')}.pdf`;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),5000);}
  catch(e){status(e.message);}finally{b.textContent=t;b.disabled=false;}});

// Personas cerca del río en las localidades de las alertas de crecidas
jsonFetch('/api/poblacion/localidades').then(d=>{for(const p of d.places){const o=make('option',`${p.place} · río ${p.river}`);o.value=p.id;$('flood-place').append(o);}
  const q=new URLSearchParams(location.search).get('localidad');if(q){$('flood-place').value=q;$('flood-place').dispatchEvent(new Event('change'));document.getElementById('crecidas').scrollIntoView();}}).catch(()=>{});
$('flood-place').addEventListener('change',async()=>{const id=$('flood-place').value;const box=$('flood-result');if(floodMap){floodMap.remove();floodMap=null;}box.replaceChildren();const requestId=++floodRequest;if(!id)return;
  $('flood-status').textContent='Calculando con Earth Engine (puede tardar hasta 30 segundos)…';
  try{const j=await jsonFetch('/api/poblacion/crecida?id='+encodeURIComponent(id));const d=j.data;if(requestId!==floodRequest)return;if(!d)throw new Error(j.error||'Sin datos');
    $('flood-status').textContent=`${d.place} · río ${d.river} · ${number(d.total)} personas en ${d.radius_km} km a la redonda (WorldPop 2020).`;
    const grid=make('div','');grid.className='flood-grid';
    for(const sc of d.scenarios||[]){const a=make('article','');a.className=sc.key==='evac'?'risk':'warn';
      a.append(make('span',`${sc.label} (${number(sc.level_m,2)} m · sube ${number(sc.rise_m,2)} m sobre aguas bajas)`),make('strong',number(sc.people)),
        make('span',`personas hasta ${sc.band_m} m sobre el río · ${number(sc.under5)} menores de 5 · ${number(sc.over65)} mayores de 65`));grid.append(a);}
    const t=make('table','');const hr=make('tr','');for(const h of ['Hasta … m sobre el río','Personas','Menores de 5','Mayores de 65','% de la zona'])hr.append(make('th',h));t.append(hr);
    for(const b of d.bands){const tr=make('tr','');tr.append(make('td',`${b.up_to_m} m`),make('td',number(b.people)),make('td',number(b.under5)),make('td',number(b.over65)),make('td',d.total?number(100*b.people/d.total,1)+' %':'Sin dato'));t.append(tr);}
    box.append(grid,t);
    // Ubicación geográfica real de la estación y radio de cálculo, no mancha de inundación.
    if(d.lat!=null&&d.lon!=null&&Number.isFinite(Number(d.lat))&&Number.isFinite(Number(d.lon))&&window.L){
      const mapTitle=make('h3','Área geográfica analizada · '+d.place);
      const mapNote=make('p','El círculo indica el radio de '+d.radius_km+' km utilizado para sumar población. NO representa superficie inundada.');
      mapNote.className='hint';
      const mapEl=make('div','');mapEl.style.cssText='height:360px;width:100%;border-radius:12px;overflow:hidden;margin:12px 0 18px';
      box.append(mapTitle,mapNote,mapEl);
      const m=L.map(mapEl,{scrollWheelZoom:false}).setView([Number(d.lat),Number(d.lon)],10);
      floodMap=m;
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:18,attribution:'© OpenStreetMap contributors'}).addTo(m);
      const circle=L.circle([Number(d.lat),Number(d.lon)],{radius:Number(d.radius_km||15)*1000,color:'#0f9fa6',weight:2,fillOpacity:.10}).addTo(m);
      const marker=L.marker([Number(d.lat),Number(d.lon)]).addTo(m);
      const summary=(d.scenarios||[]).map(sc=>sc.label+': '+number(sc.people)+' personas (≤ '+sc.band_m+' m HAND)').join(' · ');
      marker.bindPopup('<b>'+String(d.place).replace(/[&<>"']/g,'')+'</b><br>Río '+String(d.river).replace(/[&<>"']/g,'')+'<br>'+summary.replace(/[&<>"']/g,'')).openPopup();
      const mapActions=make('div','');mapActions.className='exports';
      const focus=make('button','Centrar mapa en '+d.place);focus.type='button';focus.className='secondary';
      focus.addEventListener('click',()=>{m.fitBounds(circle.getBounds(),{padding:[20,20]});marker.openPopup();});
      const open=make('a','Abrir mapa ampliado ↗');open.href='https://www.openstreetmap.org/?mlat='+encodeURIComponent(d.lat)+'&mlon='+encodeURIComponent(d.lon)+'#map=11/'+encodeURIComponent(d.lat)+'/'+encodeURIComponent(d.lon);open.target='_blank';open.rel='noopener noreferrer';
      mapActions.append(focus,open);box.append(mapActions);
      m.fitBounds(circle.getBounds(),{padding:[20,20]});
      setTimeout(()=>m.invalidateSize(),100);
    }
    // Barras horizontales: las franjas HAND son acumulativas, no sectores excluyentes.
    const barsTitle=make('h3','Población potencialmente expuesta por franja de altura');
    const bars=make('div','');bars.style.cssText='display:grid;gap:10px;margin:12px 0 20px';
    const maximum=Math.max(1,...(d.bands||[]).map(b=>Number(b.people)||0));
    for(const b of d.bands||[]){
      const line=make('div','');line.style.cssText='display:grid;grid-template-columns:65px 1fr 105px;align-items:center;gap:10px';
      const track=make('div','');track.style.cssText='height:22px;background:#e8f1f2;border-radius:5px;overflow:hidden';
      const bar=make('div','');bar.style.cssText='height:100%;background:#0f9fa6;width:'+Math.max(0,100*(Number(b.people)||0)/maximum)+'%';
      track.append(bar);line.append(make('span','≤ '+b.up_to_m+' m'),track,make('strong',number(b.people)));bars.append(line);
    }
    const note=make('p','Franja acumulada: el valor de 5 m ya incluye a las personas de 1, 2 y 3 m. No sumar las barras.');
    note.className='hint';box.append(barsTitle,bars,note);

    const exportRow=make('div','');exportRow.className='exports';
    const download=make('button','Descargar informe PDF · '+d.place);download.type='button';download.className='primary';
    const exportJson=make('button','Descargar datos JSON');exportJson.type='button';exportJson.className='secondary';
    exportJson.addEventListener('click',()=>save('DOTS-zona-baja-'+id+'.json',JSON.stringify({data:d,source:j.source||'WorldPop / MERIT Hydro',status:j.status},null,2),'application/json'));
    download.addEventListener('click',async()=>{
      download.disabled=true;download.textContent='Generando informe PDF…';
      try{
        const response=await fetch('/api/poblacion/crecida/informe',{
          method:'POST',headers:{'Content-Type':'application/json'},
          body:JSON.stringify(d),
          signal:AbortSignal.timeout(90000)
        });
        if(!response.ok){const msg=await response.json().catch(()=>({}));throw new Error(msg.error||'Error HTTP '+response.status)}
        const pdf=await response.blob();
        if(!pdf.size||!pdf.type.includes('pdf'))throw new Error('El servidor no devolvió un PDF válido');
        const url=URL.createObjectURL(pdf),link=make('a','');
        link.href=url;link.download='DOTS-poblacion-zona-baja-'+id+'.pdf';document.body.append(link);link.click();link.remove();
        setTimeout(()=>URL.revokeObjectURL(url),5000);
        $('flood-status').textContent='Informe PDF generado para '+d.place+'.';
      }catch(error){$('flood-status').textContent='No se pudo generar el PDF: '+error.message+'. Podés descargar los datos JSON.'}
      finally{download.disabled=false;download.textContent='Descargar informe PDF · '+d.place}
    });
    exportRow.append(download,exportJson);box.append(exportRow);
    renderBarrios(id,box);
  }catch(e){if(requestId===floodRequest)$('flood-status').textContent='No se pudo calcular: '+e.message;}});

// Dengue y olas de calor en 80 localidades
let health=null;const DCLS={'bajo':'h-low','moderado':'h-mod','alto':'h-high','muy alto':'h-vhigh','sin dato':''};
function drawHealth(){if(!health)return;const box=$('health-table');box.replaceChildren();const c=$('health-country').value,sort=$('health-sort').value;
  let rows=health.places.filter(p=>c==='Todos'||p.country===c);
  rows=rows.slice().sort((a,b)=>sort==='heat'?((b.heatwaves.length-a.heatwaves.length)||((b.tmax_next??-99)-(a.tmax_next??-99))):((b.dengue_index??-1)-(a.dengue_index??-1)));
  const t=make('table','');const hr=make('tr','');for(const h of ['Localidad','Dengue hoy','Próximos 16 días','Lluvia 30 días','Máxima próxima','Calor'])hr.append(make('th',h));t.append(hr);
  for(const p of rows){const tr=make('tr','');const d=make('td','');const sp=make('span',p.dengue_class);sp.className='hlv '+(DCLS[p.dengue_class]||'');d.append(sp,make('small',' '+(p.dengue_index==null?'':number(p.dengue_index,2))));
    const nx=make('td','');const sp2=make('span',p.dengue_next_class);sp2.className='hlv '+(DCLS[p.dengue_next_class]||'');nx.append(sp2);
    const heat=make('td',p.heatwaves.length?`Ola de calor ${p.heatwaves[0].from.slice(8,10)}/${p.heatwaves[0].from.slice(5,7)} al ${p.heatwaves[0].to.slice(8,10)}/${p.heatwaves[0].to.slice(5,7)}`:p.hot_days?`${p.hot_days} día(s) muy caluroso(s)`:'Sin ola de calor');
    if(p.heatwaves.length)heat.className='hot';
    const name=make('td','');name.append(make('b',p.name),make('small',' '+p.country));
    tr.append(name,d,nx,make('td',p.rain_30d_mm==null?'Sin dato':number(p.rain_30d_mm)+' mm'),make('td',p.tmax_next==null?'Sin dato':number(p.tmax_next,1)+' °C'),heat);t.append(tr);}
  box.append(t);}
jsonFetch('/api/fuentes/salud-sudamerica').then(j=>{health=j.data;const cs=[...new Set(health.places.map(p=>p.country))];for(const c of cs){const o=make('option',c);$('health-country').append(o);}
  const k=health.dengue_counts||{};$('health-status').textContent=`Dengue: ${k['muy alto']||0} localidades con riesgo muy alto, ${k['alto']||0} alto, ${k['moderado']||0} moderado. Olas de calor en los próximos 16 días: ${health.heatwave_places.length?health.heatwave_places.join(', '):'ninguna'}.`+(health.p90_available?'':' Umbrales de calor provisorios (35 °C y 22 °C) hasta completar los de cada localidad.');drawHealth();})
  .catch(e=>{$('health-status').textContent='No se pudo consultar: '+e.message;});
$('health-country').addEventListener('change',drawHealth);$('health-sort').addEventListener('change',drawHealth);

// Barrios populares por radar (modelo entrenado con RENABAP; se recalcula en GitHub Actions)
let barriosData=null;
// Informes PDF de barrios populares (por localidad y regional)
function barriosPdfButton(label,url,fname){const wrap=make('div','');wrap.className='exports';wrap.style.cssText='margin-top:14px';
  const b=make('button',label);b.type='button';b.className='primary';const msg=make('p','');msg.className='hint';
  b.addEventListener('click',async()=>{const t=b.textContent;b.disabled=true;b.textContent='Generando informe PDF… (puede tardar hasta un minuto)';msg.textContent='';
    try{const r=await fetch(url,{signal:AbortSignal.timeout(90000)});
      if(!r.ok){const j=await r.json().catch(()=>({}));throw new Error(j.error||'Error HTTP '+r.status);}
      const pdf=await r.blob();if(!pdf.size||!pdf.type.includes('pdf'))throw new Error('El servidor no devolvió un PDF válido');
      const u=URL.createObjectURL(pdf),a=make('a','');a.href=u;a.download=fname;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),5000);
      msg.textContent='Informe descargado.';}
    catch(e){msg.textContent='No se pudo generar el informe: '+e.message;}
    finally{b.disabled=false;b.textContent=t;}});
  wrap.append(b,msg);return wrap;}
function barriosLocalPdf(id,place){return barriosPdfButton('Descargar informe de barrios populares · '+place,'/api/poblacion/barrios/informe?id='+encodeURIComponent(id),'DOTS-barrios-populares-'+id+'.pdf');}
const barriosLoad=jsonFetch('/api/poblacion/barrios').then(j=>{barriosData=j;drawBarriosModel(j);return j;}).catch(e=>{$('barrios-model').replaceChildren(make('p','No se pudo consultar el modelo: '+e.message));return null;});
// Las 30 variables de entrada del modelo y lo que calcula, con su peso
function drawVariables(v,box){if(!v||!(v.entradas||[]).length)return;
  const d=make('details','');d.className='variables';d.open=true;
  d.append(make('summary','Las '+v.entradas.length+' variables que analiza el modelo y lo que calcula'));
  const intro=make('p','Para cada píxel de 10 m el modelo mira estas variables y decide si tiene la firma de un barrio popular. La barra muestra cuánto pesa cada una en la decisión.');intro.className='hint';d.append(intro);
  const maxw=Math.max(...v.entradas.map(x=>x.peso||0),0.001);
  let grupo='';const t=make('table','');t.className='var-tabla';
  const hr=make('tr','');for(const h of ['Variable','Qué mide','Peso'])hr.append(make('th',h));t.append(hr);
  for(const x of v.entradas){
    if(x.grupo!==grupo){grupo=x.grupo;const g=make('tr','');const td=make('td',grupo);td.colSpan=3;td.className='var-grupo';g.append(td);t.append(g);}
    const tr=make('tr','');const n=make('td','');n.append(make('strong',x.nombre),make('br'),make('code',x.codigo));
    const w=make('td','');w.className='var-peso';
    if(x.peso!=null){const bar=make('span','');bar.className='var-bar';bar.style.width=Math.max(4,100*x.peso/maxw)+'%';w.append(bar,make('small',number(100*x.peso,1)+' %'));}else w.append(make('small','—'));
    tr.append(n,make('td',x.mide),w);t.append(tr);}
  const wrap=make('div','');wrap.style.cssText='overflow-x:auto';wrap.append(t);d.append(wrap);
  if(v.entradas.some(x=>x.peso==null)){const q=make('p','Por ahora se conoce el peso de las 10 variables principales; el resto aparece en la próxima corrida del modelo.');q.className='hint';d.append(q);}
  d.append(make('h3','Lo que calcula en cada localidad'));
  const t2=make('table','');t2.className='var-tabla';const h2=make('tr','');for(const h of ['Resultado','Unidad','Qué es'])h2.append(make('th',h));t2.append(h2);
  for(const x of v.salidas||[]){const tr=make('tr','');tr.append(make('td',x.nombre),make('td',x.unidad),make('td',x.mide));t2.append(tr);}
  const w2=make('div','');w2.style.cssText='overflow-x:auto';w2.append(t2);d.append(w2);
  const no=make('p','No mide: agua, cloacas o luz; materiales de cada casa; cuántas personas hay en cada vivienda; ni si un barrio está inundado hoy.');no.className='hint';d.append(no);
  box.append(d);}
function pct(v){return v==null?'Sin dato':number(100*v,0)+' %';}
function drawBarriosModel(j){const box=$('barrios-model');box.replaceChildren();
  box.append(barriosPdfButton('Descargar informe regional · todas las localidades (PDF)','/api/poblacion/barrios/informe-regional','DOTS-barrios-populares-Cuenca-del-Plata.pdf'));
  if(!j||!j.data){const p=make('p',(j&&j.error)||'Todavía no hay resultados del modelo.');p.className='hint';box.append(p);drawVariables(j&&j.variables,box);drawRenabapTable(j&&j.renabap,box);return;}
  const m=j.data.model||{},avg=m.promedio||{},o=avg.optico||{},r=avg.optico_radar||{};
  const grid=make('div','');grid.className='flood-grid';
  const card=(label,val,sub,cls)=>{const a=make('article','');if(cls)a.className=cls;a.append(make('span',label),make('strong',val),make('span',sub));return a;};
  grid.append(card('Solo imagen en color',o.f1_barrio==null?'Sin dato':number(o.f1_barrio,2),'acierto para encontrar barrios populares (F1, 0 a 1)'),
    card('Color + radar',r.f1_barrio==null?'Sin dato':number(r.f1_barrio,2),'acierto para encontrar barrios populares (F1, 0 a 1)','warn'),
    card('Exactitud general',r.exactitud==null?'Sin dato':pct(r.exactitud),'color + radar, en ciudades que el modelo no vio'));
  const e=avg.optico_radar_edificios||{};
  if(e.f1_barrio!=null)grid.append(card('Color + radar + edificios',number(e.f1_barrio,2),'sumando cantidad y altura de construcciones (Google Open Buildings)'));
  const x=avg.optico_radar_externas||{};
  if(x.f1_barrio!=null)grid.append(card('Color + radar + otras ciudades',number(x.f1_barrio,2),'sumando etiquetas de '+((m.ciudades_externas||[]).join(', ')||'otras ciudades')));
  box.append(grid);
  const lines=[];
  if(o.f1_barrio!=null&&r.f1_barrio!=null)lines.push(r.f1_barrio>o.f1_barrio?`Sumar el radar mejora la detección de ${number(o.f1_barrio,2)} a ${number(r.f1_barrio,2)}: separa mejor un barrio popular de un barrio denso común.`:`En esta corrida el radar no mejoró la detección (${number(o.f1_barrio,2)} contra ${number(r.f1_barrio,2)}).`);
  if(m.modelo_final)lines.push(m.modelo_final==='optico_radar_edificios'?'El mapa usa la versión con edificios, que anduvo mejor en ciudades no vistas.':m.modelo_final==='optico_radar_externas'?'El mapa usa la versión que suma etiquetas de '+((m.ciudades_externas||[]).join(', ')||'otras ciudades')+', que anduvo mejor en ciudades argentinas no vistas.':'El mapa usa la versión color + radar.');
  lines.push(`Entrenado con los barrios RENABAP de ${(m.ciudades_entrenamiento||[]).length} localidades argentinas y evaluado dejando afuera una ciudad por vez. Imágenes de ${j.data.year}; actualizado el ${j.data.updated}.`);
  if(m.nota)lines.push(m.nota);
  for(const l of lines){const p=make('p',l);p.className='hint';box.append(p);}
  const rows=m.evaluacion_por_ciudad||[];
  if(rows.length){const d=make('details','');d.append(make('summary','Ver resultado por ciudad'));const t=make('table','');const hr=make('tr','');for(const h of ['Ciudad dejada afuera','Solo color (F1)','Color + radar (F1)','Exactitud color + radar','Con edificios (F1)'])hr.append(make('th',h));t.append(hr);
    for(const x of rows){const tr=make('tr','');tr.append(make('td',x.city),make('td',x.optico?number(x.optico.f1_barrio,2):'—'),make('td',x.optico_radar?number(x.optico_radar.f1_barrio,2):'—'),make('td',x.optico_radar?pct(x.optico_radar.exactitud):'—'),make('td',x.optico_radar_edificios?number(x.optico_radar_edificios.f1_barrio,2):'—'));t.append(tr);}
    d.append(t);box.append(d);}
  drawVariables(j.variables,box);
  const src=make('p','Fuentes: '+(j.data.sources||[]).join(' · '));src.className='hint';box.append(src);
  if(!(j.data.places||[]).length){const p=make('p','El mapa por localidad todavía no está calculado. Mientras tanto, estos son los barrios que registra el RENABAP:');p.className='hint';box.append(p);drawRenabapTable(j.renabap,box);}}
function drawRenabapTable(r,box){if(!r||!(r.places||[]).length)return;
  const rows=r.places.filter(p=>p.barrios>0).sort((a,b)=>(b.familias||0)-(a.familias||0));
  const d=make('details','');d.open=true;d.append(make('summary',`Barrios populares registrados por localidad (RENABAP, ${r.radius_km} km a la redonda)`));
  const t=make('table','');const hr=make('tr','');for(const h of ['Localidad','Barrios','Familias','Superficie'])hr.append(make('th',h));t.append(hr);
  for(const p of rows){const tr=make('tr','');tr.append(make('td',p.place),make('td',number(p.barrios)),make('td',number(p.familias)),make('td',number(p.superficie_ha)+' ha'));t.append(tr);}
  d.append(t);const n=make('p',(r.nota||'')+' Fuente: '+(r.source||'RENABAP')+'.');n.className='hint';d.append(n);box.append(d);}
function renderRenabap(id,box,j){const r=j&&j.renabap&&(j.renabap.places||[]).find(x=>x.id===id);if(!r)return;
  const sec=make('div','');sec.style.cssText='margin-top:22px';sec.append(make('h3','Barrios populares registrados · '+r.place));
  if(!r.barrios){const q=make('p','El RENABAP no registra barrios populares a '+j.renabap.radius_km+' km de esta localidad'+(/Asunción|Concepción|Pilar|Humaitá|Bahía Negra|Fray Bentos/.test(r.place)?' (está fuera de Argentina: el registro no la cubre).':'.'));q.className='hint';sec.append(q);box.append(sec);return;}
  const grid=make('div','');grid.className='flood-grid';
  const card=(label,val,sub,cls)=>{const a=make('article','');if(cls)a.className=cls;a.append(make('span',label),make('strong',val),make('span',sub));return a;};
  grid.append(card('Barrios registrados',number(r.barrios),j.renabap.radius_km+' km a la redonda'),card('Familias',number(r.familias),'según estima el registro','warn'),card('Superficie',number(r.superficie_ha)+' ha','de los barrios registrados'));
  sec.append(grid);
  if((r.mayores||[]).length){const q=make('p','Los más grandes: '+r.mayores.map(m=>`${m.nombre} (${number(m.familias)} familias)`).join(', ')+'.');q.className='hint';sec.append(q);}
  const q=make('p','Dato oficial del RENABAP (2023). El mapa con radar se suma cuando se ejecute el modelo.');q.className='hint';sec.append(q);
  sec.append(barriosLocalPdf(id,r.place));
  box.append(sec);}
async function renderBarrios(id,box){const j=barriosData||await barriosLoad;if(!j)return;
  const p=j.data&&(j.data.places||[]).find(x=>x.id===id);if(!p||p.informal_ha==null){renderRenabap(id,box,j);return;}
  const sec=make('div','');sec.style.cssText='margin-top:22px';sec.append(make('h3','Barrios populares · '+p.place));
  if(p.error){sec.append(make('p','No se pudo calcular esta localidad: '+p.error));box.append(sec);return;}
  const grid=make('div','');grid.className='flood-grid';
  const card=(label,val,sub,cls)=>{const a=make('article','');if(cls)a.className=cls;a.append(make('span',label),make('strong',val),make('span',sub));return a;};
  grid.append(card('Superficie con firma de barrio popular',number(p.informal_ha)+' ha','construcciones con la textura de radar típica'),
    card('Personas en esas zonas',number(p.pop_informal),'estimación WorldPop 2020','warn'));
  const h2=(p.pop_informal_hand||[]).find(b=>b.hasta_m===2);
  if(h2)grid.append(card('Y a 2 m o menos sobre el río',number(h2.personas),'personas en barrios populares de la zona más baja','risk'));
  if(p.in_renabap_ha!=null)grid.append(card('Dentro del RENABAP',number(p.in_renabap_ha)+' ha','de lo detectado cae en barrios registrados'));
  if(p.a_verificar_ha!=null)grid.append(card('Zonas a verificar',number(p.a_verificar_ha)+' ha','misma firma, fuera del registro','warn'));
  if(p.renabap_detectado!=null)grid.append(card('RENABAP reconocido',pct(p.renabap_detectado),'de lo construido en barrios registrados'));
  sec.append(grid);
  const lines=[];
  if(p.renabap_barrios!=null){lines.push(`El RENABAP registra ${number(p.renabap_barrios)} barrios en la zona; el modelo reconoce ${pct(p.renabap_detectado)} de su superficie construida.`);
    if(p.a_verificar_ha)lines.push(`Hay ${number(p.a_verificar_ha)} ha con la misma firma fuera de los barrios registrados: zonas a verificar en terreno, pueden ser barrios nuevos o no relevados, o falsos positivos.`);}
  else lines.push('En esta localidad no hay RENABAP (fuera de Argentina): el resultado sale solo del modelo y conviene verificarlo con datos locales.');
  lines.push('Es una estimación satelital para planificar agua, refugios y evacuación; no identifica viviendas ni personas.');
  for(const l of lines){const q=make('p',l);q.className='hint';sec.append(q);}
  if((p.pop_informal_hand||[]).length){const t=make('table','');const hr=make('tr','');for(const h of ['Hasta … m sobre el río','Personas en barrios populares'])hr.append(make('th',h));t.append(hr);
    for(const b of p.pop_informal_hand){const tr=make('tr','');tr.append(make('td',b.hasta_m+' m'),make('td',number(b.personas)));t.append(tr);}sec.append(t);}
  if(p.imagen){const fig=make('figure','');fig.style.cssText='margin:14px 0';const img=make('img','');img.src=j.image_base+p.imagen;img.alt='Mapa de barrios populares detectados por radar en '+p.place;img.loading='lazy';img.style.cssText='width:100%;max-width:640px;border-radius:12px;display:block';
    fig.append(img,make('figcaption','Rojo: firma de barrio popular según el modelo. Amarillo: barrios del RENABAP. Fondo: Sentinel-2 en color natural, radio de 15 km.'));sec.append(fig);}
  sec.append(barriosLocalPdf(id,p.place));
  box.append(sec);}

// Barrios populares: mapa interactivo y consultas sobre el RENABAP (más la capa del modelo de radar si existe)
const BX={map:null,layer:null,radar:null,data:null,rows:[],req:0};
const BX_BREAKS=[[50,'#fde0c5'],[200,'#f9b384'],[500,'#f08151'],[1000,'#d4502b'],[Infinity,'#9e2a17']];
const bxColor=f=>f==null?'#c7d3d6':BX_BREAKS.find(b=>f<b[0])[1];
const bxFormal=v=>!!v&&/formal|regular|medidor/i.test(v)&&!/irregular|informal/i.test(v);   // «regular», «con medidor» y «acceso formal» cuentan como formales
function bxEsc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function bxLegend(){const l=$('bx-legend');l.replaceChildren();let lo=0;
  for(const [hi,col] of BX_BREAKS){const s=make('span','');const i=make('i','');i.style.background=col;s.append(i,document.createTextNode(hi===Infinity?`${number(lo)} o más familias`:`${number(lo)} a ${number(hi-1)}`));l.append(s);lo=hi;}
  const s=make('span','');const i=make('i','');i.style.background='rgba(215,48,31,.55)';s.append(i,document.createTextNode('Firma de barrio popular según el radar'));l.append(s);}
function bxInitMap(){if(BX.map||!window.L)return!!BX.map;
  BX.map=L.map('barrios-map',{preferCanvas:true,scrollWheelZoom:false}).setView([-29,-58.5],6);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:18,attribution:'© OpenStreetMap contributors'}).addTo(BX.map);
  setTimeout(()=>BX.map.invalidateSize(),150);return true;}
function bxFilters(){const sv=[...document.querySelectorAll('#bx-services input[data-s]:checked')].map(x=>x.dataset.s);
  return{q:$('bx-q').value.trim().toLowerCase(),fam:+$('bx-fam').value||0,ha:+$('bx-ha').value||0,sv};}
function bxPopup(p){const row=(k,v)=>v==null||v===''?'':`<tr><th>${k}</th><td>${bxEsc(v)}</td></tr>`;
  return `<b>${bxEsc(p.nombre)}</b><br><small>${bxEsc([p.localidad,p.provincia].filter(Boolean).join(', '))}</small><table class="bx-pop">`
    +row('Familias',p.familias==null?'Sin dato':number(p.familias))+row('Superficie',number(p.ha,1)+' ha')
    +row('Agua',p.agua)+row('Cloacas',p.cloaca)+row('Electricidad',p.electricidad)+row('Tenencia',p.tenencia)
    +row('Desde',p.creacion)+row('Localidad DOTS',`${p.estacion_nombre} (${number(p.km,1)} km)`)+'</table>';}
function bxDraw(fit){if(!BX.data||!bxInitMap())return;const f=bxFilters();
  BX.rows=BX.data.features.filter(x=>{const p=x.properties;
    if(f.q&&!String(p.nombre||'').toLowerCase().includes(f.q))return false;
    if(f.fam&&!((p.familias||0)>=f.fam))return false;
    if(f.ha&&!((p.ha||0)>=f.ha))return false;
    for(const k of f.sv){if(!p[k]||bxFormal(p[k]))return false;}
    return true;});
  if(BX.layer)BX.map.removeLayer(BX.layer);
  BX.layer=L.geoJSON({type:'FeatureCollection',features:BX.rows},{style:x=>({color:'#5a2a1c',weight:1,fillColor:bxColor(x.properties.familias),fillOpacity:.75}),
    onEachFeature:(x,l)=>l.bindPopup(bxPopup(x.properties),{maxWidth:300})}).addTo(BX.map);
  if(fit&&BX.rows.length)BX.map.fitBounds(BX.layer.getBounds(),{padding:[20,20],maxZoom:14});
  const fam=BX.rows.reduce((a,x)=>a+(x.properties.familias||0),0),ha=BX.rows.reduce((a,x)=>a+(x.properties.ha||0),0);
  $('bx-sum').textContent=`${number(BX.rows.length)} barrios · ${number(fam)} familias · ${number(ha)} ha`+(BX.rows.length<BX.data.features.length?` (de ${number(BX.data.features.length)} en la selección)`:'')+'. Fuente: '+(BX.data.fuente||'RENABAP')+'.';
  $('bx-csv').disabled=!BX.rows.length;bxTable();}
function bxTable(){const box=$('bx-table');box.replaceChildren();if(!BX.rows.length){box.append(make('p','Ningún barrio cumple los filtros.'));return;}
  const rows=BX.rows.slice().sort((a,b)=>(b.properties.familias||0)-(a.properties.familias||0)).slice(0,400);
  const t=make('table','');const hr=make('tr','');for(const h of ['Barrio','Localidad','Familias','Superficie','Agua','Cloacas','Electricidad'])hr.append(make('th',h));t.append(hr);
  rows.forEach((x,i)=>{const p=x.properties,tr=make('tr','');tr.dataset.i=i;tr.tabIndex=0;
    tr.append(make('td',p.nombre),make('td',p.estacion_nombre),make('td',p.familias==null?'—':number(p.familias)),make('td',number(p.ha,1)+' ha'),
      make('td',p.agua?(bxFormal(p.agua)?'Formal':'Sin conexión formal'):'—'),make('td',p.cloaca?(bxFormal(p.cloaca)?'Formal':'Sin conexión formal'):'—'),make('td',p.electricidad?(bxFormal(p.electricidad)?'Formal':'Sin conexión formal'):'—'));
    const go=()=>{const l=L.geoJSON(x);BX.map.fitBounds(l.getBounds(),{maxZoom:16});BX.layer.eachLayer(y=>{if(y.feature===x)y.openPopup();});$('barrios-map').scrollIntoView({behavior:'smooth',block:'center'});};
    tr.addEventListener('click',go);tr.addEventListener('keydown',e=>{if(e.key==='Enter')go();});t.append(tr);});
  box.append(t);if(BX.rows.length>400){const p=make('p',`Se muestran los 400 con más familias; el CSV trae los ${number(BX.rows.length)}.`);p.className='hint';box.append(p);}}
function bxRadar(id){if(BX.radar){BX.map.removeLayer(BX.radar);BX.radar=null;}
  if(!$('bx-radar').checked||!barriosData||!barriosData.data)return;
  const places=(barriosData.data.places||[]).filter(p=>p.imagen&&(id==='todas'||p.id===id));
  if(!places.length)return;const grp=L.layerGroup();
  for(const p of places){const st=(BX.data.localidades||[]).find(s=>s.id===p.id);if(!st)continue;
    const dl=15000/111320,dn=15000/(111320*Math.cos(st.lat*Math.PI/180));
    L.imageOverlay((barriosData.image_base||'/api/poblacion/barrios/')+p.imagen,[[st.lat-dl,st.lon-dn],[st.lat+dl,st.lon+dn]],{opacity:.55}).addTo(grp);}
  BX.radar=grp.addTo(BX.map);}
async function bxLoad(){const id=$('bx-place').value,req=++BX.req;$('bx-sum').textContent='Cargando barrios…';
  try{const d=await jsonFetch('/api/poblacion/barrios/mapa?id='+encodeURIComponent(id));if(req!==BX.req)return;BX.data=d;
    const sv=$('bx-services');sv.querySelectorAll('input[data-s]').forEach(x=>{x.disabled=!d.con_servicios;});
    if(!d.con_servicios)sv.title='Los servicios se suman cuando se vuelva a ejecutar la tarea «RENABAP por localidad».';
    bxDraw(true);bxRadar(id);}
  catch(e){if(req===BX.req){$('bx-sum').textContent='No se pudieron cargar los barrios: '+e.message;$('bx-table').replaceChildren();}}}
function bxCsv(){const cols=['nombre','estacion_nombre','rio','localidad','provincia','familias','ha','agua','cloaca','electricidad','cocina','tenencia','clasificacion','creacion','lat','lon'];
  const cell=v=>typeof v==='number'&&Number.isFinite(v)?String(v):csvValue(v);   // números tal cual (sin el resguardo de fórmulas)
  const lines=[cols.join(',')].concat(BX.rows.map(x=>cols.map(c=>cell(x.properties[c])).join(',')));
  save('DOTS-barrios-populares-'+$('bx-place').value+'.csv','\ufeff'+lines.join('\n'),'text/csv;charset=utf-8');}
(function bxInit(){if(!$('barrios-explorer'))return;bxLegend();
  jsonFetch('/api/poblacion/localidades').then(d=>{for(const p of d.places){const o=make('option',`${p.place} · río ${p.river}`);o.value=p.id;$('bx-place').append(o);}}).catch(()=>{});
  let t=null;const later=()=>{clearTimeout(t);t=setTimeout(()=>bxDraw(false),200);};
  $('bx-place').addEventListener('change',bxLoad);$('bx-q').addEventListener('input',later);$('bx-fam').addEventListener('input',later);$('bx-ha').addEventListener('input',later);
  document.querySelectorAll('#bx-services input[data-s]').forEach(x=>x.addEventListener('change',()=>bxDraw(false)));
  $('bx-radar').addEventListener('change',()=>bxRadar($('bx-place').value));$('bx-csv').addEventListener('click',bxCsv);
  const start=()=>{if(window.L)bxLoad();else setTimeout(start,200);};start();
  barriosLoad.then(()=>BX.data&&bxRadar($('bx-place').value));})();
