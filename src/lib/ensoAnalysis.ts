/** Análisis ENSO de anomalías mensuales Niño 3.4.
 * Una serie de SST absoluta NO es una anomalía: primero debe corregirse
 * por climatología mensual y ponderarse espacialmente en el área Niño 3.4.
 * El promedio trimestral NO equivale automáticamente al ONI oficial NOAA.
 */
export type MonthlyAnomaly={month:string;anomalyC:number;source:string};
export type EnsoPoint={month:string;anomalyC:number;threeMonthMean:number|null;phase:"warm"|"cold"|"neutral"|"insufficient"};
const validMonth=(s:string)=>/^\d{4}-(0[1-9]|1[0-2])$/.test(s);
const serial=(s:string)=>Number(s.slice(0,4))*12+Number(s.slice(5,7));
export function calculateEnso(series:readonly MonthlyAnomaly[]):EnsoPoint[]{
 const ordered=[...series].sort((a,b)=>a.month.localeCompare(b.month));
 if(ordered.some(x=>!validMonth(x.month)||!Number.isFinite(x.anomalyC)||!x.source.trim()))throw Error("Anomalías mensuales inválidas");
 if(ordered.some((x,i)=>i>0&&serial(x.month)===serial(ordered[i-1].month)))throw Error("Mes duplicado");
 return ordered.map((p,i)=>{
  const previous=ordered.slice(Math.max(0,i-2),i+1);
  const contiguous=previous.length===3&&serial(previous[2].month)-serial(previous[0].month)===2;
  const mean=contiguous?previous.reduce((sum,x)=>sum+x.anomalyC,0)/3:null;
  return {...p,threeMonthMean:mean,phase:mean===null?"insufficient":mean>=0.5?"warm":mean<=-0.5?"cold":"neutral"};
 });
}
export function ensoEpisodes(points:readonly EnsoPoint[],minConsecutive=5){
 if(!Number.isInteger(minConsecutive)||minConsecutive<1)throw Error("Duración inválida");
 const episodes:{phase:"warm"|"cold";start:string;end:string;months:number}[]=[];
 let run:EnsoPoint[]=[];
 const flush=()=>{if(run.length>=minConsecutive)episodes.push({phase:run[0].phase as "warm"|"cold",start:run[0].month,end:run[run.length-1].month,months:run.length});run=[];};
 for(const p of points){
  if((p.phase==="warm"||p.phase==="cold")&&(!run.length||(run[run.length-1].phase===p.phase&&serial(p.month)-serial(run[run.length-1].month)===1)))run.push(p);
  else {flush();if(p.phase==="warm"||p.phase==="cold")run.push(p);}
 }
 flush();return episodes;
}
