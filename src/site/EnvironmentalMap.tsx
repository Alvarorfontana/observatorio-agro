import {useEffect,useRef} from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import {TerrainScreeningLayer} from "./TerrainScreeningLayer";
type Point=[number,number];
type Props={lat:number;lon:number;layer:string;date:string;onPoint:(lat:number,lon:number)=>void;onTramoPoint?:(lat:number,lon:number)=>void;tramoMode?:boolean;tramoStart?:Point|null;tramoEnd?:Point|null;terrainEnabled?:boolean;terrainLevel?:number};
export function EnvironmentalMap({lat,lon,layer,date,onPoint,onTramoPoint,tramoMode=false,tramoStart=null,tramoEnd=null,terrainEnabled=false,terrainLevel=60}:Props){
 const el=useRef<HTMLDivElement>(null);
 const map=useRef<L.Map|null>(null);
 const overlay=useRef<L.TileLayer.WMS|null>(null);
 const callback=useRef(onPoint);callback.current=onPoint;
 const tramoCallback=useRef(onTramoPoint);tramoCallback.current=onTramoPoint;
 const modeRef=useRef(tramoMode);modeRef.current=tramoMode;
 const tramoLayer=useRef<L.LayerGroup|null>(null);
 const terrainRef=useRef<TerrainScreeningLayer|null>(null);
 useEffect(()=>{
  if(!el.current)return;
  const m=L.map(el.current,{zoomControl:true}).setView([lat,lon],5);map.current=m;
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",{maxZoom:18,attribution:"© OpenStreetMap contributors"}).addTo(m);
  m.on("click",(event:L.LeafletMouseEvent)=>{if(modeRef.current&&tramoCallback.current)tramoCallback.current(event.latlng.lat,event.latlng.lng);else callback.current(event.latlng.lat,event.latlng.lng)});
  const resize=window.setTimeout(()=>m.invalidateSize(),100);
  return()=>{window.clearTimeout(resize);m.remove();map.current=null};
 },[]);
 useEffect(()=>{if(!tramoMode&&!tramoStart&&!tramoEnd)map.current?.panTo([lat,lon])},[lat,lon,tramoMode,tramoStart?.[0],tramoStart?.[1],tramoEnd?.[0],tramoEnd?.[1]]);
 useEffect(()=>{if(tramoStart&&tramoEnd&&map.current){const bounds=L.latLngBounds([tramoStart,tramoEnd]);map.current.fitBounds(bounds.pad(0.45),{maxZoom:12,animate:true})}},[tramoStart?.[0],tramoStart?.[1],tramoEnd?.[0],tramoEnd?.[1]]);
 useEffect(()=>{if(tramoLayer.current){tramoLayer.current.remove();tramoLayer.current=null}if(!map.current)return;const g=L.layerGroup().addTo(map.current);tramoLayer.current=g;
  if(tramoStart)L.circleMarker(tramoStart,{radius:9,color:"#24d5a7",weight:3,fillOpacity:.9}).bindTooltip("Inicio del tramo").addTo(g);
  if(tramoEnd)L.circleMarker(tramoEnd,{radius:9,color:"#ffb45d",weight:3,fillOpacity:.9}).bindTooltip("Fin del tramo").addTo(g);
  if(tramoStart&&tramoEnd)L.polyline([tramoStart,tramoEnd],{color:"#ffcc60",weight:4,dashArray:"8 6"}).bindTooltip("Referencia entre puntos: no sigue automáticamente el cauce").addTo(g);
  return()=>{g.remove();if(tramoLayer.current===g)tramoLayer.current=null};
 },[tramoStart?.[0],tramoStart?.[1],tramoEnd?.[0],tramoEnd?.[1]]);
 useEffect(()=>{if(terrainRef.current){terrainRef.current.remove();terrainRef.current=null}if(!map.current||!terrainEnabled)return;const layer=new TerrainScreeningLayer(terrainLevel);layer.addTo(map.current);terrainRef.current=layer;return()=>{layer.remove();if(terrainRef.current===layer)terrainRef.current=null}},[terrainEnabled]);
 useEffect(()=>{terrainRef.current?.setLevel(terrainLevel)},[terrainLevel]);
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
 return <div><div ref={el} role="application" aria-label="Mapa interactivo de América del Sur; seleccioná una ubicación para consultar datos" style={{height:"min(72vh,780px)",minHeight:540,width:"100%",borderRadius:12,background:"#152b38"}}/><p style={{fontSize:12}}>Mapa base © OpenStreetMap · superposiciones NASA GIBS y relieve Terrarium cuando está activado. {tramoMode?"Modo selección de tramo: marcá el inicio y el fin sobre el mapa.":"Hacé clic en cualquier lugar para consultar sus coordenadas."} La ausencia de una imagen puede deberse a la fecha, cobertura o disponibilidad del producto.</p></div>;
}
