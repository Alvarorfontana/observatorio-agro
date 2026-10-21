import {useEffect,useState} from "react";
type Dataset={source:string;source_url:string;baseline:string;method:string;months:string[];indices:Record<string,(number|null)[]>;hovmoller:{lon:number[];values:(number|null)[][]};maps:{months:string[];lat:number[];lon:number[];values:(number|null)[][][]}};
const palette=(v:number|null)=>v===null?"#53636a":v>=2?"#b83d34":v>=1?"#e88d52":v>=0.3?"#f1c9a0":v<=-2?"#2055a5":v<=-1?"#4e91c8":v<=-0.3?"#b5d7e7":"#e4e9e8";
export function EnsoHistoricalLab(){
 const [data,setData]=useState<Dataset|null>(null),[error,setError]=useState(""),[mapIndex,setMapIndex]=useState(0),[region,setRegion]=useState("nino34");
 useEffect(()=>{const ctrl=new AbortController();fetch("/data/enso-ersst.json",{signal:ctrl.signal}).then(async r=>{if(!r.ok)throw Error("El archivo histórico ERSST todavía no fue generado");return await r.json() as Dataset}).then(setData).catch(e=>{if(!ctrl.signal.aborted)setError(String(e))});return()=>ctrl.abort()},[]);
 const values=data?.indices[region]||[],min=-3,max=3;
 const coords=values.map((v,i)=>v===null?null:{x:40+i*710/Math.max(1,values.length-1),y:95-(v-min)*70/(max-min)});
 const segments:string[]=[];let current="";
 for(const p of coords){if(p){current+=(current?" L":"M")+p.x.toFixed(1)+" "+p.y.toFixed(1)}else if(current){segments.push(current);current=""}}if(current)segments.push(current);
 const hov=data?.hovmoller,hmStep=Math.max(1,Math.ceil((data?.months.length||1)/180));
 return <section aria-label="Laboratorio ENSO histórico" style={{marginTop:20,padding:14,background:"#153441",borderRadius:10,color:"#f1f7fa"}}>
 <h3>Laboratorio histórico ENSO · ERSST v5</h3>
 <p>Temperatura superficial del mar, anomalías mensuales, regiones Niño, Hovmöller ecuatorial y mapas anuales del Pacífico tropical. Base climatológica 1991–2020.</p>
 {!data&&<p role="status">{error||"Cargando archivo histórico NOAA…"}</p>}
 {data&&<><p>Fuente: <a href={data.source_url} target="_blank" rel="noreferrer" style={{color:"#9fe2ff"}}>{data.source}</a> · {data.months[0]} a {data.months[data.months.length-1]}. {data.method}.</p>
 <label>Región Niño <select value={region} onChange={e=>setRegion(e.target.value)}>{Object.keys(data.indices).map(k=><option key={k} value={k}>{k.toUpperCase()}</option>)}</select></label>
 <svg viewBox="0 0 800 145" role="img" aria-label={"Anomalías SST de "+region} style={{width:"100%",background:"#092632",marginTop:10}}>
 <line x1="40" x2="750" y1="95" y2="95" stroke="#c9d6dc" strokeDasharray="4 5"/>
 {segments.map((s,i)=><path key={i} d={s} stroke="#ffce77" strokeWidth="2" fill="none"/>)}
 <text x="40" y="132" fontSize="13" fill="#fff">{data.months[0]}</text><text x="675" y="132" fontSize="13" fill="#fff">{data.months[data.months.length-1]}</text></svg>
 <h4>Hovmöller · anomalía SST ecuatorial (5°S–5°N)</h4>
 <div style={{overflowX:"auto"}}><svg viewBox="0 0 800 350" role="img" aria-label="Diagrama Hovmöller de anomalías mensuales por longitud" style={{width:"100%",minWidth:400,background:"#092632"}}>
 {(hov?.values||[]).filter((_,i)=>i%hmStep===0).map((row,i)=>row.map((v,j)=><rect key={i+"-"+j} x={35+j*735/Math.max(1,hov!.lon.length)} y={12+i*315/Math.max(1,Math.ceil(hov!.values.length/hmStep))} width={735/Math.max(1,hov!.lon.length)+0.2} height={315/Math.max(1,Math.ceil(hov!.values.length/hmStep))+0.2} fill={palette(v)}/>))}
 <text x="35" y="343" fontSize="12" fill="#fff">{hov?.lon[0]}°E</text><text x="680" y="343" fontSize="12" fill="#fff">{hov?.lon[hov.lon.length-1]}°E</text></svg></div>
 <h4>Mapa de anomalías SST · Pacífico tropical</h4>
 <label>Período <select value={mapIndex} onChange={e=>setMapIndex(Number(e.target.value))}>{data.maps.months.map((m,i)=><option key={m} value={i}>{m}</option>)}</select></label>
 <div style={{overflowX:"auto"}}><svg viewBox="0 0 800 290" role="img" aria-label={"Mapa de anomalía SST "+data.maps.months[mapIndex]} style={{width:"100%",minWidth:400,background:"#092632"}}>
 {(data.maps.values[mapIndex]||[]).map((row,i)=>row.map((v,j)=><rect key={i+"-"+j} x={35+j*735/Math.max(1,data.maps.lon.length)} y={10+i*245/Math.max(1,data.maps.lat.length)} width={735/Math.max(1,data.maps.lon.length)+0.2} height={245/Math.max(1,data.maps.lat.length)+0.2} fill={palette(v)}/>))}
 <text x="35" y="276" fontSize="12" fill="#fff">120°E</text><text x="670" y="276" fontSize="12" fill="#fff">80°W</text></svg></div>
 <p style={{fontSize:12}}>Escala de anomalías °C: azul = enfriamiento; rojo = calentamiento; gris = sin dato. Datos derivados de NOAA ERSST v5, no pronóstico.</p>
 </>}
 </section>;
}
