/** Núcleo genérico de variables y simulaciones de DOTS Campo.
 * Separa definición de variables, proveedores de observaciones y modelos físicos.
 * No ejecuta modelos no registrados ni declara cobertura que no fue verificada.
 */
import type { ObservationKind, TemporalFrame } from './environmentalTimeline';

export type BBox = readonly [west:number,south:number,east:number,north:number];
export type VariableType = 'scalar'|'index'|'categorical'|'vector'|'geometry';
export type SpatialSupport = 'point'|'raster'|'polygon'|'timeseries';
export type VariableDefinition = {
 id:string; label:string; unit:string; type:VariableType; support:SpatialSupport;
 sourceIds:readonly string[]; description?:string; min?:number; max?:number;
};
export type SpatialRequest = {
 bbox:BBox; start:string; end:string; variableIds:readonly string[];
 countryCodes?:readonly string[]; resolutionMeters?:number;
};
export type Provider = {
 id:string; title:string; supportedVariables:readonly string[];
 getFrames(request:SpatialRequest):Promise<readonly TemporalFrame[]>;
};
export type SimulationDefinition = {
 id:string; label:string; inputs:readonly string[]; outputs:readonly string[];
 mode:'historical'|'statistical'|'physical'|'forecast';
 description:string; requiresCalibration:boolean;
};
export type SimulationResult = {
 modelId:string; kind:ObservationKind; frames:readonly TemporalFrame[];
 warnings:readonly string[]; inputSources:readonly string[];
};
export type SimulationExecutor = (request:SpatialRequest, inputs:ReadonlyMap<string,readonly TemporalFrame[]>)=>Promise<SimulationResult>;

const validId=(id:string)=>/^[a-z][a-z0-9_-]{1,63}$/.test(id);
const validDate=(d:string)=>/^\d{4}-\d{2}-\d{2}(T.*)?$/.test(d)&&Number.isFinite(Date.parse(d));
export function validateSpatialRequest(r:SpatialRequest):string[]{
 const errors:string[]=[];
 const [w,s,e,n]=r.bbox;
 if (![w,s,e,n].every(Number.isFinite)||w< -180||e>180||s< -90||n>90||w>=e||s>=n)errors.push('bbox inválido');
 if (!validDate(r.start)||!validDate(r.end)||Date.parse(r.start)>Date.parse(r.end))errors.push('período inválido');
 if (!r.variableIds.length||r.variableIds.some(v=>!validId(v)))errors.push('variables inválidas');
 if (r.resolutionMeters!==undefined&&(!Number.isFinite(r.resolutionMeters)||r.resolutionMeters<=0))errors.push('resolución inválida');
 if (r.countryCodes?.some(c=>!/^[A-Z]{2}$/.test(c)))errors.push('código de país inválido');
 return errors;
}
export class EnvironmentalEngine {
 private variables=new Map<string,VariableDefinition>();
 private providers=new Map<string,Provider>();
 private simulations=new Map<string,{definition:SimulationDefinition;execute:SimulationExecutor}>();
 registerVariable(variable:VariableDefinition):void{
  if(!validId(variable.id)||!variable.label.trim()||!variable.unit.trim())throw Error('Definición de variable inválida');
  if(this.variables.has(variable.id))throw Error('Variable duplicada: '+variable.id);
  this.variables.set(variable.id,variable);
 }
 registerProvider(provider:Provider):void{
  if(!validId(provider.id)||this.providers.has(provider.id))throw Error('Proveedor inválido o duplicado');
  this.providers.set(provider.id,provider);
 }
 registerSimulation(definition:SimulationDefinition,execute:SimulationExecutor):void{
  if(!validId(definition.id)||this.simulations.has(definition.id))throw Error('Modelo inválido o duplicado');
  if(!definition.inputs.length||!definition.outputs.length||[...definition.inputs,...definition.outputs].some(id=>!this.variables.has(id)))throw Error('Registrar todas las variables del modelo primero');
  this.simulations.set(definition.id,{definition,execute});
 }
 listVariables():VariableDefinition[]{return [...this.variables.values()];}
 listModels():SimulationDefinition[]{return [...this.simulations.values()].map(m=>m.definition);}
 listProviders():string[]{return [...this.providers.keys()];}
 async observations(request:SpatialRequest):Promise<{frames:TemporalFrame[];warnings:string[]}>{
  const errors=validateSpatialRequest(request);
  if(errors.length)throw Error(errors.join('; '));
  const missing=request.variableIds.filter(id=>!this.variables.has(id));
  if(missing.length)throw Error('Variables sin registrar: '+missing.join(', '));
  const candidates=[...this.providers.values()].filter(p=>request.variableIds.some(id=>p.supportedVariables.includes(id)));
  const results=await Promise.allSettled(candidates.map(p=>p.getFrames(request)));
  const frames:TemporalFrame[]=[];const warnings:string[]=[];
  results.forEach((result,i)=>{
   if(result.status==='rejected'){warnings.push(candidates[i].id+': error consultando fuente');return;}
   for(const frame of result.value){
    if(request.variableIds.includes(frame.variable)&&candidates[i].supportedVariables.includes(frame.variable)&&Date.parse(frame.acquiredAt)>=Date.parse(request.start)&&Date.parse(frame.acquiredAt)<=Date.parse(request.end))frames.push(frame);
   }
  });
  return {frames:frames.sort((a,b)=>Date.parse(a.acquiredAt)-Date.parse(b.acquiredAt)),warnings};
 }
 async run(modelId:string,request:SpatialRequest):Promise<SimulationResult>{
  const model=this.simulations.get(modelId);
  if(!model)throw Error('Modelo no implementado: '+modelId);
  const observations=await this.observations({...request,variableIds:model.definition.inputs});
  const inputs=new Map<string,readonly TemporalFrame[]>();
  for(const id of model.definition.inputs)inputs.set(id,observations.frames.filter(f=>f.variable===id));
  const missing=model.definition.inputs.filter(id=>!(inputs.get(id)?.length));
  if(missing.length)throw Error('Faltan datos reales para ejecutar '+modelId+': '+missing.join(', '));
  const result=await model.execute(request,inputs);
  return {...result,warnings:[...observations.warnings,...result.warnings]};
 }
}
export const SOUTH_AMERICA_COUNTRY_CODES=['AR','BO','BR','CL','CO','EC','GY','PY','PE','SR','UY','VE'] as const;
export const SOUTH_AMERICA_BBOX: BBox=[-82,-57,-34,14];
