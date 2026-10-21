import {useRef} from "react";
type Props={title:string;source:string;description?:string;filename:string;rows:(string|number|null)[][];headers:string[];children:React.ReactNode};
function csvEscape(value:string|number|null){const s=value===null?"":String(value);return /[",\r\n]/.test(s)?'"'+s.replaceAll('"','""')+'"':s}
function download(name:string,type:string,content:string){const url=URL.createObjectURL(new Blob([content],{type}));const a=document.createElement("a");a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
export function DotsReportExport({title,source,description,filename,headers,rows,children}:Props){
 const ref=useRef<HTMLDivElement>(null);
 const csv=()=>download(filename+".csv","text/csv;charset=utf-8","\uFEFF"+[headers,...rows].map(r=>r.map(csvEscape).join(",")).join("\r\n"));
 const svg=()=>{const element=ref.current?.querySelector("svg");if(!element)return;const clone=element.cloneNode(true) as SVGSVGElement;clone.setAttribute("xmlns","http://www.w3.org/2000/svg");download(filename+".svg","image/svg+xml;charset=utf-8",new XMLSerializer().serializeToString(clone))};
 const print=()=>{
  const body=ref.current?.innerHTML||"";
  const win=window.open("","_blank");
  if(!win){alert("Permití las ventanas emergentes para generar el informe PDF");return}
  const safe=(s:string)=>s.replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;");
  win.document.write('<!doctype html><html><head><meta charset="utf-8"><title>'+safe(title)+'</title><style>@page{size:A4;margin:18mm}body{font:12px Arial;color:#17313a}h1{font-size:25px;border-bottom:3px solid #148a9c;padding-bottom:12px}svg{max-width:100%;height:auto}table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #ddd;padding:6px;text-align:left}footer{margin-top:30px;font-size:10px;color:#555}button{display:none}</style></head><body><h1>'+safe(title)+'</h1><p>'+safe(description||"")+'</p>'+body+'<footer>Fuente: '+safe(source)+' · Informe generado '+new Date().toLocaleString("es-AR")+' · DOTS Campo. Verificar alcance, unidades y período de observación.</footer></body></html>');
  win.document.close();win.focus();win.print();
 };
 return <section aria-label={"Exportación DOTS: "+title}>
  <div style={{display:"flex",gap:8,flexWrap:"wrap",margin:"12px 0"}}>
   <button type="button" onClick={csv}>Descargar CSV</button>
   <button type="button" onClick={svg}>Descargar gráfico SVG</button>
   <button type="button" onClick={print}>Generar informe PDF</button>
  </div>
  <div ref={ref}>{children}</div>
  <small>El PDF se obtiene desde «Imprimir → Guardar como PDF». Incluye gráfico, fuente y fecha; no añade interpretaciones automáticas no verificadas.</small>
 </section>;
}
