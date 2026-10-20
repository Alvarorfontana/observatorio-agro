const $=id=>document.getElementById(id);
const number=(v,digits=0)=>v==null?'Sin dato':new Intl.NumberFormat('es-AR',{maximumFractionDigits:digits}).format(v);
const make=(tag,text)=>{const e=document.createElement(tag);e.textContent=text;return e;};
const colors={area:'#246fa6',hazard:'#b76d27',intersection:'#bc3647'};
let map=null,layers={},draw=null,rectMode=false,vertices=[],draft=null,last=null,token=null,busy=false,generation=0;
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
  $(id).value=JSON.stringify(value,null,2);
  if(map){if(layers[id])map.removeLayer(layers[id]);layers[id]=L.geoJSON(value,{interactive:false,style:{color:colors[id],weight:2,fillOpacity:.13}}).addTo(map);}
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
    const data=await r.json();if(!r.ok)throw new Error(data.error||'La consulta no pudo completarse.');return data;
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
function setBusy(value){busy=value;$('calculate').disabled=value;$('resume').disabled=value;}
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
    // Si WorldPop no tiene el año pedido para esta zona, se usa 2025 (último año con datos confirmados) y se avisa.
    if(year!==2025&&!/Falta dibujar|GeoJSON|geometr|vértices|Reducí/i.test(error.message)&&error.name!=='AbortError'){
      try{token=null;await run(2025,current,`WorldPop no devolvió datos para ${year}; se calculó con 2025.`);return;}
      catch(e2){error=e2;}
    }
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
jsonFetch('/api/poblacion/datasets').then(data=>{for(const d of data.datasets.filter(x=>x.id!=='worldpop-api')){const o=make('option',`${d.provider} · ${d.group} · ${d.year}`);o.value=d.id;$('dataset').append(o);}}).catch(e=>status('Registro de fuentes: '+e.message));

$('pdf').addEventListener('click',async()=>{if(!last)return;const b=$('pdf');b.disabled=true;const t=b.textContent;b.textContent='Generando PDF…';
  try{const r=await fetch('/api/poblacion/informe',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(last)});
    if(!r.ok){const j=await r.json().catch(()=>({}));throw new Error(j.error||'No se pudo generar el PDF.');}
    const url=URL.createObjectURL(await r.blob());const a=make('a','');a.href=url;a.download=`DOTS-poblacion-expuesta-${(last.event?.date||'')}.pdf`;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),2000);}
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
