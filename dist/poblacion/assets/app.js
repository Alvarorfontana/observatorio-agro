const $=id=>document.getElementById(id);
const number=(v,digits=0)=>v==null?'Sin dato':new Intl.NumberFormat('es-AR',{maximumFractionDigits:digits}).format(v);
const make=(tag,text)=>{const e=document.createElement(tag);e.textContent=text;return e;};
const colors={area:'#246fa6',hazard:'#b76d27',intersection:'#bc3647'};
let map=null,layers={},draw=null,vertices=[],draft=null,last=null,token=null,busy=false,generation=0;
const today=new Date();$('event-date').value=`${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`;
function status(text){$('status').textContent=text;}
function clearResult(){last=null;token=null;generation++;$('resume').hidden=true;
  for(const id of ['total','exposed','percent','surface'])$(id).textContent='—';
  for(const id of ['export-json','export-csv','print'])$(id).disabled=true;
  $('population-year').textContent='Esperando cálculo';$('event-label').textContent='Sin área analizada';
  $('details').replaceChildren(make('h3','Resultados con trazabilidad'),make('p','La consulta se actualiza al calcular. Las cifras anteriores se eliminan cuando cambian los parámetros.'));
  if(map&&layers.intersection){map.removeLayer(layers.intersection);delete layers.intersection;}
}
function geometry(id){const value=JSON.parse($(id).value);return value.type==='Feature'?value.geometry:value;}
function setShape(id,value){
  if(!['Polygon','MultiPolygon'].includes(value?.type))throw new Error('Se requiere Polygon o MultiPolygon.');
  $(id).value=JSON.stringify(value,null,2);
  if(map){if(layers[id])map.removeLayer(layers[id]);layers[id]=L.geoJSON(value,{style:{color:colors[id],weight:2,fillOpacity:.13}}).addTo(map);}
}
function fit(){if(!map)return;const available=Object.values(layers).filter(Boolean);if(available.length)map.fitBounds(L.featureGroup(available).getBounds(),{padding:[30,30],maxZoom:14});}
function initialiseMap(){
  if(!window.L){$('map-fallback').hidden=false;status('Mapa no disponible. Podés importar ambas geometrías en el formulario.');return;}
  map=L.map('map').setView([-27.47,-58.83],11);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap contributors'}).addTo(map).on('tileerror',()=>{$('map-fallback').hidden=false;});
  map.on('click',e=>{if(!draw)return;vertices.push([e.latlng.lng,e.latlng.lat]);if(draft)map.removeLayer(draft);
    draft=L.polyline(vertices.map(([x,y])=>[y,x]),{color:colors[draw],dashArray:'5 5'}).addTo(map);
    status(`${vertices.length} vértices. Presioná “Cerrar polígono” con al menos tres puntos.`);
  });
}
if(document.readyState==='complete')initialiseMap();else window.addEventListener('load',initialiseMap,{once:true});
function cancelDraw(){draw=null;vertices=[];if(map&&draft)map.removeLayer(draft);draft=null;}
for(const id of ['area','hazard'])$('draw-'+id).addEventListener('click',()=>{if(!map){status('Usá la importación GeoJSON: el mapa no cargó.');return;}cancelDraw();draw=id;status(`Marcá los vértices de ${id==='area'?'la zona':'la amenaza'} en el mapa.`);});
$('cancel').addEventListener('click',()=>{cancelDraw();status('Dibujo cancelado.');});
$('finish').addEventListener('click',()=>{if(!draw||vertices.length<3){status('Marcá al menos tres vértices antes de cerrar.');return;}const id=draw;
  setShape(id,{type:'Polygon',coordinates:[[...vertices,vertices[0]]]});cancelDraw();clearResult();status('Geometría guardada. Completá los parámetros y calculá.');});
$('apply').addEventListener('click',()=>{try{clearResult();setShape('area',geometry('area'));setShape('hazard',geometry('hazard'));fit();status('Geometrías importadas. El servidor validará su forma antes de calcular.');}catch(e){status(`GeoJSON: ${e.message}`);}});
for(const id of ['area','hazard','year','dataset','kind','category','event-date','event-source','enso'])$(id).addEventListener('input',()=>{clearResult();status('Parámetros modificados. Volvé a calcular para actualizar los resultados.');});

async function jsonFetch(path,payload){const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),50000);
  try{const r=await fetch(path,{method:payload?'POST':'GET',headers:payload?{'Content-Type':'application/json'}:{},body:payload?JSON.stringify(payload):undefined,signal:controller.signal});
    const data=await r.json();if(!r.ok)throw new Error(data.error||'La consulta no pudo completarse.');return data;
  }finally{clearTimeout(timer);}}
async function poll(startGeneration){
  for(let i=0;i<30;i++){
    if(generation!==startGeneration)return;
    const result=await jsonFetch('/api/poblacion/resultado',{token});
    if(generation!==startGeneration)return;
    if(result.status!=='pending'){show(result);token=null;return;}
    status(`WorldPop está procesando la zona. Consulta ${i+1}/30…`);
    await new Promise(resolve=>setTimeout(resolve,3000));
  }
  status('El cálculo sigue pendiente en WorldPop. Podés continuar la consulta sin iniciar otro trabajo.');$('resume').hidden=false;
}
function setBusy(value){busy=value;$('calculate').disabled=value;$('resume').disabled=value;}
$('analysis').addEventListener('submit',async e=>{
  e.preventDefault();if(busy)return;clearResult();setBusy(true);const current=generation;
  try{
    const payload={area:geometry('area'),hazard:geometry('hazard'),year:Number($('year').value),dataset:$('dataset').value,
      event:{kind:$('kind').value,category:$('category').value,source:$('event-source').value,date:$('event-date').value,enso:$('enso').value}};
    setShape('area',payload.area);setShape('hazard',payload.hazard);fit();status('Enviando geometrías y consultando población…');
    const data=await jsonFetch('/api/poblacion/exposicion',payload);if(generation!==current)return;
    if(data.status==='pending'){token=data.token;await poll(current);}else show(data);
  }catch(error){if(generation===current){status(error.name==='AbortError'?'El servidor excedió el tiempo de respuesta.':'No se pudo completar: '+error.message);if(token)$('resume').hidden=false;}}
  finally{setBusy(false);}
});
$('resume').addEventListener('click',async()=>{if(!token||busy)return;setBusy(true);try{await poll(generation);}catch(e){status(e.message);}finally{setBusy(false);}});

function show(data){
  last=data;$('resume').hidden=true;
  $('total').textContent=number(data.population_total);$('exposed').textContent=number(data.population_exposed);
  $('percent').textContent=data.exposed_percent==null?'Sin dato':number(data.exposed_percent,1)+'%';
  $('surface').textContent=number(data.hazard_in_area_km2,2)+' km²';
  $('population-year').textContent=`${data.source.provider} · ${data.year} · ${data.population_group}`;
  $('event-label').textContent=`${data.event.kind} · ${data.event.date}`;
  if(map&&data.intersection){layers.intersection=L.geoJSON(data.intersection,{style:{color:colors.intersection,weight:3,fillOpacity:.3}}).addTo(map);}
  const rows=[['Fuente de población',data.source.provider],['Grupo',data.population_group],['Año de población',String(data.year)],
    ['Densidad',number(data.density_per_km2,1)+' personas/km²'],['Tipo de amenaza',data.event.category],
    ['Fuente de amenaza',data.event.source],['Contexto ENOS',data.event.enso],
    ['Cobertura ráster',data.coverage_percent==null?'No informada por API de agregación':number(data.coverage_percent,1)+'%'],
    ['Método',data.method],['Calculado',data.calculated_at]];
  $('details').replaceChildren(make('h3',data.status==='partial_coverage'?'Resultado con cobertura parcial':data.status==='no_data'?'Sin cobertura poblacional':'Resultado del análisis'));
  const dl=make('dl','');for(const [key,val]of rows)dl.append(make('dt',key),make('dd',val));$('details').append(dl,make('p',data.interpretation));
  for(const note of data.notes||[])$('details').append(make('p',note));
  status(data.status==='complete'?'Consulta completada. Podés descargar los resultados y el informe.':data.status==='no_data'?'No hay datos válidos para esta zona; no equivale a población cero.':'La cobertura es parcial; las cifras corresponden al sector con datos.');
  for(const id of ['export-json','export-csv','print'])$(id).disabled=false;
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
jsonFetch('/api/poblacion/datasets').then(data=>{for(const d of data.datasets.filter(x=>x.id!=='worldpop-api')){const o=make('option',`${d.provider} · ${d.group} · ${d.year}`);o.value=d.id;$('dataset').append(o);}}).catch(e=>status('Registro de fuentes: '+e.message));
