import {CLIMATE_PROVIDERS} from "../lib/climateProviderRegistry";
export function ClimateSourcesCatalog(){
 return <section aria-label="Catálogo de fuentes climáticas" style={{marginTop:20,padding:16,background:"#163643",borderRadius:12,color:"#eaf4f8"}}>
 <h3>Fuentes climáticas internacionales · 18 proveedores</h3>
 <p>Catálogo documental para ampliar los análisis de DOTS. Los enlaces no implican que el proveedor ya esté conectado a una API. Las observaciones, los reanálisis, los pronósticos y las proyecciones tienen alcances diferentes.</p>
 <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(240px,1fr))",gap:10}}>
 {CLIMATE_PROVIDERS.map(p=><article key={p.id} style={{border:"1px solid #426171",borderRadius:8,padding:12}}>
 <strong><a href={p.url} target="_blank" rel="noreferrer" style={{color:"#a5e6ff"}}>{p.name} ↗</a></strong>
 <p style={{fontSize:13,margin:"6px 0"}}>{p.category} · {p.use}</p>
 <small>Acceso: {p.access==="registro"?"requiere cuenta o registro":p.access==="mixto"?"según producto":"público"} · Estado: referencia, integración no verificada</small>
 </article>)}
 </div>
 </section>;
}
