import React,{useEffect,useState} from "react";
type Collection={id:string;title?:string};
type Scene={id:string;collection:string;properties:{datetime?:string;"eo:cloud_cover"?:number};links:{href:string;rel:string}[]};
export function CopernicusModule(){
 const [collections,setCollections]=useState<Collection[]>([]);
 const [collection,setCollection]=useState("");
 const [bbox,setBbox]=useState("-59.10,-28.56,-58.98,-28.44");
 const [start,setStart]=useState("2026-09-01");
 const [end,setEnd]=useState("2026-10-22");
 const [scenes,setScenes]=useState<Scene[]>([]);
 const [error,setError]=useState("");
 const [loading,setLoading]=useState(false);
 useEffect(()=>{fetch("/api/copernicus/collections").then(async r=>{const j=await r.json();if(!r.ok)throw Error(j.error||"Catálogo no disponible");const c:Collection[]=j.collections||[];setCollections(c);setCollection(c.find(x=>/sentinel-2.*l2a/i.test(x.id))?.id||c[0]?.id||"")}).catch(e=>setError(String(e.message)))},[]);
 async function search(e:React.FormEvent){e.preventDefault();setError("");setScenes([]);setLoading(true);try{
 const q=new URLSearchParams({bbox,start,end,collection,limit:"25"});
 const r=await fetch("/api/copernicus/scenes?"+q);const j=await r.json();if(!r.ok)throw Error(j.detail||j.error||"Consulta fallida");setScenes(j.features||[]);
 }catch(e){setError(e instanceof Error?e.message:String(e))}finally{setLoading(false)}}
 return <main style={{maxWidth:1180,margin:"auto",padding:"32px 22px",fontFamily:"IBM Plex Sans, sans-serif",color:"#e5edf2",background:"#101c25",minHeight:"100vh"}}>
 <a href="/" style={{color:"#8bd3ef"}}>← DOTS · Inicio</a><p style={{letterSpacing:2,color:"#78bfd7",marginTop:40}}>NUEVO MÓDULO · COPERNICUS 2026</p>
 <h1 style={{fontSize:"clamp(32px,5vw,58px)",margin:"8px 0"}}>Inteligencia satelital europea</h1>
 <p style={{fontSize:19,maxWidth:840}}>Explorá imágenes oficiales del programa Copernicus y prepará análisis de parcelas, vegetación, agua, temperatura y atmósfera. Consulta del catálogo en vivo; los cálculos avanzados se incorporarán progresivamente.</p>
 <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(220px,1fr))",gap:14,margin:"28px 0"}}>
 {[
 ["Sentinel-1","Radar y superficies inundadas"],
 ["Sentinel-2","Vegetación y cambios agrícolas"],
 ["Sentinel-3","Temperatura superficial"],
 ["Sentinel-5P","Composición atmosférica"],
 ["openEO","Procesamiento remoto · pendiente de conexión"],
 ["IA geoespacial","TerraMind / TESSERA · en evaluación"]
 ].map(([name,desc])=><article key={name} style={{border:"1px solid #38505d",borderRadius:12,padding:18,background:"#192b36"}}><h2 style={{fontSize:19,margin:"0 0 8px"}}>{name}</h2><p style={{margin:0,color:"#b7c9d1"}}>{desc}</p></article>)}</div>
 <section aria-label="Aplicaciones prácticas" style={{margin:"28px 0"}}><h2>¿Para qué sirve en la práctica?</h2><p>Copernicus amplía los análisis del observatorio. No es una plataforma separada: sus imágenes y productos se relacionan con los módulos de cultivos, parcelas, agua y clima que ya ofrece DOTS.</p><div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(230px,1fr))",gap:14}}>{[
 {t:"Producción agrícola",d:"Comparar campañas y reconocer sectores de vegetación menos vigorosa. Ayuda a decidir dónde inspeccionar un lote antes de intervenir.",url:"/cultivos",link:"Ir a cultivos"},
 {t:"Crecidas e inundaciones",d:"Revisar imágenes de radar para reconocer agua sobre el terreno, incluso cuando las nubes impiden una fotografía óptica.",url:"/nino-crecidas",link:"Ir a crecidas"},
 {t:"Temperaturas y sequías",d:"Contrastar temperaturas superficiales y cambios en vegetación para investigar períodos de estrés térmico e hídrico.",url:"/simulador-ambiental",link:"Ir al simulador"},
 {t:"Historia del territorio",d:"Comparar coberturas de distintas fechas para estudiar avance agrícola, pérdida de monte y cambios en pastizales.",url:"/observatorio",link:"Abrir mapa principal"},
 {t:"Calidad atmosférica",d:"Consultar productos regionales de gases y humo para contextualizar episodios ambientales, sin atribuir emisiones a una parcela individual.",url:"/capas",link:"Ver capas"},
 {t:"Informes técnicos",d:"Usar las fuentes verificadas como respaldo de análisis de parcelas; los nuevos informes automáticos Copernicus aún están en desarrollo.",url:"/modulos",link:"Ver informes"}
 ].map(x=><article key={x.t} style={{padding:18,background:"#192b36",border:"1px solid #38505d",borderRadius:12}}><h3>{x.t}</h3><p style={{color:"#bfd0d9"}}>{x.d}</p><a style={{color:"#8bd3ef"}} href={x.url}>{x.link} →</a></article>)}</div></section>
 <section style={{background:"#192b36",border:"1px solid #38505d",padding:22,borderRadius:14}}>
 <h2>Buscar escenas satelitales</h2><p>Área de ejemplo: Bella Vista, Corrientes. Coordenadas en orden oeste, sur, este, norte.</p>
 <form onSubmit={search} style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(180px,1fr))",gap:12}}>
 <label>Colección<select required value={collection} onChange={e=>setCollection(e.target.value)} style={field}>{collections.map(c=><option key={c.id} value={c.id}>{c.title||c.id}</option>)}</select></label>
 <label>Área (bbox)<input required value={bbox} onChange={e=>setBbox(e.target.value)} style={field}/></label>
 <label>Desde<input required type="date" value={start} onChange={e=>setStart(e.target.value)} style={field}/></label>
 <label>Hasta<input required type="date" value={end} onChange={e=>setEnd(e.target.value)} style={field}/></label>
 <button disabled={loading||!collection} type="submit" style={{background:"#35b3cf",color:"#071820",fontWeight:700,border:0,borderRadius:8,padding:12,cursor:"pointer"}}>{loading?"Consultando…":"Buscar imágenes"}</button>
 </form>
 {error&&<p role="alert" style={{color:"#ffb5a7"}}>{error}</p>}
 <p role="status">{scenes.length?scenes.length+" escenas encontradas":loading?"Buscando en Copernicus…":"Los resultados aparecerán aquí. No se muestran datos simulados."}</p>
 <div style={{display:"grid",gap:8}}>{scenes.map(s=><article key={s.id} style={{borderTop:"1px solid #38505d",padding:"12px 0"}}><strong>{s.id}</strong><p>{s.collection} · {s.properties.datetime||"Fecha no informada"} · Nubes: {s.properties["eo:cloud_cover"]??"sin dato"}%</p>{s.links.find(l=>l.rel==="self")&&<a href={s.links.find(l=>l.rel==="self")!.href} target="_blank" rel="noreferrer" style={{color:"#8bd3ef"}}>Metadatos oficiales ↗</a>}</article>)}</div>
 </section>
 <p style={{color:"#9cb2bd",marginTop:22}}>Fuentes: Copernicus Data Space Ecosystem / ESA. Los productos no son mediciones de campo. El acceso al agente openEO alfa requiere autorización; DOTS no declara habilitados procesos que aún no fueron configurados.</p>
 </main>
}
const field:React.CSSProperties={display:"block",width:"100%",padding:11,borderRadius:7,border:"1px solid #647d89",background:"#0d1b25",color:"#fff",marginTop:7,boxSizing:"border-box"};
