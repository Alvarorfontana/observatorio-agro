/** Catálogo de proveedores climáticos. Una ficha NO implica conexión API operativa. */
export type ClimateProvider={id:string;name:string;url:string;category:string;use:string;access:"publico"|"registro"|"mixto";status:"referencia"};
export const CLIMATE_PROVIDERS:ClimateProvider[]=[
["chirps","CHIRPS","https://chc.ucsb.edu/data/chirps","Precipitación","Lluvias históricas y anomalías regionales","publico"],
["worldbank","World Bank Climate Change Knowledge Portal","https://climateknowledgeportal.worldbank.org","Riesgo climático","Perfiles nacionales y proyecciones","publico"],
["earthdata","NASA Earthdata","https://earthdata.nasa.gov","Satélites","MODIS, VIIRS y otros productos terrestres","mixto"],
["cds","Copernicus Climate Data Store","https://cds.climate.copernicus.eu","Reanálisis","ERA5 y proyecciones climáticas","registro"],
["power","NASA POWER","https://power.larc.nasa.gov","Agrometeorología","Radiación, temperatura y precipitación para lotes","publico"],
["era5","ECMWF ERA5","https://www.ecmwf.int/en/forecasts/dataset/ecmwf-reanalysis-v5","Reanálisis","Series horarias de atmósfera y superficie","registro"],
["sentinelhub","Sentinel Hub","https://www.sentinel-hub.com","Imágenes satelitales","Sentinel-1 SAR y Sentinel-2 óptico","registro"],
["usgs","USGS EarthExplorer","https://earthexplorer.usgs.gov","Imágenes satelitales","Landsat y archivos históricos","registro"],
["ghcn","NOAA GHCN","https://www.ncei.noaa.gov/products/land-based-station/global-historical-climatology-network-daily","Estaciones","Observaciones meteorológicas terrestres","publico"],
["gee","Google Earth Engine","https://earthengine.google.com","Procesamiento geoespacial","Catálogo y análisis remoto a escala","registro"],
["firms","NASA FIRMS","https://firms.modaps.eosdis.nasa.gov","Incendios","Detecciones térmicas MODIS y VIIRS","mixto"],
["cdr","NOAA Climate Data Records","https://www.ncei.noaa.gov/products/climate-data-records","Climatología","Registros climáticos satelitales de largo plazo","publico"],
["cmems","Copernicus Marine","https://marine.copernicus.eu","Océanos","SST, salinidad y nivel del mar","registro"],
["gfs","NOAA GFS","https://www.ncei.noaa.gov/products/weather-climate-models/global-forecast","Pronóstico","Pronóstico meteorológico numérico global","publico"],
["cmip6","CMIP6 ESGF","https://esgf-node.llnl.gov/search/cmip6/","Escenarios","Proyecciones de modelos climáticos, no observaciones","mixto"],
["argo","Argo Floats","https://argo.ucsd.edu","Océanos","Perfiles de temperatura y salinidad oceánica","publico"],
["fluxnet","FLUXNET","https://fluxnet.org","Ecosistemas","Flujos de carbono, agua y energía","mixto"],
["berkeley","Berkeley Earth","https://berkeleyearth.org/data/","Temperatura","Series históricas de temperatura terrestre","publico"]
].map(([id,name,url,category,use,access])=>({id,name,url,category,use,access:access as ClimateProvider["access"],status:"referencia" as const}));
