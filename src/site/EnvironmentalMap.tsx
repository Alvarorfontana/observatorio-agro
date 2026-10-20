import {useEffect,useRef} from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
type Props={lat:number;lon:number;layer:string;date:string;onPoint:(lat:number,lon:number)=>void};
export function EnvironmentalMap({lat,lon,layer,date,onPoint}:Props){
 const el=useRef<HTMLDivElement>(null);
 const map=useRef<L.Map|null>(null);
 const overlay=useRef<L.TileLayer.WMS|null>(null);
 const callback=useRef(onPoint);callback.current=onPoint;
 useEffect(()=>{
  if(!el.current)return;
  const m=L.map(el.current,{zoomControl:true}).setView([lat,lon],5);map.current=m;
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",{maxZoom:18,attribution:"© OpenStreetMap contributors"}).addTo(m);
  m.on("click",(event:L.LeafletMouseEvent)=>callback.current(event.latlng.lat,event.latlng.lng));
  const resize=window.setTimeout(()=>m.invalidateSize(),100);
  return()=>{window.clearTimeout(resize);m.remove();map.current=null};
 },[]);
 useEffect(()=>{map.current?.panTo([lat,lon])},[lat,lon]);
 useEffect(()=>{
  if(overlay.current){overlay.current.remove();overlay.current=null}
  if(!layer||!map.current)return;
  const wms=L.tileLayer.wms("https://gibs.earthdata.nasa.gov/wms/epsg3857/best/wms.cgi",{
   layers:layer,format:"image/png",transparent:true,opacity:0.72,
   ...(date?{time:date}:{})
  });
  wms.addTo(map.current);overlay.current=wms;
  return()=>{wms.remove();if(overlay.current===wms)overlay.current=null};
 },[layer,date]);
 return <div><div ref={el} role="application" aria-label="Mapa interactivo de América del Sur; seleccioná una ubicación para consultar datos" style={{height:480,width:"100%",borderRadius:12,background:"#152b38"}}/><p style={{fontSize:12}}>Mapa base © OpenStreetMap · superposiciones NASA GIBS. Hacé clic en cualquier lugar para consultar sus coordenadas. La ausencia de una imagen puede deberse a la fecha, cobertura o disponibilidad del producto.</p></div>;
}
