/** Catálogo del Laboratorio Ambiental DOTS.
 * Los productos identificados como visualización no son simulaciones predictivas.
 */
export type ModuleStatus = 'visualizacion' | 'analisis' | 'requiere-modelo';
export type EnvironmentalModule = {
 id: string; title: string; group: string; status: ModuleStatus;
 parameters: readonly string[]; sources: readonly string[];
 output: string; caveat: string;
};
export const ENVIRONMENTAL_CATALOG: readonly EnvironmentalModule[] = [
 {id:'flood',title:'Inundaciones y crecidas',group:'Agua',status:'analisis',parameters:['agua detectada','nivel hidrométrico','área inundada','fecha','incertidumbre'],sources:['Sentinel-1','Copernicus GFM','INA'],output:'Evolución de extensión de agua',caveat:'El nivel en una estación no determina por sí solo el área inundada.'},
 {id:'vegetation',title:'Vegetación y cultivos',group:'Agro',status:'analisis',parameters:['NDVI','NDWI','cobertura','fecha','nubes'],sources:['Sentinel-2','Landsat','MODIS'],output:'Series de índices de vegetación',caveat:'NDVI no equivale directamente a rendimiento agrícola.'},
 {id:'drought',title:'Sequía y déficit hídrico',group:'Clima',status:'analisis',parameters:['precipitación','anomalía','humedad del suelo','evapotranspiración'],sources:['CHIRPS','ERA5-Land','SMAP'],output:'Anomalías y evolución temporal',caveat:'La resolución regional no representa necesariamente cada lote.'},
 {id:'fire',title:'Incendios y áreas quemadas',group:'Riesgo',status:'analisis',parameters:['focos térmicos','FRP','área quemada','viento','humedad'],sources:['NASA FIRMS','VIIRS','MODIS'],output:'Detecciones y cicatrices de incendio',caveat:'Focos térmicos no equivalen a perímetro ni a propagación futura.'},
 {id:'storms',title:'Lluvias, tormentas y granizo',group:'Clima',status:'visualizacion',parameters:['lluvia acumulada','intensidad','nubes','viento','alertas'],sources:['GPM IMERG','GOES','SMN'],output:'Secuencia de precipitación y nubosidad',caveat:'El granizo exige radar y/o observaciones; las nubes no prueban granizo.'},
 {id:'temperature',title:'Temperatura y olas de calor',group:'Clima',status:'visualizacion',parameters:['temperatura superficial','temperatura del aire','anomalías'],sources:['Landsat TIRS','MODIS','ERA5'],output:'Mapas de temperatura y anomalías',caveat:'La temperatura superficial no es la temperatura del aire.'},
 {id:'pasture',title:'Ganadería y pasturas',group:'Agro',status:'requiere-modelo',parameters:['vigor de pasturas','biomasa estimada','lluvia','estrés térmico'],sources:['Sentinel-2','NASA POWER','SMAP'],output:'Evolución de pasturas y escenarios',caveat:'La carga animal necesita calibración local y datos de campo.'},
 {id:'soil',title:'Humedad y condiciones del suelo',group:'Agro',status:'visualizacion',parameters:['humedad','textura','temperatura','pendiente'],sources:['SMAP','SoilGrids','ERA5-Land'],output:'Evolución de humedad',caveat:'SMAP tiene escala regional; no extrapolar a metros de parcela.'},
 {id:'landuse',title:'Deforestación y uso del suelo',group:'Territorio',status:'analisis',parameters:['cobertura','pérdida arbórea','transición de clases'],sources:['Landsat','Sentinel-2','MapBiomas'],output:'Comparación multianual',caveat:'Los cambios deben validarse con fechas y resolución equivalentes.'},
 {id:'erosion',title:'Erosión y sedimentación',group:'Agua',status:'requiere-modelo',parameters:['línea de costa','sedimentos','pendiente','caudal'],sources:['Sentinel-2','Landsat','DEM'],output:'Cambios morfológicos observados',caveat:'El transporte de sedimentos requiere calibración hidrodinámica.'},
 {id:'enso',title:'El Niño y La Niña',group:'Clima',status:'visualizacion',parameters:['anomalía SST','índices ENSO','precipitación regional'],sources:['NOAA','Copernicus C3S'],output:'Evolución de anomalías y teleconexiones',caveat:'ENSO no determina de forma aislada lluvias locales.'},
 {id:'wetlands',title:'Humedales y cuerpos de agua',group:'Territorio',status:'analisis',parameters:['agua permanente','agua estacional','vegetación','área'],sources:['JRC Global Surface Water','Sentinel-1','Landsat'],output:'Cambio histórico de agua y humedales',caveat:'Distinguir agua estacional de inundación extraordinaria.'},
];
export function modulesByGroup(): Record<string, EnvironmentalModule[]> {
 return ENVIRONMENTAL_CATALOG.reduce<Record<string, EnvironmentalModule[]>>((out,m)=>{(out[m.group] ??= []).push(m);return out;},{});
}
