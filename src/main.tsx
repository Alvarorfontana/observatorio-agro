import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { EudrReadiness } from "./dashboard/EudrReadiness";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import * as echarts from "echarts/core";
import { LineChart, BarChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  MarkLineComponent,
  MarkAreaComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import {
  Satellite,
  MapPinned,
  LayoutDashboard,
  Hexagon,
  Square,
  Triangle,
  Flame,
  Beef,
  Sprout,
  Waves,
  CloudSun,
  CircleDot,
  Gauge,
  Settings,
  HelpCircle,
  Layers,
  Download,
  FileText,
  Droplets,
  Thermometer,
  TriangleAlert,
  Focus,
  Plus,
  Minus,
  Menu,
} from "lucide-react";
import "./styles.css";
import "./dashboard.css";
import "./site.css";
import "./theme-carbon.css";
import { ObsSidebar, MetricCards, buildNav } from "./dashboard/Shell";
import { MARKER_KINDS, markerIcon, kindOf, MarkerLegend } from "./dashboard/markers";
import { fieldAt, fieldsAround, compactness, FTW_ATTRIBUTION, FTW_RELIABLE } from "./dashboard/fields";
import { terrainForLot, terrainImage, DEM_ATTRIBUTION, DEM_SOURCE_URL, type TerrainAnalysis, type TerrainMode } from "./dashboard/terrain";
import { RISK_COLORS, DRAIN_COLOR } from "./dashboard/terrainCore";
import { VariablesPanel } from "./dashboard/VariablesPanel";
import { LotDashboard } from "./dashboard/LotDashboard";
import { OPEN_LAYERS, LAYER_GROUPS } from "./dashboard/openLayers";
import { GuideContent } from "./site/GuideContent";
import { CuencaPanel, AlertasTeaser, AlertasPortada } from "./site/CuencaPanel";
import { CultivosPanel } from "./site/Cultivos";
import { NdviExtra } from "./site/NdviExtra";
import { readLotFile, lotsToGeoJSON, lotsToKML } from "./dashboard/lotFiles";
echarts.use([
  MarkLineComponent,
  MarkAreaComponent,
  LineChart,
  BarChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  CanvasRenderer,
]);
type Data = Record<string, any>;
type Point = [number, number];
type Source = {
  status: "consultando" | "recibido" | "sin dato";
  payload?: Data;
  error?: string;
};
const RESEARCH = ["plataformas","sentinel-hub-ndvi","openeo-ndvi","gee-ndvi","inta-suelos-wms","aire","elevacion","ina","usgs","nasa-catalogo","productos-nasa","landsat","radar","copernicus-stac","cnes-stac","dlr-stac","deafrica-stac","firms","nasa-power-30","enso","era5-cds","sentinel-hub","noaa-cdo","usgs-m2m","nasa-earthdata","copernicus-marine","gee","openaq","gfw","aemet","eumetsat","jaxa","mosdac","kma","fengyun"];
const NDVI_VIEWS = ["ndvi","sentinel-hub-ndvi","openeo-ndvi","gee-ndvi"];
const GIBS_WMS = "https://gibs.earthdata.nasa.gov/wms/epsg3857/best/wms.cgi";
// Crecidas y focos de calor sólo se publican en coordenadas geográficas: se piden en EPSG:4326.
const GIBS_WMS_4326 = "https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi";
const FLOOD_CLASSES: [string,string][] = [["#00e5ff","Agua habitual"],["#ffd400","Anegamiento recurrente"],["#ff1a1a","Agua fuera de lo habitual"],["#9e9e9e","Sin dato"]];
const WORLDCOVER = "esa-worldcover-map-10m-2021-v2_map";
const WORLDCOVER_CLASSES: [string,string][] = [["#006400","Árboles / monte"],["#ffbb22","Arbustal"],["#ffff4c","Pastizal"],["#f096ff","Cultivo"],["#fa0000","Construido"],["#b4b4b4","Suelo desnudo"],["#0064c8","Agua"],["#0096a0","Humedal herbáceo"]];
const GIBS_LAYERS: [string,string,string,string?][] = [
  ["","Capas · ninguna",""],
  ["MODIS_Terra_NDVI_8Day","NDVI MODIS · 8 días · 250 m","Vegetación regional. Para el lote usar NDVI Sentinel-2 (10 m)."],
  ["MODIS_Terra_Land_Surface_Temp_Day","Temperatura de superficie · día · 1 km","Temperatura del suelo/canopeo, no del aire."],
  ["SMAP_L4_Analyzed_Surface_Soil_Moisture","Humedad de suelo SMAP · 9 km","Modelo asimilado, 0–5 cm. Escala regional."],
  ["IMERG_Precipitation_Rate","Lluvia GPM IMERG · 30 min","Tasa de lluvia satelital estimada, no pluviómetro."],
  ["GOES-East_ABI_Band13_Clean_Infrared","Nubes GOES-East · infrarrojo · 10 min","Satélite meteorológico geoestacionario: topes nubosos fríos = tormentas. Última imagen disponible."],
  ["MODIS_Combined_Flood_3-Day","Crecidas MODIS · 3 días · 250 m","Celeste: agua habitual · amarillo: anegamiento recurrente · rojo: agua fuera de lo habitual · gris: sin dato. Confirmar con la imagen del día: las sombras de nubes dan falsas detecciones.",GIBS_WMS_4326],
  ["VIIRS_Combined_Flood_3-Day","Crecidas VIIRS · 3 días · 375 m","Mismo producto con los satélites NOAA-20 y NOAA-21. Sirve de respaldo cuando MODIS no tiene pasada.",GIBS_WMS_4326],
  ["VIIRS_NOAA20_Thermal_Anomalies_375m_All","Focos de calor VIIRS · 375 m","Anomalías térmicas (quemas e incendios) detectadas por NOAA-20, último día disponible.",GIBS_WMS_4326],
  [WORLDCOVER,"Cobertura ESA WorldCover · 10 m","Árboles, pastizal, cultivo, agua y humedales (2021). Fuente: ESA / VITO Terrascope, CC-BY 4.0.","https://titiler.terrascope.be/wms"],
];
// Rangos de lectura para cada capa NASA: orientativos, para que cualquiera sepa qué está mirando.
const GIBS_RANGES: Record<string,{title:string;rows:[string,string][];note?:string}> = {
  "MODIS_Terra_NDVI_8Day":{title:"NDVI · vigor de la vegetación",rows:[["< 0,2","Suelo desnudo, agua o quemado"],["0,2 – 0,4","Pastizal seco o vegetación rala"],["0,4 – 0,6","Pastura o cultivo en crecimiento"],["> 0,6","Vegetación densa y activa"]]},
  "MODIS_Terra_Land_Surface_Temp_Day":{title:"Temperatura de la superficie · día",rows:[["< 15 °C","Superficie fresca"],["15 – 30 °C","Rango templado habitual"],["30 – 40 °C","Superficie caliente"],["> 40 °C","Muy caliente: suelo seco o desnudo"]],note:"Es la temperatura del suelo o canopeo, suele superar a la del aire."},
  "SMAP_L4_Analyzed_Surface_Soil_Moisture":{title:"Humedad del suelo · 0–5 cm",rows:[["< 0,15 m³/m³","Seco"],["0,15 – 0,30","Humedad intermedia"],["> 0,30","Húmedo, cerca de saturar"]],note:"El punto de saturación cambia con la textura del suelo."},
  "IMERG_Precipitation_Rate":{title:"Intensidad de lluvia",rows:[["< 2,5 mm/h","Débil"],["2,5 – 10 mm/h","Moderada"],["10 – 50 mm/h","Fuerte"],["> 50 mm/h","Muy fuerte"]],note:"Clasificación de la OMM. Estimación satelital, no pluviómetro."},
  "GOES-East_ABI_Band13_Clean_Infrared":{title:"Temperatura del tope de nubes",rows:[["> 0 °C","Suelo o nubes bajas"],["0 a −30 °C","Nubes medias"],["−30 a −50 °C","Nubes altas, posible lluvia"],["< −50 °C","Tormenta fuerte"]]},
  "VIIRS_NOAA20_Thermal_Anomalies_375m_All":{title:"Focos de calor",rows:[["Cada punto","Píxel de 375 m más caliente que su entorno"]],note:"No confirma un incendio: puede ser una quema, una chimenea o un techo caliente."},
};
const NATIONAL = ["smn", "inmet", "dmc", "eccc", "nws"];
const SOURCES = [
  ["plataformas","Matriz de conexiones","REST · STAC · WMS/WMTS · OAuth"],
  ["inta-suelos-wms","INTA Suelos · WMS","Argentina · conexión OGC"],
  ["aire","Aire · CAMS","Open-Meteo / Copernicus"],
  ["elevacion","Relieve del terreno","Open-Meteo / DEM"],
  ["ina","Río Paraná · Bella Vista","INA / estación elegida"],
  ["usgs","Agua · Estados Unidos","USGS / OGC"],
  ["nasa-catalogo","Productos MODIS","NASA / CMR catálogo"],
  ["productos-nasa","Inventario NASA","AppEEARS catálogo"],
  ["landsat","Escenas Landsat","Planetary Computer catálogo"],
  ["radar","Radar Sentinel-1","Copernicus catálogo"],
  ["copernicus-stac","Copernicus STAC oficial","Sentinel-1/2/3 · catálogo"],
  ["cnes-stac","CNES GEODES · Francia","STAC oficial"],
  ["dlr-stac","DLR EOC · Alemania","STAC oficial"],
  ["deafrica-stac","Digital Earth Africa","STAC/COG · cobertura África"],
  ["firms","Incendios · FIRMS","NASA / clave Vercel"],
  ["nasa-power-30","NASA POWER · 30 años","NASA / REST abierto"],
  ["enso","ENSO · consenso mundial","NOAA · IRI · WMO · JMA · BOM"],
  ["era5-cds","ERA5 / CDS","ECMWF · requiere CDS_API_KEY"],
  ["sentinel-hub-ndvi","NDVI · Sentinel Hub","Copernicus · CDSE OAuth2"],
  ["openeo-ndvi","NDVI · openEO","Copernicus · CDSE OAuth2"],
  ["gee-ndvi","NDVI histórico · Earth Engine","MODIS 250 m · proyecto Cloud"],
  ["sentinel-hub","Sentinel Hub · proceso","Copernicus · OAuth2 requerido"],
  ["noaa-cdo","NOAA CDO histórico","NOAA · token requerido"],
  ["usgs-m2m","USGS M2M / Landsat","USGS · cuenta/token"],
  ["nasa-earthdata","NASA Earthdata","NASA · token"],
  ["copernicus-marine","Copernicus Marine","SST/corrientes · cuenta"],
  ["gee","Google Earth Engine","procesamiento · proyecto Cloud"],
  ["openaq","OpenAQ v3","calidad de aire · API key"],
  ["gfw","Global Forest Watch","cambio de cobertura · API key"],
  ["aemet","AEMET OpenData","España · API key"],
  ["eumetsat","EUMETSAT","Meteosat · credencial"],
  ["jaxa","JAXA G-Portal","Japón · cuenta"],
  ["mosdac","ISRO MOSDAC","India · cuenta"],
  ["kma","KMA / GK2A","Corea · auth key"],
  ["fengyun","FengYun / CMA","China · cuenta"],
  ["variables", "Clima y suelo", "Open-Meteo"],
  ["modelos", "Comparar modelos globales", "Open-Meteo / 7 proveedores"],
  ["escenas", "Escenas satelitales", "Earth Search / Sentinel-2"],
  ["ndvi", "NDVI del lote", "Sentinel-2 10 m · Planetary Computer"],
  ["relieve", "Relieve y anegamiento", "Copernicus DEM 30 m · cálculo en el navegador"],
  ["historico", "Histórico reciente", "NASA POWER"],
  ["indices", "Índices agroclimáticos", "ERA5 · definiciones xclim/ETCCDI"],
  ["lluvia", "Lluvia observada y sequía", "CHIRPS · satélite + estaciones · SPI"],
  ["estadistica", "Probabilidades y tendencias", "Conjuntos ECMWF/GFS · ERA5 · SEAS5"],
  ["alertas", "Alertas del lote", "Reglas declaradas sobre fuentes verificadas"],
  ["forraje", "Pasto y carga", "Sentinel-2 + radiación · modelo de Monteith"],
  ["indices-espectrales", "Índices satelitales", "228 índices · Sentinel-2 · awesome-spectral-indices"],
  ["radar-agua", "Agua por radar", "Sentinel-1 · ve con nubes"],
  ["balance-agua", "Balance de agua y sequía", "ERA5 desde 1991 · lluvia − evapotranspiración"],
  ["costos", "Costos y logística", "OSRM · OpenStreetMap · DolarAPI · valores del productor"],
  ["sustentabilidad", "Deforestación y carbono", "Impact Observatory · ESA WorldCover · SoilGrids · IPCC"],
  ["teleconexiones", "El Niño y teleconexiones", "NOAA PSL · ENSO, SOI, AAO, TSA, PDO"],
  ["rios", "Ríos y caudales", "GloFAS / Open-Meteo"],
  ["humedad-nasa", "Humedad del suelo vs lo normal", "NASA POWER · MERRA-2"],
  ["suelo", "Nitrógeno del suelo", "ISRIC SoilGrids"],
  ["serie", "Clima de 20–30 años", "ERA5 / Open-Meteo"],
  ["proyeccion", "Proyección 2031–2040", "CMIP6 / MPI-ESM1-2-XR"],
  ["smn", "Estaciones · Argentina", "SMN / WIS2"],
  ["inmet", "Estaciones · Brasil", "INMET · METAR en tiempo real"],
  ["dmc", "Estaciones · Chile", "DMC · METAR en tiempo real"],
  ["eccc", "Estaciones · Canadá", "ECCC GeoMet"],
  ["nws", "Estaciones · EE.UU.", "NOAA / NWS"],
  ["metnorway", "Pronóstico · Noruega", "MET Norway directo"],];
const fmt = (v: unknown, n = 1) =>
  v !== null && v !== undefined && Number.isFinite(Number(v))
    ? Number(v).toLocaleString("es-AR", {
        minimumFractionDigits: n,
        maximumFractionDigits: n,
      })
    : "Sin dato";
const download = (blob: Blob, name: string) => {
  const url = URL.createObjectURL(blob),
    a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60000);
};
// NASA POWER mensual (30 años): normales por mes, serie anual y lectura en lenguaje llano.
// Claves YYYYMM; el mes 13 es el anual y se ignora. PRECTOTCORR viene en mm/día.
const MES = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"];
const MES_LARGO = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"];
function powerClimate(data: Data) {
  const par = data?.properties?.parameter || {}, fill = data?.header?.fill_value ?? -999;
  if (!par.T2M || !par.PRECTOTCORR) return null;
  const ok = (v: any) => typeof v === "number" && Number.isFinite(v) && v !== fill;
  const avg = (a: number[]) => a.length ? a.reduce((x, y) => x + y, 0) / a.length : null;
  const days = (y: number, m: number) => new Date(Date.UTC(y, m, 0)).getUTCDate();
  const tM: number[][] = MES.map(() => []), rM: number[][] = MES.map(() => []), radM: number[][] = MES.map(() => []);
  const years: Record<string, { rain: number; n: number; t: number[] }> = {};
  for (const k of Object.keys(par.T2M)) {
    const y = Number(k.slice(0, 4)), m = Number(k.slice(4, 6));
    if (m < 1 || m > 12) continue;
    const t = par.T2M[k], r = par.PRECTOTCORR[k], rad = par.ALLSKY_SFC_SW_DWN?.[k];
    const yr = (years[y] ??= { rain: 0, n: 0, t: [] });
    if (ok(t)) { tM[m - 1].push(t); yr.t.push(t); }
    if (ok(r)) { rM[m - 1].push(r * days(y, m)); yr.rain += r * days(y, m); yr.n++; }
    if (ok(rad)) radM[m - 1].push(rad);
  }
  const temp = tM.map(avg), rain = rM.map(avg), rad = radM.map(avg);
  if (temp.some(v => v == null) || rain.some(v => v == null)) return null;
  const T = temp as number[], R = rain as number[];
  const full = Object.keys(years).filter(y => years[y].n === 12 && years[y].t.length === 12).sort();
  const annualRain = full.map(y => Math.round(years[y].rain)), annualTemp = full.map(y => avg(years[y].t) as number);
  const rainYear = R.reduce((a, b) => a + b, 0), tYear = T.reduce((a, b) => a + b, 0) / 12;
  const iMax = (a: number[]) => a.indexOf(Math.max(...a)), iMin = (a: number[]) => a.indexOf(Math.min(...a));
  const wet = R.map((v, i) => v >= rainYear / 12 * 1.15 ? i : -1).filter(i => i >= 0);
  const dry = R.map((v, i) => v < rainYear / 12 * 0.6 ? i : -1).filter(i => i >= 0);
  const sortedRain = [...annualRain].sort((a, b) => a - b), medRain = sortedRain[Math.floor(sortedRain.length / 2)] ?? null;
  const dryYears = annualRain.filter(v => medRain != null && v < medRain * 0.75).length;
  const half = Math.floor(annualTemp.length / 2);
  const warming = annualTemp.length >= 20 ? (avg(annualTemp.slice(half)) as number) - (avg(annualTemp.slice(0, half)) as number) : null;
  const insights = [
    `Temperatura media anual de ${tYear.toFixed(1)} °C: ${MES_LARGO[iMax(T)]} es el mes más cálido (${T[iMax(T)].toFixed(1)} °C) y ${MES_LARGO[iMin(T)]} el más fresco (${T[iMin(T)].toFixed(1)} °C).`,
    `Llueven unos ${Math.round(rainYear)} mm por año. ${wet.length ? "Los meses más lluviosos son " + wet.map(i => MES_LARGO[i]).join(", ") + "." : "La lluvia se reparte bastante pareja en el año."}`,
    dry.length ? `Meses secos (menos del 60 % del promedio mensual): ${dry.map(i => MES_LARGO[i]).join(", ")}. Conviene planificar reservas de forraje y agua para ese período.` : "No hay meses claramente secos en el promedio; las sequías dependen del año.",
    medRain != null ? `En ${dryYears} de ${annualRain.length} años llovió menos del 75 % de lo habitual (${Math.round(medRain)} mm, mediana). Esa es la frecuencia de un año seco en el lugar.` : "",
    warming != null ? `La segunda mitad del período fue ${Math.abs(warming).toFixed(1)} °C ${warming >= 0 ? "más cálida" : "más fresca"} que la primera (comparación simple; la tendencia con prueba estadística está en Estadística del lote).` : "",
  ].filter(Boolean);
  const q = (a: number[], p: number) => { const b = [...a].sort((x, y) => x - y); return b.length ? b[Math.min(b.length - 1, Math.max(0, Math.round(p * (b.length - 1))))] : null; };
  const range = { rainLo: q(annualRain, .1), rainHi: q(annualRain, .9), rainMin: annualRain.length ? Math.min(...annualRain) : null, rainMax: annualRain.length ? Math.max(...annualRain) : null,
    tMin: Math.min(...T), tMax: Math.max(...T), rMonthMin: Math.min(...R), rMonthMax: Math.max(...R) };
  return { temp: T, rain: R, rad, years: full, annualRain, medRain, rainYear, tYear, insights, range, from: full[0], to: full[full.length - 1] };
}

function Chart({
  dates,
  series,
  unit,
}: {
  dates: string[];
  series: {
    name: string;
    values: (number | null)[];
    type?: "line" | "bar";
    color: string;
  }[];
  unit: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current, undefined, { renderer: "canvas" });
    // Colores desde el tema (claro u oscuro) y paleta DOTS unificada para todos los gráficos
    const css = getComputedStyle(ref.current);
    const v = (n: string, d: string) => css.getPropertyValue(n).trim() || d;
    const txt = v("--ta-text-2", "#c6c6c6"), txt3 = v("--ta-text-3", "#8d8d8d"), grid = v("--ta-border", "#333333"),
      tipBg = v("--ta-layer-2", "#393939"), tipTx = v("--ta-text", "#f4f4f4");
    const light = css.getPropertyValue("--ta-is-light").trim() === "1";
    const PAL: Record<string, [string, string]> = { // color viejo → [oscuro, claro]
      "#06b6d4": ["#33b1ff", "#0072c3"], "#19b98a": ["#3ddbd9", "#007d79"], "#22c55e": ["#42be65", "#198038"],
      "#e9bd72": ["#ff7eb6", "#d02670"], "#a7a5ff": ["#be95ff", "#8a3ffc"], "#b7c989": ["#8d8d8d", "#a8a8a8"],
      "#93c5fd": ["#78a9ff", "#4589ff"], "#57dce0": ["#3ddbd9", "#007d79"], "#f0b974": ["#ff7eb6", "#d02670"], "#fd9c91": ["#ff8389", "#da1e28"], "#e7a0db": ["#ff7eb6", "#9f1853"],
    };
    const col = (c: string) => (PAL[c?.toLowerCase()] || [c, c])[light ? 1 : 0];
    const many = dates.length > 24;
    chart.setOption({
      animation: false,
      textStyle: { fontFamily: "IBM Plex Sans", color: txt },
      tooltip: {
        trigger: "axis",
        backgroundColor: tipBg,
        borderWidth: 0,
        padding: [8, 10],
        textStyle: { color: tipTx, fontSize: 12 },
        axisPointer: { type: series.some(s => s.type === "bar") ? "shadow" : "line", lineStyle: { color: txt3 }, shadowStyle: { color: light ? "rgba(0,0,0,.05)" : "rgba(255,255,255,.05)" } },
        valueFormatter: (val: any) =>
          val === null || val === undefined ? "Sin dato" : fmt(val) + " " + unit,
      },
      legend: series.length > 1 ? { top: 0, right: 0, icon: "rect", itemWidth: 10, itemHeight: 10, itemGap: 14, textStyle: { color: txt, fontSize: 11 } } : undefined,
      grid: { left: 44, right: 12, top: series.length > 1 ? 36 : 16, bottom: 28 },
      xAxis: {
        type: "category",
        data: dates,
        axisLabel: { color: txt3, fontSize: 11, hideOverlap: true },
        axisLine: { lineStyle: { color: grid } },
        axisTick: { show: false },
      },
      yAxis: {
        type: "value",
        scale: true,
        splitNumber: 4,
        name: unit,
        nameTextStyle: { fontSize: 10, color: txt3, align: "left" },
        axisLabel: { color: txt3, fontSize: 11 },
        splitLine: { lineStyle: { color: grid } },
      },
      series: series.map((s) => ({
        name: s.name,
        type: s.type || "line",
        data: s.values,
        connectNulls: false,
        showSymbol: !many,
        symbolSize: 5,
        lineStyle: { width: 2 },
        itemStyle: { color: col(s.color) },
        ...(s.type !== "bar" && series.length === 1 ? { areaStyle: { color: col(s.color), opacity: 0.12 } } : {}),
        barMaxWidth: 18,
        emphasis: { focus: "series" },
      })),
    });
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(ref.current);
    return () => {
      observer.disconnect();
      chart.dispose();
    };
  }, [dates, series, unit]);
  return (
    <div
      className="chart-content"
      ref={ref}
      role="img"
      aria-label={series.map((s) => s.name).join(", ") + " en " + unit}
    />
  );
}
function annual(data: Data) {
  const daily = data?.daily || {},
    times: string[] = daily.time || [],
    groups: Record<string, { n: number; t: number[]; p: number[] }> = {};
  times.forEach((date, i) => {
    const year = date.slice(0, 4),
      g = (groups[year] ??= { n: 0, t: [], p: [] });
    g.n++;
    const t = daily.temperature_2m_mean?.[i],
      p = daily.precipitation_sum?.[i];
    if (t !== null && t !== undefined && Number.isFinite(t)) g.t.push(t);
    if (p !== null && p !== undefined && Number.isFinite(p)) g.p.push(p);
  });
  const years = Object.keys(groups).sort();
  return {
    years,
    temp: years.map((y) => {
      const expected =
          (Date.UTC(Number(y) + 1, 0, 1) - Date.UTC(Number(y), 0, 1)) /
          86400000,
        g = groups[y];
      return g.t.length === expected
        ? g.t.reduce((s, v) => s + v, 0) / g.t.length
        : null;
    }),
    rain: years.map((y) => {
      const expected =
          (Date.UTC(Number(y) + 1, 0, 1) - Date.UTC(Number(y), 0, 1)) /
          86400000,
        g = groups[y];
      return g.p.length === expected ? g.p.reduce((s, v) => s + v, 0) : null;
    }),
  };
}
function centroid(v: Point[]): Point {
  let a = 0,
    x = 0,
    y = 0;
  const cos = Math.cos(
    ((v.reduce((s, p) => s + p[0], 0) / v.length) * Math.PI) / 180,
  );
  for (let i = 0; i < v.length; i++) {
    const p = v[i],
      q = v[(i + 1) % v.length],
      c = p[1] * cos * q[0] - q[1] * cos * p[0];
    a += c;
    x += (p[1] + q[1]) * cos * c;
    y += (p[0] + q[0]) * c;
  }
  if (Math.abs(a) < 1e-10) throw Error("El lote no tiene superficie");
  return [y / (3 * a), x / (3 * a) / cos];
}
function untangle(v: Point[]): Point[] {
  const cy = v.reduce((a, p) => a + p[0], 0) / v.length, cx = v.reduce((a, p) => a + p[1], 0) / v.length;
  return [...v].sort((a, b) => Math.atan2(a[0] - cy, a[1] - cx) - Math.atan2(b[0] - cy, b[1] - cx));
}
function crosses(v: Point[]) {
  const o = (a: Point, b: Point, c: Point) =>
    (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
  const on = (a: Point, b: Point, p: Point) =>
    p[0] >= Math.min(a[0], b[0]) &&
    p[0] <= Math.max(a[0], b[0]) &&
    p[1] >= Math.min(a[1], b[1]) &&
    p[1] <= Math.max(a[1], b[1]);
  for (let i = 0; i < v.length; i++)
    for (let j = i + 1; j < v.length; j++) {
      if (j === i + 1 || (i === 0 && j === v.length - 1)) continue;
      const a = v[i],
        b = v[(i + 1) % v.length],
        c = v[j],
        d = v[(j + 1) % v.length],
        p = o(a, b, c),
        q = o(a, b, d),
        r = o(c, d, a),
        s = o(c, d, b);
      if (
        (p * q < 0 && r * s < 0) ||
        (p === 0 && on(a, b, c)) ||
        (q === 0 && on(a, b, d)) ||
        (r === 0 && on(c, d, a)) ||
        (s === 0 && on(c, d, b))
      )
        return true;
    }
  return false;
}
function Observatory({onHome}:{onHome:()=>void}) {
  const [point, setPoint] = useState<Point>([-28.507, -59.043]),
    [coords, setCoords] = useState(["-28.507", "-59.043"]),
    [sources, setSources] = useState<Record<string, Source>>({}),
    [view, setView] = useState("variables"),
    [years, setYears] = useState(30),
    [inaSeries,setInaSeries] = useState("22"),
    [usgsSite,setUsgsSite] = useState(""),
    [date, setDate] = useState(
      new Date(Date.now() - 2 * 86400000).toISOString().slice(0, 10),
    ),
    [layer, setLayer] = useState("base"),
    [gibsLayer, setGibsLayer] = useState(""),
    [openBase, setOpenBase] = useState<string>(() => { try { return localStorage.getItem("dots-open-base") || ""; } catch { return ""; } }),
    [openOver, setOpenOver] = useState<string>(() => { try { return localStorage.getItem("dots-open-over") || ""; } catch { return ""; } }),
    [openOpacity, setOpenOpacity] = useState(0.75),
    [toast, setToast] = useState(""),
    [vertices, setVertices] = useState<Point[]>([]),
    [drawing, setDrawing] = useState(false),
    [pdfBusy, setPdfBusy] = useState(false),
    [agentPrompt, setAgentPrompt] = useState("Haceme un informe integral de este lote"),
    [agentBusy, setAgentBusy] = useState(false),
    [agentResult, setAgentResult] = useState<Data | null>(null),
    [agentOpen, setAgentOpen] = useState(false),
    [placeQuery,setPlaceQuery] = useState(""),
    [placeLabel,setPlaceLabel] = useState("Bella Vista, Corrientes, Argentina"),
    [placeBusy,setPlaceBusy] = useState(false),
    [waterAssets,setWaterAssets] = useState<Data[]>([]),
    [waterType,setWaterType] = useState("bebedero"),
    [drawMode,setDrawMode] = useState<"free"|"triangle"|"rectangle">("free"),
    [fieldMarkers,setFieldMarkers] = useState<Data[]>([]),
    [markerType,setMarkerType] = useState("observación"),
    [placingMarker,setPlacingMarker] = useState(false),
    [lots,setLots] = useState<Array<{id:string;name:string;vertices:Point[];center:Point;areaHa:number;perimeterKm:number;compactness?:number|null;ftw?:any}>>([]),
    [selectedLotId,setSelectedLotId] = useState<string | null>(null);
  const mapEl = useRef<HTMLDivElement>(null),
    mapRef = useRef<L.Map | null>(null),
    marker = useRef<L.CircleMarker | null>(null),
    poly = useRef<L.Polygon | null>(null),
    line = useRef<L.Polyline | null>(null),
    vertexMarkers = useRef<L.CircleMarker[]>([]),
    currentPoints = useRef<Point[]>([]),
    drawingRef = useRef(false),
    drawModeRef = useRef<"free"|"triangle"|"rectangle">("free"),
    finishRef = useRef<(() => void) | null>(null),
    sketchRef = useRef<(() => void) | null>(null),
    generation = useRef(0),
    controllers = useRef<Record<string, AbortController>>({}),
    noticeTimer = useRef<ReturnType<typeof setTimeout> | null>(null),
    lotLayers = useRef<Record<string,L.Polygon>>({}),
    placingMarkerRef = useRef(false),
    ftwPickRef = useRef<((lat:number,lon:number)=>void)|null>(null),
    ftwLayer = useRef<L.LayerGroup|null>(null),
    ftwMoveRef = useRef<(()=>void)|null>(null),
    fieldMarkerLayers = useRef<L.Marker[]>([]),
    waterLayers = useRef<L.Marker[]>([]),
    markerTypeRef = useRef("observación");
  useEffect(()=>{markerTypeRef.current=markerType},[markerType]);
  useEffect(()=>{
    try { const saved=localStorage.getItem("dots-field-state"); if(saved){const x=JSON.parse(saved); if(Array.isArray(x.fieldMarkers))setFieldMarkers(x.fieldMarkers); if(Array.isArray(x.waterAssets))setWaterAssets(x.waterAssets);} } catch {}
  },[]);
  useEffect(()=>{ try{localStorage.setItem("dots-field-state",JSON.stringify({fieldMarkers,waterAssets}))}catch{} },[fieldMarkers,waterAssets]);
  const notify = (s: string) => {
    setToast(s);
    if (noticeTimer.current) clearTimeout(noticeTimer.current);
    noticeTimer.current = setTimeout(() => setToast(""), 6500);
  };
  async function load(key: string, p: Point = point, y = years, station = inaSeries, waterSite = usgsSite) {
    controllers.current[key]?.abort();
    const controller = new AbortController();
    controllers.current[key] = controller;
    const currentGeneration = generation.current;
    setSources((prev) => ({ ...prev, [key]: { status: "consultando" } }));
    const timer = setTimeout(() => controller.abort(), 60000);
    try {
      const r = await fetch(
        "/api/fuentes/" +
          key +
          "?" +
          new URLSearchParams({
            lat: String(p[0]),
            lon: String(p[1]),
            years: String(y),
            ...(key === "ina" ? {series:station,days:station==="22"?"30":"2"} : {}),
            ...(key === "usgs" && waterSite ? {site:waterSite} : {}),
            ...(key === "sustentabilidad" ? {heads:String(herdHeads||0)} : {}),
            ...(vertices.length >= 3 ? {polygon: JSON.stringify(vertices)} : {}),
          }),
        { signal: controller.signal },
      );
      if (!r.ok) {const failure=await r.json().catch(()=>({}));throw Error(failure.error || "La fuente no respondió (" + r.status + ")");}
      const payload = await r.json();
      if (
        currentGeneration === generation.current &&
        controllers.current[key] === controller
      )
        setSources((prev) => ({
          ...prev,
          [key]: { status: "recibido", payload },
        }));
    } catch (e) {
      if (
        currentGeneration === generation.current &&
        controllers.current[key] === controller
      )
        setSources((prev) => ({
          ...prev,
          [key]: {
            status: "sin dato",
            error: e instanceof Error ? e.message : "Sin respuesta",
          },
        }));
    } finally {
      clearTimeout(timer);
    }
  }
  useEffect(() => {
    generation.current++;
    Object.values(controllers.current).forEach((c) => c.abort());
    setSources({});
    ["variables", "escenas", "historico", "rios"].forEach(
      (k) => void load(k, point),
    );
    if (["suelo", "serie", "proyeccion", "modelos", "metnorway", ...NATIONAL, ...RESEARCH].includes(view))
      void load(view, point);
    return () => Object.values(controllers.current).forEach((c) => c.abort());
  }, [point]);
  useEffect(() => {
    if (!mapEl.current) return;
    const map = L.map(mapEl.current, { zoomControl: false }).setView(point, 13);
    mapRef.current = map;
    if ((import.meta as any).env?.DEV) (window as any).__dotsMap = map; // sólo pruebas locales
    const base = L.tileLayer("/api/fuentes/tile?z={z}&y={y}&x={x}", {
      maxNativeZoom: 19,
      tileSize: 512,
      zoomOffset: -1,
      maxZoom: 19,
      attribution:
        "Tiles © Esri — Esri, Maxar, Earthstar Geographics, GIS User Community",
    }).addTo(map);
    let good = 0,
      errors = 0;
    base.on("tileload", () => good++);
    base.on("tileerror", () => {
      if (++errors === 6 && !good)
        notify(
          "La cartografía externa no respondió. Podés seguir consultando los datos.",
        );
    });
    marker.current = L.circleMarker(point, {
      radius: 5,
      color: "#57dce0",
      fillOpacity: 1,
    })
      .addTo(map)
      .bindTooltip("PUNTO DE CONSULTA", { permanent: true, direction: "top" });
    L.control.scale({ imperial: false }).addTo(map);
    map.on("click", (e) => {
      if (ftwPickRef.current) { ftwPickRef.current(e.latlng.lat, e.latlng.lng); return; }
      if (placingMarkerRef.current) {
        const type=markerTypeRef.current;
        const item={id:`m-${Date.now()}`,type,lat:e.latlng.lat,lon:e.latlng.lng,status:type==="agua"?"DECLARADO / CONFIRMAR EN CAMPO":"OBSERVACIÓN MANUAL",source:"usuario",provenance:"DECLARADO",confidence:"usuario",observed_at:new Date().toISOString()};
        setFieldMarkers(v=>[...v,item]);
        placingMarkerRef.current=false; setPlacingMarker(false); map.getContainer().style.cursor="";
        return;
      }
      if (!drawingRef.current) return;
      const pts = currentPoints.current, here = map.latLngToContainerPoint(e.latlng);
      const px = (p: Point) => map.latLngToContainerPoint(L.latLng(p[0], p[1])).distanceTo(here);
      // tocar el primer punto cierra el lote; un clic encima del último (doble clic) no suma un vértice repetido
      if (pts.length >= 3 && px(pts[0]) < 16) { finishRef.current?.(); return; }
      if (pts.length && px(pts[pts.length - 1]) < 8) return;
      currentPoints.current = [...pts, [e.latlng.lat, e.latlng.lng]];
      setVertices([...currentPoints.current]);
      sketchRef.current?.();
      const n = currentPoints.current.length, mode = drawModeRef.current;
      if ((mode === "triangle" && n === 3) || (mode === "rectangle" && n === 2)) finishRef.current?.();
    });
    map.on("dblclick", () => { if (drawingRef.current && currentPoints.current.length >= 3) finishRef.current?.(); });
    const observer = new ResizeObserver(() => map.invalidateSize());
    observer.observe(mapEl.current);
    return () => {
      observer.disconnect();
      map.remove();
      mapRef.current = null;
    };
  }, []);
  useEffect(() => {
    marker.current?.setLatLng(point);
    mapRef.current?.panTo(point);
  }, [point]);
  useEffect(() => {
    if (layer === "base" || !mapRef.current) return;
    const overlay = L.tileLayer(
      `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/MODIS_Terra_CorrectedReflectance_TrueColor/default/${date}/GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpg`,
      { maxNativeZoom: 9, maxZoom: 19, attribution: "NASA GIBS / MODIS Terra" },
    ).addTo(mapRef.current);
    let warned = false;
    overlay.on("tileerror", () => {
      if (!warned) {
        warned = true;
        notify("NASA no devolvió imágenes para esta fecha. Probá otro día.");
      }
    });
    return () => {
      overlay.remove();
    };
  }, [layer, date]);
  // Capas abiertas del catálogo (xyzservices + curadas): una de base y una superpuesta
  const openTile = (id: string, opacity: number, pane?: string) => {
    const l = OPEN_LAYERS.find(x => x.id === id); if (!l || !mapRef.current) return null;
    const url = l.dated ? l.url.replace("{time}", date) : l.url;
    const t = L.tileLayer(url, { maxZoom: 19, maxNativeZoom: l.maxNativeZoom ?? Math.min(l.maxZoom, 19), tms: !!l.tms,
      subdomains: l.subdomains || "abc", opacity, attribution: l.attribution, pane, crossOrigin: true } as L.TileLayerOptions).addTo(mapRef.current);
    let warned = false;
    t.on("tileerror", () => { if (!warned) { warned = true; notify(`${l.name}: el servidor no devolvió imágenes aquí${l.dated ? " para esa fecha" : ""}.`); } });
    return t;
  };
  useEffect(() => {
    try { localStorage.setItem("dots-open-base", openBase); } catch {}
    if (!openBase) return;
    const t = openTile(openBase, 1); if (!t) return;
    t.bringToBack(); t.setZIndex(1);
    return () => { t.remove(); };
  }, [openBase, date]);
  useEffect(() => {
    try { localStorage.setItem("dots-open-over", openOver); } catch {}
    if (!openOver) return;
    const t = openTile(openOver, openOpacity); if (!t) return;
    t.setZIndex(400);
    return () => { t.remove(); };
  }, [openOver, openOpacity, date]);
  useEffect(() => {
    if (!gibsLayer || !mapRef.current) return;
    // WMS sin TIME: GIBS devuelve la última fecha disponible de cada capa.
    const cfg = GIBS_LAYERS.find(([k])=>k===gibsLayer);
    const isWC = gibsLayer === WORLDCOVER;
    const wms = L.tileLayer.wms(cfg?.[3] || GIBS_WMS, {
      layers: gibsLayer, format: "image/png", transparent: true, opacity: isWC ? .6 : gibsLayer.includes("Flood") ? .85 : .7,
      ...(cfg?.[3] === GIBS_WMS_4326 ? { crs: L.CRS.EPSG4326 } : {}),
      attribution: isWC ? "ESA WorldCover 2021 / VITO Terrascope (CC-BY 4.0)" : "NASA GIBS / EOSDIS",
    } as L.WMSOptions).addTo(mapRef.current);
    let warned = false;
    wms.on("tileerror", () => { if (!warned) { warned = true; notify(gibsLayer===WORLDCOVER?"Terrascope no devolvió la capa WorldCover. Probá más tarde.":"NASA GIBS no devolvió esta capa ahora. Probá más tarde u otra capa."); } });
    return () => { wms.remove(); };
  }, [gibsLayer]);
  useEffect(() => {
    const d = (sources.lluvia?.payload as any)?.data;
    if (!d?.job || d.status !== "en proceso") return;
    const t = setTimeout(async () => {
      try {
        const r = await fetch(`/api/fuentes/lluvia?${new URLSearchParams({ lat: String(point[0]), lon: String(point[1]), job: d.job })}`);
        const j = await r.json();
        if (!r.ok) throw Error(j.error || "ClimateSERV no respondió");
        setSources(prev => ({ ...prev, lluvia: { status: j.status === "sin dato" ? "sin dato" : "recibido", payload: j, error: j.error } }));
      } catch (e) { setSources(prev => ({ ...prev, lluvia: { status: "sin dato", error: (e as Error).message } })); }
    }, 5000);
    return () => clearTimeout(t);
  }, [sources.lluvia]);
  const [alertsData, setAlertsData] = useState<any>(null);
  const [alertsBusy, setAlertsBusy] = useState(false);
  const loadAlerts = async () => {
    setAlertsBusy(true);
    try {
      const data = (k: string) => (sources[k]?.payload as any)?.data;
      const r = await fetch("/api/fuentes/alertas", { method: "POST", headers: { "Content-Type": "application/json" }, signal: AbortSignal.timeout(55000),
        body: JSON.stringify({ lat: point[0], lon: point[1], polygon: vertices.length >= 3 ? vertices : null,
          known: { estadistica: data("estadistica"), alertas: alertsData, forraje: data("forraje")?.growth_rate_30d!=null ? data("forraje") : null, sustentabilidad: data("sustentabilidad"), lluvia: data("lluvia")?.spi ? data("lluvia") : null, ndvi: data("ndvi"), firms: data("firms") ?? null } }) });
      const j = await r.json();
      if (!r.ok) throw Error(j.error || "No se pudieron evaluar las alertas");
      setAlertsData(j.data);
    } catch (e) { notify((e as Error).message); } finally { setAlertsBusy(false); }
  };
  useEffect(() => { void loadAlerts(); }, [point[0], point[1], vertices.length]);
  const [forageKind, setForageKind] = useState("pastizal");
  const [forageUse, setForageUse] = useState(0.5);
  const loadForage = async () => {
    if (vertices.length < 3) { setSources(p => ({ ...p, forraje: { status: "sin dato", error: "Dibujá un lote para estimar el pasto" } })); return; }
    setSources(p => ({ ...p, forraje: { status: "consultando" } }));
    try {
      const r = await fetch("/api/fuentes/forraje", { method: "POST", headers: { "Content-Type": "application/json" }, signal: AbortSignal.timeout(58000),
        body: JSON.stringify({ lat: point[0], lon: point[1], polygon: vertices, kind: forageKind, use: forageUse, heads: herdHeads || null,
          ndvi: (sources.ndvi?.payload as any)?.data?.series ? (sources.ndvi?.payload as any).data : null }) });
      const j = await r.json();
      if (!r.ok) throw Error(j.error || "No se pudo estimar");
      setSources(p => ({ ...p, forraje: { status: "recibido", payload: j } }));
    } catch (e) { setSources(p => ({ ...p, forraje: { status: "sin dato", error: (e as Error).message } })); }
  };
  const COST_FIELDS: [string, string, string][] = [
    ["heads","Cabezas a vender",""],["sale_kg","Peso de venta","kg/cab"],["price_kg","Precio","$/kg vivo"],
    ["shrink_pct","Desbaste","%"],["commission_pct","Comisión","%"],["health_head","Sanidad","$/cab/año"],
    ["feed_head","Suplemento","$/cab/año"],["other_head","Otros por cabeza","$/cab/año"],["labor_month","Mano de obra","$/mes"],
    ["rent_ha","Arrendamiento","$/ha/año"],["structure_ha","Estructura","$/ha/año"],["freight_km","Tarifa de flete","$/km por jaula"],["truck_heads","Capacidad de la jaula","cabezas"]];
  const [costParams, setCostParams] = useState<Record<string, string>>(() => { try { return JSON.parse(localStorage.getItem("dots-costs") || "{}"); } catch { return {}; } });
  const [costDest, setCostDest] = useState<string>(() => { try { return localStorage.getItem("dots-cost-dest") || ""; } catch { return ""; } });
  const setCost = (k: string, v: string) => setCostParams(p => { const n = { ...p, [k]: v }; try { localStorage.setItem("dots-costs", JSON.stringify(n)); } catch {} return n; });
  const loadCosts = async () => {
    setSources(p => ({ ...p, costos: { status: "consultando" } }));
    try {
      const params: Record<string, number> = {};
      Object.entries(costParams).forEach(([k, v]) => { if (v !== "" && v != null && Number.isFinite(Number(v))) params[k] = Number(v); });
      if (params.heads == null && herdHeads) params.heads = herdHeads;
      if (lotAreaHa) params.area_ha = Math.round(lotAreaHa * 10) / 10;
      const r = await fetch("/api/fuentes/costos", { method: "POST", headers: { "Content-Type": "application/json" }, signal: AbortSignal.timeout(45000),
        body: JSON.stringify({ lat: point[0], lon: point[1], destination: costDest || null, params }) });
      const j = await r.json();
      if (!r.ok) throw Error(j.error || "No se pudo calcular");
      setSources(p => ({ ...p, costos: { status: j.status, payload: j } }));
    } catch (e) { setSources(p => ({ ...p, costos: { status: "sin dato", error: (e as Error).message } })); }
  };
  const routeLine = useRef<L.Polyline | null>(null);
  useEffect(() => {
    routeLine.current?.remove(); routeLine.current = null;
    const lg = (sources.costos?.payload as any)?.data?.logistics;
    if (!mapRef.current || view !== "costos" || !lg?.line?.length) return;
    const pl = L.polyline(lg.line, { color: "#f79009", weight: 4, opacity: .9, dashArray: lg.estimated ? "8 8" : undefined }).addTo(mapRef.current);
    L.circleMarker([lg.destination.lat, lg.destination.lon], { radius: 7, color: "#b54708", fillColor: "#f79009", fillOpacity: 1 }).bindTooltip(lg.destination.name).addTo(pl as any);
    mapRef.current.fitBounds(pl.getBounds(), { padding: [30, 30] });
    routeLine.current = pl;
    return () => { pl.remove(); };
  }, [sources.costos, view]);
  const [estName, setEstName] = useState<string>(() => { try { return localStorage.getItem("dots-establishment") || ""; } catch { return ""; } });
  const [coverYear, setCoverYear] = useState<number | null>(null);
  const [eudrBusy, setEudrBusy] = useState(false);
  const coverOverlay = useRef<L.ImageOverlay | null>(null);
  const currentLot = () => { const l = lots.find(x => x.id === selectedLotId); return l ? { name: l.name, vertices: l.vertices, areaHa: l.areaHa, perimeterKm: l.perimeterKm, ftw: l.ftw } : (vertices.length >= 3 ? { name: "Lote", vertices, areaHa: lotAreaHa, perimeterKm: lotPerimeterKm } : null); };
  const eudrReady = useRef<any>(null);
  const [whisp, setWhisp] = useState<any>(null), [whispBusy, setWhispBusy] = useState(false);
  const askWhisp = async (product: string) => {
    const lot = currentLot(); if (!lot) { notify("Dibujá o seleccioná un lote primero."); return; }
    setWhispBusy(true); setWhisp(null);
    try {
      let token: string | undefined;
      for (let i = 0; i < 4; i++) {
        const r = await fetch("/api/fuentes/eudr/whisp", { method: "POST", headers: { "Content-Type": "application/json" }, signal: AbortSignal.timeout(58000),
          body: JSON.stringify(token ? { token, product } : { lot, product }) });
        const j = await r.json().catch(() => ({}));
        if (!r.ok) { setWhisp({ error: j.error || "Whisp no respondió." }); return; }
        if (j.data?.status === "en proceso" && j.data?.token) { token = j.data.token; continue; }
        setWhisp(j.data?.status === "requiere credencial" ? { status: "requiere credencial" } : j.data); return;
      }
      setWhisp({ error: "Whisp sigue procesando. Probá de nuevo en unos minutos." });
    } catch { setWhisp({ error: "Whisp no respondió." }); } finally { setWhispBusy(false); }
  };
  const eudrDownload = async (kind: "pdf" | "geojson") => {
    const lot = currentLot(); if (!lot) { notify("Dibujá o seleccioná un lote primero."); return; }
    setEudrBusy(true);
    try {
      const r = await fetch(`/api/fuentes/eudr/${kind}`, { method: "POST", headers: { "Content-Type": "application/json" }, signal: AbortSignal.timeout(58000),
        body: JSON.stringify({ lot, establecimiento: estName, heads: herdHeads || null, sustentabilidad: (sources.sustentabilidad?.payload as any)?.data, readiness: eudrReady.current }) });
      if (!r.ok) { const j = await r.json().catch(() => ({})); throw Error(j.error || "No se pudo generar"); }
      download(await r.blob(), kind === "pdf" ? "DOTS-libre-de-deforestacion.pdf" : "DOTS-lote-geolocalizacion.geojson");
    } catch (e) { notify((e as Error).message); } finally { setEudrBusy(false); }
  };
  useEffect(() => {
    coverOverlay.current?.remove(); coverOverlay.current = null;
    const ser = (sources.sustentabilidad?.payload as any)?.data?.deforestation?.series || [];
    const row = ser.find((r: any) => r.year === coverYear);
    if (!mapRef.current || view !== "sustentabilidad" || !row?.item || vertices.length < 3) return;
    const lats = vertices.map(v => v[0]), lons = vertices.map(v => v[1]);
    const url = "/api/fuentes/cobertura-imagen?" + new URLSearchParams({ lat: String(point[0]), lon: String(point[1]), item: row.item, polygon: JSON.stringify(vertices) });
    const ov = L.imageOverlay(url, [[Math.min(...lats), Math.min(...lons)], [Math.max(...lats), Math.max(...lons)]], { opacity: .85, interactive: false }).addTo(mapRef.current);
    ov.on("error", () => notify("No se pudo dibujar la cobertura de ese año."));
    coverOverlay.current = ov;
    return () => { ov.remove(); };
  }, [coverYear, sources.sustentabilidad, view, vertices]);
  const [showNdvi, setShowNdvi] = useState(true);
  const [overlayMode, setOverlayMode] = useState<"ndvi"|"rgb">("ndvi");
  const [navCollapsed, setNavCollapsed] = useState(() => typeof window !== "undefined" && window.innerWidth < 1800);
  const [navOpen, setNavOpen] = useState(false);
  const [ftwMode, setFtwMode] = useState(false);
  const [herdHeads, setHerdHeads] = useState<number>(() => { try { return Number(localStorage.getItem("dots-heads") || 0); } catch { return 0; } });
  const [ftwBusy, setFtwBusy] = useState(false);
  const [sideTab, setSideTab] = useState<"lote" | "datos" | "asistente">("lote");
  const [srcQuery, setSrcQuery] = useState("");
  const [mainView, setMainView] = useState<"mapa" | "tablero">(() => { try { return localStorage.getItem("dots-vista") === "mapa" ? "mapa" : "tablero"; } catch { return "tablero"; } });
  useEffect(() => { try { localStorage.setItem("dots-vista", mainView); } catch {} if (mainView === "mapa") setTimeout(() => mapRef.current?.invalidateSize(), 50); }, [mainView]);
  const [theme, setTheme] = useState<"oscuro" | "claro">(() => { try { return localStorage.getItem("dots-theme") === "claro" ? "claro" : "oscuro"; } catch { return "oscuro"; } });
  useEffect(() => { try { localStorage.setItem("dots-theme", theme); } catch {} }, [theme]);
  const ndviOverlay = useRef<L.ImageOverlay | null>(null);
  // Línea de tiempo NDVI (como el Time Slider de GeoLibre): recorre las escenas válidas del lote.
  const ndviValid: Data[] = ((sources.ndvi?.payload as any)?.data?.series || []).filter((r: Data) => r.status === "válida" && r.item);
  const [ndviPick, setNdviPick] = useState<number | null>(null);
  const [ndviPlay, setNdviPlay] = useState(false);
  const ndviIdx = ndviPick == null || ndviPick >= ndviValid.length ? ndviValid.length - 1 : ndviPick;
  useEffect(() => { setNdviPick(null); setNdviPlay(false); }, [sources.ndvi]);
  useEffect(() => {
    if (!ndviPlay || ndviValid.length < 2) return;
    const t = setInterval(() => setNdviPick(i => ((i ?? ndviValid.length - 1) + 1) % ndviValid.length), 2200);
    return () => clearInterval(t);
  }, [ndviPlay, ndviValid.length]);
  useEffect(() => {
    ndviOverlay.current?.remove(); ndviOverlay.current = null;
    const latest = ndviValid[ndviIdx] || (sources.ndvi?.payload as any)?.data?.latest;
    if (!mapRef.current || !showNdvi || view !== "ndvi" || !String(latest?.item||"").startsWith("S2") || vertices.length < 3) return;
    const lats = vertices.map(v=>v[0]), lons = vertices.map(v=>v[1]);
    const bounds: L.LatLngBoundsExpression = [[Math.min(...lats), Math.min(...lons)], [Math.max(...lats), Math.max(...lons)]];
    const url = "/api/fuentes/ndvi-imagen?" + new URLSearchParams({lat:String(point[0]),lon:String(point[1]),item:latest.item,baseline:String(latest.processing_baseline||""),mode:overlayMode,polygon:JSON.stringify(vertices)});
    const ov = L.imageOverlay(url, bounds, {opacity: .85, interactive: false}).addTo(mapRef.current);
    ov.on("error", () => notify("La imagen NDVI no se pudo recortar al lote. Los valores del panel siguen siendo válidos."));
    ndviOverlay.current = ov;
    return () => { ov.remove(); };
  }, [sources.ndvi, showNdvi, view, vertices, overlayMode, ndviIdx]);
  // Relieve y anegamiento: DEM Copernicus leído y procesado en el navegador (enfoque GeoLibre/Whitebox).
  const terrainRef = useRef<{ key: string; a: TerrainAnalysis } | null>(null);
  const terrainCtl = useRef<AbortController | null>(null);
  const terrainOverlay = useRef<L.ImageOverlay | null>(null);
  const [terrainMode, setTerrainMode] = useState<TerrainMode | "off">("anegamiento");
  const [terrainTick, setTerrainTick] = useState(0);
  const lotKey = JSON.stringify(vertices);
  const loadTerrain = async () => {
    if (vertices.length < 3) { setSources(p => ({ ...p, relieve: { status: "sin dato", error: "Dibujá o seleccioná un lote para analizar su relieve" } })); return; }
    terrainCtl.current?.abort();
    const ctl = new AbortController(); terrainCtl.current = ctl;
    const key = lotKey, poly = vertices;
    setSources(p => ({ ...p, relieve: { status: "consultando" } }));
    try {
      const a = await terrainForLot(poly, ctl.signal);
      if (terrainCtl.current !== ctl) return;
      terrainRef.current = { key, a };
      setSources(p => ({ ...p, relieve: { status: "recibido", payload: { data: { ...a.summary, lot: key }, consulted_at: new Date().toISOString(), source_url: DEM_SOURCE_URL } } }));
      setTerrainTick(t => t + 1);
    } catch (e) {
      if (terrainCtl.current !== ctl || ctl.signal.aborted) return;
      setSources(p => ({ ...p, relieve: { status: "sin dato", error: (e as Error).message } }));
    }
  };
  useEffect(() => {
    terrainOverlay.current?.remove(); terrainOverlay.current = null;
    const t = terrainRef.current;
    if (!mapRef.current || view !== "relieve" || terrainMode === "off" || !t || t.key !== lotKey) return;
    const { url, bounds } = terrainImage(t.a, terrainMode);
    const ov = L.imageOverlay(url, bounds, { opacity: .78, interactive: false, className: "pixel-layer" }).addTo(mapRef.current);
    terrainOverlay.current = ov;
    return () => { ov.remove(); };
  }, [terrainTick, terrainMode, view, lotKey]);
  // En la vista Tablero, con un lote elegido, se piden solos los datos del lote (una vez por lote)
  useEffect(() => {
    if (mainView !== "tablero" || vertices.length < 3) return;
    const t = setTimeout(() => {
      const want = ["ndvi", "lluvia", "humedad-nasa"].filter(k => !sources[k]);
      const needTerrain = !sources.relieve && terrainRef.current?.key !== lotKey;
      if (!want.length && !needTerrain) return;
      want.forEach(k => void load(k));
      if (needTerrain) void loadTerrain();
    }, 600);
    return () => clearTimeout(t);
  }, [mainView, lotKey, !!sources.ndvi, !!sources.lluvia, !!sources.relieve, !!sources["humedad-nasa"]]);
  const changeView = (key: string) => {
    // Always refresh: source results are spatial/temporal and must follow the currently selected lot.
    // Reusing an old payload after changing polygon was a functional bug in earlier versions.
    setView(key);
    setSideTab("datos");
    if (key === "alertas") { void loadAlerts(); } else if (key === "forraje") { void loadForage(); } else if (key === "relieve") { void loadTerrain(); } else if (key === "costos") { void loadCosts(); } else void load(key);
    requestAnimationFrame(() => { const el = document.getElementById("dots-detail"); const side = el?.closest(".sidebar") as HTMLElement | null; if (el && side) side.scrollTo({ top: Math.max(0, el.offsetTop - side.offsetTop - 16), behavior: "smooth" }); });
  };
  const addFieldMarker = (type = markerType) => {
    if (!mapRef.current) return;
    markerTypeRef.current=type; placingMarkerRef.current=true; setPlacingMarker(true);
    drawingRef.current=false; setDrawing(false);
    mapRef.current.getContainer().style.cursor="crosshair";
    notify(`Marcador ${type}: hacé clic en la ubicación exacta dentro del lote.`);
  };
  useEffect(()=>{
    fieldMarkerLayers.current.forEach(m=>m.remove()); fieldMarkerLayers.current=[];
    if(!mapRef.current)return;
    fieldMarkers.forEach((m:any)=>{
      const k=kindOf(m.type);
      const cm=L.marker([m.lat,m.lon],{icon:markerIcon(m.type,{satellite:m.source==="NASA FIRMS"}),riseOnHover:true}).addTo(mapRef.current!);
      cm.bindPopup(`<b>${k.label}</b><br>${m.provenance||"DECLARADO"}<br>${m.status||""}<br>Fuente: ${m.source||""}<br>Confianza: ${m.confidence||"s/d"}`); fieldMarkerLayers.current.push(cm);
    });
  },[fieldMarkers]);
  useEffect(()=>{
    waterLayers.current.forEach(m=>m.remove()); waterLayers.current=[];
    if(!mapRef.current)return;
    waterAssets.forEach((a:any)=>{ if(a.lat==null||a.lon==null)return;
      const mk=L.marker([a.lat,a.lon],{icon:markerIcon(a.type),riseOnHover:true}).addTo(mapRef.current!);
      mk.bindTooltip(`${kindOf(a.type).label} · ${a.type}`,{direction:"top"}); waterLayers.current.push(mk); });
  },[waterAssets]);
  useEffect(()=>{
    const det=(sources.firms?.payload as any)?.data?.detections; if(!Array.isArray(det))return;
    setFieldMarkers(prev=>{const manual=prev.filter((m:any)=>m.source!=="NASA FIRMS"); const auto=det.slice(0,150).map((r:any,i:number)=>({id:`firms-${r.latitude}-${r.longitude}-${i}`,type:"incendio",lat:Number(r.latitude),lon:Number(r.longitude),status:`${r.inside_lot===true?"DENTRO DEL LOTE":"ENTORNO"} · ${r.satellite||r.instrument||"VIIRS"} · ${r.acq_date||""} ${r.acq_time||""} · FRP ${r.frp||"s/d"}`,source:"NASA FIRMS",provenance:"SATELITAL",confidence:r.confidence||"s/d",observed_at:`${r.acq_date||""} ${r.acq_time||""}`})).filter((m:any)=>Number.isFinite(m.lat)&&Number.isFinite(m.lon)); return [...manual,...auto]});
  },[sources.firms]);
  // Boceto en vivo: el lote se ve cerrado desde el tercer punto; el primer punto, grande, cierra al tocarlo
  const drawSketch = () => {
    const map = mapRef.current; if (!map) return;
    line.current?.remove(); line.current = null;
    vertexMarkers.current.forEach(m => m.remove()); vertexMarkers.current = [];
    const pts = currentPoints.current;
    if (pts.length >= 3) line.current = L.polygon(pts, { color: "#57dce0", weight: 2, dashArray: "6,5", fillColor: "#57dce0", fillOpacity: 0.15 }).addTo(map) as unknown as L.Polyline;
    else if (pts.length === 2) line.current = L.polyline(pts, { color: "#57dce0", weight: 2, dashArray: "6,5" }).addTo(map);
    pts.forEach((p, i) => {
      const first = i === 0 && pts.length >= 3;
      const vm = L.circleMarker(L.latLng(p[0], p[1]), { radius: first ? 10 : 6, color: "#071820", weight: 2, fillColor: first ? "#ffd166" : "#57dce0", fillOpacity: 1 }).addTo(map);
      vm.bindTooltip(first ? "Tocá acá para cerrar" : String(i + 1), { permanent: true, direction: first ? "top" : "center", className: first ? "vertex-close" : "vertex-label" });
      if (first) vm.on("click", (ev) => { L.DomEvent.stop(ev); finishRef.current?.(); });
      vertexMarkers.current.push(vm);
    });
  };
  sketchRef.current = drawSketch;
  const undoPoint = () => {
    if (!currentPoints.current.length) return;
    currentPoints.current = currentPoints.current.slice(0, -1);
    setVertices([...currentPoints.current]); drawSketch();
  };
  useEffect(() => {
    if (!drawing) return;
    const k = (e: KeyboardEvent) => {
      if (e.key === "Backspace" || (e.key.toLowerCase() === "z" && (e.ctrlKey || e.metaKey))) { e.preventDefault(); undoPoint(); }
      else if (e.key === "Enter" && currentPoints.current.length >= 3) finishRef.current?.();
      else if (e.key === "Escape") stopDraw();
    };
    addEventListener("keydown", k); return () => removeEventListener("keydown", k);
  }, [drawing]);
  const startDraw = (mode:"free"|"triangle"|"rectangle"="free") => {
    setMainView("mapa");
    setDrawMode(mode); drawModeRef.current = mode;
    mapRef.current?.doubleClickZoom.disable();
    poly.current = null;
    setSelectedLotId(null);
    line.current?.remove();
    currentPoints.current = [];
    vertexMarkers.current.forEach(m=>m.remove()); vertexMarkers.current=[];
    setVertices([]);
    setDrawing(true);
    drawingRef.current = true;
    mapRef.current!.getContainer().style.cursor = "crosshair";
  };
  const stopDraw = () => {
    setDrawing(false);
    drawingRef.current = false;
    line.current?.remove();
    line.current = null;
    vertexMarkers.current.forEach(m => m.remove()); vertexMarkers.current = [];
    mapRef.current?.doubleClickZoom.enable();
    if (mapRef.current) mapRef.current.getContainer().style.cursor = "";
  };
  const drawLotLayer = (id: string, name: string, points: Point[], center: Point) => {
    const layer=L.polygon(points,{color:"#57dce0",fillOpacity:.12,weight:2}).addTo(mapRef.current!).bindTooltip(name,{permanent:true,direction:"center"});
    layer.on("click",()=>{ setSelectedLotId(id); setVertices(points); currentPoints.current=points; poly.current=layer; setPoint(center); setCoords(center.map(v=>v.toFixed(6))); mapRef.current?.fitBounds(layer.getBounds(),{padding:[40,40]}); });
    lotLayers.current[id]=layer;
    return layer;
  };
  const removeLot = (id: string) => {
    const l = lots.find(x => x.id === id); if (!l) return;
    if (!window.confirm(`¿Borrar "${l.name}" de este navegador? Antes podés descargarlo en KML.`)) return;
    lotLayers.current[id]?.remove(); delete lotLayers.current[id];
    setLots(prev => prev.filter(x => x.id !== id));
    if (selectedLotId === id) { setSelectedLotId(null); poly.current = null; currentPoints.current = []; setVertices([]); }
    notify(`${l.name} borrado.`);
    if (cloudOn && cloudKey) void syncLots([id]);
  };
  // Nube: lotes guardados en el repositorio privado de datos y resultados del procesamiento semanal (geoai)
  const [cloudOn, setCloudOn] = useState<boolean | null>(null);
  const [cloudKey, setCloudKey] = useState<string>(() => { try { return localStorage.getItem("dots-clave") || ""; } catch { return ""; } });
  const [cloudBusy, setCloudBusy] = useState(false);
  const [cloudMsg, setCloudMsg] = useState("");
  const [water, setWater] = useState<Record<string, any>>({});
  useEffect(() => { fetch("/api/lotes/estado").then(r => r.ok ? r.json() : null).then(j => setCloudOn(!!j?.configured)).catch(() => setCloudOn(false)); }, []);
  useEffect(() => { try { localStorage.setItem("dots-clave", cloudKey); } catch {} }, [cloudKey]);
  const syncLots = async (remove: string[] = []) => {
    if (!cloudKey) { setCloudMsg("Escribí la clave del establecimiento."); return; }
    setCloudBusy(true); setCloudMsg("");
    try {
      const r = await fetch("/api/lotes/sincronizar", { method: "POST", headers: { "Content-Type": "application/json", "X-DOTS-Key": cloudKey },
        body: JSON.stringify({ lotes: lots.map(l => ({ id: l.id, name: l.name, vertices: l.vertices, areaHa: l.areaHa })), quitar: remove }) });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw Error(j.error || "No se pudo guardar");
      setCloudMsg(`Guardado: ${j.lotes} lote${j.lotes === 1 ? "" : "s"} en el procesamiento semanal. Los resultados aparecen después del próximo lunes.`);
    } catch (e) { setCloudMsg((e as Error).message); } finally { setCloudBusy(false); }
  };
  useEffect(() => {
    const id = selectedLotId; if (!id || !cloudOn || !cloudKey || water[id]) return;
    fetch(`/api/lotes/resultado?id=${encodeURIComponent(id)}`, { headers: { "X-DOTS-Key": cloudKey } })
      .then(async r => { const j = await r.json().catch(() => ({})); setWater(w => ({ ...w, [id]: r.ok ? j : { status: "sin dato", error: j.error } })); })
      .catch(() => setWater(w => ({ ...w, [id]: { status: "sin dato", error: "Sin conexión" } })));
  }, [selectedLotId, cloudOn, cloudKey]);
  const waterLayer = useRef<L.GeoJSON | null>(null);
  useEffect(() => {
    waterLayer.current?.remove(); waterLayer.current = null;
    const w = selectedLotId ? water[selectedLotId] : null;
    if (!mapRef.current || mainView !== "mapa" || !w?.water_geojson?.features?.length) return;
    waterLayer.current = L.geoJSON(w.water_geojson, { style: { color: "#33b1ff", weight: 1.5, fillColor: "#33b1ff", fillOpacity: 0.45 }, interactive: false }).addTo(mapRef.current);
    return () => { waterLayer.current?.remove(); };
  }, [water, selectedLotId, mainView]);

  // Los lotes quedan guardados en este navegador: sobreviven a recargar la página.
  const lotsRestored = useRef(false);
  useEffect(() => {
    if (lotsRestored.current || !mapRef.current) return;
    lotsRestored.current = true;
    try {
      const saved = JSON.parse(localStorage.getItem("dots-lotes") || "[]");
      if (!Array.isArray(saved) || !saved.length) return;
      const ok = saved.filter((l: any) => l && typeof l.id === "string" && Array.isArray(l.vertices) && l.vertices.length >= 3 && Array.isArray(l.center));
      ok.forEach((l: any) => drawLotLayer(l.id, l.name, l.vertices, l.center));
      setLots(ok);
    } catch {}
  }, []);
  useEffect(() => {
    if (!lotsRestored.current) return;
    try { localStorage.setItem("dots-lotes", JSON.stringify(lots)); } catch {}
  }, [lots]);
  const finish = (given?: Point[], origin?: string, ftw?: any, label?: string) => {
    try {
      let points = given ?? currentPoints.current;
      if(!given && drawMode==="triangle" && points.length!==3) throw Error("Triángulo: marcá exactamente 3 vértices.");
      if(!given && drawMode==="rectangle" && points.length!==2 && points.length!==4) throw Error("Rectángulo: marcá 2 esquinas opuestas o 4 vértices.");
      if(!given && drawMode==="rectangle" && points.length===2){const a=points[0],b=points[1];points=[a,[a[0],b[1]],b,[b[0],a[1]]];currentPoints.current=points;setVertices(points);}
      let reordered = false;
      points = points.filter((p, i) => points.findIndex(q => q[0] === p[0] && q[1] === p[1]) === i);   // sin vértices repetidos
      if(points.length<3) throw Error("Marcá al menos 3 vértices para cerrar el lote.");
      if (crosses(points)) {
        const fixed = untangle(points);
        if (crosses(fixed)) throw Error("Los lados se cruzan. Usá «Deshacer punto» y marcá las esquinas en orden, recorriendo el borde.");
        points = fixed; currentPoints.current = points; setVertices(points); reordered = true;
      }
      const center = centroid(points);
      const areaHa = (()=>{ const R=6378137,lat0=points.reduce((a,p)=>a+p[0],0)/points.length*Math.PI/180,xy=points.map(([la,lo])=>[R*lo*Math.PI/180*Math.cos(lat0),R*la*Math.PI/180]);let a=0;for(let i=0;i<xy.length;i++){const j=(i+1)%xy.length;a+=xy[i][0]*xy[j][1]-xy[j][0]*xy[i][1]}return Math.abs(a)/2/10000;})();
      const perimeterKm = (()=>{const rad=(x:number)=>x*Math.PI/180,R=6371;let d=0;for(let i=0;i<points.length;i++){const a=points[i],b=points[(i+1)%points.length],dl=rad(b[0]-a[0]),dn=rad(b[1]-a[1]);const h=Math.sin(dl/2)**2+Math.cos(rad(a[0]))*Math.cos(rad(b[0]))*Math.sin(dn/2)**2;d+=2*R*Math.asin(Math.sqrt(h))}return d;})();
      const id=`lote-${Date.now()}-${Math.random().toString(36).slice(2,7)}`;
      const name=label || `Lote ${lots.length+1}${origin?" · "+origin:""}`;
      if(given){currentPoints.current=points;setVertices(points);}
      const layer=drawLotLayer(id,name,points,center);
      poly.current=layer;
      if(given) mapRef.current?.fitBounds(layer.getBounds(),{padding:[60,60],maxZoom:16});
      setLots(prev=>[...prev,{id,name,vertices:[...points],center,areaHa,perimeterKm,compactness:compactness(areaHa,perimeterKm),ftw}]);
      setSelectedLotId(id);
      stopDraw();
      setCoords(center.map((v) => v.toFixed(6)));
      setPoint(center);
      notify(`${name} guardado · ${areaHa.toFixed(2)} ha · ${perimeterKm.toFixed(2)} km de perímetro.${reordered ? " Reordené los puntos para que los lados no se crucen: revisá el contorno." : ""}`);
    } catch (e) {
      notify((e as Error).message);
    }
  };
  finishRef.current = () => finish();

  const importLots = async (file?: File | null) => {
    if (!file || !mapRef.current) return;
    try {
      const found = await readLotFile(file);
      let ok = 0, bad = 0;
      const bounds = L.latLngBounds([]);
      for (const f of found) {
        if (f.polygon.length < 3 || crosses(f.polygon as Point[])) { bad++; continue; }
        finish(f.polygon as Point[], "importado", undefined, f.name);
        f.polygon.forEach(p => bounds.extend(p)); ok++;
      }
      if (ok) mapRef.current.fitBounds(bounds, { padding: [40, 40], maxZoom: 16 });
      notify(`${ok} lote${ok === 1 ? "" : "s"} importado${ok === 1 ? "" : "s"} de ${file.name}${bad ? ` · ${bad} con lados cruzados no se cargaron` : ""}.`);
    } catch (e) { notify((e as Error).message || "No se pudo leer el archivo."); }
  };
  const selectLot = (id: string) => {
    const l = lots.find(x => x.id === id); if (!l) return;
    setSelectedLotId(l.id); setVertices(l.vertices); currentPoints.current = l.vertices; poly.current = lotLayers.current[l.id];
    setPoint(l.center); setCoords(l.center.map(v => v.toFixed(6)));
    mapRef.current?.fitBounds(lotLayers.current[l.id].getBounds(), { padding: [40, 40] });
  };
  const exportLots = (kind: "geojson" | "kml") => {
    if (!lots.length) { notify("Todavía no hay lotes para descargar."); return; }
    const rows = lots.map(l => ({ name: l.name, vertices: l.vertices, areaHa: l.areaHa, perimeterKm: l.perimeterKm, origin: l.ftw ? "Fields of the World" : undefined }));
    const title = estName ? `Lotes · ${estName}` : "Lotes DOTS Campo";
    if (kind === "kml") download(new Blob([lotsToKML(rows, title)], { type: "application/vnd.google-earth.kml+xml" }), "DOTS-lotes.kml");
    else download(new Blob([lotsToGeoJSON(rows)], { type: "application/geo+json" }), "DOTS-lotes.geojson");
  };
  const clearFtw = () => { ftwLayer.current?.remove(); ftwLayer.current = null; };
  const showFtwAround = async (lat:number, lon:number) => {
    if (!mapRef.current || mapRef.current.getZoom() < 12) { clearFtw(); return; }
    try {
      const feats = await fieldsAround(lat, lon);
      clearFtw();
      if (!ftwPickRef.current || !mapRef.current) return;
      const g = L.layerGroup();
      feats.forEach(f => f.geom.forEach(poly => {
        const conf = f.props.confidence == null ? null : Number(f.props.confidence);
        L.polygon(poly.map(r => r.map(([x, y]) => [y, x] as [number, number])), {
          color: conf != null && conf >= FTW_RELIABLE ? "#32d583" : "#fdb022", weight: 1.2, fillOpacity: .08, dashArray: "4,3", interactive: false,
        }).addTo(g);
      }));
      ftwLayer.current = g.addTo(mapRef.current);
      if (!feats.length) notify("Fields of the World no tiene lotes en esta zona. Suele faltar en pasturas: dibujalo a mano.");
    } catch { notify("No se pudo leer el mapa de lotes de Fields of the World. Revisá la conexión e intentá de nuevo."); }
  };
  const stopFtw = () => {
    ftwPickRef.current = null; setFtwMode(false); clearFtw();
    if (ftwMoveRef.current) mapRef.current?.off("moveend", ftwMoveRef.current);
    ftwMoveRef.current = null;
    if (mapRef.current) mapRef.current.getContainer().style.cursor = "";
  };
  const startFtw = () => {
    if (!mapRef.current) return;
    setMainView("mapa");
    stopDraw(); setFtwMode(true);
    const map = mapRef.current;
    if (map.getZoom() < 13) map.setZoom(14);
    map.getContainer().style.cursor = "crosshair";
    ftwPickRef.current = async (lat, lon) => {
      setFtwBusy(true);
      try {
        const f = await fieldAt(lat, lon);
        if (!f) { notify("No hay un lote de Fields of the World en ese punto. Tocá dentro de un contorno sugerido o dibujalo a mano."); return; }
        stopFtw();
        finish(f.polygon as Point[], "FTW", {confidence:f.confidence, reliable:f.reliable, areaHa:f.areaHa, neighborhood:f.neighborhood, source:"Fields of the World 2025"});
        notify(`Lote tomado de Fields of the World · ${f.areaHa!=null?f.areaHa.toFixed(1)+" ha":""} · confianza ${f.confidence!=null?Math.round(f.confidence):"sin dato"}${f.reliable?"":" (baja: revisá el borde)"}. Podés redibujarlo si no coincide.`);
      } catch { notify("No se pudo leer el mapa de lotes. Intentá de nuevo o dibujalo a mano."); }
      finally { setFtwBusy(false); }
    };
    const onMove = () => { const c = map.getCenter(); void showFtwAround(c.lat, c.lng); };
    ftwMoveRef.current = onMove; map.on("moveend", onMove);
    onMove();
  };
  async function searchPlace() {
    if (!placeQuery.trim()) return;
    setPlaceBusy(true);
    try {
      const r=await fetch('/api/fuentes/geocode?q='+encodeURIComponent(placeQuery.trim()),{signal:AbortSignal.timeout(20000)});
      const data=await r.json(); if(!r.ok||!data.results?.length) throw Error(data.error||'No se encontró la localidad');
      const x=data.results[0], p:[number,number]=[Number(x.lat),Number(x.lon)];
      setPoint(p); setCoords([String(x.lat),String(x.lon)]); setPlaceLabel(x.display_name||placeQuery);
      mapRef.current?.setView(p,13); notify('Mapa centrado en '+(x.display_name||placeQuery));
    } catch(e){notify((e as Error).message)} finally {setPlaceBusy(false)}
  }
  const lotAreaHa = (()=>{ if(vertices.length<3)return null; const R=6378137, lat0=vertices.reduce((a,p)=>a+p[0],0)/vertices.length*Math.PI/180; const xy=vertices.map(([la,lo])=>[R*lo*Math.PI/180*Math.cos(lat0),R*la*Math.PI/180]); let a=0; for(let i=0;i<xy.length;i++){const j=(i+1)%xy.length;a+=xy[i][0]*xy[j][1]-xy[j][0]*xy[i][1]} return Math.abs(a)/2/10000; })();
  const lotPerimeterKm = (()=>{ if(vertices.length<2)return null; const rad=(x:number)=>x*Math.PI/180,R=6371; let d=0; for(let i=0;i<vertices.length;i++){const a=vertices[i],b=vertices[(i+1)%vertices.length],dl=rad(b[0]-a[0]),dn=rad(b[1]-a[1]);const h=Math.sin(dl/2)**2+Math.cos(rad(a[0]))*Math.cos(rad(b[0]))*Math.sin(dn/2)**2;d+=2*R*Math.asin(Math.sqrt(h))}return d; })();
  async function askDots(prompt = agentPrompt) {
    setAgentBusy(true);
    setAgentResult(null);
    try {
      const r = await fetch("/api/fuentes/agentic", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lat: point[0], lon: point[1], prompt, polygon: poly.current ? vertices : null, inaSeries, waterAssets, fieldMarkers, known: reportExtras() }),
        signal: AbortSignal.timeout(60000),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw Error(data.error || "DOTS Agentic no respondió");
      setAgentResult(data);
      setAgentOpen(true);
      setAgentPrompt(prompt);
      notify("Análisis Agentic completado con trazabilidad de fuentes.");
    } catch (e) { notify((e as Error).message); } finally { setAgentBusy(false); }
  }
  const reportExtras = () => {
    const l = lots.find(x => x.id === selectedLotId);
    const data = (k: string) => (sources[k]?.payload as any)?.data;
    return {
      lot: l ? { name: l.name, areaHa: l.areaHa, perimeterKm: l.perimeterKm, compactness: l.compactness, ftw: l.ftw, vertices: l.vertices } : null,
      ndvi: data("ndvi"), indices: data("indices"), telecon: data("teleconexiones"), clima: data("variables"), lluvia: data("lluvia")?.spi ? data("lluvia") : null, estadistica: data("estadistica"),
      alertas: alertsData, forraje: data("forraje")?.growth_rate_30d != null ? data("forraje") : null, sustentabilidad: data("sustentabilidad"),
      relieve: data("relieve")?.lot === JSON.stringify(vertices) ? data("relieve") : null,
      agua: selectedLotId && water[selectedLotId]?.status === "recibido" ? water[selectedLotId] : null,
      humedad: data("humedad-nasa")?.root_pct != null ? data("humedad-nasa") : null,
      entorno: selectedLotId ? water[selectedLotId]?.entorno || null : null,
      costos: data("costos")?.margin ? data("costos") : null,
      place: placeLabel,
    };
  };
  async function agentPdf() {
    setPdfBusy(true);
    try {
      const r = await fetch("/api/fuentes/agentic/pdf", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lat: point[0], lon: point[1], prompt: agentPrompt, polygon: poly.current ? vertices : null, inaSeries, waterAssets, fieldMarkers, nombre: lots.find(x=>x.id===selectedLotId)?.name || "Lote DOTS", analysis: agentResult, extras: reportExtras() }),
        signal: AbortSignal.timeout(60000),
      });
      if (!r.ok) throw Error("No se pudo generar el informe Agentic");
      const blob=await r.blob();
      if ((await blob.slice(0,5).text()) !== "%PDF-") throw Error("Respuesta PDF inválida");
      download(blob,"DOTS-informe-territorial.pdf");
    } catch(e) { notify((e as Error).message); } finally { setPdfBusy(false); }
  }
  async function pdf() {
    setPdfBusy(true);
    try {
      const r = await fetch("/api/fuentes/analizar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          inaSeries: view === "ina" ? inaSeries : undefined,
          nombre: lots.find(x=>x.id===selectedLotId)?.name || "Lote DOTS",
          lat: point[0],
          lon: point[1],
          polygon: poly.current ? vertices : null,
          area_ha: lotAreaHa,
          perimeter_km: lotPerimeterKm,
          fieldMarkers,
          extras: reportExtras(),
        }),
        signal: AbortSignal.timeout(45000),
      });
      if (!r.ok) throw Error("El servidor no pudo generar el PDF");
      const blob = await r.blob();
      if ((await blob.slice(0, 5).text()) !== "%PDF-")
        throw Error("Respuesta PDF inválida");
      download(blob, "DOTS-informe-territorial.pdf");
      notify(
        "Informe Territorial DOTS descargado: polígono, métricas, rangos, gráficos, interpretación y trazabilidad.",
      );
    } catch (e) {
      notify((e as Error).message);
    } finally {
      setPdfBusy(false);
    }
  }
  const weather = sources.variables?.payload?.data,
    cur = weather?.current || {},
    daily = weather?.daily || {},
    scenes: Data[] = sources.escenas?.payload?.data?.features || [],
    river = sources.rios?.payload?.data,
    thi =
      Number.isFinite(cur.temperature_2m) &&
      Number.isFinite(cur.relative_humidity_2m)
        ? 1.8 * cur.temperature_2m +
          32 -
          (0.55 - 0.0055 * cur.relative_humidity_2m) *
            (1.8 * cur.temperature_2m - 26)
        : null,
    annualData = annual(sources[view]?.payload?.data || {}),
    pclim = view === "nasa-power-30" ? powerClimate(sources[view]?.payload?.data) : null,
    dates: string[] = (daily.time || []).map((d: string) =>
      d.slice(5).split("-").reverse().join("/"),
    ),
    payload = sources[view]?.payload?.data;
  const soilIndex =
    weather?.hourly?.time?.findIndex(
      (t: string) => t >= (cur.time || "").slice(0, 13) + ":00",
    ) ?? -1;
  const history = sources.historico?.payload?.data,
    hparams = history?.properties?.parameter || {},
    htimes = Object.keys(hparams.T2M || {}),
    nitrogen = payload?.properties?.layers?.find(
      (l: Data) => l.name === "nitrogen",
    ),
    depth = nitrogen?.depths?.[0];
  return (
    <div className={"whole ta-shell"+(navCollapsed?" nav-collapsed":"")} data-theme={theme}>
      <ObsSidebar groups={buildNav(changeView,()=>startDraw("free"),()=>void agentPdf())} active={view} collapsed={navCollapsed} mobileOpen={navOpen} onCollapse={()=>setNavCollapsed(c=>!c)} onCloseMobile={()=>setNavOpen(false)} onHome={onHome}/>
      <div className="ta-main">
      <header className="panel ta-header">
        <button className="ta-icon-btn ta-hamburger" onClick={()=>{ if (window.matchMedia("(max-width: 1279px)").matches) setNavOpen(true); else setNavCollapsed(c=>!c); }} aria-label="Menú"><Menu/></button>
        <div className="breadcrumb">
          <span>ÁREA DE ANÁLISIS</span>
          <b>
            {placeLabel.split(',').slice(0,2).join(' / ').toUpperCase()}
          </b>
          <span>WGS84</span>
        </div>
        <button className="theme-toggle" onClick={()=>setTheme(t=>t==="oscuro"?"claro":"oscuro")} title="Cambiar entre tema claro y oscuro" aria-label="Cambiar tema">{theme==="oscuro"?"Claro":"Oscuro"}</button>
        <button className={"ta-bell"+(alertsData?.alerts?.some((a:any)=>a.level==="alta")?" hot":alertsData?.alerts?.length?" warm":"")} onClick={()=>{setView("alertas");void loadAlerts();}} title="Alertas del lote">
          <TriangleAlert/>{alertsData?.alerts?.length ? <b>{alertsData.alerts.length}</b> : null}
        </button>
        <span className="live">
          {Object.values(sources).filter((s) => s.status === "recibido").length}{" "}
          FUENTES RECIBIDAS
        </span>
      </header>
      <main className={"app ta-content mode-" + mainView}>
        {(()=>{
          const l = lots.find(x => x.id === selectedLotId);
          const rain7 = (daily.precipitation_sum||[]).reduce((a:number,b:number)=>a+(Number(b)||0),0);
          const et7 = (daily.et0_fao_evapotranspiration||[]).reduce((a:number,b:number)=>a+(Number(b)||0),0);
          const bal = daily.precipitation_sum && daily.et0_fao_evapotranspiration ? rain7 - et7 : null;
          const nl:any = (sources.ndvi?.payload as any)?.data?.latest;
          const nd = nl?.ndvi_mean != null ? Number(nl.ndvi_mean) : null;
          const chips = [
            { k: "Agua", tone: bal==null?"idle":bal<-30?"risk":bal<-15?"warn":"ok", word: bal==null?"Sin dato":bal<-30?"Déficit marcado":bal<-15?"Balance negativo":bal<10?"Equilibrado":"Excedente", val: bal==null?"":`${bal>0?"+":""}${fmt(bal,0)} mm en 7 días`, go: "variables" },
            { k: "Pasto", tone: nd==null?"idle":nd>=0.5?"ok":nd>=0.3?"warn":"risk", word: nd==null?(vertices.length>=3?"Calcular NDVI":"Sin lote"):nd>=0.5?"Vigor alto":nd>=0.3?"Vigor medio":"Vigor bajo", val: nd==null?"":`NDVI ${fmt(nd,2)}`, go: "ndvi" },
            { k: "Calor y rodeo", tone: thi==null?"idle":thi>=79?"risk":thi>=72?"warn":"ok", word: thi==null?"Sin dato":thi>=79?"Peligro":thi>=72?"Alerta":"Sin estrés", val: thi==null?"":`THI ${fmt(thi)}`, go: "variables" },
          ];
          return <section className="lot-bar" aria-label="Tablero del lote">
            <div className="lot-bar-id">
              <span className="lot-bar-kicker">Tablero del lote</span>
              <div className="lot-bar-title">
                {lots.length > 1
                  ? <select value={selectedLotId || ""} onChange={e => selectLot(e.target.value)} aria-label="Elegir lote">{!l && <option value="">Elegí un lote</option>}{lots.map(x => <option key={x.id} value={x.id}>{x.name}</option>)}</select>
                  : <h1>{l ? l.name : "Sin lote seleccionado"}</h1>}
              </div>
              <a className="lot-bar-help" href="/guia" target="_blank" rel="noreferrer">¿Cómo se calcula cada dato?</a><span className="lot-bar-meta">{l ? `${fmt(l.areaHa,1)} ha · ${fmt(l.perimeterKm,2)} km de perímetro · ${l.ftw ? "límite automático FTW" : "límite dibujado"} · ${placeLabel}` : `${placeLabel} · dibujá, tomá automático o importá tus lotes`}</span>
            </div>
            <div className="lot-bar-week">
              {chips.map(c => <button key={c.k} className={"week-chip tone-" + c.tone} onClick={() => changeView(c.go)}>
                <span>{c.k}</span><b>{c.word}</b>{c.val && <small>{c.val}</small>}
              </button>)}
            </div>
            <div className="lot-bar-actions">
              <div className="view-switch" role="tablist" aria-label="Vista">
                {([["tablero","Tablero"],["mapa","Mapa"]] as const).map(([k,t])=><button key={k} role="tab" aria-selected={mainView===k} className={mainView===k?"active":""} onClick={()=>setMainView(k)}>{t}</button>)}
              </div>
              {!l && <button onClick={() => { setSideTab("lote"); startDraw("free"); }}>Dibujar lote</button>}
              {!l && <button onClick={() => { setSideTab("lote"); startFtw(); }}>Automático</button>}
              <button className="primary" onClick={() => void pdf()} disabled={pdfBusy}><FileText className="icon" />{pdfBusy ? "Generando…" : "Informe PDF"}</button>
            </div>
          </section>;
        })()}
        {(()=>{
          const nl:any = (sources.ndvi?.payload as any)?.data?.latest;
          const rain = (daily.precipitation_sum||[]).reduce((a:number,b:number)=>a+(Number(b)||0),0);
          const et0 = (daily.et0_fao_evapotranspiration||[]).reduce((a:number,b:number)=>a+(Number(b)||0),0);
          const det:any[] = (sources.firms?.payload as any)?.data?.detections || [];
          const inside = det.filter(d=>d.inside_lot===true).length;
          return <MetricCards items={[
            {key:"ndvi",label:"NDVI del lote",value:nl?fmt(nl.ndvi_mean,2):"—",hint:nl?`Sentinel-2 · ${String(nl.datetime||"").slice(0,10)}`:(vertices.length>=3?"Tocá para calcular":"Dibujá un lote"),icon:<Sprout/>,tone:nl?(nl.ndvi_mean>=0.5?"ok":nl.ndvi_mean>=0.2?"warn":"risk"):"idle",onClick:()=>changeView("ndvi")},
            {key:"temp",label:"Temperatura actual",value:cur.temperature_2m!=null?fmt(cur.temperature_2m):"—",unit:"°C",hint:cur.relative_humidity_2m!=null?`Humedad ${fmt(cur.relative_humidity_2m,0)} % · Open-Meteo`:"Open-Meteo · modelo",icon:<Thermometer/>,tone:cur.temperature_2m>=35?"risk":cur.temperature_2m!=null?"ok":"idle",onClick:()=>changeView("variables")},
            {key:"agua",label:"Lluvia próximos 7 días",value:daily.precipitation_sum?fmt(rain):"—",unit:"mm",hint:daily.et0_fao_evapotranspiration?`ET₀ ${fmt(et0)} mm · balance ${fmt(rain-et0)} mm`:"Pronóstico Open-Meteo",icon:<Droplets/>,tone:daily.precipitation_sum?(rain-et0<-15?"warn":"ok"):"idle",onClick:()=>changeView("variables")},
            {key:"focos",label:"Focos térmicos",value:sources.firms?.status==="recibido"?String(inside):"—",unit:sources.firms?.status==="recibido"?"en el lote":undefined,hint:sources.firms?.status==="recibido"?`${det.length} en el entorno · NASA FIRMS 3 días`:"Tocá para consultar FIRMS",icon:<Flame/>,tone:sources.firms?.status==="recibido"?(inside>0?"risk":"ok"):"idle",onClick:()=>changeView("firms")},
          ]}/>;
        })()}
        {mainView === "tablero" && <section className="db-wrap" aria-label="Tablero del lote">
          <LotDashboard weather={weather} sources={sources as any} thi={thi} hasLot={vertices.length >= 3}
            lot={lots.find(x => x.id === selectedLotId) || null}
            terrain={(sources.relieve?.payload as any)?.data?.lot === lotKey ? (sources.relieve?.payload as any)?.data : null}
            labels={Object.fromEntries(SOURCES.map(([k, l]) => [k, l]))}
            water={selectedLotId ? water[selectedLotId] ?? null : null} cloudOn={!!cloudOn} hasKey={!!cloudKey} onCloud={() => { setMainView("mapa"); setSideTab("lote"); }}
            onLoad={(k) => void load(k)} onTerrain={() => void loadTerrain()}
            onOpen={(k) => { setMainView("mapa"); changeView(k); }} />
        </section>}
        <aside className="sidebar">
          <nav className="side-tabs" role="tablist" aria-label="Secciones del tablero">
            {([["lote","Lote"],["datos","Datos"],["asistente","Asistente"]] as const).map(([k,t])=><button key={k} role="tab" aria-selected={sideTab===k} className={sideTab===k?"active":""} onClick={()=>setSideTab(k)}>{t}</button>)}
          </nav>
          <section className="panel block" hidden={sideTab!=="lote"}>
            <div className="tag">01 / ÁREA E INFORMES</div>
            <h1>Lectura del campo</h1>
            <p className="small location">{placeLabel}. Buscá cualquier localidad o paraje y luego delimitá el lote.</p>
            <div className="place-search"><input value={placeQuery} onChange={e=>setPlaceQuery(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'){e.preventDefault();void searchPlace()}}} placeholder="Localidad, paraje, provincia, país"/><button type="button" onClick={()=>void searchPlace()} disabled={placeBusy}>{placeBusy?'Buscando…':'Buscar mapa'}</button></div>
            <form
              className="form"
              onSubmit={(e) => {
                e.preventDefault();
                poly.current?.remove();
                poly.current = null;
                currentPoints.current = [];
                setVertices([]);
                stopDraw();
                setPoint(coords.map(Number) as Point);
              }}
            >
              <label>
                Latitud
                <input
                  required
                  type="number"
                  step="any"
                  min="-90"
                  max="90"
                  value={coords[0]}
                  onChange={(e) => setCoords([e.target.value, coords[1]])}
                />
              </label>
              <label>
                Longitud
                <input
                  required
                  type="number"
                  step="any"
                  min="-180"
                  max="180"
                  value={coords[1]}
                  onChange={(e) => setCoords([coords[0], e.target.value])}
                />
              </label>
              <button className="primary">
                <MapPinned className="icon" />
                Consultar este punto
              </button>
            </form>
            <div className="status">
              {poly.current ? `${vertices.length} vértices · ${lotAreaHa?.toFixed(1)} ha · perímetro ${lotPerimeterKm?.toFixed(2)} km` : "Sin lote delimitado"}
            </div>
            <div className="water-inventory">
              <div className="tag">AGUA / INFRAESTRUCTURA</div>
              <p className="small">Registrá infraestructura conocida. DOTS la separa de futuras detecciones satelitales.</p>
              <div className="water-add"><select value={waterType} onChange={e=>setWaterType(e.target.value)}><option>bebedero</option><option>tajamar</option><option>represa</option><option>molino</option><option>perforación</option><option>tanque australiano</option><option>bomba</option><option>cañería</option><option>arroyo</option><option>canal</option></select><button type="button" onClick={()=>{const item={type:waterType,lat:point[0],lon:point[1],source:'declarado por usuario'};setWaterAssets(v=>[...v,item]);notify('Infraestructura registrada: '+waterType)}}>+ En punto actual</button></div>
              {!!waterAssets.length && <div className="water-list">{waterAssets.map((a,i)=><span key={i}>{i+1}. {a.type}</span>)}</div>}
            </div>
          </section>
          <section className="panel block agentic-box" hidden={sideTab!=="asistente"}>
            <div className="tag">02 / DOTS AGENTIC</div>
            <h2>Preguntarle a DOTS</h2>
            <p className="small">El orquestador selecciona las fuentes disponibles, conserva los faltantes y audita lo que puede afirmar.</p>
            <div className="quick-grid">
              {[
                ["Informe integral","Haceme un informe integral de este lote"],
                ["Pasturas","Evaluá pasturas y vegetación"],
                ["Agua","Analizá agua, lluvia y disponibilidad hídrica"],
                ["Ganado","Analizá estrés térmico y entorno del ganado"],
                ["Sequía","Evaluá riesgo de sequía e incendio"],
                ["Suelo","Analizá humedad y condición del suelo"],
                ["Clima","Resumí clima actual y próximos 7 días"],
              ].map(([label,prompt]) => <button key={label} type="button" onClick={()=>void askDots(prompt)} disabled={agentBusy}>{label}</button>)}
            </div>
            <textarea className="agent-input" rows={3} value={agentPrompt} onChange={e=>setAgentPrompt(e.target.value)} placeholder="Ej.: ¿Cómo está este campo y qué debería vigilar esta semana?" />
            <button className="primary" onClick={()=>void askDots()} disabled={agentBusy}>{agentBusy ? "Analizando fuentes…" : "Generar análisis"}</button>
            {agentResult && <div className="agent-result compact-result">
              <div className="confidence"><strong>{agentResult.confidence?.score}/100</strong><span>CONFIANZA {String(agentResult.confidence?.label||"").toUpperCase()}</span></div>
              <p className="small">{agentResult.summary}</p>
              <button type="button" onClick={()=>setAgentOpen(true)}>Abrir informe en pantalla</button>
              <button className="primary" onClick={()=>void agentPdf()} disabled={pdfBusy}><FileText className="icon" />{pdfBusy?"Generando…":"Descargar PDF técnico"}</button>
            </div>}
          </section>
          <section className="panel block" hidden={sideTab!=="datos"}>
            <div className="tag" style={{ marginBottom: 10 }}>
              03 / FUENTES Y VARIABLES
            </div>
            <input className="src-search" type="search" value={srcQuery} onChange={e=>setSrcQuery(e.target.value)} placeholder="Buscar dato o fuente…" aria-label="Buscar dato o fuente"/>
            <div className="src-list">
            {SOURCES.filter(([key]) => !NATIONAL.includes(key) && key !== "metnorway" && !RESEARCH.includes(key))
              .filter(([, label, by]) => !srcQuery || (label + " " + by).toLowerCase().includes(srcQuery.toLowerCase())).map(([key, label, by]) => (
              <button
                key={key}
                className={"data-button " + (view === key ? "active" : "")}
                onClick={() => changeView(key)}
                aria-pressed={view === key}
              >
                <span className="src-name">{label}<small>{by}</small></span>
                <span className={"src-state st-" + (sources[key]?.status || "consultar").replace(" ", "-")}>{sources[key]?.status || "consultar"}</span>
              </button>
            ))}
            </div>
            <details style={{marginTop:12}}><summary className="small">Agencias directas · 6 conexiones</summary><div style={{marginTop:10}}>{SOURCES.filter(([key])=>NATIONAL.includes(key)||key==="metnorway").map(([key,label])=><button key={key} className={"data-button "+(view===key?"active":"")} onClick={()=>changeView(key)} aria-pressed={view===key}>{label}<span>{sources[key]?.status.toUpperCase()||"CONSULTAR"}</span></button>)}</div></details>
            <details style={{marginTop:12}}><summary className="small">Conectores globales · abiertos y con credencial</summary><div style={{marginTop:10}}>{SOURCES.filter(([key])=>RESEARCH.includes(key)).map(([key,label])=><button key={key} className={"data-button "+(view===key?"active":"")} onClick={()=>changeView(key)}>{label}<span>{sources[key]?.status.toUpperCase()||"CONSULTAR"}</span></button>)}</div></details>
            <a className="small" href="/CONEXIONES-INVESTIGACION.md" target="_blank" rel="noreferrer">Matriz de 20 servicios y activación</a>
            <div style={{ marginTop: 18 }} id="dots-detail">
              {sources[view]?.status === "consultando" && (
                <p className="small">Consultando datos reales…</p>
              )}
              {sources[view]?.status === "sin dato" && (
                <p className="error">
                  {sources[view].error}. No se sustituyen datos faltantes.
                </p>
              )}
              {RESEARCH.includes(view) && <>
                <p className="footnote">{SOURCES.find(([key])=>key===view)?.[2]} · consulta real · {sources[view]?.payload?.consulted_at||"Sin fecha de consulta"}</p>
                {view==="aire" && <><p className="footnote">Pronóstico CAMS en grilla. NO₂ y amoníaco atmosféricos no son nitrógeno del suelo.</p>{Object.keys(payload?.hourly||{}).filter(k=>k!=="time").map(k=><div className="soil" key={k}><span>{k.replaceAll("_"," ")}</span><strong>{fmt(payload.hourly[k]?.[0])} <small>{payload?.hourly_units?.[k]}</small></strong></div>)}<p className="footnote">Hora mostrada: {payload?.hourly?.time?.[0]||"Sin fecha"}. Valores ausentes se conservan.</p></>}
                {view==="nasa-power-30" && (pclim ? <>
                  <div className="lot-vars-title">Clima del lugar · {pclim.from}–{pclim.to}</div>
                  <div className="soil"><span>Temperatura media anual</span><strong>{fmt(pclim.tYear,1)} °C</strong></div>
                  <div className="soil"><span>Lluvia anual promedio</span><strong>{fmt(pclim.rainYear,0)} mm</strong></div>
                  {pclim.medRain!=null && <div className="soil"><span>Lluvia anual · mediana</span><strong>{fmt(pclim.medRain,0)} mm</strong></div>}
                  <div className="lot-vars-title" style={{marginTop:12}}>Rangos del lugar</div>
                  <div className="soil"><span>Temperatura media mensual<small style={{display:"block"}}>del mes más fresco al más cálido</small></span><strong>{fmt(pclim.range.tMin,1)} a {fmt(pclim.range.tMax,1)} °C</strong></div>
                  <div className="soil"><span>Lluvia mensual promedio<small style={{display:"block"}}>del mes más seco al más lluvioso</small></span><strong>{fmt(pclim.range.rMonthMin,0)} a {fmt(pclim.range.rMonthMax,0)} mm</strong></div>
                  {pclim.range.rainLo!=null && <div className="soil"><span>Lluvia anual habitual<small style={{display:"block"}}>8 de cada 10 años caen en este rango</small></span><strong>{fmt(pclim.range.rainLo,0)} a {fmt(pclim.range.rainHi,0)} mm</strong></div>}
                  {pclim.range.rainMin!=null && <div className="soil"><span>Lluvia anual extrema<small style={{display:"block"}}>el año más seco y el más lluvioso</small></span><strong>{fmt(pclim.range.rainMin,0)} a {fmt(pclim.range.rainMax,0)} mm</strong></div>}
                  {pclim.medRain!=null && <p className="footnote">Cómo leer un año: seco si llueve menos de {fmt(pclim.medRain*.75,0)} mm (75 % de la mediana) · normal entre {fmt(pclim.medRain*.75,0)} y {fmt(pclim.medRain*1.25,0)} mm · lluvioso por encima de {fmt(pclim.medRain*1.25,0)} mm.</p>}
                  <div className="lot-vars-title" style={{marginTop:12}}>Lectura del clima</div>
                  {pclim.insights.map((t,i)=><p className="small" key={i} style={{margin:"0 0 8px"}}>{t}</p>)}
                  <p className="footnote">NASA POWER (comunidad AG) · grilla de ~50 km: describe la zona, no el lote. Lluvia corregida con satélite y modelo; para el lote, comparar con pluviómetro propio.</p>
                </> : <p className="footnote">{sources[view]?.status==="consultando"?"Consultando NASA POWER…":"NASA POWER no devolvió una serie completa para este punto."}</p>)}
                {view==="elevacion" && <div className="key"><span>Elevación estimada DEM</span><strong>{fmt(payload?.elevation?.[0])} m</strong></div>}
                {view==="ina" && <><label className="small">Serie de estación · Bella Vista<select style={{width:"100%",marginTop:8}} value={inaSeries} onChange={e=>{setInaSeries(e.target.value);void load("ina",point,years,e.target.value)}}><option value="22">Altura Paraná · 30 días</option><option value="25500">Altura mensual · 30 años</option><option value="37299">Temperatura RMA08 · 2 días</option></select></label><p className="footnote">Estación Bella Vista · serie {inaSeries} · unidad y procedimiento de la fuente. No cambia de estación al mover el mapa.</p><div className="key"><span>Último registro · {payload?.data?.at(-1)?.timestart||"Sin fecha"}</span><strong>{fmt(payload?.data?.at(-1)?.valor)} {payload?.responseHeader?.seriesmetadata?.unit_abrev||""}</strong></div><p className="footnote">{payload?.data?.length||0} registros recibidos · exportables en JSON.</p></>}
                {["nasa-catalogo","productos-nasa","landsat","radar","copernicus-stac","cnes-stac","dlr-stac","deafrica-stac"].includes(view) && <><p className="footnote">Catálogo y metadatos. Todavía no se extraen valores de NDVI, temperatura de superficie ni píxeles de radar.</p>{(payload?.features||payload?.feed?.entry||Object.values(payload||{})).slice(0,5).map((item:any,i:number)=><div className="soil" key={i}><span style={{overflowWrap:"anywhere"}}>{item?.id||item?.title||item?.long_name||item?.short_name||"Producto NASA"}<small style={{display:"block"}}>{item?.properties?.datetime||item?.time_start||"Metadatos de catálogo"}</small></span></div>)}</>}
                {["era5-cds","sentinel-hub","noaa-cdo","usgs-m2m","nasa-earthdata","copernicus-marine","gee","openaq","gfw","aemet","eumetsat","jaxa","mosdac","kma","fengyun"].includes(view) && <><div className="metric-card"><span className="muted">ESTADO DE INTEGRACIÓN</span><strong>{payload?.status || "Sin verificar"}</strong><p>{payload?.missing_env?.length ? "Faltan en Vercel: "+payload.missing_env.join(", ") : "Credenciales detectadas. Falta validar consulta end-to-end antes de marcar OPERATIVA."}</p></div></>}
                {view==="usgs" && <><label className="small">Estación opcional (ej. USGS-06887000)<input style={{width:"100%",marginTop:8}} value={usgsSite} onChange={e=>setUsgsSite(e.target.value)} placeholder="Vacío: región del mapa"/></label><p className="footnote">Muestra de hasta 50 registros dentro de la región consultada. Sin cobertura USGS fuera de EE.UU.</p><p className="small">{payload?.features?.length||0} registros recibidos. JSON incluye códigos, unidades y fechas originales.</p></>}
              </>}
              {NATIONAL.includes(view) && (
                <>
                  <p className="footnote">{payload?.agency || "Servicio oficial directo"}. {payload?.scope || "Seleccioná coordenadas dentro del país de la agencia."}</p>
                  {payload?.source_mode==="respaldo METAR" && <p className="footnote warn-note">Partes horarios de aeropuertos (METAR) del servicio meteorológico del país, vía NOAA. {payload?.native_note||""}</p>}
                  {sources[view]?.status === "recibido" && !payload?.observations?.length && <p className="error">Sin observaciones en esta ubicación y período. No se sustituyen por datos de otro país.</p>}
                  {(payload?.observations || []).slice(0,35).map((o: Data,i: number)=><div className="soil" key={i}><span style={{fontSize:10,maxWidth:"60%",overflowWrap:"anywhere"}}>{o.variable}<small style={{display:"block"}}>{o.station} · {fmt(o.distance_km)} km</small><small style={{display:"block"}}>{o.observed_at || "Sin fecha"}</small><small style={{display:"block"}}>Calidad: {o.quality ?? "no informada"}</small></span><strong style={{fontSize:12}}>{fmt(o.value)}<small style={{display:"block"}}>{o.unit || "sin unidad"}</small></strong></div>)}
                  <p className="footnote">Se muestran hasta 35 valores; exportá JSON para ver toda la respuesta. La antigüedad y la distancia de cada registro importan.</p>
                </>
              )}
              {view==="forraje" && <>
                <div className="forage-form">
                  <label>Tipo de recurso<select value={forageKind} onChange={e=>setForageKind(e.target.value)}><option value="pastizal">Pastizal natural</option><option value="templada">Pastura templada</option><option value="megatermica">Pastura megatérmica</option><option value="verdeo">Verdeo de invierno</option></select></label>
                  <label>Uso del pasto · {Math.round(forageUse*100)} %<input type="range" min={0.3} max={0.7} step={0.05} value={forageUse} onChange={e=>setForageUse(Number(e.target.value))}/></label>
                  <label>Cabezas en el lote<input type="number" min={0} value={herdHeads||""} placeholder="opcional" onChange={e=>{const v=Math.max(0,Number(e.target.value)||0);setHerdHeads(v);try{localStorage.setItem("dots-heads",String(v))}catch{}}}/></label>
                  <button className="primary" onClick={()=>void loadForage()}>Estimar pasto y carga</button>
                </div>
                {payload?.growth_rate_30d!=null && <>
                  <div className="keygrid">
                    <div className="key"><span>Crecimiento · últimos 30 días</span><strong>{fmt(payload.growth_rate_30d,0)} <small>kg MS/ha/día</small></strong></div>
                    <div className="key"><span>Carga que sostiene</span><strong>{fmt(payload.ev_ha,2)} <small>EV/ha</small></strong></div>
                    {payload.ev_lot!=null && <div className="key"><span>En todo el lote</span><strong>{fmt(payload.ev_lot,0)} <small>EV</small></strong></div>}
                    <div className="key"><span>Acumulado {payload.accumulated_days} días</span><strong>{fmt(payload.accumulated,0)} <small>kg MS/ha</small></strong></div>
                  </div>
                  {payload.current_load_ev_ha!=null && <div className={"verdict "+(String(payload.load_balance).includes("encima")?"warn":"ok")}><span>Carga actual {fmt(payload.current_load_ev_ha,2)} EV/ha</span><b>{payload.load_balance}</b></div>}
                  <p className="footnote">{Object.values(payload.assumptions||{}).join(" · ")}. {payload.note}</p>
                </>}
              </>}
              {view==="indices-espectrales" && <>
                {vertices.length<3 && <p className="error">Dibujá un lote: los índices se calculan dentro del polígono.</p>}
                {payload?.indices?.length>0 && <>
                  <p className="footnote">Escena Sentinel-2 del {String(payload.datetime||"").slice(0,10)} · {Math.round((payload.clear_fraction_lot||0)*100)} % del lote despejado</p>
                  <div className="cost-lines">{payload.indices.map((x:Data)=><div key={x.name} title={x.formula}><span><b>{x.name}</b> · {x.domain}<small style={{display:"block",color:"#667085"}}>{x.meaning||x.long_name}</small></span><b>{x.mean!=null?fmt(x.mean,3):"—"}</b></div>)}</div>
                </>}
                {payload?.catalog && <p className="footnote">{payload.catalog.total} índices disponibles ({Object.entries(payload.catalog.by_domain||{}).map(([k,v])=>`${v} de ${k}`).join(", ")}). Fórmulas del catálogo abierto awesome-spectral-indices (MIT).</p>}
              </>}
              {view==="radar-agua" && <>
                {vertices.length<3 && <p className="error">Dibujá un lote para medir el agua con radar.</p>}
                {payload?.latest && <>
                  <div className={"verdict "+(payload.latest.water_fraction>0.1?"warn":"ok")}><span>Agua en el lote · {String(payload.latest.datetime||"").slice(0,10)}</span><b>{fmt(payload.latest.water_fraction*100,1)} % · {fmt(payload.latest.water_ha,1)} ha</b><small>{payload.trend||""}</small></div>
                  <p className="footnote">{payload.method}</p>
                </>}
              </>}
              {view==="balance-agua" && payload?.spei && <>
                <div className={"verdict "+(String(payload.spei["3"]?.class).includes("sequía")?"warn":"ok")}><span>Últimos 3 meses · hasta {payload.last_month}</span><b>{payload.spei["3"]?.class}</b><small>Índice {payload.spei["3"]?.index} · balance {payload.spei["3"]?.balance_mm} mm (normal {payload.spei["3"]?.normal_mm} mm)</small></div>
                <div className="wx-grid">{["1","3","6","12"].map(k=><div key={k}><span>{k} {k==="1"?"mes":"meses"}</span><b>{payload.spei[k]?.index??"—"}<small> {payload.spei[k]?.class}</small></b></div>)}</div>
                <p className="footnote">{payload.reading} Índice tipo SPEI: menor a −1 es sequía; mayor a 1, exceso de agua.</p>
              </>}
              {view==="costos" && <>
                <label className="small" style={{display:"block",marginBottom:8}}>Destino de la hacienda<input value={costDest} placeholder="ej. Mercado Agroganadero Cañuelas, Corrientes, frigorífico…" onChange={e=>{setCostDest(e.target.value);try{localStorage.setItem("dots-cost-dest",e.target.value)}catch{}}}/></label>
                <div className="cost-form">{COST_FIELDS.map(([k,l,u])=><label key={k}>{l}{u&&<small> · {u}</small>}<input type="number" min={0} value={costParams[k]??""} placeholder={k==="heads"&&herdHeads?String(herdHeads):""} onChange={e=>setCost(k,e.target.value)}/></label>)}</div>
                <button className="primary" style={{width:"100%",marginTop:8}} onClick={()=>void loadCosts()}>Calcular costos y ruta</button>
                <p className="footnote">Los precios y costos los cargás vos y quedan guardados en este navegador. DOTS aporta la distancia por camino, el tiempo de viaje y el dólar del día. Referencias: Mercado Agroganadero de Cañuelas (precios), CATAC (tarifas de flete).</p>
                {payload?.logistics && <>
                  <div className="lot-vars-title" style={{marginTop:10}}>Logística</div>
                  <div className="wx-grid">
                    <div><span>Distancia</span><b>{fmt(payload.logistics.km,0)}<small> km</small></b></div>
                    <div><span>Viaje</span><b>{payload.logistics.hours!=null?fmt(payload.logistics.hours,1):"—"}<small> h</small></b></div>
                    {payload.margin?.trips!=null && <div><span>Viajes de jaula</span><b>{payload.margin.trips}</b></div>}
                    {payload.margin?.freight!=null && <div><span>Flete total</span><b>$ {fmt(payload.margin.freight,0)}</b></div>}
                    {payload.margin?.freight_per_kg!=null && <div><span>Flete por kg</span><b>$ {fmt(payload.margin.freight_per_kg,1)}</b></div>}
                  </div>
                  <p className="footnote">{payload.logistics.destination?.name} · {payload.logistics.method}</p>
                </>}
                {payload?.margin?.gross!=null && <>
                  <div className={"verdict "+((payload.margin.net??0)>=0?"ok":"warn")}><span>Margen bruto estimado</span><b>$ {fmt(payload.margin.net,0)}{payload.margin.net_usd!=null?` · US$ ${fmt(payload.margin.net_usd,0)}`:""}</b><small>{payload.margin.net_ha!=null?`$ ${fmt(payload.margin.net_ha,0)}/ha`:""}{payload.margin.net_ha_usd!=null?` · US$ ${fmt(payload.margin.net_ha_usd,1)}/ha`:""}{payload.margin.net_head!=null?` · $ ${fmt(payload.margin.net_head,0)}/cabeza`:""}</small></div>
                  {payload.margin.breakeven_price_kg!=null && <p className="small" style={{marginTop:6}}>Precio de equilibrio: <b>$ {fmt(payload.margin.breakeven_price_kg,0)}/kg</b>{payload.margin.breakeven_usd_kg!=null?` (US$ ${fmt(payload.margin.breakeven_usd_kg,2)}/kg)`:""}</p>}
                  <div className="cost-lines">{payload.margin.lines.map((l:Data)=><div key={l.label}><span>{l.label}</span><b className={l.value<0?"neg":""}>{l.value<0?"− ":""}$ {fmt(Math.abs(l.value),0)}</b></div>)}</div>
                </>}
                {payload?.exchange?.oficial_venta && <p className="footnote">Dólar oficial ${fmt(payload.exchange.oficial_venta,2)}{payload.exchange.mayorista_venta?` · mayorista $${fmt(payload.exchange.mayorista_venta,2)}`:""} · {payload.exchange.source}</p>}
                {payload?.missing?.length>0 && <p className="footnote warn-note">Para completar el cálculo falta: {payload.missing.join(", ")}.</p>}
                {payload?.method && <p className="footnote">{payload.method}</p>}
              </>}
              {view==="sustentabilidad" && <>
                <label className="small" style={{display:"block",marginBottom:8}}>Cabezas en el lote (para emisiones)<div className="row" style={{marginTop:6}}><input type="number" min={0} value={herdHeads||""} placeholder="ej. 250" onChange={e=>{const v=Math.max(0,Number(e.target.value)||0);setHerdHeads(v);try{localStorage.setItem("dots-heads",String(v))}catch{}}}/><button onClick={()=>void load("sustentabilidad")}>Calcular</button></div></label>
                {payload?.deforestation && (()=>{const d=payload.deforestation;const ok=String(d.verdict).startsWith("sin pérdida");return <div className={"verdict "+(ok?"ok":d.verdict==="sin dato"?"":"warn")}><span>Libre de deforestación · corte {d.cutoff}</span><b>{d.verdict}</b><small>Árboles en el lote: {d.baseline_year} {fmt((d.series.find((r:Data)=>r.year===d.baseline_year)?.trees??0)*100,1)} % → {d.last_year} {fmt((d.series.find((r:Data)=>r.year===d.last_year)?.trees??0)*100,1)} % · pérdida estimada {fmt(d.tree_loss_ha,1)} ha</small></div>})()}
                {payload?.deforestation?.series?.length>0 && <>
                  <div className="lot-vars-title" style={{marginTop:10}}>Cobertura año por año · % del lote</div>
                  <div className="cover-table"><div className="cover-head"><span>Año</span><span>Árboles</span><span>ha</span><span>Pastizal</span><span>Cultivo</span><span>Ver</span></div>
                    {payload.deforestation.series.map((r:Data)=><div className={"cover-row"+(r.year===2020?" cut":"")} key={r.year}><span>{r.year}</span><b>{r.trees!=null?fmt(r.trees*100,1):"—"}</b><span>{r.trees!=null&&payload.deforestation.area_ha?fmt(r.trees*payload.deforestation.area_ha,1):"—"}</span><span>{r.rangeland!=null?fmt(r.rangeland*100,0):"—"}</span><span>{r.crops!=null?fmt(r.crops*100,0):"—"}</span><button className={coverYear===r.year?"active":""} onClick={()=>setCoverYear(coverYear===r.year?null:r.year)} title="Ver la cobertura de ese año sobre el lote">◧</button></div>)}
                  </div>
                  {coverYear && <div className="dots-legend-inline">{[["#397d49","Árboles"],["#e3e2c3","Pastizal"],["#e49635","Cultivo"],["#419bdf","Agua"],["#7a87c6","Veg. inundada"],["#a59b8f","Suelo desnudo"]].map(([c,l])=><span key={l}><i style={{background:c}}/>{l}</span>)}</div>}
                  <p className="footnote">Fila resaltada: año de corte. Tocá ◧ para ver la cobertura de ese año sobre el lote y comparar 2020 con el último.</p>
                </>}
                <EudrReadiness d={payload?.deforestation} onState={r=>{eudrReady.current=r}} whisp={whisp} onWhisp={p=>void askWhisp(p)} whispBusy={whispBusy}/>
                <div className="eudr-actions">
                  <label className="small">Establecimiento (para el informe)<input value={estName} placeholder="Nombre · partido · provincia" onChange={e=>{setEstName(e.target.value);try{localStorage.setItem("dots-establishment",e.target.value)}catch{}}}/></label>
                  <button className="primary" disabled={eudrBusy} onClick={()=>void eudrDownload("pdf")}>{eudrBusy?"Generando…":"Informe de verificación (PDF)"}</button>
                  <button disabled={eudrBusy} onClick={()=>void eudrDownload("geojson")}>Geolocalización del lote (GeoJSON)</button>
                </div>
                {payload?.deforestation?.worldcover_tree_2020!=null && <p className="footnote">Control con ESA WorldCover: árboles {fmt(payload.deforestation.worldcover_tree_2020*100,1)} % (2020) y {fmt((payload.deforestation.worldcover_tree_2021??0)*100,1)} % (2021).</p>}
                {payload?.carbon && <>
                  <div className="lot-vars-title" style={{marginTop:10}}>Carbono del suelo · 0–30 cm</div>
                  <div className="wx-grid">
                    <div><span>Stock por hectárea</span><b>{fmt(payload.carbon.soc_t_ha,1)}<small> t C/ha</small></b></div>
                    {payload.carbon.soc_t_ha_range?.[0]!=null && <div><span>Rango probable</span><b>{fmt(payload.carbon.soc_t_ha_range[0],0)}–{fmt(payload.carbon.soc_t_ha_range[1],0)}<small> t C/ha</small></b></div>}
                    {payload.carbon.soc_total_t!=null && <div><span>Total del lote</span><b>{fmt(payload.carbon.soc_total_t,0)}<small> t C</small></b></div>}
                    {payload.carbon.soc_total_tco2e!=null && <div><span>Equivalente CO₂</span><b>{fmt(payload.carbon.soc_total_tco2e,0)}<small> t CO₂e</small></b></div>}
                  </div>
                  {payload.carbon.herd && <><div className="lot-vars-title" style={{marginTop:10}}>Emisiones del rodeo · {payload.carbon.herd.heads} cabezas</div><div className="wx-grid"><div><span>Metano por año</span><b>{fmt(payload.carbon.herd.ch4_t_year,1)}<small> t CH₄</small></b></div><div><span>CO₂ equivalente</span><b>{fmt(payload.carbon.herd.co2e_t_year,0)}<small> t CO₂e/año</small></b></div></div><p className="footnote">{payload.carbon.herd.method}.</p></>}
                  <p className="footnote">{payload.carbon.scope}</p>
                </>}
                {payload?.deforestation?.scope && <p className="footnote">{payload.deforestation.scope}</p>}
                {payload?.errors && Object.keys(payload.errors).length>0 && <p className="error">{Object.entries(payload.errors).map(([k,v]:any)=>`${k}: ${v}`).join(" · ")}</p>}
              </>}
              {view==="alertas" && <>
                <div className="row" style={{marginBottom:8}}><p className="footnote" style={{margin:0}}>{alertsBusy?"Evaluando reglas…":alertsData?.summary||"Sin evaluar"}</p><button onClick={()=>void loadAlerts()} disabled={alertsBusy}>Actualizar</button></div>
                {(alertsData?.alerts||[]).map((a:Data,i:number)=><article className={"alert-card lvl-"+a.level} key={i}><header><b>{a.title}</b><span>{a.level}</span></header><p>{a.detail}</p><p className="alert-action">→ {a.action}</p><small>{a.source}</small></article>)}
                {alertsData && !alertsData.alerts?.length && <p className="small">No hay alertas activas en las reglas que pudieron evaluarse.</p>}
                {alertsData?.unevaluated && Object.keys(alertsData.unevaluated).length>0 && <p className="footnote">Sin evaluar: {Object.entries(alertsData.unevaluated).map(([k,v]:any)=>`${k} (${v})`).join(" · ")}. Abrí NDVI, Lluvia y sequía o Riesgos para completar esas reglas.</p>}
              </>}
              {view==="estadistica" && payload && <>
                {payload.ensemble?.week_rain && <div className="key"><span>Lluvia próximos 7 días · {payload.ensemble.members} pronósticos</span><strong>{fmt(payload.ensemble.week_rain.median,0)} mm</strong><small className="small">rango probable {fmt(payload.ensemble.week_rain.p10,0)}–{fmt(payload.ensemble.week_rain.p90,0)} mm · {payload.ensemble.week_rain.p_ge20} % de chance de 20 mm o más</small></div>}
                {payload.ensemble?.days && <div className="prob-table"><div className="prob-head"><span>Día</span><span>Helada</span><span>≥35 °C</span><span>Lluvia ≥10</span></div>{payload.ensemble.days.map((d:Data)=><div className="prob-row" key={d.date}><span>{d.date.slice(8,10)}/{d.date.slice(5,7)}<small>{fmt(d.tmin_med,0)}° / {fmt(d.tmax_med,0)}°</small></span>{[d.p_frost,d.p_heat35,d.p_rain10].map((v:number,i:number)=><b key={i} className={"p "+(v>=60?"hi":v>=30?"mid":v>0?"lo":"")} style={{"--p":`${v||0}%`} as any}>{v!=null?`${v}%`:"—"}</b>)}</div>)}</div>}
                {payload.seasonal?.length>0 && <><div className="lot-vars-title" style={{marginTop:12}}>Perspectiva estacional ECMWF</div>{payload.seasonal.map((m:Data)=><div className="soil" key={m.period}><span>{m.period}<small style={{display:"block"}}>lluvia: {m.rain_reading} · temperatura: {m.temp_reading}</small></span><strong>{m.rain?`${m.rain.below}/${m.rain.normal}/${m.rain.above}`:"—"}</strong></div>)}<p className="footnote">Porcentajes de pronósticos con lluvia baja / normal / alta frente a los terciles de 1991–2020 en este lugar.</p></>}
                {payload.trends?.length>0 && <><div className="lot-vars-title" style={{marginTop:12}}>Tendencias {payload.trends[0].years?.[0]}–{payload.trends[0].years?.[1]}</div>{payload.trends.map((t:Data)=><div className="soil" key={t.key}><span>{t.label}<small style={{display:"block"}}>{t.reading} · p = {fmt(t.p_value,3)}</small></span><strong className={t.significant?"":"muted"}>{t.per_decade>0?"+":""}{fmt(t.per_decade,t.key==="tx"?2:1)} {t.unit}/década</strong></div>)}</>}
                {Object.keys(payload.errors||{}).length>0 && <p className="error">Sin dato: {Object.keys(payload.errors).join(", ")}. No se completan con valores supuestos.</p>}
                <p className="footnote">{payload.method}</p>
              </>}
              {view==="lluvia" && payload?.status==="en proceso" && <p className="small">CHIRPS está calculando la lluvia diaria desde {payload.start} sobre {vertices.length>=3?"el lote":"el entorno del punto"}… {payload.progress!=null?`${payload.progress} %`:""} Puede tardar uno o dos minutos.</p>}
              {view==="lluvia" && payload?.spi && <>
                <p className="footnote">{payload.product} · último mes completo {payload.last_month} · normal {payload.normal_period?.[0]}–{payload.normal_period?.[1]}.</p>
                <div className="spi-grid">{["1","3","6","12"].map(k=>{const x=payload.spi[k]||{};const cls=x.spi==null?"":x.spi<=-1?"dry":x.spi>=1?"wet":"ok";return <div className={"spi "+cls} key={k}><span>{k==="1"?"Último mes":`Últimos ${k} meses`}</span><b>{x.mm!=null?fmt(x.mm,0):"—"}<small> mm</small></b><em>{x.class}{x.spi!=null?` · SPI ${fmt(x.spi,1)}`:""}</em><small>normal {x.normal!=null?fmt(x.normal,0):"—"} mm</small></div>})}</div>
                <p className="footnote">SPI: menos de −1 sequía, más de 1 exceso. Se compara con los mismos meses de 1991–2020 en este lugar.</p>
              </>}
              {view==="indices" && payload?.catalog && <>
                <p className="footnote">ERA5 diario en el punto del lote · {payload.period?.[0]}–{payload.period?.[1]} · último año {payload.last_year} comparado con el promedio del período.</p>
                <div className="idx-table">
                  <div className="idx-head"><span>Índice</span><span>{payload.last_year}</span><span>Promedio</span><span>Dif.</span></div>
                  {payload.catalog.map((k:Data)=>{const last=(payload.years||[]).slice(-1)[0]||{};const v=last[k.key];const a=payload.anomaly_last_year?.[k.key];const isDate=k.unit==="fecha";const dv=(k.unit==="días"||k.unit==="eventos")?0:(k.key==="prcptot"||k.key==="gdd10")?0:1;const dm=(k.key==="prcptot"||k.key==="gdd10")?0:1;return <div className="idx-row" key={k.key} title={`${k.description} · xclim: ${k.xclim}`}><span>{k.label}<small>{k.unit}</small></span><strong>{isDate?(v?String(v).slice(5).split("-").reverse().join("/"):"—"):fmt(v,dv)}</strong><span>{isDate?"":fmt(payload.mean?.[k.key],dm)}</span><span className={a==null||isDate?"":a>0?"up":a<0?"down":""}>{isDate||a==null?"":(a>0?"+":"")+fmt(a,dm)}</span></div>})}
                </div>
                <p className="footnote">Grilla ERA5 de ~25 km: describe el clima de la zona, no microclimas del lote.</p>
              </>}
              {view==="teleconexiones" && payload?.indices && <>
                {payload.enso_consensus && <div className="key"><span>El Niño · consenso NOAA</span><strong>{payload.enso_consensus}</strong><small className="small">{payload.enso_agreement} índices coinciden (Niño 3.4, ONI, MEI v2)</small></div>}
                {Object.entries(payload.indices).map(([k,e]:[string,any])=><div className="soil" key={k}><span>{e?.data?.name||e?.scope||k}<small style={{display:"block"}}>{e?.status==="recibido"?`${e.data.period} · ${e.data.phase}`:"sin dato"}</small></span><strong>{e?.status==="recibido"?fmt(e.data.value,2):"—"}</strong></div>)}
                <p className="footnote">Niño 3.4, ONI y MEI: ±0,5 marca Niño o Niña. AAO negativo y TSA cálido suelen acompañar cambios de lluvia en el Litoral; interpretar junto al pronóstico estacional.</p>
              </>}
              {NDVI_VIEWS.includes(view) && <>
                {vertices.length < 3 && <p className="error">Dibujá el lote primero: el NDVI es una estadística dentro del polígono, no un valor de punto.</p>}
                {payload?.latest && <div className="keygrid">
                  <div className="key"><span>NDVI medio</span><strong>{fmt(payload.latest.ndvi_mean,2)}</strong></div>
                  <div className="key"><span>Mediana</span><strong>{fmt(payload.latest.ndvi_median ?? payload.latest.ndvi_p50,2)}</strong></div>
                  <div className="key"><span>Rango p2–p98</span><strong>{payload.latest.ndvi_p2!=null?`${fmt(payload.latest.ndvi_p2,2)} – ${fmt(payload.latest.ndvi_p98,2)}`:"s/d"}</strong></div>
                  <div className="key"><span>Lote despejado</span><strong>{payload.latest.clear_fraction_lot!=null?Math.round(payload.latest.clear_fraction_lot*100)+" %":"s/d"}</strong></div>
                </div>}
                {payload?.latest?.indices && <div className="idx-cards">{["evi","savi","ndmi","ndwi"].map(k=>{const x=payload.latest.indices[k];return x?<div className="idx-card" key={k} title={x.meaning}><span>{x.name}</span><b>{fmt(x.mean,2)}</b><small>{x.meaning}</small></div>:null})}{payload.latest.indices.water_fraction!=null&&<div className="idx-card" title="Fracción de píxeles con NDWI positivo"><span>Agua en superficie</span><b>{fmt(payload.latest.indices.water_fraction*100,1)} %</b><small>del lote con agua libre o anegado</small></div>}</div>}
                {payload?.latest && <p className="footnote">Última escena válida: {(payload.latest.datetime||payload.latest.from||"").slice(0,10)} · {payload.area_ha} ha · {payload.latest.pixels??"s/d"} píxeles · {payload.sensor}</p>}
                {payload?.fallback && <p className="footnote warn-note">Fuente de respaldo: {payload.fallback_reason ? `${payload.fallback_reason}. ` : ""}Se usó NDVI MODIS de NASA (250 m), más grueso que Sentinel-2. {payload.interpretation_scope}</p>}
                {(payload?.series||[]).slice().reverse().map((r:Data,i:number)=><div className="soil" key={i}><span>{(r.datetime||r.from||"").slice(0,10)}<small style={{display:"block"}}>{r.status}{r.clear_fraction_lot!=null?` · ${Math.round(r.clear_fraction_lot*100)} % despejado`:""}</small></span><strong>{r.status==="válida"?fmt(r.ndvi_mean,2):"—"}</strong></div>,2)}
                {view==="ndvi" && ndviValid.length>1 && <div className="ndvi-timeline"><button onClick={()=>setNdviPlay(p=>!p)} aria-label={ndviPlay?"Pausar":"Reproducir"}>{ndviPlay?"❚❚":"▶"}</button><input type="range" min={0} max={ndviValid.length-1} step={1} value={ndviIdx} onChange={e=>{setNdviPlay(false);setNdviPick(Number(e.target.value))}} aria-label="Fecha de la escena"/><small>Escena {ndviIdx+1} de {ndviValid.length} · {String(ndviValid[ndviIdx]?.datetime||"").slice(0,10)} · NDVI medio {fmt(ndviValid[ndviIdx]?.ndvi_mean,2)}</small></div>}
                {view==="ndvi" && payload?.latest && <div className="overlay-switch"><span>Sobre el lote · {String((ndviValid[ndviIdx]||payload.latest).datetime||"").slice(0,10)}</span>{[["ndvi","NDVI"],["rgb","Color real"],["off","Ninguna"]].map(([k,l])=><button key={k} className={(k==="off"?!showNdvi:showNdvi&&overlayMode===k)?"active":""} onClick={()=>{if(k==="off"){setShowNdvi(false)}else{setShowNdvi(true);setOverlayMode(k as any)}}}>{l}</button>)}</div>}
                <p className="footnote">Escala: menos de 0,2 suelo desnudo o agua · 0,2–0,5 vegetación rala o pastura seca · más de 0,5 vegetación activa. No reemplaza la recorrida a campo.</p>
                {view==="ndvi" && vertices.length>=3 && <NdviExtra point={point} vertices={vertices} map={mapRef.current}/>}
              </>}
              {view === "metnorway" && <><p className="footnote">MET Norway · conexión directa · pronóstico modelado. Actualizado: {payload?.properties?.meta?.updated_at || "Sin fecha"}</p>{Object.entries(payload?.properties?.timeseries?.[0]?.data?.instant?.details || {}).map(([key,value])=><div className="soil" key={key}><span style={{fontSize:10,maxWidth:"65%"}}>{key.replaceAll("_"," ")}</span><strong style={{fontSize:12}}>{fmt(value)} <small>{payload?.properties?.meta?.units?.[key]}</small></strong></div>)}<p className="footnote">Hora válida: {payload?.properties?.timeseries?.[0]?.time || "Sin fecha"}. Datos MET Norway, CC BY 4.0.</p></>}
              {view === "variables" && <VariablesPanel weather={weather} />}
              {view === "modelos" && (
                <>
                  <p className="footnote">
                    Modelos de 7 organismos vía Open-Meteo. Pronósticos
                    independientes; no son estaciones ni un ensemble
                    estadístico.
                  </p>
                  {[
                    ["NOAA · Estados Unidos", "gfs_global"],
                    ["ECMWF · Europa", "ecmwf_ifs025"],
                    ["DWD · Alemania", "icon_global"],
                    ["ECCC · Canadá", "gem_global"],
                    ["JMA · Japón", "jma_gsm"],
                    ["CMA · China", "cma_grapes_global"],
                    ["Météo-France", "meteofrance_arpege_world"],
                  ].map(([label, id]) => {
                    const i =
                      payload?.hourly?.time?.findIndex(
                        (t: string) =>
                          t >= (cur.time || "").slice(0, 13) + ":00",
                      ) ?? -1;
                    return (
                      <div className="soil" key={id}>
                        <span>
                          {label}
                          <small style={{ display: "block" }}>
                            {payload?.hourly?.time?.[i] || "Sin fecha"}
                          </small>
                        </span>
                        <strong>
                          {fmt(payload?.hourly?.["temperature_2m_" + id]?.[i])}{" "}
                          <small>°C</small>
                        </strong>
                      </div>
                    );
                  })}
                  <p className="footnote">
                    Temperatura a 2 m · zona {payload?.timezone || "sin dato"}.
                    El JSON exportado incluye además humedad, lluvia y viento de
                    cada modelo.
                  </p>
                </>
              )}
              {view === "escenas" && (
                <>
                  <div className="scene-list">
                    {scenes.map((s) => (
                      <article className="scene" key={s.id}>
                        {s.assets?.thumbnail?.href && (
                          <img
                            src={
                              "/api/fuentes/foto?" +
                              new URLSearchParams({
                                asset: s.assets.thumbnail.href,
                              })
                            }
                            alt="Fotografía satelital de la escena Sentinel-2 completa"
                            onError={(e) => (e.currentTarget.hidden = true)}
                          />
                        )}
                        <div>{s.properties.datetime.slice(0, 19)} UTC</div>
                        <div>
                          Nubes: {fmt(s.properties["eo:cloud_cover"])}% de
                          escena
                        </div>
                        <a
                          href={
                            s.links.find((l: Data) => l.rel === "self")?.href
                          }
                          target="_blank"
                          rel="noopener"
                        >
                          {s.id}
                        </a>
                      </article>
                    ))}
                  </div>
                  <p className="footnote">
                    Fotografías reales de escenas completas. No representan
                    exclusivamente el lote. NDVI pendiente de procesamiento.
                  </p>
                </>
              )}
              {view === "historico" && (
                <p className="small">
                  NASA POWER · {history?.header?.start || "sin fecha"} —{" "}
                  {history?.header?.end || "sin fecha"}. Serie diaria de
                  temperatura, humedad y precipitación corregida. Horario LST;
                  grilla regional.
                </p>
              )}
              {view === "rios" && (
                <p className="small">
                  Caudal simulado GloFAS en m³/s. Celda devuelta:{" "}
                  {fmt(river?.latitude, 4)}, {fmt(river?.longitude, 4)}. La
                  selección automática corresponde al río dominante en el área;
                  verificar que represente el río buscado. No es altura de agua
                  ni medición de estación. Caudales muy pequeños pueden
                  corresponder a una celda que no representa el Paraná.
                </p>
              )}
              {view === "suelo" && payload?.dots_summary && <>
                {payload.dots_summary.available_water_mm_0_60!=null && <div className="key"><span>Agua útil del suelo · 0–60 cm</span><strong>{fmt(payload.dots_summary.available_water_mm_0_60,0)} mm</strong><small className="small">lo que el suelo puede guardar para el pasto entre capacidad de campo y marchitez</small></div>}
                <div className="soil-table"><div className="soil-head"><span>Propiedad</span>{payload.dots_summary.depths.map((d:string)=><span key={d}>{d.replace("cm"," cm")}</span>)}</div>
                  {payload.dots_summary.rows.map((r:Data)=><div className="soil-row" key={r.key}><span>{r.label}<small>{r.unit}</small></span>{payload.dots_summary.depths.map((d:string)=><b key={d}>{r.by_depth?.[d]!=null?fmt(r.by_depth[d],r.key==="nitrogen"||r.key==="bdod"?2:1):"—"}</b>)}</div>)}
                </div>
                <p className="footnote">{payload.dots_summary.note}</p>
              </>}
              {view === "suelo" && (
                <div className="metric-card">
                  <span className="muted">
                    Nitrógeno total · {depth?.label || "0–5 cm"}
                  </span>
                  <strong>
                    {fmt(
                      depth?.values?.mean !== undefined
                        ? depth.values.mean /
                            (nitrogen.unit_measure?.d_factor || 1)
                        : null,
                      3,
                    )}{" "}
                    {nitrogen?.unit_measure?.target_units || ""}
                  </strong>
                  <p>
                    SoilGrids: predicción espacial estática a 250 m, no
                    nitrógeno disponible medido hoy. Requiere análisis de
                    laboratorio para decisiones de fertilización.
                  </p>
                </div>
              )}
              {view === "serie" && (
                <>
                  <label className="small">
                    Período{" "}
                    <select
                      value={years}
                      onChange={(e) => {
                        const y = Number(e.target.value);
                        setYears(y);
                        void load("serie", point, y);
                      }}
                    >
                      <option value={20}>20 años completos</option>
                      <option value={30}>30 años completos</option>
                    </select>
                  </label>
                  <p className="small" style={{ marginTop: 12 }}>
                    ERA5 · {payload?.daily?.time?.[0] || "sin fecha"} —{" "}
                    {payload?.daily?.time?.at(-1) || "sin fecha"}. Reanálisis
                    regional, no estación local. Los años incompletos se
                    muestran sin valor.
                  </p>
                </>
              )}
              {view === "proyeccion" && (
                <p className="warning">
                  CMIP6 / MPI-ESM1-2-XR · 2031–2040. Simulación climática de un
                  modelo con corrección de sesgo; no pronóstico diario ni
                  observación. Esta prueba no compara escenarios ni modelos.
                </p>
              )}
              {sources[view]?.payload && (
                <p className="footnote">
                  Consulta: {sources[view].payload!.consulted_at}
                  <br />
                  <a
                    href={sources[view].payload!.source_url}
                    target="_blank"
                    rel="noopener"
                  >
                    Ver respuesta de la fuente
                  </a>
                </p>
              )}
              {view==="relieve" && (()=>{const t=terrainRef.current; const s=t && t.key===lotKey ? t.a.summary : null; const busy=sources.relieve?.status==="consultando"; return <>
                <p className="footnote">Copernicus DEM 30 m leído por partes desde el navegador. Se calculan bajos cerrados, escurrimiento y humedad topográfica del lote y su entorno, sin servidor.</p>
                {!s && !busy && <button className="primary" style={{width:"100%"}} onClick={()=>void loadTerrain()} disabled={vertices.length<3}>{vertices.length<3?"Dibujá un lote primero":t?"Recalcular para este lote":"Analizar relieve del lote"}</button>}
                {busy && <p className="small">Leyendo el DEM y calculando el escurrimiento…</p>}
                {s && <>
                  <div className={"verdict "+(s.riskPct.alto>=15?"warn":"ok")}><span>Posición en el paisaje</span><b>{s.positionLabel==="bajo"?"Bajo":s.positionLabel==="loma"?"Loma":"Media loma"} · {s.position} / 100</b><small>{s.riskPct.alto>=15?`${fmt(s.riskPct.alto,0)} % del lote con alta propensión a anegarse.`:"Sin sectores extensos propensos a anegarse."} Cota media {fmt(s.elevMean,1)} m; entorno {fmt(s.envMean,1)} m.</small></div>
                  <div className="keygrid">
                    <div className="key"><span>Desnivel dentro del lote</span><strong>{fmt(s.relief,1)} <small>m (p5–p95)</small></strong></div>
                    <div className="key"><span>Pendiente media</span><strong>{fmt(s.slopeMeanPct,2)} <small>%</small></strong></div>
                    <div className="key"><span>Bajos cerrados ≥ 10 cm</span><strong>{fmt(s.depressionHa,1)} <small>ha · {fmt(s.depressionPct,0)} %</small></strong></div>
                    <div className="key"><span>Agua que retienen</span><strong>{fmt(s.storageM3/1000,1)} <small>mil m³ · máx {fmt(s.maxDepthM,2)} m</small></strong></div>
                    <div className="key"><span>Vías de escurrimiento</span><strong>{fmt(s.drainageHa,1)} <small>ha del lote</small></strong></div>
                    <div className="key"><span>Casi plano (&lt; 0,5 %)</span><strong>{fmt(s.flatPct,0)} <small>%</small></strong></div>
                  </div>
                  <div className="terrain-bar" aria-label="Propensión a anegarse">{(["bajo","medio","alto"] as const).map((k,i)=><i key={k} style={{width:s.riskPct[k]+"%",background:`rgb(${RISK_COLORS[i+1].join(",")})`}} title={`${k}: ${s.riskPct[k]} %`}/>)}</div>
                  <div className="dots-legend-inline">{[["bajo","Baja"],["medio","Media"],["alto","Alta"]].map(([k,l],i)=><span key={k}><i style={{background:`rgb(${RISK_COLORS[i+1].join(",")})`}}/>{l} {fmt((s.riskPct as any)[k],0)} %</span>)}<span><i style={{background:`rgb(${DRAIN_COLOR.join(",")})`}}/>Escurrimiento</span></div>
                  <div className="overlay-switch"><span>Capa sobre el lote</span>{([["anegamiento","Anegamiento"],["relieve","Relieve"],["pendiente","Pendiente"],["twi","Humedad topográfica"],["off","Ninguna"]] as const).map(([k,l])=><button key={k} className={terrainMode===k?"active":""} onClick={()=>setTerrainMode(k)}>{l}</button>)}</div>
                  <p className="footnote">Método: relleno de depresiones priority-flood (Barnes 2014), flujo D8, pendiente de Horn e índice topográfico de humedad ln(a/tan β). Propensión alta = bajo de 20 cm o más, o humedad topográfica en el 10 % superior del entorno; media = 5 cm o 25 % superior. Escurrimiento = más de 10 ha aguas arriba. Celdas de {s.cellM} m.</p>
                  <p className="warning">El DEM es un modelo de superficie: montes y construcciones suman altura. En llanuras con desniveles de centímetros es un indicador relativo, no una cota de inundación. Validar con recorrida, napa y antecedentes de lluvia.</p>
                  <p className="footnote">{DEM_ATTRIBUTION}.</p>
                  <button style={{width:"100%",marginTop:8}} onClick={()=>void loadTerrain()}>Recalcular</button>
                </>}
              </>})()}
              {view!=="alertas" && view!=="forraje" && view!=="relieve" && view!=="costos" && <button
                style={{ width: "100%", marginTop: 13 }}
                onClick={() => void load(view)}
              >
                Reintentar / Actualizar fuente
              </button>}
            </div>
          </section>
          <section className="panel block" hidden={sideTab!=="datos"}>
            <div className="section-title">FUENTES DEL MUNDO</div>
            <p className="footnote">
              Brasil, Argentina, Chile, Colombia, Venezuela, México, EE.UU.,
              Canadá, Europa, Sudáfrica, Japón, China y Rusia. Los modelos
              globales cubren estos territorios; las conexiones nacionales
              tienen estados propios.
            </p>
            <a
              className="small"
              href="/FUENTES-GLOBALES.md"
              target="_blank"
              rel="noreferrer"
            >
              Ver registro de fuentes y acceso ↗
            </a>
          </section>
          <section className="panel block lot-manager" hidden={sideTab!=="lote"}>
            <div className="section-title">LOTES DEL ESTABLECIMIENTO</div>
            <p className="footnote">Cada polígono conserva límites, superficie y contexto de análisis. Seleccioná un lote para consultar todas las fuentes sobre ese territorio.</p>
            <div className="lot-list">{lots.length===0?<span className="small">Todavía no hay lotes delimitados.</span>:lots.map(l=><button key={l.id} className={selectedLotId===l.id?"active":""} onClick={()=>selectLot(l.id)}><strong>{l.name}</strong><span>{l.areaHa.toFixed(2)} ha</span></button>)}</div>
            {(()=>{const l=lots.find(x=>x.id===selectedLotId); if(!l) return null; const c=l.compactness; const nb=l.ftw?.neighborhood; return <div className="lot-vars">
              <div className="lot-vars-title">Variables del lote <button className="lot-delete" onClick={()=>removeLot(l.id)} title="Borrar este lote del navegador">Borrar lote</button></div>
              <div className="lot-var"><span>Superficie</span><b>{fmt(l.areaHa,1)} ha</b></div>
              <div className="lot-var"><span>Perímetro</span><b>{fmt(l.perimeterKm,2)} km</b></div>
              <div className="lot-var" title="Polsby-Popper: 1 es un círculo. Bajo 0,4 el lote es alargado o irregular: más alambrado por hectárea y aguadas más lejanas."><span>Compacidad</span><b>{c!=null?`${fmt(c,2)} · ${c>=0.6?"compacto":c>=0.4?"intermedio":"alargado"}`:"—"}</b></div>
              <div className="lot-var"><span>Origen del límite</span><b>{l.ftw?"FTW automático":"Dibujado"}</b></div>
              {l.ftw && <div className="lot-var"><span>Confianza FTW</span><b className={l.ftw.reliable?"ok":"warn"}>{l.ftw.confidence!=null?Math.round(l.ftw.confidence):"sin dato"}{l.ftw.reliable?"":" · revisar"}</b></div>}
              {nb && <>
                <div className="lot-vars-title">Entorno · radio {nb.radiusKm} km</div>
                <div className="lot-var"><span>Lotes agrícolas detectados</span><b>{nb.count}</b></div>
                <div className="lot-var"><span>Tamaño medio · mediana</span><b>{nb.meanHa!=null?`${fmt(nb.meanHa,1)} · ${fmt(nb.medianHa,1)} ha`:"—"}</b></div>
                <div className="lot-var"><span>Superficie agrícola</span><b>{fmt(nb.coverPct,1)} %</b></div>
                {nb.reliablePct!=null && <div className="lot-var"><span>Con confianza alta</span><b>{nb.reliablePct} %</b></div>}
                <p className="footnote">Fields of the World detecta cultivos anuales: un valor bajo en zona ganadera indica predominio de pasturas o monte, no ausencia de producción.</p>
              </>}
            </div>})()}
            <div className="lot-io">
              <label className="data-button" title="KML de Google Earth o GeoJSON">Importar lotes (KML / GeoJSON)<input type="file" accept=".kml,.kmz,.geojson,.json,application/vnd.google-earth.kml+xml,application/geo+json" onChange={e=>{void importLots(e.target.files?.[0]);e.target.value=""}}/></label>
              {lots.length>0 && <><button onClick={()=>exportLots("kml")}>Descargar KML</button><button onClick={()=>exportLots("geojson")}>Descargar GeoJSON</button></>}
            </div>
            {cloudOn !== null && <div className="cloud-box">
              <div className="lot-vars-title">Procesamiento semanal · agua por satélite</div>
              {cloudOn ? <>
                <p className="footnote">Guardá tus lotes en el repositorio privado de DOTS. Cada lunes se analizan con geoai sobre Sentinel-2 para detectar aguadas, tajamares y bajos con agua.</p>
                <input type="password" value={cloudKey} onChange={e=>setCloudKey(e.target.value)} placeholder="Clave del establecimiento" aria-label="Clave del establecimiento" autoComplete="current-password"/>
                <button className="primary" style={{width:"100%",marginTop:6}} onClick={()=>void syncLots()} disabled={cloudBusy||!lots.length}>{cloudBusy?"Guardando…":"Guardar lotes en la nube"}</button>
                {cloudMsg && <p className="small" style={{marginTop:6}}>{cloudMsg}</p>}
              </> : <p className="footnote">Todavía no está activado en este sitio. Por ahora los lotes se guardan solo en este navegador.</p>}
            </div>}
            {selectedLotId&&<button className="primary" style={{width:"100%",marginTop:10}} onClick={()=>void askDots("Analizá integralmente el lote seleccionado: clima, agua, suelo, vegetación, riesgos, ENSO y trazabilidad. No inventes variables faltantes.")}>{agentBusy?"Analizando fuentes…":"Analizar lote seleccionado"}</button>}
          </section>
          <section className="panel block operations" hidden={sideTab!=="lote"}>
            <div className="tag">OPERACIONES DEL LOTE</div>
            <div className="draw-chooser"><button onClick={()=>startDraw("triangle")}><Triangle className="icon"/>Triángulo</button><button onClick={()=>startDraw("rectangle")}><Square className="icon"/>Rectángulo</button><button onClick={()=>startDraw("free")}><Layers className="icon"/>Polígono libre</button><button className="ftw-btn" onClick={startFtw} title="Lote automático desde el mapa global Fields of the World (gratis)"><Sprout className="icon"/>Automático · FTW</button></div>
            <p className="footnote">Cada informe queda vinculado al polígono cerrado: superficie, perímetro, centroide y límites.</p>
            <div className="marker-chooser"><select value={markerType} onChange={e=>setMarkerType(e.target.value)}>{["General","Rodeo","Agua","Vegetación","Infraestructura","Riesgo"].map(g=><optgroup key={g} label={g}>{MARKER_KINDS.filter(k=>k.group===g).map(k=><option key={k.key} value={k.key}>{k.label}</option>)}</optgroup>)}</select><button type="button" onClick={()=>addFieldMarker()}>{placingMarker?"Clic en el mapa…":"+ Marcar en mapa"}</button></div>
            <div className="actions">
              <button className="advanced-json" title="Exportación técnica / avanzada"
                onClick={() => {
                  if (!Object.values(sources).some((s) => s.payload)) {
                    notify("Todavía no hay datos para exportar");
                    return;
                  }
                  download(
                    new Blob(
                      [
                        JSON.stringify(
                          {
                            point,
                            polygon: poly.current ? vertices : null,
                            sources,
                          },
                          null,
                          2,
                        ),
                      ],
                      { type: "application/json" },
                    ),
                    "DOTS-datos.json",
                  );
                }}
              >
                <Download className="icon" />
                Exportación técnica
              </button>
              <button
                className="primary"
                onClick={() => void pdf()}
                disabled={pdfBusy}
              >
                <FileText className="icon" />
                {pdfBusy ? "Generando…" : "Informe Territorial DOTS · PDF"}
              </button>
              <button
                style={{ gridColumn: "1/-1" }}
                onClick={() => window.print()}
              >
                Imprimir dashboard
              </button>
            </div>
          </section>
        </aside>
        <section className="ta-map-card">
        <div id="map" ref={mapEl} />
        <div className="panel toolbar">
          <button
            className={layer === "base" ? "active" : ""}
            onClick={() => setLayer("base")}
            aria-pressed={layer === "base"}
          >
            Mapa satelital
          </button>
          <button className={layer === "modis" ? "active" : ""} onClick={() => setLayer("modis")} aria-pressed={layer === "modis"}>MODIS · imagen</button>
          <select value={gibsLayer} onChange={e=>{setGibsLayer(e.target.value); const d=GIBS_LAYERS.find(([k])=>k===e.target.value)?.[2]; if(d) notify(d);}} aria-label="Capas de NASA y cobertura del suelo">{GIBS_LAYERS.map(([k,l])=><option key={k} value={k}>{l}</option>)}</select>
          <select value={openBase} onChange={e=>setOpenBase(e.target.value)} aria-label="Mapa base" title="Mapa base (catálogo abierto)">
            <option value="">Mapa base · Esri satelital (DOTS)</option>
            {LAYER_GROUPS.map(g=><optgroup key={g} label={g}>{OPEN_LAYERS.filter(l=>l.group===g&&!l.overlay).map(l=><option key={l.id} value={l.id}>{l.name}</option>)}</optgroup>)}
          </select>
          <select value={openOver} onChange={e=>setOpenOver(e.target.value)} aria-label="Capa superpuesta" title="Capa superpuesta (catálogo abierto)">
            <option value="">Capa superpuesta · ninguna</option>
            {LAYER_GROUPS.map(g=><optgroup key={g} label={g}>{OPEN_LAYERS.filter(l=>l.group===g&&l.overlay).map(l=><option key={l.id} value={l.id}>{l.name}</option>)}</optgroup>)}
          </select>
          {openOver && <label className="small" style={{display:"inline-flex",alignItems:"center",gap:6}}>Transparencia<input type="range" min={0.2} max={1} step={0.05} value={openOpacity} onChange={e=>setOpenOpacity(Number(e.target.value))}/></label>}
          <button onClick={()=>changeView("firms")}>FIRMS · focos térmicos</button>
          <button onClick={()=>changeView("nasa-power-30")}>NASA POWER · clima</button>
          <button onClick={()=>changeView("enso")}>ENSO · multifuente</button>
          <button onClick={()=>changeView("suelo")}>SoilGrids · suelo</button>
          <button onClick={()=>changeView("gibs")}>NASA GIBS · verificar servicio</button>
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            aria-label="Fecha de imagen MODIS"
            max={new Date().toISOString().slice(0, 10)}
          />
        </div>
        <div className="map-meta">
          {layer === "base"
            ? "ESRI WORLD IMAGERY · MOSAICO BASE · FECHA DE CADA ESCENA NO HOMOGÉNEA"
            : `NASA MODIS / ${date} / 250 m nominal · no resuelve animales`}
        </div>
        <div className="tools">
          <button onClick={() => mapRef.current?.zoomIn()} aria-label="Acercar">
            <Plus size={16} />
          </button>
          <button onClick={() => mapRef.current?.zoomOut()} aria-label="Alejar">
            <Minus size={16} />
          </button>
          <button
            onClick={() =>
              poly.current
                ? mapRef.current?.fitBounds(poly.current.getBounds())
                : mapRef.current?.setView(point, 13)
            }
            aria-label="Centrar"
          >
            <Focus size={16} />
          </button>
        </div>
        {ftwMode && (
          <div className="panel message show ftw-message">
            <p><b>Lote automático</b><br/>{ftwBusy?"Reconstruyendo el lote…":"Tocá dentro de un contorno. Verde: confianza alta. Ámbar: revisar borde."}</p>
            <p className="small">Fields of the World mapea cultivos anuales; en pasturas puede no haber contorno. {FTW_ATTRIBUTION}.</p>
            <div className="row"><button onClick={stopFtw}>Cancelar</button></div>
          </div>
        )}
        {drawing && (
          <div className="panel message show">
            <p><b>{drawMode==="rectangle"?"Rectángulo":drawMode==="triangle"?"Triángulo":"Polígono libre"}</b> · {vertices.length} {vertices.length===1?"punto":"puntos"}<br/>
              {drawMode==="rectangle"?"Tocá dos esquinas opuestas: el lote se cierra solo.":drawMode==="triangle"?"Tocá tres esquinas: el lote se cierra solo.":
                vertices.length<3?"Tocá las esquinas del lote siguiendo el borde.":"Para cerrar: tocá el punto amarillo, hacé doble clic o tocá Finalizar."}</p>
            <div className="row">
              <button
                className="primary"
                disabled={drawMode==="rectangle" ? !(vertices.length===2||vertices.length===4) : vertices.length < 3}
                onClick={()=>finish()}
              >
                Finalizar
              </button>
              <button onClick={undoPoint} disabled={!vertices.length}>Deshacer punto</button>
              <button onClick={stopDraw}>Cancelar</button>
            </div>
          </div>
        )}
        <div className="map-bottom">
          WGS84 · {fmt(point[0], 5)} / {fmt(point[1], 5)} ·{" "}
          {poly.current
            ? "LÍMITE DELIMITADO POR EL USUARIO"
            : "SIN LÍMITES CATASTRALES"}
        </div>
        {GIBS_RANGES[gibsLayer] && <div className="dots-legend wc-legend gibs-ranges" aria-label={"Rangos: "+GIBS_RANGES[gibsLayer].title}><b>{GIBS_RANGES[gibsLayer].title}</b>{GIBS_RANGES[gibsLayer].rows.map(([r,l])=><span key={r}><em>{r}</em>{l}</span>)}{GIBS_RANGES[gibsLayer].note && <small>{GIBS_RANGES[gibsLayer].note}</small>}</div>}
        {gibsLayer.includes("_Flood_") && <div className="dots-legend wc-legend" aria-label="Leyenda de crecidas">{FLOOD_CLASSES.map(([c,l])=><span key={l}><i style={{background:c}}/>{l}</span>)}</div>}
        {gibsLayer===WORLDCOVER && <div className="dots-legend wc-legend" aria-label="Leyenda WorldCover">{WORLDCOVER_CLASSES.map(([c,l])=><span key={l}><i style={{background:c}}/>{l}</span>)}</div>}
        <MarkerLegend types={[...fieldMarkers.map((m:any)=>m.type),...waterAssets.map((a:any)=>a.type)]}/>
        </section>
        <aside className="inspector">
          <section className="panel block">
            <div className="row">
              <h2>
                <Thermometer className="icon" />
                Entorno del ganado
              </h2>
              <span className="tag">THI</span>
            </div>
            {(()=>{const tn=thi==null?"idle":thi>=79?"risk":thi>=72?"warn":"ok";const word=thi==null?"Sin dato":thi>=79?"Peligro":thi>=72?"Alerta":"Sin estrés";const pos=thi==null?0:Math.min(100,Math.max(0,(thi-60)/30*100));return <div className={"cv-thi tone-"+tn}>
              <div className="cv-thi-top"><strong>{thi==null?"—":fmt(thi)}</strong><span className={"cv-tag tone-"+tn}>{word}</span></div>
              <div className="cv-thi-scale" aria-hidden="true"><i style={{left:"40%"}}/><i style={{left:"63.3%"}}/>{thi!=null&&<b style={{left:pos+"%"}}/>}</div>
              <div className="cv-thi-legend"><span style={{left:0}}>60</span><span style={{left:"40%"}}>72 alerta</span><span style={{left:"63.3%"}}>79 peligro</span></div>
            </div>})()}
            <p className="small">
              Calculado con temperatura y humedad del modelo. Sin diagnóstico
              veterinario automático.
            </p>
            <div className="notice">
              <strong>
                <TriangleAlert className="icon" />
                Pasturas / NDVI
              </strong>
              {(sources.ndvi?.payload as any)?.data?.latest ? <p>
                NDVI medio {fmt((sources.ndvi?.payload as any).data.latest.ndvi_mean,2)} · {String((sources.ndvi?.payload as any).data.latest.datetime||"").slice(0,10)} · Sentinel-2, nubes del lote excluidas.
              </p> : <p>
                {vertices.length>=3 ? <button className="data-button" style={{marginTop:6}} onClick={()=>changeView("ndvi")}>Calcular NDVI del lote</button> : "Dibujá un lote para calcular NDVI Sentinel-2 dentro del polígono."}
              </p>}
            </div>
            <div className="notice">
              <strong>Ganado / bebederos</strong>
              <p>
                Sin inventario ni sensores conectados. Ningún conteo se infiere
                de estas imágenes.
              </p>
            </div>
          </section>
          <section className="panel block sources">
            <h2>
              <Satellite className="icon" />
              Últimas escenas recibidas
            </h2>
            <div className="scene-thumbs" style={{ marginTop: 12 }}>
              {scenes
                .slice(0, 2)
                .map((s) =>
                  s.assets?.thumbnail?.href ? (
                    <img
                      key={s.id}
                      src={
                        "/api/fuentes/foto?" +
                        new URLSearchParams({ asset: s.assets.thumbnail.href })
                      }
                      alt={"Escena satelital " + s.id}
                      onError={(e) => (e.currentTarget.hidden = true)}
                    />
                  ) : null,
                )}
            </div>
            <p className="photo-credit">
              Copernicus Sentinel‑2 / Earth Search.{" "}
              {scenes.length
                ? scenes[0].properties.datetime.slice(0, 10)
                : "Sin fotografía disponible"}
              . Escenas completas.
            </p>
            <p className="footnote">
              El mapa y los modelos no reemplazan la inspección en campo.
              Consulta al centroide aproximado, no promedio espacial.
            </p>
          </section>
        </aside>
        <section className="charts" key={theme}>
          {view==="relieve" && payload?.histogram && payload?.lot===lotKey ? <>
            <section className="panel chart"><h2>Distribución de cotas del lote</h2><p className="small">Copernicus DEM 30 m · % del lote por franja de altura · m s. n. m.</p><Chart dates={payload.histogram.map((h:Data)=>`${fmt(h.from,1)}–${fmt(h.to,1)}`)} unit="% del lote" series={[{name:"Superficie",values:payload.histogram.map((h:Data)=>h.pct),type:"bar",color:"#06b6d4"}]}/></section>
            <section className="panel chart"><h2>Propensión a anegarse</h2><p className="small">% del lote por clase · bajos cerrados y humedad topográfica</p><Chart dates={["Baja","Media","Alta"]} unit="% del lote" series={[{name:"Superficie",values:[payload.riskPct.bajo,payload.riskPct.medio,payload.riskPct.alto],type:"bar",color:"#e9bd72"}]}/></section>
          </> : view==="forraje" && payload?.daily ? <>
            <section className="panel chart"><h2>Crecimiento diario del pasto</h2><p className="small">kg MS/ha/día · {payload.kind_label} · últimos 60 días</p><Chart dates={payload.daily.map((d:Data)=>d.date.slice(5))} unit="kg MS/ha/día" series={[{name:"Crecimiento",values:payload.daily.map((d:Data)=>d.ppna),color:"#19b98a"}]}/></section>
            <section className="panel chart"><h2>Producción por mes</h2><p className="small">kg MS/ha acumulados en cada mes</p><Chart dates={payload.monthly.map((m:Data)=>m.month)} unit="kg MS/ha" series={[{name:"Producción",values:payload.monthly.map((m:Data)=>m.total),type:"bar",color:"#22c55e"}]}/></section>
          </> : view==="balance-agua" && payload?.recent ? <>
            <section className="panel chart"><h2>Balance de agua mes a mes</h2><p className="small">ERA5 · lluvia − evapotranspiración de referencia · mm · últimos 12 meses</p><Chart dates={payload.recent.map((r:Data)=>r.period)} unit="mm" series={[{name:"Balance",values:payload.recent.map((r:Data)=>r.balance_mm),type:"bar",color:"#3a8ee6"},{name:"Normal 1991–2020",values:payload.recent.map((r:Data)=>r.normal_balance_mm),color:"#98a2b3"}]}/></section>
            <section className="panel chart"><h2>Balance anual desde 1991</h2><p className="small">mm por año · negativo = el ambiente pidió más agua de la que llovió</p><Chart dates={payload.annual.map((r:Data)=>String(r.year))} unit="mm" series={[{name:"Balance anual",values:payload.annual.map((r:Data)=>r.balance_mm),type:"bar",color:"#f79009"}]}/></section>
          </> : view==="radar-agua" && payload?.series?.length ? <>
            <section className="panel chart"><h2>Agua en el lote por radar</h2><p className="small">Sentinel-1 · % del lote con agua libre en cada pasada</p><Chart dates={payload.series.filter((r:Data)=>r.status==="válida").map((r:Data)=>String(r.datetime).slice(0,10))} unit="%" series={[{name:"Agua",values:payload.series.filter((r:Data)=>r.status==="válida").map((r:Data)=>Math.round(r.water_fraction*1000)/10),type:"bar",color:"#3a8ee6"}]}/></section>
          </> : view==="indices-espectrales" && payload?.indices?.length ? <>
            <section className="panel chart"><h2>Índices del lote</h2><p className="small">Media dentro del polígono · última escena despejada · índices de escala −1 a 1 (el resto, en la lista)</p><Chart dates={payload.indices.filter((x:Data)=>x.mean!=null&&Math.abs(x.mean)<=1.2).map((x:Data)=>x.name)} unit="" series={[{name:"Media",values:payload.indices.filter((x:Data)=>x.mean!=null&&Math.abs(x.mean)<=1.2).map((x:Data)=>x.mean),type:"bar",color:"#19b98a"}]}/></section>
          </> : view==="costos" && payload?.sensitivity ? <>
            <section className="panel chart"><h2>Margen según el precio de venta</h2><p className="small">$ totales · precio −20 % a +20 % · con la tarifa de flete actual y con +25 %</p><Chart dates={payload.sensitivity.map((r:Data)=>`${Math.round((r.price_factor-1)*100)>0?"+":""}${Math.round((r.price_factor-1)*100)} %`)} unit="$" series={[{name:"Margen",values:payload.sensitivity.map((r:Data)=>r.net),type:"bar",color:"#22c55e"},...(payload.sensitivity[0].net_freight_up!=null?[{name:"Flete +25 %",values:payload.sensitivity.map((r:Data)=>r.net_freight_up),color:"#f79009"}]:[])]}/></section>
          </> : view==="sustentabilidad" && payload?.deforestation?.series?.length ? <>
            <section className="panel chart"><h2>Cobertura del lote por año</h2><p className="small">Impact Observatory 10 m · % del lote · árboles, pastizal y cultivo · corte EUDR 2020</p><Chart dates={payload.deforestation.series.map((r:Data)=>String(r.year))} unit="%" series={[{name:"Árboles",values:payload.deforestation.series.map((r:Data)=>r.trees!=null?r.trees*100:null),color:"#22c55e"},{name:"Pastizal",values:payload.deforestation.series.map((r:Data)=>r.rangeland!=null?r.rangeland*100:null),color:"#e9bd72"},{name:"Cultivo",values:payload.deforestation.series.map((r:Data)=>r.crops!=null?r.crops*100:null),color:"#a7a5ff"}]}/></section>
          </> : view==="nasa-power-30" && pclim ? <>
            <section className="panel chart"><h2>Temperatura media por mes</h2><p className="small">NASA POWER · promedio {pclim.from}–{pclim.to} · °C a 2 m</p><Chart dates={MES} unit="°C" series={[{name:"Temperatura media",values:pclim.temp,color:"#f0b974"}]}/></section>
            <section className="panel chart"><h2>Lluvia por mes</h2><p className="small">NASA POWER · promedio {pclim.from}–{pclim.to} · mm por mes</p><Chart dates={MES} unit="mm" series={[{name:"Lluvia",values:pclim.rain.map(v=>Math.round(v)),type:"bar",color:"#06b6d4"}]}/></section>
            <section className="panel chart"><h2>Lluvia de cada año</h2><p className="small">Total anual · líneas: mediana, límite de año seco y de año lluvioso</p><Chart dates={pclim.years} unit="mm" series={[{name:"Lluvia anual",values:pclim.annualRain,type:"bar",color:"#3a8ee6"},...(pclim.medRain!=null?[{name:"Mediana",values:pclim.years.map(()=>pclim.medRain),color:"#77868b"},{name:"Límite año seco (75 %)",values:pclim.years.map(()=>Math.round((pclim.medRain as number)*.75)),color:"#e9bd72"},{name:"Límite año lluvioso (125 %)",values:pclim.years.map(()=>Math.round((pclim.medRain as number)*1.25)),color:"#a7a5ff"}]:[])]}/></section>
          </> : view==="estadistica" && payload?.climatology ? <>
            <section className="panel chart"><h2>Probabilidad de helada y calor por mes</h2><p className="small">ERA5 1991–{new Date().getFullYear()-1} · % de años con al menos una helada · días con máxima ≥ 35 °C</p><Chart dates={payload.climatology.map((m:Data)=>m.label)} unit="%" series={[{name:"Prob. de helada",values:payload.climatology.map((m:Data)=>m.p_frost),type:"bar",color:"#93c5fd"},{name:"Días ≥ 35 °C",values:payload.climatology.map((m:Data)=>m.heat_days),color:"#fd9c91"}]}/></section>
            <section className="panel chart"><h2>Lluvia mensual típica</h2><p className="small">Terciles 1991–hoy · seco por debajo, lluvioso por encima · mm</p><Chart dates={payload.climatology.map((m:Data)=>m.label)} unit="mm" series={[{name:"Tercil seco",values:payload.climatology.map((m:Data)=>m.rain_p33),color:"#e9bd72"},{name:"Mediana",values:payload.climatology.map((m:Data)=>m.rain_med),type:"bar",color:"#06b6d4"},{name:"Tercil lluvioso",values:payload.climatology.map((m:Data)=>m.rain_p67),color:"#a7a5ff"}]}/></section>
          </> : view==="lluvia" && payload?.recent ? <>
            <section className="panel chart"><h2>Lluvia mensual vs. normal</h2><p className="small">CHIRPS · últimos 12 meses · mm · normal = mediana 1991–2020</p><Chart dates={payload.recent.map((r:Data)=>r.period)} unit="mm" series={[{name:"Lluvia",values:payload.recent.map((r:Data)=>r.mm),type:"bar",color:"#06b6d4"},{name:"Normal",values:payload.recent.map((r:Data)=>r.normal),color:"#e9bd72"}]}/></section>
            <section className="panel chart"><h2>Lluvia anual observada</h2><p className="small">CHIRPS · años completos · mm</p><Chart dates={(payload.annual||[]).map((r:Data)=>String(r.year))} unit="mm" series={[{name:"Lluvia anual",values:(payload.annual||[]).map((r:Data)=>r.mm),type:"bar",color:"#19b98a"}]}/></section>
          </> : view==="indices" && payload?.years ? <>
            <section className="panel chart"><h2>Lluvia anual y días de lluvia intensa</h2><p className="small">ERA5 · mm por año · días con 20 mm o más</p><Chart dates={payload.years.map((r:Data)=>String(r.year))} unit="mm" series={[{name:"Lluvia anual",values:payload.years.map((r:Data)=>r.prcptot),type:"bar",color:"#06b6d4"}]}/></section>
            <section className="panel chart"><h2>Heladas y calor extremo</h2><p className="small">Días por año · mínima menor a 0 °C · máxima de 35 °C o más</p><Chart dates={payload.years.map((r:Data)=>String(r.year))} unit="días" series={[{name:"Heladas",values:payload.years.map((r:Data)=>r.frost_days),color:"#93c5fd"},{name:"Máx ≥ 35 °C",values:payload.years.map((r:Data)=>r.tx35),color:"#fd9c91"},{name:"Racha seca",values:payload.years.map((r:Data)=>r.cdd),color:"#e9bd72"}]}/></section>
          </> : view==="teleconexiones" && payload?.indices ? <>
            {[["Pacífico ecuatorial · El Niño",["nino34","oni","meiv2"]],["Hemisferio sur y Atlántico",["aao","soi","tsa"]]].map(([title,keys]:any)=><section className="panel chart" key={title}><h2>{title}</h2><p className="small">NOAA PSL · últimos 12 meses publicados</p><Chart dates={(payload.indices[keys[0]]?.data?.last12||[]).map((r:Data)=>r.period)} unit="índice" series={keys.map((k:string,i:number)=>({name:payload.indices[k]?.data?.name||k,values:(payload.indices[k]?.data?.last12||[]).map((r:Data)=>r.value),color:["#06b6d4","#e9bd72","#a7a5ff"][i]}))}/></section>)}
          </> : NDVI_VIEWS.includes(view) ? <section className="panel chart"><h2>NDVI del lote · serie</h2><p className="small">{payload?.sensor||"Sentinel-2"} · media zonal dentro del polígono · escenas nubladas en el lote excluidas</p><Chart dates={(payload?.series||[]).filter((r:Data)=>r.status==="válida").map((r:Data)=>(r.datetime||r.from||"").slice(0,10))} unit="NDVI" series={[{name:"NDVI medio",values:(payload?.series||[]).filter((r:Data)=>r.status==="válida").map((r:Data)=>r.ndvi_mean??null),color:"#19b98a"}]}/></section> : view==="ina" ? <><section className="panel chart"><h2>{inaSeries==="37299"?"Temperatura observada":"Río Paraná · altura observada"}</h2><p className="small">INA · Bella Vista · serie {inaSeries} · fechas originales</p><Chart dates={(payload?.data||[]).map((r:Data)=>r.timestart)} unit={payload?.responseHeader?.seriesmetadata?.unit_abrev||"m"} series={[{name:"Altura",values:(payload?.data||[]).map((r:Data)=>r.valor??null),color:"#06b6d4"}]}/></section><section className="panel chart"><h2>Estación hidrométrica</h2><p className="footnote">Nivel del río medido en una estación; no describe inundación del lote. Para evaluar riesgo hacen falta relieve, umbrales y delimitación de la cuenca.</p></section></> : view==="aire" ? <>{["pm2_5","pm10"].map((k,i)=><section className="panel chart" key={k}><h2>{i===0?"Partículas PM2.5":"Partículas PM10"}</h2><p className="small">CAMS · pronóstico modelado · UTC</p><Chart dates={payload?.hourly?.time||[]} unit={payload?.hourly_units?.[k]||""} series={[{name:k,values:payload?.hourly?.[k]||[],color:i===0?"#06b6d4":"#b7c989"}]}/></section>)}</> : NATIONAL.includes(view) ? (
            <>
              {[["Temperatura","temperature","air_temperature","TEMP"],["Viento","windSpeed","wind_speed","WIND_SPEED"]].map((names,i)=>{
                const variable=names[0];
                const rows=(payload?.observations||[]).filter((o:Data)=>names.includes(o.variable)).sort((a:Data,b:Data)=>String(a.observed_at).localeCompare(String(b.observed_at)));
                return <section className="panel chart" key={variable}><h2>{i===0?"Temperatura observada":"Viento observado"}</h2><p className="small">{payload?.agency||"Agencia oficial"} · muestra de estaciones · {rows[0]?.unit||"Sin dato"}</p><Chart dates={rows.map((o:Data)=>o.observed_at+" · "+o.station)} unit={rows[0]?.unit||""} series={[{name:variable,values:rows.map((o:Data)=>o.value),type:"bar",color:i===0?"#06b6d4":"#b7c989"}]}/></section>;
              })}
            </>
          ) : view === "metnorway" ? (
            <>{["air_temperature","wind_speed"].map((variable,i)=>{const rows=payload?.properties?.timeseries||[];return <section className="panel chart" key={variable}><h2>{i===0?"Temperatura · MET Norway":"Viento · MET Norway"}</h2><p className="small">Pronóstico directo · {payload?.properties?.meta?.units?.[variable]||"Sin dato"}</p><Chart dates={rows.map((r:Data)=>r.time)} unit={payload?.properties?.meta?.units?.[variable]||""} series={[{name:variable,values:rows.map((r:Data)=>r.data?.instant?.details?.[variable]??null),color:i===0?"#06b6d4":"#b7c989"}]}/></section>})}</>
          ) : view === "modelos" ? (
            <>
              <section className="panel chart"><h2>Temperatura · modelos globales</h2><p className="small">Pronósticos separados · 3 días · °C</p><Chart dates={payload?.hourly?.time || []} unit="°C" series={[["GFS","gfs_global","#06b6d4"],["IFS","ecmwf_ifs025","#e9bd72"],["ICON","icon_global","#a7a5ff"],["GEM","gem_global","#b7c989"],["JMA","jma_gsm","#fd9c91"],["CMA","cma_grapes_global","#e7a0db"],["ARPEGE","meteofrance_arpege_world","#93c5fd"]].map(([name,id,color])=>({name,values:payload?.hourly?.["temperature_2m_"+id] || [],color}))}/></section>
              <section className="panel chart"><h2>Precipitación · comparación</h2><p className="small">Acumulado por hora · mm · sin promediar modelos</p><Chart dates={payload?.hourly?.time || []} unit="mm" series={[["GFS","gfs_global","#06b6d4"],["IFS","ecmwf_ifs025","#e9bd72"],["ICON","icon_global","#a7a5ff"]].map(([name,id,color])=>({name,values:payload?.hourly?.["precipitation_"+id] || [],color}))}/></section>
            </>
          ) : view === "serie" || view === "proyeccion" ? (
            <>
              <section className="panel chart">
                <div className="row">
                  <h2>Temperatura media anual</h2>
                  <span className="tag">
                    {view === "serie" ? "ERA5" : "PROYECCIÓN"}
                  </span>
                </div>
                <p className="small">
                  {view === "serie"
                    ? `${years} años completos · región del punto`
                    : "2031–2040 · un modelo CMIP6"}
                </p>
                <Chart
                  dates={annualData.years}
                  unit="°C"
                  series={[
                    {
                      name: "Temperatura",
                      values: annualData.temp,
                      color: "#57dce0",
                    },
                  ]}
                />
              </section>
              <section className="panel chart">
                <h2>Precipitación anual</h2>
                <p className="small">
                  Acumulado de años completos · sin interpolar vacíos
                </p>
                <Chart
                  dates={annualData.years}
                  unit="mm/año"
                  series={[
                    {
                      name: "Precipitación",
                      values: annualData.rain,
                      type: "bar",
                      color: "#b7c989",
                    },
                  ]}
                />
              </section>
            </>
          ) : view === "rios" ? (
            <>
              <section className="panel chart">
                <h2>
                  <Droplets className="icon" />
                  Caudal del río · modelo GloFAS
                </h2>
                <p className="small">
                  Predicción · verificar correspondencia del tramo
                </p>
                <Chart
                  dates={(river?.daily?.time || []).map((d: string) =>
                    d.slice(5),
                  )}
                  unit="m³/s"
                  series={[
                    {
                      name: "Caudal",
                      values: river?.daily?.river_discharge || [],
                      color: "#57dce0",
                    },
                  ]}
                />
              </section>
              <section className="panel chart">
                <h2>Precipitación prevista en el punto</h2>
                <p className="small">
                  No equivale a lluvia acumulada de toda la cuenca
                </p>
                <Chart
                  dates={dates}
                  unit="mm/día"
                  series={[
                    {
                      name: "Lluvia",
                      values: daily.precipitation_sum || [],
                      type: "bar",
                      color: "#b7c989",
                    },
                  ]}
                />
              </section>
            </>
          ) : view === "historico" ? (
            <>
              <section className="panel chart">
                <h2>Temperatura histórica diaria</h2>
                <p className="small">
                  NASA POWER · LST · valores faltantes preservados
                </p>
                <Chart
                  dates={htimes.map((d) => d.slice(4, 6) + "/" + d.slice(6))}
                  unit="°C"
                  series={[
                    {
                      name: "Temperatura media",
                      values: htimes.map((d) =>
                        hparams.T2M[d] === history?.header?.fill_value
                          ? null
                          : hparams.T2M[d],
                      ),
                      color: "#57dce0",
                    },
                  ]}
                />
              </section>
              <section className="panel chart">
                <h2>Precipitación histórica corregida</h2>
                <p className="small">NASA POWER · grilla regional</p>
                <Chart
                  dates={htimes.map((d) => d.slice(4, 6) + "/" + d.slice(6))}
                  unit="mm/día"
                  series={[
                    {
                      name: "Precipitación",
                      values: htimes.map((d) =>
                        hparams.PRECTOTCORR?.[d] === history?.header?.fill_value
                          ? null
                          : (hparams.PRECTOTCORR?.[d] ?? null),
                      ),
                      type: "bar",
                      color: "#b7c989",
                    },
                  ]}
                />
              </section>
            </>
          ) : (
            <>
              <section className="panel chart">
                <h2>Temperatura · próximos 7 días</h2>
                <p className="small">
                  Mínima y máxima · Open-Meteo ·{" "}
                  {weather?.timezone || "sin zona"}
                </p>
                <Chart
                  dates={dates}
                  unit="°C"
                  series={[
                    {
                      name: "Mínima",
                      values: daily.temperature_2m_min || [],
                      color: "#57dce0",
                    },
                    {
                      name: "Máxima",
                      values: daily.temperature_2m_max || [],
                      color: "#f0b974",
                    },
                  ]}
                />
              </section>
              <section className="panel chart">
                <h2>Agua · precipitación y ET₀</h2>
                <p className="small">
                  Pronóstico diario · no balance completo del suelo
                </p>
                <Chart
                  dates={dates}
                  unit="mm/día"
                  series={[
                    {
                      name: "Precipitación",
                      values: daily.precipitation_sum || [],
                      type: "bar",
                      color: "#57dce0",
                    },
                    {
                      name: "ET₀",
                      values: daily.et0_fao_evapotranspiration || [],
                      type: "bar",
                      color: "#b7c989",
                    },
                  ]}
                />
              </section>
            </>
          )}
        </section>
      </main>
      </div>
      {agentOpen && agentResult && <div className="agent-modal-backdrop" onClick={()=>setAgentOpen(false)}>
        <section className="agent-modal" onClick={e=>e.stopPropagation()}>
          <header><div><div className="tag">DOTS AGENTIC / INFORME DEL LOTE</div><h2>Diagnóstico multifuente</h2></div><button onClick={()=>setAgentOpen(false)}>Cerrar ×</button></header>
          <div className="agent-modal-grid"><div className="confidence big"><strong>{agentResult.confidence?.score}/100</strong><span>CONFIANZA {String(agentResult.confidence?.label||"").toUpperCase()}<br/>{agentResult.confidence?.received_sources} FUENTES RECIBIDAS</span></div><div><b>Consulta</b><p>{agentResult.prompt}</p></div></div>
          <p className="agent-summary">{agentResult.summary}</p>
          <h3>Hallazgos</h3><div className="modal-findings">{(agentResult.findings||[]).map((x:Data,i:number)=><article key={i}><span>{x.status}</span><h4>{x.topic}</h4><p>{x.text}</p></article>)}</div>
          <h3>Recomendaciones operativas</h3>{(agentResult.recommendations||[]).map((x:string,i:number)=><p key={i}>• {x}</p>)}
          {!!agentResult.warnings?.length && <><h3>Límites y advertencias</h3>{agentResult.warnings.map((x:string,i:number)=><p className="warning" key={i}>• {x}</p>)}</>}
          <h3>Evidencia y APIs</h3><div className="modal-evidence">{(agentResult.evidence||[]).map((e:Data,i:number)=><div key={i}><b>{e.source}</b><span className={e.status==='recibido'?'ok':'miss'}>{e.status}</span><small>{e.consulted_at?.slice(0,19)||'sin fecha'}</small></div>)}</div>
          <div className="modal-actions"><button className="primary" onClick={()=>void agentPdf()} disabled={pdfBusy}><FileText className="icon" />{pdfBusy?'Generando PDF…':'Descargar informe técnico PDF'}</button><button onClick={()=>setAgentOpen(false)}>Volver al mapa</button></div>
        </section>
      </div>}
      {toast && (
        <div className="toast show" role="status" aria-live="polite">
          {toast}
        </div>
      )}
    </div>
  );
}
function SiteLink({to,children,className=""}:{to:string;children:React.ReactNode;className?:string}){
  return <a href={to} className={className} onClick={(e)=>{e.preventDefault();history.pushState({},"",to);window.dispatchEvent(new PopStateEvent("popstate"));window.scrollTo({top:0,behavior:"smooth"});}}>{children}</a>
}
function Brand(){return <SiteLink to="/" className="site-brand"><img className="brand-logo" src="/dots-logo.svg" alt="DOTS Campo"/><span><b>DOTS <em>CAMPO</em></b><small>DATOS · OBSERVACIÓN · TERRITORIO · SATÉLITE</small></span></SiteLink>}
function PublicHeader({onDemo}:{onDemo:()=>void}){return <header className="site-header"><Brand/><nav>
  <SiteLink to="/que-es-dots">Qué es DOTS</SiteLink>
  <SiteLink to="/libre-deforestacion" className="nav-highlight">Vender a Europa</SiteLink>
  <SiteLink to="/panel">Panel regional</SiteLink>
  <SiteLink to="/modulos">Módulos</SiteLink>
  <details className="nav-more"><summary>Más</summary><div>
    <SiteLink to="/guia">Cómo funciona</SiteLink><SiteLink to="/cultivos">Cultivos</SiteLink><SiteLink to="/capas">Capas del mapa</SiteLink>
    <SiteLink to="/tecnologia">Fuentes</SiteLink><SiteLink to="/conexiones">APIs</SiteLink><SiteLink to="/casos">Casos</SiteLink><SiteLink to="/contacto">Contacto</SiteLink>
  </div></details>
</nav><div className="site-head-actions"><SiteLink to="/alertas" className="alert-btn">⚠ Alertas</SiteLink><SiteLink to="/acceso" className="ghost-link">Ingresar</SiteLink><button className="demo-btn" onClick={onDemo}>Abrir Observatorio →</button>
  <details className="nav-mobile"><summary aria-label="Menú">☰</summary><div>
    <button className="nav-mobile-demo" onClick={onDemo}>Abrir Observatorio →</button>
    {([["/que-es-dots","Qué es DOTS"],["/libre-deforestacion","Vender a Europa"],["/panel","Panel regional"],["/alertas","Alertas de crecidas"],["/modulos","Módulos"],["/guia","Cómo funciona"],["/cultivos","Cultivos"],["/capas","Capas del mapa"],["/tecnologia","Fuentes"],["/conexiones","APIs"],["/casos","Casos"],["/contacto","Contacto"],["/acceso","Ingresar"]] as [string,string][]).map(([to,l])=><SiteLink key={to} to={to}>{l}</SiteLink>)}
  </div></details></div></header>}
const sourceGroups=[
 ["ARGENTINA",["CONAE · SAOCOM","SMN","INA"]],
 ["EUROPA",["Copernicus · Sentinel","ECMWF · C3S","EUMETSAT","DLR · Alemania","CNES · Francia"]],
 ["AMÉRICAS",["NASA","NOAA","USGS · Landsat","INPE · Brasil","ECCC · Canadá"]],
 ["ASIA-PACÍFICO",["JAXA · Japón","ISRO · India","KMA · Corea","CMA · FengYun","BOM · Australia"]],
 ["GLOBAL",["IRI · Columbia","FAO · WaPOR","Digital Earth Africa","ISRIC · SoilGrids"]]
];
const tech=sourceGroups.flatMap(([,xs])=>xs);
const STRIP:[string,string,boolean][]=[["NASA","EE.UU.",true],["NOAA","EE.UU.",true],["ESA · Copernicus","Unión Europea",true],["ECMWF","Unión Europea",true],["USGS · Landsat","EE.UU.",true],["Microsoft Planetary Computer","Sentinel-2",true],["Climate Hazards Center","UCSB · CHIRPS",true],["ISRIC","Países Bajos",true],["SMN","Argentina",true],["INA","Argentina",true],["Fields of the World","Lotes",true],["CONAE · SAOCOM","Argentina",false],["JAXA","Japón",false],["ISRO","India",false],["CMA · FengYun","China",false],["EUMETSAT","Europa",false]];
function SourceStrip(){const items=[...STRIP,...STRIP];return <section className="source-strip marquee"><span>FUENTES OFICIALES<br/>Y TRAZABLES</span><div className="marquee-viewport" aria-label="Fuentes de datos de DOTS"><div className="marquee-track">{items.map(([n,c,on],i)=><b key={i} className={on?"on":"soon"} aria-hidden={i>=STRIP.length}><i/>{n}<small>{on?c:c+" · requiere cuenta"}</small></b>)}</div></div></section>}
function Home({onDemo}:{onDemo:()=>void}){return <div className="public-site"><PublicHeader onDemo={onDemo}/><main>
 <AlertasPortada/>
 <section className="cover-hero"><img src="/dots-hero.jpg" alt="Satélite observando lotes de un campo ganadero con índice de vegetación"/><div className="cover-shade"></div><div className="cover-copy"><div className="cover-kicker">INTELIGENCIA TERRITORIAL PARA LA GESTIÓN GANADERA</div><h1>Conocé tu campo<br/><em>como nunca antes.</em></h1><p>Unificamos el lote real con observación satelital, clima, suelo, agua, pasturas, riesgos e historia. Cada dato conserva su fuente, fecha y alcance.</p><div className="cover-actions"><button onClick={onDemo}>Ver demostración →</button><SiteLink to="/que-es-dots">Qué es DOTS</SiteLink></div><div className="truth-row"><span>DATOS REALES</span><span>POLÍGONOS REALES</span><span>FUENTES TRAZABLES</span></div></div></section>
 <SourceStrip/>
 <section className="home-intro editorial"><div><span className="section-tag">UN CAMPO · UNA LECTURA</span><h2>Del límite del potrero a la decisión.</h2></div><p>DOTS no reemplaza la recorrida ni el análisis profesional. Ordena información dispersa alrededor de una unidad territorial concreta y muestra qué fue observado, modelado, calculado o pronosticado.</p></section>
 <section className="journey"><article><b>01</b><h3>Delimitá</h3><p>Triángulo, rectángulo o polígono libre. Superficie, perímetro y centroide.</p></article><article><b>02</b><h3>Observá</h3><p>Escenas, clima, agua, suelo, vegetación y riesgos sobre el mismo territorio.</p></article><article><b>03</b><h3>Compará</h3><p>Fechas, modelos y fuentes sin perder procedencia ni calidad.</p></article><article><b>04</b><h3>Decidí</h3><p>Hallazgos, alertas, tareas e Informe Territorial DOTS unificado.</p></article></section>
 <section className="layers-teaser"><div><span className="section-tag">CAPAS DEL MAPA</span><h2>{OPEN_LAYERS.length + DOTS_LAYERS.length} capas abiertas sobre tu lote.</h2><p>Bosque, agua, anegamiento, imagen satelital diaria, rutas y vías, más lo que DOTS calcula para cada lote. Superponelas para ver lo que ninguna muestra sola.</p></div><SiteLink to="/capas" className="layers-btn big">Ver qué es una capa y para qué sirve →</SiteLink></section><section className="eudr-feature"><div><span className="section-tag">NUEVO · UNIÓN EUROPEA</span><h2>Libre de deforestación, verificado por satélite.</h2><p>Desde el 30/12/2026 la carne, la soja y la madera que se exporten a Europa deben probar que no vienen de tierras deforestadas después de 2020. DOTS lo verifica lote por lote y entrega el informe y la geolocalización listos para la debida diligencia, con el carbono del suelo y las emisiones del rodeo.</p><div className="cover-actions"><SiteLink to="/libre-deforestacion">Cómo funciona →</SiteLink><button onClick={onDemo}>Verificar un lote</button></div></div><ul><li><b>2017–2023</b>cobertura anual a 10 m</li><li><b>2 fuentes</b>Impact Observatory y ESA</li><li><b>6 decimales</b>polígono GeoJSON</li><li><b>t C/ha</b>carbono del suelo</li></ul></section>
 <section className="field-story"><div className="field-visual"><img src="/dots-hero.jpg" alt="Lotes de un establecimiento con índice de vegetación por sector"/></div><div><span className="section-tag">GEMELO DIGITAL GANADERO</span><h2>Cada potrero tiene contexto.</h2><p>Límites, pasturas, agua, infraestructura, ganado, clima, suelo, satélite, riesgos e historial se leen juntos. El mapa permanece como centro operativo mientras cambian las capas de análisis.</p><button onClick={onDemo}>Explorar el Observatorio</button></div></section>
 <section className="cap-grid">{[[MapPinned,"Lotes y potreros","Geometría, hectáreas, perímetro, historial y comparación."],[Droplets,"Agua e infraestructura","Fuentes de agua, cobertura, balance hídrico e inspecciones."],[Layers,"Pasturas y suelos","Vegetación, humedad y propiedades del suelo con método declarado."],[Thermometer,"Clima y ganado","Pronósticos, THI y contexto térmico para el rodeo."],[TriangleAlert,"Riesgos","Fuego, sequía, exceso hídrico y anomalías con evidencia."],[FileText,"Informe territorial","Un único PDF con mapa, gráficos, interpretación y trazabilidad."]].map(([Icon,t,d]:any)=><article key={t}><Icon/><h3>{t}</h3><p>{d}</p><SiteLink to="/modulos" className="cap-more">Cómo funciona →</SiteLink></article>)}</section>
 <section className="demo-call"><div><span className="section-tag">DEMOSTRACIÓN</span><h2>El mapa es el centro. Los datos explican el territorio.</h2><p>Delimitá un lote y consultá las fuentes disponibles. Si una fuente no responde o una variable no está medida, DOTS lo declara.</p></div><button onClick={onDemo}>Abrir Observatorio →</button></section>
 </main><SiteFooter/></div>}

const MODULES:[string,string,string,any,{mide:string;fuente:string;como:string;limite:string}][]=[
 ["lotes","Delimitación de lotes","Dibujado a mano o automático con un clic.",MapPinned,{
  mide:"Superficie, perímetro, centroide y compacidad del lote (índice de Polsby-Popper: 1 es un círculo; menos de 0,4 indica un potrero alargado, con más alambrado por hectárea y aguadas más lejanas).",
  fuente:"Dibujo del usuario (triángulo, rectángulo o polígono libre) o el mapa global de lotes Fields of the World 2025, publicado con licencia CC-BY-4.0.",
  como:"En modo automático DOTS lee el mapa de lotes por partes, directo desde el navegador, sin costo. Al tocar dentro de un contorno lo reconstruye aunque esté cortado entre sectores del mapa. Verde indica confianza alta (69 o más sobre 100); ámbar, revisar el borde. Además calcula el entorno en 2 km: cuántos lotes agrícolas hay, su tamaño y qué porcentaje del territorio ocupan.",
  limite:"Fields of the World mapea cultivos anuales: en pasturas y monte puede no haber contorno. No es un plano catastral."}],
 ["ndvi","Vegetación · NDVI","Vigor de la pastura medido dentro del lote.",Sprout,{
  mide:"NDVI medio, mediana y rango (percentiles 2 y 98) dentro del polígono, en cada pasada de Sentinel-2 de los últimos meses, y la serie en el tiempo.",
  fuente:"Sentinel-2 L2A de la ESA a 10 m, procesado en Microsoft Planetary Computer. Opcionales con credencial: Sentinel Hub y openEO de Copernicus, y la serie MODIS de 20 años en Google Earth Engine.",
  como:"Para cada fecha se mide primero qué parte del lote está despejada usando la clasificación de escena (SCL). Si menos del 60 % del lote se ve limpio, esa fecha se marca nublada y no se interpreta. Se corrige el desplazamiento de reflectancia de las imágenes procesadas desde 2022.",
  limite:"Un lote chico tiene pocos píxeles de 10 m. El NDVI no distingue especies ni mide biomasa por sí solo."}],
 ["clima","Clima e índices agroclimáticos","Heladas, calor, sequía y lluvias intensas, año por año.",Thermometer,{
  mide:"16 índices por año con definiciones internacionales (xclim / ETCCDI): días con helada, primera y última helada, días de calor de 30 y 35 °C, olas de calor, noches tropicales, grados día, lluvia anual, días de lluvia intensa, máxima lluvia en 1 y 5 días, rachas secas y húmedas. Se compara el último año con el promedio del período.",
  fuente:"Reanálisis ERA5 de Copernicus a escala diaria, vía Open-Meteo; pronóstico de 7 modelos globales; NASA POWER.",
  como:"Se descargan hasta 30 años de datos diarios en el punto del lote y se calculan los índices en el servidor, sin estimar valores faltantes: un año con datos incompletos se excluye.",
  limite:"La grilla de ERA5 es de unos 25 km: describe el clima de la zona, no el microclima del bajo o la loma."}],
 ["enso","El Niño y teleconexiones","Lo que pasa en el océano y anticipa la campaña.",Gauge,{
  mide:"Niño 3.4, ONI, MEI v2 y Niño 1+2 para El Niño; SOI; Modo Anular del Sur (AAO); Atlántico Sur tropical (TSA) y PDO. DOTS muestra el consenso entre los índices del Pacífico.",
  fuente:"NOAA Physical Sciences Laboratory y NOAA CPC; disponibilidad de BOM Australia e IRI Columbia.",
  como:"Se leen las series mensuales oficiales y se toma el último mes publicado. ±0,5 en Niño 3.4, ONI o MEI marca fase Niño o Niña.",
  limite:"Un índice no es un pronóstico de lluvia para el lote: se interpreta junto al pronóstico estacional del SMN."}],
 ["agua","Agua y suelo","Balance de agua, ríos y propiedades del suelo.",Droplets,{
  mide:"Lluvia y evapotranspiración de referencia (ET₀) a 7 días, humedad del suelo superficial, caudal de ríos, altura del Paraná en Bella Vista, y nitrógeno, carbono, pH y textura del suelo por profundidad.",
  fuente:"Open-Meteo y GloFAS, INA, ISRIC SoilGrids; capas de NASA (humedad SMAP, lluvia GPM) para ver en el mapa.",
  como:"El balance lluvia − ET₀ indica si el aporte de agua cubre la demanda de la atmósfera. Los bebederos y tajamares cargados por el usuario se guardan como infraestructura declarada.",
  limite:"SoilGrids es un modelo global: no reemplaza un análisis de laboratorio."}],
 ["riesgos","Riesgos y estrés térmico","Fuego y calor para el rodeo.",Flame,{
  mide:"Focos térmicos de los últimos 3 días dentro y alrededor del lote, e índice temperatura-humedad (THI) para bovinos.",
  fuente:"NASA FIRMS (sensor VIIRS) y Open-Meteo.",
  como:"Cada foco conserva fecha, hora, potencia radiativa y confianza, y se marca si cae dentro del polígono. El THI se clasifica en confort, atención, alto y severo.",
  limite:"Un foco térmico no confirma un incendio: puede ser una quema o una superficie caliente."}],
 ["informe","Informe territorial en PDF","Todo lo anterior, en un documento para compartir.",FileText,{
  mide:"Portada con el lote dibujado, indicadores, ficha del lote, hallazgos, gráficos de clima, NDVI y lluvia anual, índices, El Niño y la trazabilidad completa de las fuentes.",
  fuente:"Los mismos datos del observatorio, en el momento de la consulta.",
  como:"El documento se compone con Typst, un motor de diseño editorial abierto, con tipografía IBM Plex. Cada fuente figura con su estado y hora de consulta.",
  limite:"El informe ordena evidencia; no reemplaza la recorrida ni el criterio profesional."}],
];
function Modules({onDemo}:{onDemo:()=>void}){
  return <div className="public-site"><PublicHeader onDemo={onDemo}/><main className="inner modules-page">
    <PageHero eyebrow="MÓDULOS" title="Qué hace DOTS, por dentro." lead="Cada módulo explica qué mide, de dónde sale el dato, cómo se calcula y qué no puede afirmar. Así se lee un informe DOTS."/>
    <nav className="module-index">{MODULES.map(([id,t,,Icon])=><a key={id} href={"#"+id}><Icon/>{t}</a>)}</nav>
    {MODULES.map(([id,t,lead,Icon,x],i)=><section className="module-block" id={id} key={id}>
      <div className="module-head"><span className="module-num">{String(i+1).padStart(2,"0")}</span><div className="module-icon"><Icon/></div><div><h2>{t}</h2><p>{lead}</p></div></div>
      <div className="module-grid">
        <article><span>Qué mide</span><p>{x.mide}</p></article>
        <article><span>De dónde sale el dato</span><p>{x.fuente}</p></article>
        <article><span>Cómo se calcula</span><p>{x.como}</p></article>
        <article className="limit"><span>Qué no afirma</span><p>{x.limite}</p></article>
      </div>
    </section>)}
    <section className="demo-call"><div><span className="section-tag">PROBALO</span><h2>Dibujá un lote y mirá cada módulo funcionando.</h2><p>Los datos son reales y se consultan en el momento. Si una fuente no responde, DOTS lo dice.</p></div><button onClick={onDemo}>Abrir Observatorio →</button></section>
  </main><SiteFooter/></div>;
}
const REGIONS:[string,string,number,number][]=[["bellavista","Bella Vista · Corrientes",-28.507,-59.043],["mercedes","Mercedes · Corrientes",-29.18,-58.08],["reconquista","Reconquista · Santa Fe",-29.15,-59.65],["resistencia","Resistencia · Chaco",-27.45,-58.99],["pergamino","Pergamino · Buenos Aires",-33.89,-60.57]];
function CultivosPage({onDemo}:{onDemo:()=>void}){
  useEffect(()=>{document.title="Informe de cultivo · DOTS";},[]);
  return <div className="public-site"><PublicHeader onDemo={onDemo}/><main className="inner regional-panel alerts-page">
    <div className="no-print"><PageHero eyebrow="AGRICULTURA" title="Informe de cultivo por localidad." lead="Lluvia y evapotranspiración de los últimos 30 días y la semana que viene, temperaturas contra el umbral de helada de cada cultivo, grados día desde la siembra, alertas y recomendaciones. Maíz, soja, trigo, girasol, sorgo y arroz."/></div>
    <CultivosPanel/>
  </main><div className="no-print"><SiteFooter/></div></div>;
}
function AlertsPage({onDemo}:{onDemo:()=>void}){
  useEffect(()=>{document.title="Sistema de Alerta de Crecidas · DOTS";},[]);
  return <div className="public-site"><PublicHeader onDemo={onDemo}/><main className="inner regional-panel alerts-page">
    <CuencaPanel/>
    <section className="demo-call"><div><span className="section-tag">TU CAMPO</span><h2>Bajá de la cuenca a tu potrero.</h2><p>En el Observatorio ves el relieve, los bajos que se anegan y el agua detectada por satélite en tu lote.</p></div><button onClick={onDemo}>Abrir Observatorio →</button></section>
  </main><SiteFooter/></div>;
}

// El Niño para toda la región: estado oficial NOAA, ONI/RONI, Niño 3.4 semanal, mar por satélite, historia y rangos.
const NINO_RANGES:[string,string,string][]=[["≥ 2,0","Muy fuerte","#b42318"],["1,5 a 1,9","Fuerte","#e8590c"],["1,0 a 1,4","Moderado","#f79009"],["0,5 a 0,9","Débil","#fdb022"],["−0,5 a 0,5","Neutro","#77868b"],["≤ −0,5","La Niña","#1f5fbf"]];
const ninoColor=(v:number|null|undefined)=>v==null?"#77868b":v>=2?"#b42318":v>=1.5?"#e8590c":v>=1?"#f79009":v>=.5?"#fdb022":v<=-.5?"#1f5fbf":"#77868b";
function gibsPacific(day:string){
  const q=(layer:string,extra:Record<string,string>={})=>"https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi?"+new URLSearchParams({SERVICE:"WMS",REQUEST:"GetMap",VERSION:"1.1.1",LAYERS:layer,STYLES:"",SRS:"EPSG:4326",BBOX:"-160,-30,-70,30",WIDTH:"900",HEIGHT:"600",FORMAT:"image/png",TRANSPARENT:"TRUE",...extra}).toString();
  return {sst:q("GHRSST_L4_MUR_Sea_Surface_Temperature_Anomalies",{TIME:day}),coast:q("Coastlines_15m")};
}
function ElNinoPanel(){
  const [d,setD]=useState<any>(null),[err,setErr]=useState(""),[mapOk,setMapOk]=useState(true);
  useEffect(()=>{let live=true;fetch("/api/fuentes/el-nino?lat=-28.5&lon=-59").then(r=>r.json()).then(j=>{if(!live)return;if(j.status==="recibido")setD(j.data);else setErr(j.error||"NOAA CPC no respondió.")}).catch(()=>live&&setErr("NOAA CPC no respondió."));return()=>{live=false}},[]);
  const day=new Date(Date.now()-3*86400000).toISOString().slice(0,10), map=gibsPacific(day);
  const ref=d?.roni||d?.oni, ph=ref?.phase, st=ref?.strength;
  const head=ph==="El Niño"?`El Niño ${st||""}`.trim():ph==="La Niña"?`La Niña ${st||""}`.trim():ph?"Fase neutra":"Consultando…";
  const card=(label:string,v:any,val:number|undefined,when:string,help:string)=><article className="nino-card" style={{borderColor:ninoColor(val)}}><span>{label}</span><b style={{color:ninoColor(val)}}>{val!=null?`${val>0?"+":""}${fmt(val,2)} °C`:"—"}</b><em>{v?.phase?(v.phase==="Neutro"?"Neutro":`${v.phase} ${v.strength||""}`):"sin dato"} · {when}</em><small>{help}</small></article>;
  const s=d?.series;
  return <section className="nino-panel">
    <div className="nino-head">
      <div><span className="section-tag">EL NIÑO · TODA LA REGIÓN</span><h2>{head}</h2>
        <p>{d?.status?<><b className="nino-chip">{d.status.es}</b> según el sistema de alerta de NOAA.</>:"Estado oficial de NOAA CPC."} La fase se decide con el RONI, el índice relativo que NOAA usa desde 2026: descuenta que todo el océano tropical está más caliente.</p>
        {err && <p className="rp-error">{err} No se muestran valores supuestos.</p>}
      </div>
      <div className="nino-cards">
        {card("Niño 3.4 · semanal",d?.weekly,d?.weekly?.nino34,d?.weekly?.week?`semana del ${d.weekly.week.slice(0,2)}/${d.weekly.week.slice(2,5).toLowerCase()}`:"",`Temperatura del mar en el Pacífico central frente a 1991–2020. Reacciona primero.`)}
        {card("ONI · trimestral",d?.oni,d?.oni?.anom,d?.oni?`${d.oni.season_es} ${d.oni.year}`:"","Índice clásico: promedio de 3 meses del Niño 3.4.")}
        {card("RONI · oficial",d?.roni,d?.roni?.anom,d?.roni?`${d.roni.season_es} ${d.roni.year}`:"","Índice relativo: el que usa NOAA para declarar la fase.")}
      </div>
    </div>
    <div className="nino-ranges" aria-label="Rangos de intensidad">{NINO_RANGES.map(([r,l,c])=><span key={l}><i style={{background:c}}/><b>{l}</b> {r} °C</span>)}<small>Anomalía trimestral de la temperatura del mar en la región Niño 3.4. Hace falta sostenerla 5 trimestres para que cuente como episodio.</small></div>
    {s && <div className="rp-charts">
      <div className="rp-chart"><h3>ONI y RONI · últimos 6 años</h3><Chart dates={(s.roni?.length?s.roni:s.oni).map((r:Data)=>`${r.season_es} ${String(r.year).slice(2)}`)} unit="°C" series={[{name:"RONI (oficial)",values:(s.roni?.length?s.roni:s.oni).map((r:Data)=>r.anom),color:"#e8590c"},...(s.roni?.length?[{name:"ONI",values:(()=>{const m=new Map(s.oni.map((r:Data)=>[r.season+r.year,r.anom]));return s.roni.map((r:Data)=>m.get(r.season+r.year)??null)})(),color:"#a7a5ff"}]:[]),{name:"Umbral El Niño",values:(s.roni?.length?s.roni:s.oni).map(()=>.5),color:"#fdb022"},{name:"Umbral muy fuerte",values:(s.roni?.length?s.roni:s.oni).map(()=>2),color:"#b42318"}]}/></div>
      <div className="rp-chart"><h3>Niño 3.4 semana a semana · último año</h3><Chart dates={(s.weekly||[]).map((r:Data)=>r.week.slice(0,5))} unit="°C" series={[{name:"Anomalía Niño 3.4",values:(s.weekly||[]).map((r:Data)=>r.nino34),type:"bar",color:"#06b6d4"},{name:"Niño 1+2 (costa de Perú)",values:(s.weekly||[]).map((r:Data)=>r.nino12),color:"#fd9c91"}]}/></div>
    </div>}
    <div className="nino-grid">
      {mapOk && <figure className="cp-map nino-map"><div className="cp-map-img"><img src={map.sst} alt="Anomalía de la temperatura del mar en el Pacífico" onError={()=>setMapOk(false)}/><img src={map.coast} alt="" aria-hidden="true" className="over"/></div>
        <figcaption><b>El Pacífico visto por satélite</b> · {day.split("-").reverse().join("/")} — GHRSST MUR (NASA JPL) vía NASA GIBS. Rojo: mar más cálido que lo normal; azul: más frío. La lengua roja sobre el ecuador es El Niño.</figcaption>
        <div className="cp-scale"><span>−3 °C</span><i/><span>+3 °C</span></div></figure>}
      <div className="nino-impact"><h3>Qué suele traer a la Cuenca del Plata</h3><ul>
        <li><b>Primavera y verano:</b> más lluvia que lo normal en el NEA, Entre Ríos, Uruguay, el sur de Brasil y el este de Paraguay.</li>
        <li><b>Ríos:</b> el Uruguay responde en días a las lluvias del sur de Brasil; el Paraná crece semanas o meses después, con el agua de toda la cuenca alta.</li>
        <li><b>Campo:</b> más pasto, pero bajos anegados, caminos cortados, más parásitos y problemas de patas en el rodeo. Conviene sacar hacienda de los bajos con tiempo.</li>
        <li><b>Cuanto más fuerte, más probable:</b> un Niño fuerte no garantiza inundación, pero las grandes crecidas del Litoral ocurrieron con Niños fuertes o muy fuertes.</li>
      </ul><p className="footnote">Patrón documentado por el SMN, el INA y el CIIFEN. Seguí el panel de crecidas de abajo para el agua real en cada río.</p></div>
    </div>
    {d?.events?.length>0 && <div className="nino-events"><h3>Los Niños más fuertes desde 1950 · y qué pasó en la región</h3>
      <div className="nino-table"><div className="nt-head"><span>Período</span><span>Pico (ONI)</span><span>Intensidad</span><span>En la región</span></div>
        {d.events.map((e:Data)=><div className={"nt-row"+(e.ongoing?" now":"")} key={e.from}><span>{e.from} – {e.ongoing?"en curso":e.to}</span><b style={{color:ninoColor(e.peak)}}>+{fmt(e.peak,1)} °C<small> {e.peak_at}</small></b><span>{e.strength}</span><span>{e.region||(e.ongoing?"Evento actual: seguir el panel de crecidas.":"—")}</span></div>)}
      </div></div>}
    <div className="nino-links"><h3>Pronósticos de los centros del mundo</h3><div>
      <a href="https://iri.columbia.edu/our-expertise/climate/forecasts/enso/current/" target="_blank" rel="noreferrer"><b>IRI · Universidad de Columbia</b><span>Pluma de 22 modelos y probabilidades por trimestre</span></a>
      <a href="https://cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc_Sp.shtml" target="_blank" rel="noreferrer"><b>NOAA CPC · en español</b><span>Discusión diagnóstica mensual y sistema de alerta</span></a>
      <a href="https://climate.copernicus.eu/seasonal-forecasts" target="_blank" rel="noreferrer"><b>Copernicus C3S</b><span>Pronóstico estacional multimodelo europeo</span></a>
      <a href="https://ciifen.org/" target="_blank" rel="noreferrer"><b>CIIFEN</b><span>Boletín de El Niño para Sudamérica</span></a>
      <a href="https://www.pmel.noaa.gov/gtmba/" target="_blank" rel="noreferrer"><b>Boyas TAO/TRITON · NOAA PMEL</b><span>Calor bajo la superficie del Pacífico</span></a>
    </div></div>
    <p className="rp-note">NOAA CPC (ONI, RONI y Niño 3.4 semanal, base 1991–2020), dominio público. Mapa: NASA GIBS. Se consulta en el momento; si una fuente no responde, se deja vacío.</p>
  </section>;
}

function RegionalPanel({onDemo}:{onDemo:()=>void}){
  const [reg,setReg]=useState(REGIONS[0]);
  const [tele,setTele]=useState<any>(null),[idx,setIdx]=useState<any>(null),[err,setErr]=useState("");
  useEffect(()=>{let live=true;setErr("");setTele(null);
    fetch(`/api/fuentes/teleconexiones?lat=${reg[2]}&lon=${reg[3]}`).then(r=>r.json()).then(j=>{if(live)setTele(j.data)}).catch(()=>live&&setErr("NOAA no respondió."));
    return()=>{live=false}},[]);
  useEffect(()=>{let live=true;setIdx(null);
    fetch(`/api/fuentes/indices?lat=${reg[2]}&lon=${reg[3]}&index_years=10`).then(r=>r.json()).then(j=>{if(live)setIdx(j.status==="recibido"?j.data:null);if(j.status!=="recibido"&&live)setErr(j.error||"ERA5 no respondió.")}).catch(()=>live&&setErr("ERA5 no respondió."));
    return()=>{live=false}},[reg]);
  const last=idx?.years?.slice(-1)[0];
  const card=(label:string,key:string,unit:string,dec=0)=>{const v=last?.[key],a=idx?.anomaly_last_year?.[key];return <article className="rp-card" key={key}><span>{label}</span><b>{v!=null?fmt(v,dec):"—"}<small> {unit}</small></b><em className={a>0?"up":a<0?"down":""}>{a!=null?`${a>0?"+":""}${fmt(a,dec)} vs. promedio`:"cargando…"}</em></article>};
  return <div className="public-site"><PublicHeader onDemo={onDemo}/><main className="inner regional-panel">
    <PageHero eyebrow="PANEL REGIONAL" title="El clima de la zona, abierto a todos." lead="El Niño, las crecidas de la Cuenca del Plata, heladas, calor y lluvia de los últimos diez años. Datos oficiales consultados en el momento."/>
    <div className="rp-tabs">{REGIONS.map(r=><button key={r[0]} className={r[0]===reg[0]?"active":""} onClick={()=>setReg(r)}>{r[1]}</button>)}</div>
    {err && <p className="rp-error">{err} No se muestran valores supuestos.</p>}
    <ElNinoPanel/>
    <section className="rp-enso">
      <div><span className="section-tag">OTRAS SEÑALES · NOAA PSL</span><h2>Teleconexiones</h2><p>{tele?.enso_agreement?`${tele.enso_agreement} índices del Pacífico (Niño 3.4, ONI, MEI v2) dan fase ${tele.enso_consensus}. Último dato mensual: ${tele?.indices?.nino34?.data?.period||""}.`:"Niño 3.4, ONI y MEI v2."} SOI negativo acompaña a El Niño; AAO y Atlántico Sur (TSA) modulan la lluvia del Litoral.</p></div>
      <div className="rp-telegrid">{Object.entries(tele?.indices||{}).filter(([,e]:any)=>e?.status==="recibido").slice(0,6).map(([k,e]:any)=><article key={k}><span>{e.data.name}</span><b>{fmt(e.data.value,2)}</b><em>{e.data.phase}</em></article>)}</div>
    </section>
    <AlertasTeaser/>
    <section className="rp-cards">{card("Lluvia "+(last?.year||""),"prcptot","mm")}{card("Días con helada","frost_days","días")}{card("Días con máxima ≥ 35 °C","tx35","días")}{card("Racha seca más larga","cdd","días")}</section>
    {idx?.years && <section className="rp-charts">
      <div className="rp-chart"><h3>Lluvia anual · {idx.period?.[0]}–{idx.period?.[1]}</h3><Chart dates={idx.years.map((r:Data)=>String(r.year))} unit="mm" series={[{name:"Lluvia",values:idx.years.map((r:Data)=>r.prcptot),type:"bar",color:"#19b98a"}]}/></div>
      <div className="rp-chart"><h3>Heladas y calor extremo</h3><Chart dates={idx.years.map((r:Data)=>String(r.year))} unit="días" series={[{name:"Heladas",values:idx.years.map((r:Data)=>r.frost_days),color:"#93c5fd"},{name:"Máx ≥ 35 °C",values:idx.years.map((r:Data)=>r.tx35),color:"#fd9c91"}]}/></div>
    </section>}
    <p className="rp-note">ERA5 (Copernicus) vía Open-Meteo, grilla de ~25 km; índices con definiciones xclim/ETCCDI. Teleconexiones: NOAA PSL. Para un lote puntual, usá el Observatorio.</p>
    <section className="demo-call"><div><span className="section-tag">TU CAMPO</span><h2>Bajá del panel regional a tu potrero.</h2><p>En el Observatorio los mismos datos se calculan para el lote que dibujes, con NDVI y focos térmicos.</p></div><button onClick={onDemo}>Abrir Observatorio →</button></section>
  </main><SiteFooter/></div>;
}

const ABOUT:[string,string,string[]][]=[
 ["dots","Qué es DOTS",[
  "DOTS (Datos · Observación · Territorio · Satélite) es un observatorio territorial para la ganadería. Reúne en un solo lugar lo que miden los satélites, las estaciones meteorológicas y los modelos de clima y suelo, y lo ordena alrededor de la unidad que importa en el campo: el potrero.",
  "No es un mapa lindo ni una colección de indicadores sueltos. Cada número que muestra DOTS dice de dónde viene, cuándo se midió, a qué escala y si es una observación, un cálculo, un modelo o un pronóstico. Cuando una fuente no responde, DOTS lo declara en vez de completar el hueco con un valor supuesto.",
  "La idea es simple: que el productor, el asesor y el técnico miren lo mismo, sobre el mismo lote, con la misma evidencia, y puedan decidir mejor y más temprano."]],
 ["ganaderia","El sistema ganadero",[
  "Un establecimiento ganadero es un sistema donde el pasto, el agua, el suelo, el clima y el rodeo están conectados. La cantidad de animales que un campo sostiene —la carga— depende de cuánto pasto produce, y eso depende de la lluvia, la temperatura, el suelo y el manejo.",
  "En el Litoral y el NEA la base son los pastizales naturales, a veces combinados con pasturas implantadas. Son sistemas de cría y recría donde los años húmedos y secos cambian mucho la oferta de forraje, y donde el agua de bebida, la sombra y el calor del verano pesan en el bienestar y la producción del rodeo.",
  "DOTS sigue esas piezas por potrero: cómo viene el vigor del pasto, cuánta lluvia cayó frente a lo normal, cuánta agua pide la atmósfera, si se anuncian heladas o calor, dónde están los bebederos y tajamares, y qué riesgos de fuego o sequía hay alrededor."]],
 ["pasturas","Pasturas y vegetación",[
  "Las plantas sanas absorben la luz roja para hacer fotosíntesis y reflejan mucho infrarrojo cercano. El NDVI compara esas dos bandas: valores cercanos a 0 indican suelo desnudo o agua; entre 0,2 y 0,5, vegetación rala o pasto seco; por encima de 0,5, vegetación activa.",
  "DOTS calcula el NDVI dentro del lote con imágenes Sentinel-2 de 10 metros, descartando las fechas en que las nubes tapan el potrero. Seguir la curva en el tiempo muestra el rebrote después de una lluvia, el efecto de una helada, el pastoreo y el descanso de cada potrero.",
  "El NDVI es una medida del verdor, no de los kilos de pasto ni de su calidad. Sirve para comparar potreros y fechas y para decidir dónde mirar primero; la recorrida y la medición a campo siguen siendo necesarias."]],
 ["nitrogeno","Nitrógeno y suelo",[
  "El nitrógeno es el nutriente que más limita el crecimiento de las pasturas. Está en el suelo sobre todo como parte de la materia orgánica, y se libera a medida que los microorganismos la descomponen; por eso los suelos con más carbono orgánico suelen tener más nitrógeno disponible.",
  "Las leguminosas —tréboles, lotus, alfalfa— fijan nitrógeno del aire con bacterias en sus raíces y enriquecen el sistema. Las gramíneas, en cambio, responden mucho a la fertilización nitrogenada cuando hay humedad. El pH, la textura y la densidad del suelo influyen en cuánto de ese nitrógeno queda al alcance de las raíces.",
  "DOTS muestra nitrógeno total, carbono orgánico, pH, arcilla, arena y limo por profundidad a partir de SoilGrids, un modelo global de suelos. Es una referencia para comparar y planificar muestreos: no reemplaza un análisis de laboratorio del lote."]],
 ["agua","Agua",[
  "El agua define cuánto pasto crece y cuántos animales se pueden atender. DOTS compara la lluvia con la evapotranspiración de referencia (ET₀), que indica cuánta agua pide la atmósfera: si durante varias semanas la ET₀ supera a la lluvia, el suelo se va secando y el pasto lo siente.",
  "La lluvia observada de CHIRPS, desde 1981, permite saber si los últimos meses fueron secos o húmedos frente a lo normal del lugar, con el índice SPI que usan los servicios de sequía. Los bebederos, tajamares, molinos y tanques se cargan en el mapa para cruzar infraestructura con potreros y carga."]],
 ["clima","Clima, El Niño y riesgos",[
  "El clima de cada campaña está muy influido por El Niño y La Niña, el calentamiento o enfriamiento del océano Pacífico ecuatorial. En el Litoral y el NEA, El Niño suele asociarse a más lluvia en primavera y verano, y La Niña a condiciones más secas. DOTS lee los índices oficiales de NOAA y muestra si coinciden.",
  "Para el día a día, DOTS compara pronósticos de varios modelos globales y calcula índices como días de helada, olas de calor o rachas secas de los últimos años. Con temperatura y humedad estima el THI, que indica estrés por calor en bovinos, y con el sensor VIIRS de la NASA detecta focos de calor dentro y alrededor del lote."]],
 ["lectura","Cómo leer un dato de DOTS",[
  "Observado: lo midió un sensor (una estación, un satélite). Modelado: lo estimó un modelo físico o estadístico a partir de observaciones. Calculado: DOTS lo derivó de otros datos con un método declarado. Pronosticado: es una estimación del futuro, con su incertidumbre.",
  "Cada valor trae su escala: el NDVI de Sentinel-2 mira 10 metros; el clima de ERA5, unos 25 kilómetros; la lluvia de CHIRPS, unos 5. Un dato de escala gruesa describe la zona, no el bajo o la loma de un potrero. Por eso DOTS no reemplaza la recorrida: la ordena."]],
];
function About({onDemo}:{onDemo:()=>void}){
  return <div className="public-site"><PublicHeader onDemo={onDemo}/><main className="inner about-page">
    <PageHero eyebrow="QUÉ ES DOTS" title="Un observatorio para leer el campo potrero por potrero." lead="Satélites, clima, suelo y agua, ordenados alrededor del lote y con su procedencia a la vista."/>
    <nav className="module-index">{ABOUT.map(([id,t])=><a key={id} href={"#"+id}>{t}</a>)}</nav>
    <div className="about-body">{ABOUT.map(([id,t,ps],i)=><section className="about-block" id={id} key={id}>
      <div className="about-side"><span className="module-num">{String(i+1).padStart(2,"0")}</span><h2>{t}</h2></div>
      <div className="about-text">{ps.map((x,j)=><p key={j}>{x}</p>)}</div>
    </section>)}</div>
    <section className="demo-call"><div><span className="section-tag">PROBALO</span><h2>Dibujá un potrero y mirá todo esto en acción.</h2><p>Los datos se consultan en el momento y cada uno muestra su fuente.</p></div><button onClick={onDemo}>Abrir Observatorio →</button></section>
  </main><SiteFooter/></div>;
}

// Guía pública para vender a Europa: acuerdo, sanidad, EUDR, trámite, quién certifica, herramientas y otros países.
function EuropeGuide(){
  const flow:[string,string,string][]=[
    ["Productor","Demuestra el origen","Polígono de cada campo, sin desmonte después de 2020, papeles en regla (título o contrato, RENSPA, OTBN, registros laborales) y animales identificados con DT-e."],
    ["Frigorífico o acopio","Junta los orígenes","Pide a cada proveedor la geolocalización y la evidencia. Separa lo que va a Europa de lo que no tiene respaldo."],
    ["Exportador","Arma el legajo","Reúne geolocalizaciones, evaluación de riesgo y documentación del lote exportado y lo entrega al importador."],
    ["Importador europeo","Presenta la declaración","Es el operador: carga la declaración de diligencia debida en el sistema de información de la UE (TRACES) con los polígonos en GeoJSON y obtiene un número de referencia."],
    ["Autoridad del país europeo","Controla","Revisa una parte de los envíos según el riesgo del país de origen. Para Argentina, riesgo estándar, el 3 % de los operadores. Si algo no cierra, puede frenar la mercadería y aplicar multas."],
  ];
  const show:[string,string][]=[
    ["Libre de deforestación","La tierra no se convirtió de bosque a uso agropecuario después del 31/12/2020. Se prueba con imágenes satelitales y mapas de cobertura."],
    ["Legalidad","Se produjo cumpliendo las leyes del país: uso de la tierra, ambiente (en Argentina, la Ley de Bosques 26.331 y su ordenamiento provincial), trabajo, impuestos y derechos de comunidades indígenas."],
    ["Geolocalización","Coordenadas de cada predio de origen con 6 decimales, en polígono si supera 4 ha. Para ganado, la ubicación de cada establecimiento donde estuvo el animal."],
    ["Trazabilidad","Poder seguir el producto desde ese campo hasta el embarque, sin mezclarlo con mercadería de origen desconocido."],
  ];
  const tools:[string,string,string,string][]=[
    ["DOTS","Argentina · gratis","Verificación de cobertura 2017–2023 por lote, GeoJSON con el formato de TRACES, lista para el comprador en PDF y segunda opinión de Whisp.","/guia"],
    ["VISEC","Cadena argentina · gratis","Plataforma sectorial reconocida por el Estado para soja libre de deforestación; usa el RENSPA de SENASA. El IPCVA la presentó también para carne.","https://argentina.controlunion.com/programa-de-certificacion/visec-plataforma-de-trazabilidad-para-soja-y-carne-sin-deforestacion/"],
    ["Whisp","FAO · código MIT","Cruza decenas de mapas públicos, incluido el mapa de bosques 2020 de la Comisión Europea (JRC), y devuelve un riesgo por producto.","https://github.com/forestdatapartnership/whisp"],
    ["GeoRoots","Código abierto","Valida, repara, une y separa archivos GeoJSON en el navegador, sin subir datos a ningún servidor.","https://georoots.eu/"],
    ["Open Foris Ground · KoboToolbox","FAO y Google · AGPL","Apps de celular para relevar polígonos y fotos en el campo, sin señal, y exportarlos en GeoJSON.","https://www.openforis.org/ground/"],
    ["INATrace · WHIMO","GIZ · Instituto Forestal Europeo","Trazabilidad abierta del campo al comprador, con mapas de fincas y registro de entregas.","https://inatrace.org/en"],
  ];
  return <>
    <section className="about-body">
      <section className="about-block"><div className="about-side"><span className="module-num">EL ACUERDO</span><h2>UE-Mercosur: más mercado, mismas reglas</h2></div><div className="about-text">
        <p>El acuerdo comercial se aplica de forma provisional desde el 1 de mayo de 2026 para Argentina, Brasil, Paraguay y Uruguay. La UE elimina aranceles sobre el 92 % de lo que importa del Mercosur y abre cuotas con arancel reducido para otro 7,5 %; la carne vacuna dentro de la cuota paga 7,5 % desde el primer día.</p>
        <p>Lo que no cambia: las normas sanitarias son las mismas que para los productores europeos, y el reglamento de deforestación se aplica igual, con o sin acuerdo. El acuerdo abre la puerta; la sanidad y el EUDR deciden quién pasa.</p></div></section>
      <section className="about-block"><div className="about-side"><span className="module-num">LLAVE 1</span><h2>Sanidad: SENASA</h2></div><div className="about-text">
        <p>Para carne, solo pueden exportar frigoríficos habilitados por la UE, con hacienda de campos inscriptos en el registro de SENASA de establecimientos proveedores para Europa, animales identificados individualmente y sin anabólicos ni hormonas, que Europa prohíbe. El estatus sanitario de cada zona frente a la aftosa define qué productos y con qué tratamiento se pueden enviar.</p>
        <p>Esto lo certifica SENASA con su firma oficial en cada embarque. DOTS no interviene en esta llave: conviene confirmar con el veterinario del establecimiento y con SENASA que el campo esté en el registro.</p></div></section>
      <section className="about-block"><div className="about-side"><span className="module-num">LLAVE 2</span><h2>EUDR: qué hay que demostrar</h2></div><div className="about-text">
        <div className="eu-show">{show.map(([t,d])=><div key={t}><b>{t}</b><p>{d}</p></div>)}</div></div></section>
    </section>
    <section className="eu-flow"><h2>Cómo se procesa, paso a paso</h2><ol>{flow.map(([w,t,d],i)=><li key={w}><span>{String(i+1).padStart(2,"0")}</span><div><em>{w}</em><b>{t}</b><p>{d}</p></div></li>)}</ol></section>
    <section className="about-body">
      <section className="about-block"><div className="about-side"><span className="module-num">QUIÉN CERTIFICA</span><h2>Nadie te da un sello obligatorio</h2></div><div className="about-text">
        <p>El EUDR no exige un certificado. El responsable legal es la empresa que introduce el producto en Europa: ella hace la debida diligencia y firma la declaración. Las autoridades de cada país europeo controlan.</p>
        <p>Las certificaciones privadas y plataformas como VISEC ayudan a respaldar la evaluación de riesgo, pero según la guía de la Comisión ninguna reemplaza la debida diligencia. La Comisión prepara un registro de esquemas de certificación, previsto para fines de 2026.</p>
        <p>Hay una declaración simplificada para micro y pequeños productores primarios, pero solo en países de riesgo bajo. Argentina figura como riesgo estándar, así que acá no aplica: el productor no presenta nada en Europa, pero tiene que entregarle la evidencia a quien le compra.</p>
        <p>La revisión de la Comisión de mayo de 2026 confirmó las fechas sin más postergaciones: 30 de diciembre de 2026 para empresas grandes y medianas y 30 de junio de 2027 para micro y pequeñas.</p></div></section>
      <section className="about-block"><div className="about-side"><span className="module-num">OTROS PAÍSES</span><h2>Cómo lo resuelven</h2></div><div className="about-text">
        <p><b>Uruguay</b> tiene trazabilidad bovina individual obligatoria hace casi dos décadas, a cargo del Estado: cada animal se sigue desde que nace. Es la base que más ayuda frente al EUDR.</p>
        <p><b>Argentina</b> se organizó desde la cadena: VISEC nació en las cámaras de la soja, usa el RENSPA y el Estado la reconoce; el IPCVA la presentó para carne.</p>
        <p><b>En el Mercosur</b> un relevamiento de Proforest, Solidaridad y la Tropical Forest Alliance identificó 15 instrumentos que ayudan a cumplir en la cadena de la carne, casi todos públicos o público-privados: registros de trazabilidad, controles de legalidad y monitoreo de proveedores.</p>
        <p><b>Del lado europeo</b> la FAO, la Comisión y el Instituto Forestal Europeo publican herramientas gratuitas y abiertas, como las de abajo.</p></div></section>
    </section>
    <section className="eu-tools"><h2>Herramientas gratuitas para preparar la evidencia</h2><div>{tools.map(([n,o,d,u])=>u.startsWith("/")?<SiteLink key={n} to={u}><b>{n}</b><em>{o}</em><span>{d}</span></SiteLink>:<a key={n} href={u} target="_blank" rel="noreferrer"><b>{n}</b><em>{o}</em><span>{d}</span></a>)}</div></section>
    <section className="eu-dots"><div><span className="section-tag">CÓMO TE AYUDA DOTS</span><h2>Del potrero al legajo del comprador, en cuatro pasos.</h2>
      <ol><li>Dibujás el campo en el Observatorio o lo tomás del mapa de lotes.</li><li>En Sustentabilidad, DOTS mide la cobertura de árboles desde 2017 y la compara con 2020.</li><li>Marcás la lista de lo que podés demostrar y, si querés, pedís la segunda opinión de Whisp con el mapa oficial europeo.</li><li>Descargás el informe PDF para el comprador y el GeoJSON con el formato de TRACES, listo para que el importador lo cargue.</li></ol>
      <p className="footnote">Es evidencia técnica gratuita para la debida diligencia, no un certificado. Fuentes: Comisión Europea (Access2Markets, guía y FAQ del EUDR, documentación de TRACES), Reglamento (UE) 2023/1115 y 2025/2650, FAO, Instituto Forestal Europeo y Proforest.</p></div></section>
  </>;
}

function Deforestation({onDemo}:{onDemo:()=>void}){
  const steps:[string,string,string][]=[
    ["01","Delimitá el lote","Dibujalo o tomalo con un clic del mapa global de lotes. DOTS guarda el polígono en WGS84 con seis decimales, como pide la norma."],
    ["02","DOTS mide la cobertura año por año","Impact Observatory (10 m, 2017–2023) clasifica cada píxel del lote en árboles, pastizal, cultivo o agua. ESA WorldCover controla 2020 y 2021 con otro sensor."],
    ["03","Compara contra el corte","La cobertura arbórea del último año se compara con la de 2020. Se informan la pérdida en hectáreas y el cambio en puntos, con criterios publicados."],
    ["04","Entrega la evidencia","Informe PDF con resultado, tabla anual, método, fuentes y límites, más el archivo GeoJSON del lote con su huella digital para cargar en el sistema europeo."],
  ];
  return <div className="public-site"><PublicHeader onDemo={onDemo}/><main className="inner eudr-page">
    <section className="eudr-hero"><div>
      <span className="section-tag">VENDER A EUROPA · EUDR</span>
      <h1>Lo que pide Europa para comprarte, explicado y verificado por lote.</h1>
      <p>Con el acuerdo UE-Mercosur en marcha, Europa compra con menos aranceles, pero exige dos llaves: la sanitaria de siempre y, desde el 30 de diciembre de 2026, la prueba de que la carne, la soja o la madera no vienen de tierras deforestadas después del 31 de diciembre de 2020. Esta guía explica el trámite completo y DOTS te da la evidencia satelital, la geolocalización y la lista para el comprador, gratis.</p>
      <div className="cover-actions"><button onClick={onDemo}>Verificar un lote →</button><SiteLink to="/contacto">Consultar para frigoríficos y exportadores</SiteLink></div>
    </div><div className="eudr-badge"><b>31/12/2020</b><span>fecha de corte</span><b>30/12/2026</b><span>aplicación para operadores grandes y medianos</span><b>30/06/2027</b><span>microempresas y personas humanas</span></div></section>
    <section className="eudr-steps">{steps.map(([n,t,d])=><article key={n}><span>{n}</span><h3>{t}</h3><p>{d}</p></article>)}</section>
    <EuropeGuide/>
    <section className="about-body">
      <section className="about-block"><div className="about-side"><span className="module-num">QUÉ PIDE LA NORMA</span><h2>Reglamento (UE) 2023/1115</h2></div><div className="about-text">
        <p>El reglamento alcanza, entre otros productos, al ganado bovino y la carne vacuna, la soja y la madera. El cuero bovino quedó fuera del alcance con el acto delegado de julio de 2026. Para venderlos en la Unión Europea, el operador tiene que demostrar tres cosas: que no provienen de tierras deforestadas después del 31 de diciembre de 2020, que se produjeron según la legislación del país de origen y que están cubiertos por una declaración de debida diligencia.</p>
        <p>La geolocalización se expresa con al menos seis decimales. Para el ganado se admite la ubicación de cada establecimiento donde se crió el animal; DOTS entrega además el polígono completo del lote, que es la evidencia más sólida ante una consulta o una alerta.</p>
        <p>Tras las modificaciones de 2025, las obligaciones rigen desde el 30 de diciembre de 2026 para operadores grandes y medianos y desde el 30 de junio de 2027 para microempresas y personas humanas.</p></div></section>
      <section className="about-block"><div className="about-side"><span className="module-num">CÓMO SE DECIDE</span><h2>Criterios publicados</h2></div><div className="about-text">
        <p><b>Sin pérdida detectada</b>: menos de 0,5 ha de pérdida estimada o una variación de cobertura arbórea mayor a −1 punto entre 2020 y el último año.</p>
        <p><b>Pérdida menor · revisar</b>: entre 0,5 y 5 ha. Puede ser poda, sombra, un error de clasificación o un desmonte puntual.</p>
        <p><b>Requiere verificación</b>: 5 ha o más. Se recomienda revisar imágenes de mayor resolución y la documentación del establecimiento.</p></div></section>
      <section className="about-block"><div className="about-side"><span className="module-num">CARBONO</span><h2>Suelo y rodeo</h2></div><div className="about-text">
        <p>El mismo informe muestra el carbono orgánico que guarda el suelo del lote en los primeros 30 cm (ISRIC SoilGrids, con su rango de incertidumbre) y su equivalente en CO₂. Con la cantidad de cabezas, estima el metano del rodeo con los factores del IPCC.</p>
        <p>Es una línea de base para conversar con compradores y programas de carbono. Un proyecto de bonos de carbono requiere además muestreo de suelo y una metodología certificada.</p></div></section>
      <section className="about-block"><div className="about-side"><span className="module-num">LÍMITES</span><h2>Qué no reemplaza</h2></div><div className="about-text">
        <p>Es evidencia técnica de teledetección para la debida diligencia, no una certificación legal ni la declaración ante el sistema europeo. Los mapas de 10 m pueden confundir monte abierto con pastizal arbolado; ante una alerta corresponde revisar imágenes de mayor resolución, la documentación y, si hace falta, el campo.</p>
        <p>Los animales que pasaron por otros establecimientos necesitan la geolocalización de cada uno.</p></div></section>
    </section>
    <section className="demo-call"><div><span className="section-tag">PARA QUIÉN</span><h2>Productores, frigoríficos, consignatarias y exportadores.</h2><p>Verificación por lote en el Observatorio, o por lotes completos de proveedores para empresas. Consultanos por volumen.</p></div><button onClick={onDemo}>Abrir Observatorio →</button></section>
  </main><SiteFooter/></div>;
}
function Guide({onDemo}:{onDemo:()=>void}){return <div className="public-site"><PublicHeader onDemo={onDemo}/><main className="inner guide"><PageHero eyebrow="CÓMO FUNCIONA DOTS" title="Lo que el satélite ve de un campo, contado para todos." lead="Para productores, estudiantes, profesionales, periodistas y curiosos: qué es DOTS, de qué satélite sale cada dato, cómo se procesa la información de un lote y cómo usarlo en cinco minutos."/><GuideContent onDemo={onDemo}/></main><SiteFooter/></div>}
const LAYER_THEMES: [string,string,string][] = [
  ["Campo y ambiente","Bosque, agua y anegamiento","Pérdida de bosque año por año desde 2001 y dónde hubo agua en superficie desde 1984: bajos que se anegan, lagunas que aparecen o se secan, desmontes. Sirve para elegir potreros, ubicar aguadas y respaldar la verificación libre de deforestación."],
  ["Satélite NASA","Imagen satelital diaria","Color real de MODIS y VIIRS de cada día, combinaciones de bandas que resaltan agua, quemas y anegamiento, temperatura de la superficie y humo. Sirve para seguir inundaciones, incendios y sequías a escala regional."],
  ["Mapas base","Mapas para ubicarse","Imagen satelital de alta resolución, topográficos con curvas de nivel, caminos rurales, el mapa oficial del IGN argentino y fondos claros u oscuros para leer mejor los datos."],
  ["Etiquetas y redes","Rutas, vías y localidades","Rutas, caminos, vías férreas, límites y nombres de lugares sobre cualquier fondo. Sirven para la logística: cómo sale la hacienda y a qué distancia están el remate, el frigorífico o el puerto."],
];
const DOTS_LAYERS: [string,string][] = [
  ["NDVI del lote · Sentinel-2 10 m","Vigor del pasto dentro del polígono, escena por escena, con nubes excluidas."],
  ["Color real del lote · Sentinel-2","La foto satelital más reciente del lote, recortada a su borde."],
  ["Cobertura anual 2017–2023 · 10 m","Árboles, pastizal, cultivo y agua de cada año, para comparar contra 2020."],
  ["Relieve y anegamiento · DEM 30 m","Bajos cerrados, escurrimiento y propensión a anegarse, calculados en el navegador."],
  ["Límites de lotes · Fields of the World","Lotes detectados por inteligencia artificial en todo el mundo, para tomar el borde con un clic."],
  ["NDVI regional, humedad del suelo, lluvia y nubes · NASA","NDVI MODIS cada 8 días, humedad SMAP, lluvia GPM IMERG cada 30 minutos y nubes GOES cada 10 minutos."],
  ["Cobertura ESA WorldCover y suelos INTA","Clases de cobertura a 10 m y cartografía de suelos de Argentina."],
];
function LayersPage({onDemo}:{onDemo:()=>void}){
  const n = OPEN_LAYERS.length + DOTS_LAYERS.length;
  return <div className="public-site"><PublicHeader onDemo={onDemo}/><main className="inner layers-page">
    <PageHero eyebrow="CAPAS DEL MAPA" title={`${n} capas para ver el campo desde arriba, gratis y sin claves.`} lead="Satélites de la NASA y de Europa, mapas oficiales, bosque, agua, rutas y lo que DOTS calcula para tu lote, todo sobre el mismo mapa. Acá explicamos qué es una capa, para qué sirve combinarlas y con qué tecnología funciona."/>
    <section className="layer-funnel">
      <div><b>950</b><span>capas revisadas en el catálogo abierto xyzservices (GeoPandas)</span></div>
      <div><b>≈120</b><span>gratuitas y sin clave</span></div>
      <div><b>{OPEN_LAYERS.length}</b><span>útiles para el campo, con cobertura en la región y probadas todos los días</span></div>
      <div><b>+{DOTS_LAYERS.length}</b><span>capas que DOTS calcula o integra para cada lote</span></div>
    </section>
    <section className="layer-what">
      <div className="layer-figure">
        <div className="layer-stack" aria-hidden="true">
          {[["Tu lote","#25efb5"],["Rutas y caminos","#f5b544"],["Agua 1984–2021","#3a8ee6"],["Pérdida de bosque","#e5484d"],["Imagen satelital","#2f5d50"]].map(([t,c],i)=><div key={t} style={{["--c" as any]:c,["--i" as any]:i}}/>)}
        </div>
        <ol className="layer-legend">{[["Tu lote","#25efb5"],["Rutas y caminos","#f5b544"],["Agua 1984–2021","#3a8ee6"],["Pérdida de bosque","#e5484d"],["Imagen satelital (fondo)","#2f5d50"]].map(([t,c])=><li key={t}><i style={{background:c}}/>{t}</li>)}</ol>
      </div>
      <div className="layer-what-text">
        <span className="module-num">QUÉ ES UNA CAPA</span>
        <h2>Una capa es una hoja transparente con un solo tema.</h2>
        <p>Imaginá un mapa hecho de hojas de acetato apiladas. Abajo va el fondo: una foto satelital o un mapa topográfico. Encima, cada hoja muestra una sola cosa: dónde hubo agua, dónde se perdió bosque, por dónde pasan las rutas, cómo está el pasto hoy. Arriba de todo, el borde de tu lote.</p>
        <p>Como cada hoja es transparente, se pueden combinar y graduar. Lo que ninguna capa dice sola aparece al superponerlas: un bajo que se anega, un desmonte cerca de un arroyo, el camino más corto hasta el remate.</p>
      </div>
    </section>
    <section className="about-body"><section className="about-block"><div className="about-side"><span className="module-num">EL POTENCIAL</span><h2>Preguntas que se responden combinando capas</h2></div><div className="about-text layer-uses">
      {[["¿Qué parte del campo se anega?","Agua superficial 1984–2021 + relieve del lote + imagen MODIS 7-2-1 del día de la lluvia."],
        ["¿Hubo desmonte después de 2020?","Pérdida de bosque + cobertura anual 2017–2023 + foto satelital del lote. Es la base del informe para Europa."],
        ["¿Cómo está el pasto y cuánto aguanta?","NDVI del lote + lluvia observada + temperatura de superficie. De ahí sale la carga que sostiene."],
        ["¿Por dónde y a qué costo sale la hacienda?","Rutas y caminos + vías férreas + localidades, con la distancia real al destino y el flete."],
        ["¿Hay fuego o humo cerca?","Focos de calor NASA FIRMS + aerosoles y humo MODIS + imagen VIIRS del día."],
        ["¿Qué pasa en la región, no sólo en el lote?","Imagen diaria de la NASA, humedad del suelo, lluvia satelital cada 30 minutos y nubes cada 10 minutos."]].map(([q,a])=><p key={q}><b>{q}</b><br/>{a}</p>)}
    </div></section>
    <section className="about-block"><div className="about-side"><span className="module-num">TECNOLOGÍA</span><h2>Cómo funciona por dentro</h2></div><div className="about-text layer-tech">
      {[["Teselas","El mapa se arma con miles de imágenes chicas de 256 píxeles (teselas) que se piden sólo para la zona y el zoom que estás mirando. Por eso carga rápido aun con imágenes de todo el planeta."],
        ["Estándares abiertos","Las capas llegan por protocolos internacionales: XYZ y WMTS para teselas, WMS y OGC API del Open Geospatial Consortium para servicios oficiales. Cualquier fuente que los respete se puede sumar."],
        ["Satélites a pedido","Para el lote, DOTS busca escenas Sentinel-2 en catálogos STAC y las lee como Cloud Optimized GeoTIFF en Microsoft Planetary Computer: recorta sólo el polígono, enmascara nubes y calcula el índice al instante, sin descargar la imagen entera."],
        ["Cálculo en el navegador","El relieve y los límites de lotes se procesan en tu propia computadora: el modelo de elevación Copernicus de 30 m y los lotes de Fields of the World (archivos PMTiles) se leen por partes."],
        ["Catálogo abierto","La lista de capas parte de xyzservices, el catálogo libre de GeoPandas (licencia BSD), más capas agro elegidas por DOTS: Global Forest Watch, JRC/Copernicus, IGN Argentina y la NASA."],
        ["Control diario","Todos los días un chequeo automático pide una imagen de cada capa sobre Corrientes y prueba cada función del sitio. Si una fuente deja de responder, queda registrado."]].map(([t,d])=><article key={t}><h3>{t}</h3><p>{d}</p></article>)}
    </div></section></section>
    <h2 className="layer-section-title">Las {OPEN_LAYERS.length} capas abiertas, por tema</h2>
    <section className="layer-themes">{LAYER_THEMES.map(([g,t,d])=><article key={g}><span className="module-num">{OPEN_LAYERS.filter(l=>l.group===g).length} capas</span><h3>{t}</h3><p>{d}</p>
      <ul>{OPEN_LAYERS.filter(l=>l.group===g).map(l=><li key={l.id}>{l.name}</li>)}</ul></article>)}</section>
    <section className="about-body"><section className="about-block"><div className="about-side"><span className="module-num">PROPIAS DE DOTS</span><h2>Capas calculadas para el lote</h2></div><div className="about-text">
      {DOTS_LAYERS.map(([t,d])=><p key={t}><b>{t}.</b> {d}</p>)}
    </div></section>
    <section className="about-block"><div className="about-side"><span className="module-num">CÓMO SE ELIGIERON</span><h2>Criterio</h2></div><div className="about-text">
      <p>Se descartaron las capas que exigen clave o pago, las que sólo cubren otro país (Francia, Alemania, Estados Unidos, Singapur) y las que no devolvieron imagen al probarlas sobre Corrientes. Un chequeo automático pide todos los días una imagen de cada capa y avisa si alguna deja de responder.</p>
      <p>Las capas muestran datos de cada fuente tal como los publica: no se mezclan ni se rellenan. Las de la NASA son diarias y regionales (250 m a 1 km); para el detalle del lote, DOTS usa Sentinel-2 a 10 m.</p>
    </div></section></section>
    <section className="demo-call"><div><span className="section-tag">PROBALO</span><h2>Elegí el mapa base y una capa encima.</h2><p>En el Observatorio, arriba del mapa, hay un selector de mapa base y otro de capa superpuesta con control de transparencia.</p></div><button onClick={onDemo}>Abrir el mapa →</button></section>
    <p className="footnote layer-credits">Catálogo base: xyzservices (github.com/geopandas/xyzservices, licencia BSD-3). Atribuciones: Esri, OpenStreetMap (ODbL), OpenTopoMap (CC-BY-SA), CyclOSM, Carto, OpenRailwayMap, NASA GIBS/EOSDIS, Hansen/UMD/Google/USGS/NASA vía Global Forest Watch (CC-BY 4.0), EC JRC/Google Global Surface Water, Instituto Geográfico Nacional de Argentina.</p>
  </main><SiteFooter/></div>
}
function PageHero({eyebrow,title,lead}:{eyebrow:string;title:string;lead:string}){return <section className="page-hero"><span className="section-tag">{eyebrow}</span><h1>{title}</h1><p>{lead}</p></section>}
const cards={producto:[["01","Territorio primero","Todo análisis comienza en el polígono real del lote o potrero."],["02","Observación multifuente","Satélites, estaciones, modelos y bases territoriales se consultan por lugar y fecha."],["03","Interpretación trazable","Cada variable indica fuente, unidad, fecha, método, estado y alcance."],["04","Decisión y seguimiento","DOTS reúne hallazgos, recomendaciones, tareas e informe en una sola lectura."]],soluciones:[["Lotes y potreros","Superficie, perímetro, centroides, historial y análisis por unidad de manejo."],["Pasturas","Escenas y evolución espectral cuando existe procesamiento raster verificable."],["Agua","Lluvia, balance, ríos e infraestructura hídrica declarada o detectada con su nivel de evidencia."],["Suelos","Humedad, temperatura, relieve y propiedades modeladas con profundidad y fuente declaradas."],["Ganado","THI, carga y rotación cuando existe inventario o dato aportado por el productor."],["Riesgos","FIRMS, calor, sequía y exceso hídrico sin convertir ausencia de detección en ausencia de riesgo."]],ganaderia:[["Potrero como unidad","Cada lectura parte de un límite territorial y su historia."],["Agua para el rodeo","Cobertura, distancias y estado de la infraestructura hídrica."],["Pastura y carga","Condición vegetal cruzada con ocupación y presión de pastoreo cuando hay datos."],["Bienestar térmico","THI y meteorología para anticipar condiciones de estrés por calor."],["Rotación","Entrada, salida, descanso y recuperación del potrero."],["Tareas","Del diagnóstico a inspecciones, movimientos y acciones verificables."]]};
function InstitutionalDepth({kind}:{kind:"producto"|"soluciones"|"ganaderia"}){
 const copy:any={
 producto:["Qué es DOTS","DOTS Campo es una plataforma de inteligencia territorial para la gestión ganadera. Integra cartografía, observación satelital, meteorología, suelo, agua, infraestructura, riesgos e historia en torno a una unidad concreta: el establecimiento, el lote o el potrero.","Qué es el Observatorio profesional","Es el espacio operativo donde el productor o el técnico delimita el territorio, selecciona fuentes, compara fechas y transforma datos dispersos en una lectura única. El mapa permanece como referencia; cada módulo aporta una capa distinta sin perder el polígono analizado.","Cómo trabajan los gestores","Los gestores de DOTS organizan las consultas por dominio: territorio, satélites, clima, vegetación, agua, suelo, ganado, riesgos y contexto climático global. Un orquestador reúne las respuestas, un control de calidad conserva faltantes y advertencias, y el informe final muestra la procedencia de cada resultado."],
 soluciones:["Una plataforma para gestionar, no sólo mirar","El Observatorio convierte el mapa en una mesa de trabajo. Permite delimitar potreros, registrar infraestructura, revisar escenas recientes, contrastar pronósticos, seguir el balance hídrico y reunir alertas en un mismo contexto territorial.","De la variable a la decisión","Una cifra aislada no alcanza. DOTS presenta valor, unidad, referencia, estado, fecha, fuente y método. Cuando una variable no está disponible, se declara como faltante; cuando es una inferencia, se identifica como interpretación.","Seguimiento en el tiempo","El objetivo es que cada potrero pueda compararse consigo mismo: vegetación, lluvia, evapotranspiración, humedad, ocupación, agua, riesgos e intervenciones. Así el sistema construye memoria territorial y no una fotografía aislada."],
 ganaderia:["Pensado desde la lógica del campo","DOTS parte de potreros, aguadas, recorridas, carga, rotación y condición de las pasturas. La tecnología satelital se incorpora como evidencia adicional para responder preguntas de manejo, no como un fin en sí mismo.","Agua, pastura y rodeo en una misma lectura","El sistema vincula disponibilidad hídrica, distancia a fuentes de agua, condición vegetal, meteorología y estrés térmico. Los datos declarados por el productor se distinguen de las observaciones satelitales y de los cálculos del sistema.","Un gemelo digital ganadero","Con el tiempo, cada establecimiento puede reunir límites, potreros, suelos, pasturas, agua, infraestructura, ganado, clima, satélite, riesgos, historial y tareas. Esa estructura permite documentar decisiones y producir informes comparables." ]};
 const a=copy[kind]; return <section className="institutional-depth"><article><span>01</span><h2>{a[0]}</h2><p>{a[1]}</p></article><article><span>02</span><h2>{a[2]}</h2><p>{a[3]}</p></article><article><span>03</span><h2>{a[4]}</h2><p>{a[5]}</p></article></section>;
}
function InfoPage({kind,onDemo}:{kind:"producto"|"soluciones"|"ganaderia";onDemo:()=>void}){const cfg:any={producto:["CÓMO FUNCIONA","Un sistema territorial, no una colección de indicadores.","DOTS organiza la información alrededor del establecimiento y de cada potrero: primero territorio, después evidencia, interpretación y decisión."],soluciones:["CAPACIDADES","Las capas del campo, conectadas.","El valor aparece cuando agua, suelo, vegetación, clima, ganado, riesgo e historia se leen sobre el mismo polígono."],ganaderia:["GANADERÍA","El potrero es la unidad de decisión.","DOTS está diseñado para el manejo ganadero: pastura, agua, carga, rotación, bienestar térmico, riesgo y tareas en contexto."]}[kind];return <div className="public-site"><PublicHeader onDemo={onDemo}/><main className="inner"><PageHero eyebrow={cfg[0]} title={cfg[1]} lead={cfg[2]}/><section className="info-grid">{cards[kind].map(([n,t,d])=><article key={t}><span>{n}</span><h2>{t}</h2><p>{d}</p></article>)}</section><InstitutionalDepth kind={kind}/>{kind==="producto"&&<><section className="workflow-band"><div><b>CAMPO</b><span>→</span><b>POLÍGONO</b><span>→</span><b>FUENTES</b><span>→</span><b>DOTS</b><span>→</span><b>DECISIÓN</b></div><p>La procedencia del dato nunca se pierde durante el proceso.</p></section><section className="product-shot"><div className="mock-map"><div className="mock-poly"></div><span>Potrero seleccionado</span><small>satélite · clima · suelo · agua · riesgo</small></div><div><span className="section-tag">OBSERVATORIO</span><h2>El mapa permanece. Las capas cambian.</h2><p>Resumen, lotes, imágenes, vegetación, agua, suelos, ganado, clima, riesgos, ENOS, alertas e informes trabajan sobre el mismo territorio seleccionado.</p><button onClick={onDemo}>Probar demostración</button></div></section></>}<SourceStrip/></main><SiteFooter/></div>}
// Fuentes y licencias: a quién le debemos cada dato y cada pieza de código, y con qué condiciones.
const LIC_DATA:[string,string,string,string][]=[
 ["INA · Sistema de Alerta","Instituto Nacional del Agua (Argentina), escalas de Prefectura Naval","Datos públicos del Estado argentino","https://alerta.ina.gob.ar/"],
 ["Open-Meteo (pronóstico, conjuntos ECMWF y GFS, GloFAS, ERA5; informe de cultivo)","Open-Meteo.com","Datos CC-BY 4.0 · API gratuita sólo para uso no comercial","https://open-meteo.com/en/licence"],
 ["ECMWF IFS","Centro Europeo de Pronósticos a Plazo Medio","Datos abiertos CC-BY 4.0","https://www.ecmwf.int/en/forecasts/datasets/open-data"],
 ["NOAA GFS, CPC (El Niño), PSL","NOAA (EE. UU.)","Dominio público del gobierno de EE. UU.","https://www.cpc.ncep.noaa.gov/"],
 ["Copernicus: Sentinel-1, Sentinel-2, GloFAS, DEM, GFM","Unión Europea · ESA · ECMWF","Acceso libre y abierto, con cita obligatoria de Copernicus","https://www.copernicus.eu/es/acceso-los-datos"],
 ["Landsat 8 y 9","USGS · NASA","Dominio público, se pide citar a USGS","https://www.usgs.gov/landsat-missions"],
 ["NASA: GIBS (VIIRS, MODIS, IMERG), POWER, FIRMS, MUR","NASA EOSDIS","Uso libre, se pide citar a NASA","https://www.earthdata.nasa.gov/engage/open-data-services-software-policies"],
 ["Represas de Brasil","ONS · Operador Nacional do Sistema Elétrico","CC-BY 4.0","https://dados.ons.org.br/"],
 ["Microsoft Planetary Computer","Microsoft (distribuye Sentinel y Landsat)","Servicio gratuito; cada colección conserva su licencia","https://planetarycomputer.microsoft.com/"],
 ["CHIRPS (lluvia observada)","Climate Hazards Center · UCSB, vía ClimateSERV","Uso libre, se pide citar","https://www.chc.ucsb.edu/data/chirps"],
 ["Fields of the World (lotes)","TGI · Microsoft AI for Good","CC-BY 4.0","https://fieldsofthe.world/"],
 ["ESA WorldCover","ESA · VITO","CC-BY 4.0","https://esa-worldcover.org/"],
 ["Mapas base","OpenStreetMap, Esri, Carto, OpenTopoMap, IGN Argentina","OSM: ODbL · OpenTopoMap: CC-BY-SA · Esri y Carto: según sus términos, con atribución visible","https://www.openstreetmap.org/copyright"],
];
const LIC_CODE:[string,string,string][]=[
 ["React y React DOM","MIT","interfaz de la web"],["Leaflet","BSD-2-Clause","mapas"],["ECharts","Apache-2.0","gráficos"],
 ["Lucide (íconos)","ISC","íconos del observatorio"],["geotiff.js","MIT","lectura de relieve"],["PMTiles, pbf, @mapbox/vector-tile","BSD-3-Clause","mapa de lotes"],
 ["polygon-clipping","MIT","recorte de polígonos"],["Flask, Requests","BSD-3-Clause · Apache-2.0","servidor"],["Typst","Apache-2.0","informes en PDF"],
 ["ReportLab","BSD","informes en PDF"],["Pillow","MIT-CMU","medir nubes en las imágenes"],["IBM Plex (tipografía)","SIL Open Font License 1.1","textos de la web y los PDF"],
];
const LIC_ADAPTED:[string,string,string][]=[
 ["TailAdmin · free-react-tailwind-admin-dashboard","MIT · © 2023 TailAdmin","estructura del tablero del observatorio; se conserva el aviso de copyright en el código"],
 ["Carbon Design System (IBM)","Apache-2.0","reglas visuales del tema oscuro; no se copian componentes"],
 ["xyzservices (GeoPandas)","BSD-3-Clause","catálogo base de capas del mapa"],
 ["xclim (Ouranos)","Apache-2.0","definición y nombres de los índices agroclimáticos; el cálculo es propio"],
 ["chirps (rOpenSci)","MIT","forma de consultar la API pública ClimateSERV; el código es propio"],
];
function Licenses({onDemo}:{onDemo:()=>void}){
 const th={textAlign:"left" as const,padding:"10px 12px",fontSize:12,letterSpacing:".08em",textTransform:"uppercase" as const,color:"#8fb3b8",borderBottom:"1px solid rgba(130,170,174,.3)"};
 const td={padding:"10px 12px",verticalAlign:"top" as const,borderBottom:"1px solid rgba(130,170,174,.14)",fontSize:15,lineHeight:1.5,color:"#d6e2e4"};
 const box={overflowX:"auto" as const,margin:"8px 0 36px"};
 return <div className="public-site"><PublicHeader onDemo={onDemo}/><main className="inner">
  <PageHero eyebrow="FUENTES Y LICENCIAS" title="Lo que usa DOTS, de quién es y con qué condiciones." lead="DOTS se construye sobre datos públicos y software libre. Acá está cada fuente y cada pieza de código de terceros, con su licencia y la forma en que la citamos."/>
  <section className="institutional-depth">
   <article><span>DATOS</span><h2>Siempre con su fuente</h2><p>Cada gráfico, informe y parte para WhatsApp nombra de dónde sale el dato. Las fuentes con licencia CC-BY exigen esa cita, y la cumplimos en todos los formatos.</p></article>
   <article><span>CÓDIGO</span><h2>Software libre, con sus avisos</h2><p>Las librerías se instalan desde sus repositorios oficiales y conservan su licencia. Donde adaptamos ideas o código de otros proyectos, lo decimos en el archivo y en esta página.</p></article>
   <article><span>USO</span><h2>Sin fines comerciales</h2><p>Hoy DOTS no tiene uso comercial. Algunas fuentes, como la API gratuita de Open-Meteo, sólo se pueden usar así; si eso cambia, hay que pasar a sus planes pagos o a otra fuente.</p></article>
  </section>
  <h2>Datos y servicios</h2>
  <div style={box}><table style={{width:"100%",borderCollapse:"collapse"}}><thead><tr><th style={th}>Fuente</th><th style={th}>Titular</th><th style={th}>Licencia o condición</th></tr></thead>
   <tbody>{LIC_DATA.map(([n,o,l,u])=><tr key={n}><td style={td}><a href={u} target="_blank" rel="noreferrer">{n}</a></td><td style={td}>{o}</td><td style={td}>{l}</td></tr>)}</tbody></table></div>
  <h2>Librerías de software</h2>
  <div style={box}><table style={{width:"100%",borderCollapse:"collapse"}}><thead><tr><th style={th}>Librería</th><th style={th}>Licencia</th><th style={th}>Para qué la usamos</th></tr></thead>
   <tbody>{LIC_CODE.map(([n,l,u])=><tr key={n}><td style={td}>{n}</td><td style={td}>{l}</td><td style={td}>{u}</td></tr>)}</tbody></table></div>
  <h2>Proyectos en los que nos basamos</h2>
  <div style={box}><table style={{width:"100%",borderCollapse:"collapse"}}><thead><tr><th style={th}>Proyecto</th><th style={th}>Licencia</th><th style={th}>Qué tomamos</th></tr></thead>
   <tbody>{LIC_ADAPTED.map(([n,l,u])=><tr key={n}><td style={td}>{n}</td><td style={td}>{l}</td><td style={td}>{u}</td></tr>)}</tbody></table></div>
  <p className="footnote">Cita de Copernicus: «Contiene datos modificados de Copernicus Sentinel y del Servicio de Gestión de Emergencias de Copernicus». DOTS no es un organismo oficial; ante una emergencia mandan Defensa Civil y Prefectura. ¿Ves una fuente mal citada? <SiteLink to="/contacto">Escribinos</SiteLink> y la corregimos.</p>
 </main><SiteFooter/></div>}
function Technology({onDemo}:{onDemo:()=>void}){return <div className="public-site"><PublicHeader onDemo={onDemo}/><main className="inner"><PageHero eyebrow="FUENTES Y DATOS" title="Una red mundial, con procedencia visible." lead="DOTS integra servicios oficiales y abiertos cuando existe una interfaz programática verificable. Catálogo, imagen, modelo y medición no son lo mismo: el sistema los identifica por separado."/><section className="institutional-depth"><article><span>RED</span><h2>Por qué integramos múltiples fuentes</h2><p>Ningún satélite ni modelo describe por sí solo un establecimiento. Radar, óptico, meteorología, suelo, hidrología y clima global responden preguntas diferentes. DOTS los consulta por ubicación y fecha y conserva la fuente original.</p></article><article><span>API</span><h2>Qué significa “conectada”</h2><p>Una fuente sólo figura como operativa cuando el backend puede realizar una consulta válida. Las que requieren registro o clave quedan marcadas como credencial pendiente. Una API de catálogo confirma productos disponibles; no se presenta como índice o medición raster procesada.</p></article><article><span>QA</span><h2>Control y trazabilidad</h2><p>Cada resultado debe conservar fuente, producto o sensor, fecha, geometría consultada, variable, unidad, método y estado. Si una fuente falla, DOTS conserva el faltante y continúa con las demás, sin reemplazarlo por cero ni por un valor inventado.</p></article></section><section className="source-world">{sourceGroups.map(([region,items]:any)=><article key={region}><span>{region}</span>{items.map((x:string)=><div className="source-line" key={x}><i></i><b>{x}</b></div>)}</article>)}</section><section className="method-banner"><h2>OBSERVADO · SATELITAL · MODELADO · CALCULADO · PRONOSTICADO · INTERPRETACIÓN DOTS</h2><p>Fuente, producto o sensor, fecha, polígono, variable, unidad, método, estado y confianza acompañan cada resultado.</p></section><section className="status-explainer"><div><i className="ok"></i><b>Operativa</b><p>La consulta obtuvo una respuesta válida.</p></div><div><i className="key"></i><b>Requiere credencial</b><p>La integración está preparada pero necesita acceso autorizado.</p></div><div><i className="pending"></i><b>Pendiente</b><p>No se presenta como conectada hasta comprobarla.</p></div></section><section className="demo-call"><div><span className="section-tag">OBSERVATORIO</span><h2>Las fuentes se prueban desde el lote.</h2><p>Dentro del Observatorio podés seleccionar Copernicus, Sentinel-1/2, Landsat, NASA MODIS, CNES, DLR, Digital Earth Africa y FIRMS. El panel muestra la respuesta o el motivo por el que la fuente no está disponible.</p></div><button onClick={onDemo}>Probar fuentes →</button></section></main><SiteFooter/></div>}


type ApiSource={id:string;name:string;org:string;country:string;domain:string;manage:string;test?:string;access:string;use:string;variables:string;priority:number};
const apiSources:ApiSource[]=[
 {id:"sentinel-hub",name:"Sentinel Hub",org:"Copernicus Data Space",country:"UE · Global",domain:"dataspace.copernicus.eu",manage:"https://www.sentinel-hub.com/develop/",test:"sentinel-hub",access:"OAuth 2.0 · requiere Client ID/Secret",use:"Procesamiento Sentinel-1/2 y estadísticas por polígono.",variables:"RGB · NDVI · NDMI/NDWI · EVI · radar · series",priority:1},
 {id:"era5-cds",name:"ERA5 / CDS",org:"ECMWF · Copernicus",country:"UE · Global",domain:"cds.climate.copernicus.eu",manage:"https://cds.climate.copernicus.eu/api-how-to",test:"era5-cds",access:"Registro gratuito · CDS API",use:"Reanálisis climático histórico de largo plazo.",variables:"Temperatura · lluvia · humedad · viento · radiación",priority:1},
 {id:"nasa-earthdata",name:"NASA Earthdata",org:"NASA",country:"EE.UU. · Global",domain:"earthdata.nasa.gov",manage:"https://urs.earthdata.nasa.gov/",test:"nasa-earthdata",access:"Cuenta + token",use:"Acceso autenticado a productos de observación de la Tierra.",variables:"MODIS · VIIRS · GPM · SMAP · productos terrestres",priority:1},
 {id:"usgs-m2m",name:"USGS M2M / EarthExplorer",org:"USGS",country:"EE.UU. · Global",domain:"usgs.gov",manage:"https://m2m.cr.usgs.gov/",test:"usgs-m2m",access:"Cuenta + acceso M2M",use:"Archivo histórico Landsat y evolución territorial.",variables:"Landsat · reflectancia · térmico · histórico",priority:1},
 {id:"noaa-cdo",name:"NOAA NCEI / CDO",org:"NOAA",country:"EE.UU. · Global",domain:"noaa.gov",manage:"https://www.ncdc.noaa.gov/cdo-web/token",test:"noaa-cdo",access:"Token gratuito",use:"Series históricas de estaciones y climatología.",variables:"Temperatura · precipitación · viento · estaciones",priority:1},
 {id:"copernicus-marine",name:"Copernicus Marine",org:"Copernicus Marine Service",country:"UE · Global",domain:"marine.copernicus.eu",manage:"https://data.marine.copernicus.eu/",test:"copernicus-marine",access:"Cuenta / credenciales",use:"Contexto oceánico para clima y ENSO.",variables:"SST · salinidad · corrientes · nivel del mar",priority:1},
 {id:"gee",name:"Google Earth Engine",org:"Google Earth Engine",country:"Global",domain:"earthengine.google.com",manage:"https://developers.google.com/earth-engine/",test:"gee",access:"Proyecto Cloud + Earth Engine",use:"Procesamiento pesado de series raster históricas.",variables:"CHIRPS · Landsat · Sentinel · ERA5 · colecciones GEE",priority:1},
 {id:"open-meteo",name:"Open-Meteo",org:"Open-Meteo · ECMWF · DWD · NOAA",country:"Global",domain:"open-meteo.com",manage:"https://open-meteo.com/en/docs",test:"variables",access:"Abierta · sin clave (uso no comercial gratuito; plan comercial para producción)",use:"Pronóstico de 7 modelos globales, ERA5 desde 1940, calidad de aire, caudales y elevación.",variables:"Temperatura · lluvia · humedad · viento · ET₀ · humedad del suelo",priority:0},
 {id:"pc-ndvi",name:"Planetary Computer",org:"Microsoft · ESA Sentinel-2",country:"Global",domain:"planetarycomputer.microsoft.com",manage:"https://planetarycomputer.microsoft.com/docs/reference/data/",access:"Abierta · sin clave",use:"NDVI de Sentinel-2 a 10 m recortado al lote, con máscara de nubes.",variables:"NDVI · mediana · percentiles · % del lote despejado",priority:0},
 {id:"ftw",name:"Fields of the World",org:"TGI · Microsoft AI for Good",country:"Global",domain:"fieldsofthe.world",manage:"https://source.coop/ftw/global-data",access:"Abierta · CC-BY 4.0 · sin clave",use:"Mapa mundial de lotes agrícolas 2025 para delimitar con un clic.",variables:"Polígono · superficie · confianza",priority:0},
 {id:"chirps",name:"CHIRPS / ClimateSERV",org:"Climate Hazards Center (UCSB) · SERVIR",country:"Global (50°S–50°N)",domain:"chc.ucsb.edu",manage:"https://climateserv.servirglobal.net/",access:"Abierta · sin clave",use:"Lluvia observada diaria desde 1981 a ~5 km, satélite más estaciones.",variables:"Lluvia mensual · normal · SPI 1/3/6/12",priority:0},
 {id:"noaa-psl",name:"NOAA PSL",org:"NOAA Physical Sciences Laboratory",country:"EE.UU. · Global",domain:"psl.noaa.gov",manage:"https://psl.noaa.gov/data/climateindices/list/",test:"teleconexiones",access:"Abierta · sin clave",use:"Índices oceánicos y atmosféricos mensuales para El Niño y el Cono Sur.",variables:"Niño 3.4 · ONI · MEI v2 · SOI · AAO · TSA · PDO",priority:0},
 {id:"worldcover",name:"ESA WorldCover",org:"ESA · VITO Terrascope",country:"Global",domain:"esa-worldcover.org",manage:"https://esa-worldcover.org/",access:"Abierta · CC-BY 4.0",use:"Cobertura del suelo a 10 m para ver monte, pastizal, cultivo y agua.",variables:"11 clases de cobertura (2020 y 2021)",priority:0},
 {id:"goes",name:"GOES-East",org:"NOAA · vía NASA GIBS",country:"América",domain:"goes.noaa.gov",manage:"https://nasa-gibs.github.io/gibs-api-docs/",access:"Abierta · sin clave",use:"Satélite meteorológico geoestacionario: nubes y tormentas cada 10 minutos.",variables:"Infrarrojo banda 13 · topes nubosos",priority:0},
 {id:"nasa-power",name:"NASA POWER",org:"NASA",country:"Global",domain:"power.larc.nasa.gov",manage:"https://power.larc.nasa.gov/api/",test:"nasa-power-30",access:"Abierta · sin registro",use:"Agrometeorología histórica del punto/lote.",variables:"T° · humedad · precipitación · radiación · viento",priority:0},
 {id:"nasa-gibs",name:"NASA GIBS",org:"NASA Earthdata",country:"Global",domain:"earthdata.nasa.gov",manage:"https://nasa-gibs.github.io/gibs-api-docs/",test:"gibs",access:"WMS/WMTS abierto · sin API key",use:"Capas satelitales reales directamente sobre el mapa.",variables:"MODIS · VIIRS · SMAP · GPM · SST · nubes · aerosoles",priority:0},
 {id:"soilgrids",name:"SoilGrids",org:"ISRIC",country:"Global",domain:"isric.org",manage:"https://rest.isric.org/soilgrids/",test:"suelo",access:"Abierta · servicio sujeto a disponibilidad",use:"Propiedades edáficas modeladas; nunca sustituye laboratorio.",variables:"N total · carbono · pH · arcilla · arena · densidad",priority:0},
 {id:"copernicus-stac",name:"Copernicus STAC",org:"Copernicus Data Space",country:"UE · Global",domain:"dataspace.copernicus.eu",manage:"https://documentation.dataspace.copernicus.eu/APIs/STAC.html",test:"copernicus-stac",access:"Catálogo abierto",use:"Localización de escenas por fecha y territorio.",variables:"Sentinel-1 · Sentinel-2 · Sentinel-3 · metadatos",priority:0},
 {id:"firms",name:"NASA FIRMS",org:"NASA",country:"Global",domain:"firms.modaps.eosdis.nasa.gov",manage:"https://firms.modaps.eosdis.nasa.gov/api/map_key/",test:"firms",access:"MAP_KEY · ya prevista en Vercel",use:"Detecciones térmicas e incendios cercanos al lote.",variables:"VIIRS · MODIS · focos · fecha · confianza",priority:0},
 {id:"openaq",name:"OpenAQ v3",org:"OpenAQ",country:"Global",domain:"openaq.org",manage:"https://docs.openaq.org/",test:"openaq",access:"API key",use:"Calidad del aire y humo como contexto ambiental.",variables:"PM2.5 · PM10 · O3 · NO2 · SO2 · CO",priority:2},
 {id:"gfw",name:"Global Forest Watch",org:"WRI",country:"Global",domain:"globalforestwatch.org",manage:"https://data.globalforestwatch.org/",test:"gfw",access:"API key / token según servicio",use:"Cambio de cobertura y alertas forestales.",variables:"Cobertura · pérdida forestal · alertas · uso del suelo",priority:2},
 {id:"aemet",name:"AEMET OpenData",org:"AEMET",country:"España",domain:"aemet.es",manage:"https://opendata.aemet.es/centrodedescargas/altaUsuario",test:"aemet",access:"API key gratuita",use:"Meteorología oficial española cuando el lote esté en cobertura.",variables:"Observaciones · pronóstico · avisos · climatología",priority:2},
 {id:"eumetsat",name:"EUMETSAT",org:"EUMETSAT Data Store",country:"Europa · África",domain:"eumetsat.int",manage:"https://data.eumetsat.int/",test:"eumetsat",access:"Cuenta + credenciales",use:"Meteorología satelital y Meteosat.",variables:"Nubes · temperatura · humedad · productos Meteosat",priority:2},
 {id:"jaxa",name:"JAXA G-Portal",org:"JAXA",country:"Japón · Global",domain:"jaxa.jp",manage:"https://gportal.jaxa.jp/gpr/",test:"jaxa",access:"Registro para descargas",use:"Productos japoneses de observación terrestre.",variables:"ALOS · GCOM · GPM · AMSR2",priority:2},
 {id:"mosdac",name:"ISRO MOSDAC",org:"ISRO",country:"India",domain:"mosdac.gov.in",manage:"https://www.mosdac.gov.in/",test:"mosdac",access:"Cuenta / credenciales",use:"Satélites meteorológicos y oceánicos de India.",variables:"INSAT · precipitación · océano · atmósfera",priority:2},
 {id:"kma",name:"KMA / GK2A",org:"Korea Meteorological Administration",country:"Corea del Sur",domain:"data.kma.go.kr",manage:"https://data.kma.go.kr/",test:"kma",access:"Auth key según servicio",use:"Meteorología y observación geoestacionaria asiática.",variables:"Canales GK2A · nubes · IR · vapor de agua",priority:2},
 {id:"fengyun",name:"FengYun / CMA-NSMC",org:"China Meteorological Administration",country:"China",domain:"cma.gov.cn",manage:"https://satellite.nsmc.org.cn/PortalSite/Default.aspx",test:"fengyun",access:"Registro / autorización",use:"Observación meteorológica satelital china.",variables:"FY-3 · FY-4 · nubes · humedad · temperatura",priority:2},
 {id:"waqi",name:"WAQI",org:"World Air Quality Index",country:"Global",domain:"aqicn.org",manage:"https://aqicn.org/data-platform/token/",access:"Token gratuito",use:"Fuente complementaria de calidad del aire.",variables:"AQI · PM2.5 · PM10 · O3 · NO2 · SO2",priority:3},
 {id:"airnow",name:"AirNow",org:"US EPA",country:"EE.UU. / Norteamérica",domain:"airnow.gov",manage:"https://docs.airnowapi.org/",access:"API key gratuita",use:"Calidad del aire de referencia en Norteamérica.",variables:"AQI · partículas · ozono",priority:3},
 {id:"usda-nass",name:"USDA NASS QuickStats",org:"USDA",country:"EE.UU.",domain:"usda.gov",manage:"https://quickstats.nass.usda.gov/api",access:"API key gratuita",use:"Contexto estadístico agropecuario y ganadero.",variables:"Ganado · producción · rendimiento · tierras",priority:3}
];
function sourceLogo(domain:string){return `https://www.google.com/s2/favicons?sz=128&domain_url=https://${domain}`}
function ApiConnections({onDemo}:{onDemo:()=>void}){
 const [results,setResults]=useState<Record<string,{state:string;detail:string}>>({});
 const [busy,setBusy]=useState<string>("");
 const test=async(s:ApiSource)=>{if(!s.test)return;setBusy(s.id);setResults(r=>({...r,[s.id]:{state:"checking",detail:"Comprobando…"}}));try{const extra=s.test==="nasa-power-30"?"&years=30":"";const res=await fetch(`/api/fuentes/${s.test}?lat=-28.507&lon=-59.043${extra}`,{signal:AbortSignal.timeout(25000)});const data=await res.json();const state=res.ok?((data?.data?.status||data?.status)==="requiere credencial"?"key":"ok"):(res.status===409?"key":"fail");const detail=data?.data?.status||data?.status||data?.error||(res.ok?"Respuesta válida":"Sin respuesta válida");setResults(r=>({...r,[s.id]:{state,detail:String(detail)}}))}catch(e){setResults(r=>({...r,[s.id]:{state:"fail",detail:"No se obtuvo respuesta válida"}}))}finally{setBusy("")}};
 return <div className="public-site"><PublicHeader onDemo={onDemo}/><main className="inner"><PageHero eyebrow="APIs Y CONEXIONES" title="Cada botón tiene una fuente detrás." lead="Directorio operativo de accesos DOTS. Los servicios abiertos pueden probarse desde el sitio; los protegidos verifican si la credencial está configurada. Ningún logo equivale por sí solo a una conexión."/>
 <section className="api-intro"><article><b>1 · GESTIONAR</b><h2>Acceso oficial</h2><p>El botón abre la dirección de registro o documentación del proveedor. Las contraseñas no se guardan en esta página.</p></article><article><b>2 · PROBAR</b><h2>Conector DOTS</h2><p>El segundo botón llama al backend. Verde significa respuesta válida; ámbar indica credencial pendiente; rojo, fuente sin respuesta válida.</p></article><article><b>3 · USAR</b><h2>Territorio y variables</h2><p>La fuente se aplica al lote/potrero y conserva procedencia, fecha, variable, unidad, método y estado.</p></article></section>
 {[0,1,2,3].map(level=>{const group=apiSources.filter(x=>x.priority===level);if(!group.length)return null;return <section className="api-section" key={level}><div className="api-section-head"><span>{level===0?"ABIERTAS / YA DISPONIBLES":level===1?"GESTIÓN PRIORITARIA":level===2?"SEGUNDA ETAPA":"COMPLEMENTARIAS"}</span><h2>{level===0?"Podemos avanzar sin esperar credenciales":level===1?"Estas son las cuentas que conviene gestionar primero":level===2?"Amplían la cobertura internacional":"Se incorporan cuando aporten valor al territorio"}</h2></div><div className="api-grid">{group.map(s=>{const r=results[s.id];return <article className="api-card" key={s.id}><div className="api-card-top"><img src={sourceLogo(s.domain)} alt={`Identificador web de ${s.org}`} loading="lazy"/><div><span>{s.country}</span><h3>{s.name}</h3><small>{s.org}</small></div></div><p>{s.use}</p><div className="api-vars">{s.variables}</div><div className="api-access"><b>Acceso</b><span>{s.access}</span></div>{r&&<div className={`api-result ${r.state}`}><i></i>{r.detail}</div>}<div className="api-actions"><a href={s.manage} target="_blank" rel="noreferrer">Gestión / documentación ↗</a>{s.test?<button onClick={()=>void test(s)} disabled={busy===s.id}>{busy===s.id?"Probando…":"Probar conexión"}</button>:<button disabled>Conector pendiente</button>}</div></article>})}</div></section>})}
 <section className="method-banner"><h2>BOTÓN → CONECTOR → API → DATO → PROCESAMIENTO → MAPA/GRÁFICO → INFORME</h2><p>Si una etapa no está disponible, DOTS la muestra como pendiente. No se reemplazan faltantes con valores inventados.</p></section><section className="demo-call"><div><span className="section-tag">OBSERVATORIO</span><h2>La prueba definitiva se hace sobre un lote.</h2><p>Una conexión sólo se considera productiva cuando devuelve datos válidos para la geometría, fecha y variable solicitadas.</p></div><button onClick={onDemo}>Abrir Observatorio →</button></section></main><SiteFooter/></div>
}

function Cases({onDemo}:{onDemo:()=>void}){return <div className="public-site"><PublicHeader onDemo={onDemo}/><main className="inner"><PageHero eyebrow="CASOS DE USO" title="Preguntas reales del campo." lead="El sistema debe responder una pregunta de manejo y mostrar la evidencia utilizada, no llenar una pantalla de cifras."/><section className="case-list">{["¿Qué potrero perdió vigor y desde cuándo?","¿Dónde falta cobertura de agua para el rodeo?","¿La lluvia prevista compensa la evapotranspiración?","¿Hay condiciones de estrés térmico esta semana?","¿Cómo cambió este lote frente al mismo período anterior?","¿Qué fuentes coinciden y cuáles divergen?"].map((x,i)=><article key={x}><b>0{i+1}</b><h2>{x}</h2><p>DOTS cruza sólo las capas disponibles y conserva los datos faltantes como faltantes.</p></article>)}</section></main><SiteFooter/></div>}
function Pricing({onDemo}:{onDemo:()=>void}){return <div className="public-site"><PublicHeader onDemo={onDemo}/><main className="inner"><PageHero eyebrow="ACCESO" title="DOTS puede crecer con cada establecimiento." lead="La demostración permanece abierta; los planes comerciales se publicarán únicamente cuando autenticación, permisos y cobro estén realmente conectados."/><section className="pricing-grid"><article><span>DEMO</span><h2>Explorar</h2><p>Recorrido del Observatorio y establecimiento demostrativo.</p><b>Sin cargo</b><button onClick={onDemo}>Ver demo</button></article><article className="featured"><span>PRODUCTOR</span><h2>Gestión territorial</h2><p>Lotes, fuentes, históricos, alertas e informes.</p><b>En preparación</b></article><article><span>PROFESIONAL</span><h2>Multiestablecimiento</h2><p>Comparación, equipos técnicos y reportes avanzados.</p><b>En preparación</b></article></section></main><SiteFooter/></div>}
function Blog({onDemo}:{onDemo:()=>void}){return <div className="public-site"><PublicHeader onDemo={onDemo}/><main className="inner"><PageHero eyebrow="CUADERNO DOTS" title="Método antes que promesas." lead="Notas sobre observación de la Tierra, ganadería, clima y límites de interpretación."/><section className="blog-grid">{[["SATÉLITES","Qué puede observar Sentinel-2 y qué no"],["ARGENTINA","SAOCOM y el radar de banda L"],["CLIMA","ENOS: cómo comparar NOAA, IRI, JMA y BOM"],["AGUA","Del milímetro de lluvia a la disponibilidad real"],["SUELOS","Por qué nitrógeno modelado no es laboratorio"],["MÉTODO","Dato, cálculo, pronóstico e interpretación"]].map(([k,t])=><article key={t}><span>{k}</span><h2>{t}</h2><p>Contenido técnico DOTS.</p></article>)}</section></main><SiteFooter/></div>}
function Contact({onDemo}:{onDemo:()=>void}){
  const [ch,setCh]=useState<any>(null),[f,setF]=useState<any>({tema:"consulta"}),[st,setSt]=useState<{kind:string;msg:string}|null>(null),[busy,setBusy]=useState(false);
  useEffect(()=>{fetch("/api/fuentes/contacto/canal").then(r=>r.json()).then(setCh).catch(()=>setCh({email_enabled:false,topics:{}}))},[]);
  const set=(k:string)=>(e:any)=>setF((v:any)=>({...v,[k]:e.target.value}));
  const submit=async(e:any)=>{e.preventDefault();setBusy(true);setSt(null);
    try{const r=await fetch("/api/fuentes/contacto",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(f),signal:AbortSignal.timeout(25000)});const j=await r.json();
      if(!r.ok)throw Error(j.error||"No se pudo enviar");setSt({kind:"ok",msg:"¡Gracias! Recibimos tu consulta y te respondemos por correo."});setF({tema:f.tema});}
    catch(err){setSt({kind:"err",msg:(err as Error).message})}finally{setBusy(false)}};
  const topics=ch?.topics&&Object.keys(ch.topics).length?ch.topics:{consulta:"Consulta general",demo:"Pedido de demostración",soporte:"Soporte técnico",sugerencia:"Sugerencia o inquietud",alianza:"Alianza o institución"};
  return <div className="public-site"><PublicHeader onDemo={onDemo}/><main className="inner"><PageHero eyebrow="CONTACTO" title="Dejanos tu consulta." lead="Productores, asesores, técnicos e instituciones: contanos qué necesitás, qué te gustaría ver en DOTS o qué no funcionó. Respondemos por correo."/>
    <section className="contact-box"><div><h2>Inteligencia territorial para la gestión ganadera.</h2><p>Cada consulta llega directo al equipo de DOTS. Usamos tus datos solo para responderte.</p>
      {ch?.whatsapp && <a className="wa-btn" href={`https://wa.me/${ch.whatsapp}?text=${encodeURIComponent("Hola, quiero consultar sobre DOTS / Campo")}`} target="_blank" rel="noreferrer">Escribinos por WhatsApp →</a>}
    </div>
    <form className="contact-form" onSubmit={submit}>
      <label>Tema<select value={f.tema} onChange={set("tema")}>{Object.entries(topics).map(([k,v]:any)=><option key={k} value={k}>{v}</option>)}</select></label>
      <label>Nombre<input required maxLength={100} value={f.nombre||""} onChange={set("nombre")} placeholder="Tu nombre"/></label>
      <label>Correo<input required type="email" value={f.correo||""} onChange={set("correo")} placeholder="nombre@correo.com"/></label>
      <label>Teléfono (opcional)<input value={f.telefono||""} onChange={set("telefono")} placeholder="+54 9 …"/></label>
      <label>Establecimiento u organización (opcional)<input maxLength={120} value={f.establecimiento||""} onChange={set("establecimiento")} placeholder="Campo, empresa o institución"/></label>
      <label>Consulta<textarea required minLength={10} maxLength={4000} value={f.mensaje||""} onChange={set("mensaje")} placeholder="Contanos qué necesitás"></textarea></label>
      <input className="hp" tabIndex={-1} autoComplete="off" value={f.website||""} onChange={set("website")} aria-hidden="true" placeholder="No completar"/>
      <button type="submit" disabled={busy||ch?.email_enabled===false}>{busy?"Enviando…":ch?.email_enabled===false?"Canal de correo en configuración":"Enviar consulta"}</button>
      {st && <p className={"form-status "+st.kind} role="status">{st.msg}</p>}
      {ch?.email_enabled===false && <p className="form-status">El envío se habilita cuando el correo de destino esté configurado. No simulamos envíos.</p>}
    </form></section></main><SiteFooter/></div>}
function Access({onDemo}:{onDemo:()=>void}){return <div className="public-site"><PublicHeader onDemo={onDemo}/><main className="inner access-page"><PageHero eyebrow="ACCESO" title="Observatorio DOTS" lead="La autenticación real se incorporará con permisos por establecimiento. La demostración no simula una cuenta de usuario."/><button className="big-demo" onClick={onDemo}>Entrar a la demostración →</button></main><SiteFooter/></div>}
function SiteFooter(){return <footer className="site-footer"><Brand/><p>Inteligencia territorial para la gestión ganadera.</p><div><SiteLink to="/guia">Guía: cómo funciona</SiteLink><SiteLink to="/producto">Cómo funciona</SiteLink><SiteLink to="/tecnologia">Fuentes</SiteLink><SiteLink to="/capas">Capas</SiteLink><SiteLink to="/conexiones">APIs</SiteLink><SiteLink to="/demo">Demo</SiteLink><SiteLink to="/cultivos">Informe de cultivo</SiteLink><SiteLink to="/licencias">Fuentes y licencias</SiteLink><SiteLink to="/contacto">Contacto</SiteLink></div></footer>}

function App(){
  const [path,setPath]=useState(window.location.pathname);
  const [inside,setInside]=useState(path==="/observatorio"||path==="/demo");
  useEffect(()=>{const h=()=>{setPath(window.location.pathname);setInside(window.location.pathname==="/observatorio"||window.location.pathname==="/demo")};addEventListener("popstate",h);return()=>removeEventListener("popstate",h)},[]);
  const openDemo=()=>{history.pushState({},"","/observatorio");setPath("/observatorio");setInside(true);window.scrollTo(0,0)};
  const home=()=>{history.pushState({},"","/");setPath("/");setInside(false);window.scrollTo(0,0)};
  if(inside)return <Observatory onHome={home}/>;
  if(path==="/producto")return <InfoPage kind="producto" onDemo={openDemo}/>;
  if(path==="/soluciones")return <InfoPage kind="soluciones" onDemo={openDemo}/>;
  if(path==="/ganaderia")return <InfoPage kind="ganaderia" onDemo={openDemo}/>;
  if(path==="/que-es-dots")return <About onDemo={openDemo}/>;
  if(path==="/guia"||path==="/como-funciona")return <Guide onDemo={openDemo}/>;
  if(path==="/libre-deforestacion")return <Deforestation onDemo={openDemo}/>;
  if(path==="/modulos")return <Modules onDemo={openDemo}/>;
  if(path==="/panel")return <RegionalPanel onDemo={openDemo}/>;
  if(path==="/alertas")return <AlertsPage onDemo={openDemo}/>;
  if(path==="/cultivos")return <CultivosPage onDemo={openDemo}/>;
  if(path==="/tecnologia")return <Technology onDemo={openDemo}/>;
  if(path==="/licencias")return <Licenses onDemo={openDemo}/>;
  if(path==="/capas")return <LayersPage onDemo={openDemo}/>;
  if(path==="/conexiones")return <ApiConnections onDemo={openDemo}/>;
  if(path==="/casos")return <Cases onDemo={openDemo}/>;
  if(path==="/precios")return <Pricing onDemo={openDemo}/>;
  if(path==="/blog")return <Blog onDemo={openDemo}/>;
  if(path==="/contacto")return <Contact onDemo={openDemo}/>;
  if(path==="/acceso")return <Access onDemo={openDemo}/>;
  return <Home onDemo={openDemo}/>;
}
createRoot(document.getElementById("root")!).render(<App />);
