/** Cálculos reproducibles para series ambientales. Sin inventar valores faltantes.
 * Las unidades y la procedencia se mantienen en los metadatos de entrada.
 */
export type NumericSample = { date:string; value:number|null; source:string; quality?:string };
export type NumericSeries = { variableId:string; unit:string; samples:readonly NumericSample[] };
export type NumericResult = { series:NumericSeries; warnings:string[]; method:string };
function finiteSamples(series:NumericSeries):NumericSample[]{
 return series.samples.filter(s=>s.value!==null&&Number.isFinite(s.value)&&Number.isFinite(Date.parse(s.date))).sort((a,b)=>Date.parse(a.date)-Date.parse(b.date));
}
export function movingAverage(series:NumericSeries,window:number):NumericResult{
 if(!Number.isInteger(window)||window<1||window>365)throw Error('Ventana inválida');
 const samples=finiteSamples(series);
 const out:NumericSample[]=samples.map((s,i)=>i<window-1?{...s,value:null}:{...s,value:samples.slice(i-window+1,i+1).reduce((sum,x)=>sum+(x.value as number),0)/window});
 return {series:{...series,samples:out},warnings:series.samples.length!==samples.length?['Se omitieron observaciones sin valor o fecha válida']:[],method:'Media móvil de '+window+' observaciones válidas; no interpola fechas ausentes'};
}
export function baselineAnomaly(series:NumericSeries,baselineStart:string,baselineEnd:string):NumericResult{
 const start=Date.parse(baselineStart),end=Date.parse(baselineEnd);
 if(!Number.isFinite(start)||!Number.isFinite(end)||start>end)throw Error('Período de referencia inválido');
 const samples=finiteSamples(series);
 const base=samples.filter(s=>Date.parse(s.date)>=start&&Date.parse(s.date)<=end);
 if(base.length<2)throw Error('Referencia insuficiente: se requieren al menos dos observaciones');
 const mean=base.reduce((sum,s)=>sum+(s.value as number),0)/base.length;
 return {series:{...series,samples:samples.map(s=>({...s,value:(s.value as number)-mean}))},warnings:['La anomalía usa una media simple, no corrige estacionalidad ni equivale a SPI/SPEI'],method:'Anomalía absoluta frente a media de '+base.length+' observaciones entre '+baselineStart+' y '+baselineEnd};
}
export function summarizeSeries(series:NumericSeries):{count:number;min:number|null;max:number|null;mean:number|null;first:string|null;last:string|null}{
 const samples=finiteSamples(series);const values=samples.map(s=>s.value as number);
 return {count:values.length,min:values.length?Math.min(...values):null,max:values.length?Math.max(...values):null,mean:values.length?values.reduce((a,b)=>a+b,0)/values.length:null,first:samples[0]?.date??null,last:samples[samples.length-1]?.date??null};
}
