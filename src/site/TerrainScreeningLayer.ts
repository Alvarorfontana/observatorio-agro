import L from "leaflet";

/** Visualización exploratoria de cotas topográficas, NO modelo hidrodinámico.
 * Terrarium: elevación (m s.n.m.) = R*256 + G + B/256 - 32768.
 * Se colorean todas las celdas bajo una cota absoluta: NO se calcula conectividad hidráulica.
 */
export class TerrainScreeningLayer extends L.GridLayer {
 private level:number;
 constructor(level:number){super({tileSize:256,opacity:0.66,minZoom:4,maxZoom:13,updateWhenIdle:true});this.level=level;}
 setLevel(level:number){this.level=level;this.redraw();}
 createTile(coords:L.Coords,done:L.DoneCallback):HTMLElement{
  const canvas=document.createElement("canvas");canvas.width=256;canvas.height=256;
  const ctx=canvas.getContext("2d",{willReadFrequently:true});
  const img=new Image();img.crossOrigin="anonymous";
  img.onload=()=>{
   if(!ctx){done(new Error("Canvas no disponible"),canvas);return}
   try{
    ctx.drawImage(img,0,0,256,256);
    const frame=ctx.getImageData(0,0,256,256);
    const px=frame.data;
    for(let i=0;i<px.length;i+=4){
     const elevation=px[i]*256+px[i+1]+px[i+2]/256-32768;
     const low=elevation<=this.level;
     px[i]=low?15:0;px[i+1]=low?138:0;px[i+2]=low?239:0;px[i+3]=low?155:0;
    }
    ctx.putImageData(frame,0,0);done(undefined,canvas);
   }catch(e){ctx.clearRect(0,0,256,256);done(e instanceof Error?e:new Error("No se pudo leer el relieve"),canvas)}
  };
  img.onerror=()=>done(new Error("Tesela de elevación no disponible"),canvas);
  const z=Math.min(coords.z,13);
  const x=coords.x>>Math.max(0,coords.z-13),y=coords.y>>Math.max(0,coords.z-13);
  img.src=`https://s3.amazonaws.com/elevation-tiles-prod/terrarium/${z}/${x}/${y}.png`;
  return canvas;
 }
}
