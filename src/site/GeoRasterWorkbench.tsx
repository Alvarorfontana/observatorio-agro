import {useState} from "react";
import {fromBlob} from "geotiff";
import {analyzeD8,delineateUpstream} from "../lib/demHydrology";

type Grid={width:number;height:number;values:ReturnType<typeof analyzeD8>;bounds:number[];crs:string};
type DemInfo={name:string;width:number;height:number;bands:number;bounds:string;resolution:string;minimum:string;maximum:string;nodata:string;crs:string;hydrology:ReturnType<typeof analyzeD8>};
export function GeoRasterWorkbench({basin,river,tramoStart,tramoEnd}:{basin:string;river:string;tramoStart:[number,number]|null;tramoEnd:[number,number]|null}){
 const [info,setInfo]=useState<DemInfo|null>(null);
 const [error,setError]=useState("");
 const [busy,setBusy]=useState(false);
 const [grid,setGrid]=useState<Grid|null>(null);
 const [outlet,setOutlet]=useState<{lat:number;lon:number;cells:number}|null>(null);
 const [mask,setMask]=useState<Uint8Array|null>(null);
 function selectOutlet(){
  if(!grid||!tramoEnd){setError("Marcá el final del tramo en el mapa y cargá un DEM.");return}
  if(grid.crs!=="4326"){setError("Para delimitar con coordenadas del mapa se requiere un DEM en EPSG:4326. Reproyectá el archivo antes de continuar.");return}
  const [west,south,east,north]=grid.bounds;
  const [lat,lon]=tramoEnd;
  if(lon<west||lon>east||lat<south||lat>north){setError("El extremo final del tramo está fuera de la cobertura del DEM.");return}
  const x=Math.min(grid.width-1,Math.max(0,Math.floor((lon-west)/(east-west)*grid.width)));
  const y=Math.min(grid.height-1,Math.max(0,Math.floor((north-lat)/(north-south)*grid.height)));
  const index=y*grid.width+x;
  const basinMask=delineateUpstream(grid.values.downstream,grid.width,grid.height,index);
  let cells=0;for(const v of basinMask)cells+=v;
  setMask(basinMask);setOutlet({lat,lon,cells});setError("");
 }
 async function load(file:File|undefined){
  if(!file)return;setError("");setInfo(null);setGrid(null);setMask(null);setOutlet(null);setBusy(true);
  try{
   if(file.size>100*1024*1024)throw new Error("Para esta prueba usá un GeoTIFF de hasta 100 MB. Los COG grandes requieren lectura por rangos.");
   const tiff=await fromBlob(file);
   const image=await tiff.getImage();
   const bbox=image.getBoundingBox();
   const resolution=image.getResolution();
   const geo=image.getGeoKeys();
   const fmt=(n:number)=>Number.isFinite(n)?n.toFixed(3):"Sin dato";
   const width=image.getWidth(),height=image.getHeight();
   const sampleStep=Math.max(1,Math.ceil(Math.sqrt(width*height/300000)));
   const data=await image.readRasters({samples:[0],width:Math.ceil(width/sampleStep),height:Math.ceil(height/sampleStep),interleave:true});
   const nodata=image.getGDALNoData();
   let lo=Infinity,hi=-Infinity;
   for(const value of data){const v=Number(value);if(Number.isFinite(v)&&(nodata===null||v!==nodata)){lo=Math.min(lo,v);hi=Math.max(hi,v)}}
   const sampledWidth=Math.ceil(width/sampleStep),sampledHeight=Math.ceil(height/sampleStep);
   const elevationValues=Float64Array.from(Array.from(data as ArrayLike<number>,value=>Number(value)));
   const hydrology=analyzeD8(elevationValues,sampledWidth,sampledHeight,nodata);
   setGrid({width:sampledWidth,height:sampledHeight,values:hydrology,bounds:bbox,crs:String(geo.ProjectedCSTypeGeoKey||geo.GeographicTypeGeoKey||"")});
   setInfo({hydrology,name:file.name,width,height,bands:image.getSamplesPerPixel(),bounds:bbox.map(fmt).join(", "),resolution:resolution.slice(0,2).map(fmt).join(" × "),minimum:lo===Infinity?"Sin datos":fmt(lo),maximum:hi===-Infinity?"Sin datos":fmt(hi),nodata:nodata===null?"No declarado":String(nodata),crs:String(geo.ProjectedCSTypeGeoKey||geo.GeographicTypeGeoKey||"No identificado")});
  }catch(e){setError(e instanceof Error?e.message:"No se pudo interpretar el archivo ráster.")}finally{setBusy(false)}
 }
 return <section aria-label="Laboratorio geoespacial" style={{background:"#142834",color:"#edf5f8",borderRadius:12,padding:16,marginTop:14}}>
 <h2 style={{margin:"0 0 8px"}}>Laboratorio geoespacial · GeoTIFF / DEM</h2>
 <p style={{fontSize:13}}>Primera integración de procesamiento ráster en el navegador, compatible con el flujo de trabajo GeoLibre/Terrio. Cargá un modelo digital de elevación GeoTIFF para inspeccionar su cobertura, proyección y valores antes de utilizarlo en un análisis hidrológico.</p>
 <p><strong>Selección del mapa:</strong> {basin} · {river}. {tramoStart&&tramoEnd?"Tramo con ambos extremos marcados.":"Todavía no hay dos extremos marcados."}</p>
 <label style={{display:"block"}}>Abrir GeoTIFF local (.tif / .tiff)<input type="file" accept=".tif,.tiff,image/tiff" onChange={e=>void load(e.target.files?.[0])} style={{display:"block",marginTop:8}}/></label>
 {busy&&<p role="status">Leyendo ráster y calculando estadísticas de muestra…</p>}
 {error&&<p role="alert" style={{color:"#ffcfab"}}>{error}</p>}
 {info&&<div><button type="button" onClick={selectOutlet} disabled={!tramoEnd} style={{padding:9,margin:"8px 0"}}>Delimitar área aportante al final del tramo (D8)</button>{outlet&&mask&&<p role="status"><strong>Área aportante preliminar:</strong> {outlet.cells.toLocaleString("es-AR")} celdas de la muestra. Punto de salida: {outlet.lat.toFixed(5)}, {outlet.lon.toFixed(5)}. Este conteo no es una superficie en km² ni una cuenca validada.</p>}<div role="status"><h3>{info.name}</h3><table style={{width:"100%",textAlign:"left"}}><tbody>{([["Dimensiones",info.width+" × "+info.height+" píxeles"],["Bandas",String(info.bands)],["Sistema de referencia (EPSG)",info.crs],["Extensión en coordenadas del archivo",info.bounds],["Resolución en unidades del archivo",info.resolution],["Mínimo muestreado",info.minimum],["Máximo muestreado",info.maximum],["NoData",info.nodata],["D8 · celdas válidas",String(info.hydrology.validPixels)],["D8 · celdas sin salida descendente",String(info.hydrology.sinks)],["D8 · acumulación máxima (celdas)",String(info.hydrology.maxAccumulation)],["D8 · celdas con acumulación alta",String(info.hydrology.drainagePixels)+" (umbral ≥ "+info.hydrology.cutoff+")"]] as [string,string][]).map(([key,value])=><tr key={key}><th style={{padding:6}}>{key}</th><td style={{padding:6}}>{value}</td></tr>)}</tbody></table></div></div>}
 <p style={{fontSize:12,color:"#ffdb99"}}>Los extremos del tramo y los metadatos se muestran juntos, y el botón D8 permite trazar una contribución aguas arriba en celdas del DEM, pero aún no se recorta el DEM al tramo ni se calcula una cuenca oficial o una inundación. D8 es un análisis exploratorio sobre una muestra remuestreada, sin corrección de depresiones, sin acondicionamiento de cauces y sin calibración. Las estadísticas son de una muestra remuestreada, no valores exactos de todos los píxeles. No se envía el archivo al servidor.</p>
 </section>;
}
