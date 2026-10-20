/** Catálogo inicial extensible: fuentes candidatas, no conexiones verificadas. */
import type { VariableDefinition } from './environmentalEngine';
import { EnvironmentalEngine } from './environmentalEngine';
export const INITIAL_VARIABLES:readonly VariableDefinition[]=[
 {id:"precipitation",label:"Precipitación acumulada",unit:"mm",type:'scalar',support:'raster',sourceIds:["GPM IMERG","CHIRPS"]},
 {id:"rain_rate",label:"Intensidad de precipitación",unit:"mm/h",type:'scalar',support:'raster',sourceIds:["GPM IMERG"]},
 {id:"air_temperature",label:"Temperatura del aire",unit:"°C",type:'scalar',support:'raster',sourceIds:["ERA5","NASA POWER"]},
 {id:"surface_temperature",label:"Temperatura superficial",unit:"°C",type:'scalar',support:'raster',sourceIds:["Landsat","MODIS"]},
 {id:"soil_moisture",label:"Humedad del suelo",unit:"m³/m³",type:'scalar',support:'raster',sourceIds:["SMAP","ERA5-Land"]},
 {id:"relative_humidity",label:"Humedad relativa",unit:"%",type:'scalar',support:'raster',sourceIds:["ERA5"]},
 {id:"wind_speed",label:"Velocidad del viento",unit:"m/s",type:'scalar',support:'raster',sourceIds:["ERA5"]},
 {id:"wind_direction",label:"Dirección del viento",unit:"grados",type:'scalar',support:'raster',sourceIds:["ERA5"]},
 {id:"solar_radiation",label:"Radiación solar",unit:"W/m²",type:'scalar',support:'raster',sourceIds:["NASA POWER"]},
 {id:"evapotranspiration",label:"Evapotranspiración",unit:"mm",type:'scalar',support:'raster',sourceIds:["MODIS","ERA5-Land"]},
 {id:"ndvi",label:"Índice NDVI",unit:"índice",type:'index',support:'raster',sourceIds:["Sentinel-2","Landsat"]},
 {id:"ndwi",label:"Índice NDWI",unit:"índice",type:'index',support:'raster',sourceIds:["Sentinel-2","Landsat"]},
 {id:"evi",label:"Índice EVI",unit:"índice",type:'index',support:'raster',sourceIds:["MODIS","Sentinel-2"]},
 {id:"land_cover",label:"Cobertura del suelo",unit:"clase",type:'categorical',support:'raster',sourceIds:["ESA WorldCover","MapBiomas"]},
 {id:"tree_cover_loss",label:"Pérdida de cobertura arbórea",unit:"ha",type:'scalar',support:'polygon',sourceIds:["Global Forest Watch"]},
 {id:"surface_water",label:"Extensión de agua superficial",unit:"ha",type:'scalar',support:'polygon',sourceIds:["JRC GSW","Sentinel-1"]},
 {id:"flood_extent",label:"Extensión de inundación",unit:"ha",type:'scalar',support:'polygon',sourceIds:["Copernicus GFM"]},
 {id:"river_level",label:"Altura hidrométrica",unit:"m",type:'scalar',support:'timeseries',sourceIds:["INA","servicios nacionales"]},
 {id:"river_discharge",label:"Caudal fluvial",unit:"m³/s",type:'scalar',support:'timeseries',sourceIds:["INA","servicios nacionales"]},
 {id:"elevation",label:"Elevación",unit:"m",type:'scalar',support:'raster',sourceIds:["Copernicus DEM","ALOS"]},
 {id:"slope",label:"Pendiente",unit:"grados",type:'scalar',support:'raster',sourceIds:["DEM"]},
 {id:"thermal_hotspots",label:"Focos térmicos",unit:"conteo",type:'scalar',support:'point',sourceIds:["NASA FIRMS"]},
 {id:"fire_radiative_power",label:"Potencia radiativa del fuego",unit:"MW",type:'scalar',support:'point',sourceIds:["NASA FIRMS"]},
 {id:"burned_area",label:"Superficie quemada",unit:"ha",type:'scalar',support:'polygon',sourceIds:["MODIS","Sentinel-2"]},
 {id:"drought_anomaly",label:"Anomalía de sequía",unit:"índice",type:'index',support:'raster',sourceIds:["CHIRPS","ERA5"]},
 {id:"sst_anomaly",label:"Anomalía de temperatura oceánica",unit:"°C",type:'scalar',support:'raster',sourceIds:["NOAA"]},
 {id:"cloud_cover",label:"Cobertura nubosa",unit:"%",type:'scalar',support:'raster',sourceIds:["GOES","Sentinel-2"]},
 {id:"soil_texture",label:"Textura del suelo",unit:"clase",type:'categorical',support:'raster',sourceIds:["SoilGrids"]},
 {id:"sediment_turbidity",label:"Turbidez estimada",unit:"índice",type:'index',support:'raster',sourceIds:["Sentinel-2"]},
 {id:"pasture_biomass",label:"Biomasa de pastura estimada",unit:"kg/ha",type:'scalar',support:'raster',sourceIds:["modelo local"]},
 {id:"heat_stress",label:"Índice de estrés térmico",unit:"índice",type:'index',support:'raster',sourceIds:["modelo local"]},
 {id:"groundwater_level",label:"Nivel freático",unit:"m",type:'scalar',support:'timeseries',sourceIds:["redes nacionales"]},
];
export function createEnvironmentalEngine():EnvironmentalEngine {
 const engine=new EnvironmentalEngine();
 for(const variable of INITIAL_VARIABLES)engine.registerVariable(variable);
 return engine;
}
