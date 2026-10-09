import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import * as echarts from "echarts/core";
import { LineChart, BarChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
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
import { ObsSidebar, MetricCards, buildNav } from "./dashboard/Shell";
import { MARKER_KINDS, markerIcon, kindOf, MarkerLegend } from "./dashboard/markers";
import { fieldAt, fieldsAround, compactness, FTW_ATTRIBUTION, FTW_RELIABLE } from "./dashboard/fields";
echarts.use([
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
const WORLDCOVER = "esa-worldcover-map-10m-2021-v2_map";
const WORLDCOVER_CLASSES: [string,string][] = [["#006400","Árboles / monte"],["#ffbb22","Arbustal"],["#ffff4c","Pastizal"],["#f096ff","Cultivo"],["#fa0000","Construido"],["#b4b4b4","Suelo desnudo"],["#0064c8","Agua"],["#0096a0","Humedal herbáceo"]];
const GIBS_LAYERS: [string,string,string,string?][] = [
  ["","Capas · ninguna",""],
  ["MODIS_Terra_NDVI_8Day","NDVI MODIS · 8 días · 250 m","Vegetación regional. Para el lote usar NDVI Sentinel-2 (10 m)."],
  ["MODIS_Terra_Land_Surface_Temp_Day","Temperatura de superficie · día · 1 km","Temperatura del suelo/canopeo, no del aire."],
  ["SMAP_L4_Analyzed_Surface_Soil_Moisture","Humedad de suelo SMAP · 9 km","Modelo asimilado, 0–5 cm. Escala regional."],
  ["IMERG_Precipitation_Rate","Lluvia GPM IMERG · 30 min","Tasa de lluvia satelital estimada, no pluviómetro."],
  [WORLDCOVER,"Cobertura ESA WorldCover · 10 m","Árboles, pastizal, cultivo, agua y humedales (2021). Fuente: ESA / VITO Terrascope, CC-BY 4.0.","https://titiler.terrascope.be/wms"],
];
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
  ["historico", "Histórico reciente", "NASA POWER"],
  ["indices", "Índices agroclimáticos", "ERA5 · definiciones xclim/ETCCDI"],
  ["teleconexiones", "El Niño y teleconexiones", "NOAA PSL · ENSO, SOI, AAO, TSA, PDO"],
  ["rios", "Ríos y caudales", "GloFAS / Open-Meteo"],
  ["suelo", "Nitrógeno del suelo", "ISRIC SoilGrids"],
  ["serie", "Clima de 20–30 años", "ERA5 / Open-Meteo"],
  ["proyeccion", "Proyección 2031–2040", "CMIP6 / MPI-ESM1-2-XR"],
  ["smn", "Estaciones · Argentina", "SMN / WIS2"],
  ["inmet", "Estaciones · Brasil", "INMET / WIS2"],
  ["dmc", "Estaciones · Chile", "DMC / WIS2"],
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
    chart.setOption({
      animation: false,
      textStyle: { fontFamily: "Inter", color: "#a0b3bf" },
      tooltip: {
        trigger: "axis",
        backgroundColor: "#132734",
        borderColor: "#42616c",
        textStyle: { color: "#e7f1f5" },
        valueFormatter: (v: any) =>
          v === null ? "Sin dato" : fmt(v) + " " + unit,
      },
      grid: { left: 42, right: 15, top: 12, bottom: 27 },
      xAxis: {
        type: "category",
        data: dates,
        axisLabel: { color: "#a0b3bf", fontSize: 11, hideOverlap: true },
        axisLine: { lineStyle: { color: "#3a4d57" } },
        axisTick: { show: false },
      },
      yAxis: {
        type: "value",
        scale: true,
        name: unit,
        nameTextStyle: { fontSize: 10, color: "#a0b3bf" },
        axisLabel: { color: "#a0b3bf", fontSize: 11 },
        splitLine: { lineStyle: { color: "#293d49" } },
      },
      series: series.map((s) => ({
        name: s.name,
        type: s.type || "line",
        data: s.values,
        connectNulls: false,
        symbolSize: 5,
        lineStyle: { width: 2 },
        itemStyle: { color: s.color },
        barMaxWidth: 16,
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
      currentPoints.current = [...currentPoints.current,[e.latlng.lat,e.latlng.lng]];
      setVertices([...currentPoints.current]);
      const vm=L.circleMarker(e.latlng,{radius:6,color:"#071820",weight:2,fillColor:"#57dce0",fillOpacity:1}).addTo(map);
      vm.bindTooltip(String(currentPoints.current.length),{permanent:true,direction:"center",className:"vertex-label"});
      vertexMarkers.current.push(vm);
      line.current?.remove();
      line.current = L.polyline(currentPoints.current, {
        color: "#57dce0",
        dashArray: "5,5",
      }).addTo(map);
    });
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
  useEffect(() => {
    if (!gibsLayer || !mapRef.current) return;
    // WMS sin TIME: GIBS devuelve la última fecha disponible de cada capa.
    const cfg = GIBS_LAYERS.find(([k])=>k===gibsLayer);
    const isWC = gibsLayer === WORLDCOVER;
    const wms = L.tileLayer.wms(cfg?.[3] || GIBS_WMS, {
      layers: gibsLayer, format: "image/png", transparent: true, opacity: isWC ? .6 : .7,
      attribution: isWC ? "ESA WorldCover 2021 / VITO Terrascope (CC-BY 4.0)" : "NASA GIBS / EOSDIS",
    } as L.WMSOptions).addTo(mapRef.current);
    let warned = false;
    wms.on("tileerror", () => { if (!warned) { warned = true; notify(gibsLayer===WORLDCOVER?"Terrascope no devolvió la capa WorldCover. Probá más tarde.":"NASA GIBS no devolvió esta capa ahora. Probá más tarde u otra capa."); } });
    return () => { wms.remove(); };
  }, [gibsLayer]);
  const [showNdvi, setShowNdvi] = useState(true);
  const [navCollapsed, setNavCollapsed] = useState(() => typeof window !== "undefined" && window.innerWidth < 1800);
  const [navOpen, setNavOpen] = useState(false);
  const [ftwMode, setFtwMode] = useState(false);
  const [ftwBusy, setFtwBusy] = useState(false);
  const ndviOverlay = useRef<L.ImageOverlay | null>(null);
  useEffect(() => {
    ndviOverlay.current?.remove(); ndviOverlay.current = null;
    const latest = (sources.ndvi?.payload as any)?.data?.latest;
    if (!mapRef.current || !showNdvi || view !== "ndvi" || !latest?.item || vertices.length < 3) return;
    const lats = vertices.map(v=>v[0]), lons = vertices.map(v=>v[1]);
    const bounds: L.LatLngBoundsExpression = [[Math.min(...lats), Math.min(...lons)], [Math.max(...lats), Math.max(...lons)]];
    const url = "/api/fuentes/ndvi-imagen?" + new URLSearchParams({lat:String(point[0]),lon:String(point[1]),item:latest.item,baseline:String(latest.processing_baseline||""),polygon:JSON.stringify(vertices)});
    const ov = L.imageOverlay(url, bounds, {opacity: .85, interactive: false}).addTo(mapRef.current);
    ov.on("error", () => notify("La imagen NDVI no se pudo recortar al lote. Los valores del panel siguen siendo válidos."));
    ndviOverlay.current = ov;
    return () => { ov.remove(); };
  }, [sources.ndvi, showNdvi, view, vertices]);
  const changeView = (key: string) => {
    // Always refresh: source results are spatial/temporal and must follow the currently selected lot.
    // Reusing an old payload after changing polygon was a functional bug in earlier versions.
    setView(key);
    void load(key);
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
  const startDraw = (mode:"free"|"triangle"|"rectangle"="free") => {
    setDrawMode(mode);
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
    if (mapRef.current) mapRef.current.getContainer().style.cursor = "";
  };
  const finish = (given?: Point[], origin?: string, ftw?: any) => {
    try {
      let points = given ?? currentPoints.current;
      if(!given && drawMode==="triangle" && points.length!==3) throw Error("Triángulo: marcá exactamente 3 vértices.");
      if(!given && drawMode==="rectangle" && points.length!==2 && points.length!==4) throw Error("Rectángulo: marcá 2 esquinas opuestas o 4 vértices.");
      if(!given && drawMode==="rectangle" && points.length===2){const a=points[0],b=points[1];points=[a,[a[0],b[1]],b,[b[0],a[1]]];currentPoints.current=points;setVertices(points);}
      if(points.length<3) throw Error("Marcá al menos 3 vértices para cerrar el lote.");
      if (
        crosses(points) ||
        new Set(points.map((p) => p.join(","))).size !== points.length
      )
        throw Error(
          "Hay lados cruzados o vértices repetidos. Cancelá y delimitá nuevamente.",
        );
      const center = centroid(points);
      const areaHa = (()=>{ const R=6378137,lat0=points.reduce((a,p)=>a+p[0],0)/points.length*Math.PI/180,xy=points.map(([la,lo])=>[R*lo*Math.PI/180*Math.cos(lat0),R*la*Math.PI/180]);let a=0;for(let i=0;i<xy.length;i++){const j=(i+1)%xy.length;a+=xy[i][0]*xy[j][1]-xy[j][0]*xy[i][1]}return Math.abs(a)/2/10000;})();
      const perimeterKm = (()=>{const rad=(x:number)=>x*Math.PI/180,R=6371;let d=0;for(let i=0;i<points.length;i++){const a=points[i],b=points[(i+1)%points.length],dl=rad(b[0]-a[0]),dn=rad(b[1]-a[1]);const h=Math.sin(dl/2)**2+Math.cos(rad(a[0]))*Math.cos(rad(b[0]))*Math.sin(dn/2)**2;d+=2*R*Math.asin(Math.sqrt(h))}return d;})();
      const id=`lote-${Date.now()}`;
      const name=`Lote ${lots.length+1}${origin?" · "+origin:""}`;
      if(given){currentPoints.current=points;setVertices(points);}
      const layer=L.polygon(points,{color:"#57dce0",fillOpacity:.12,weight:2}).addTo(mapRef.current!).bindTooltip(name,{permanent:true,direction:"center"});
      layer.on("click",()=>{ setSelectedLotId(id); setVertices(points); currentPoints.current=points; poly.current=layer; setPoint(center); setCoords(center.map(v=>v.toFixed(6))); mapRef.current?.fitBounds(layer.getBounds(),{padding:[40,40]}); });
      lotLayers.current[id]=layer; poly.current=layer;
      if(given) mapRef.current?.fitBounds(layer.getBounds(),{padding:[60,60],maxZoom:16});
      setLots(prev=>[...prev,{id,name,vertices:[...points],center,areaHa,perimeterKm,compactness:compactness(areaHa,perimeterKm),ftw}]);
      setSelectedLotId(id);
      stopDraw();
      setCoords(center.map((v) => v.toFixed(6)));
      setPoint(center);
      notify(`${name} guardado · ${areaHa.toFixed(2)} ha · ${perimeterKm.toFixed(2)} km de perímetro.`);
    } catch (e) {
      notify((e as Error).message);
    }
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
        body: JSON.stringify({ lat: point[0], lon: point[1], prompt, polygon: poly.current ? vertices : null, inaSeries, waterAssets, fieldMarkers }),
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
      ndvi: data("ndvi"), indices: data("indices"), telecon: data("teleconexiones"), clima: data("variables"),
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
    <div className={"whole ta-shell"+(navCollapsed?" nav-collapsed":"")}>
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
        <span className="live">
          {Object.values(sources).filter((s) => s.status === "recibido").length}{" "}
          FUENTES RECIBIDAS
        </span>
      </header>
      <main className="app ta-content">
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
        <aside className="sidebar">
          <section className="panel block">
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
          <section className="panel block agentic-box">
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
          <section className="panel block">
            <div className="tag" style={{ marginBottom: 10 }}>
              03 / FUENTES Y VARIABLES
            </div>
            {SOURCES.filter(([key]) => !NATIONAL.includes(key) && key !== "metnorway" && !RESEARCH.includes(key)).map(([key, label]) => (
              <button
                key={key}
                className={"data-button " + (view === key ? "active" : "")}
                onClick={() => changeView(key)}
                aria-pressed={view === key}
              >
                {label}
                <span>{sources[key]?.status.toUpperCase() || "CONSULTAR"}</span>
              </button>
            ))}
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
                {view==="elevacion" && <div className="key"><span>Elevación estimada DEM</span><strong>{fmt(payload?.elevation?.[0])} m</strong></div>}
                {view==="ina" && <><label className="small">Serie de estación · Bella Vista<select style={{width:"100%",marginTop:8}} value={inaSeries} onChange={e=>{setInaSeries(e.target.value);void load("ina",point,years,e.target.value)}}><option value="22">Altura Paraná · 30 días</option><option value="25500">Altura mensual · 30 años</option><option value="37299">Temperatura RMA08 · 2 días</option></select></label><p className="footnote">Estación Bella Vista · serie {inaSeries} · unidad y procedimiento de la fuente. No cambia de estación al mover el mapa.</p><div className="key"><span>Último registro · {payload?.data?.at(-1)?.timestart||"Sin fecha"}</span><strong>{fmt(payload?.data?.at(-1)?.valor)} {payload?.responseHeader?.seriesmetadata?.unit_abrev||""}</strong></div><p className="footnote">{payload?.data?.length||0} registros recibidos · exportables en JSON.</p></>}
                {["nasa-catalogo","productos-nasa","landsat","radar","copernicus-stac","cnes-stac","dlr-stac","deafrica-stac"].includes(view) && <><p className="footnote">Catálogo y metadatos. Todavía no se extraen valores de NDVI, temperatura de superficie ni píxeles de radar.</p>{(payload?.features||payload?.feed?.entry||Object.values(payload||{})).slice(0,5).map((item:any,i:number)=><div className="soil" key={i}><span style={{overflowWrap:"anywhere"}}>{item?.id||item?.title||item?.long_name||item?.short_name||"Producto NASA"}<small style={{display:"block"}}>{item?.properties?.datetime||item?.time_start||"Metadatos de catálogo"}</small></span></div>)}</>}
                {["era5-cds","sentinel-hub","noaa-cdo","usgs-m2m","nasa-earthdata","copernicus-marine","gee","openaq","gfw","aemet","eumetsat","jaxa","mosdac","kma","fengyun"].includes(view) && <><div className="metric-card"><span className="muted">ESTADO DE INTEGRACIÓN</span><strong>{payload?.status || "Sin verificar"}</strong><p>{payload?.missing_env?.length ? "Faltan en Vercel: "+payload.missing_env.join(", ") : "Credenciales detectadas. Falta validar consulta end-to-end antes de marcar OPERATIVA."}</p></div></>}
                {view==="usgs" && <><label className="small">Estación opcional (ej. USGS-06887000)<input style={{width:"100%",marginTop:8}} value={usgsSite} onChange={e=>setUsgsSite(e.target.value)} placeholder="Vacío: región del mapa"/></label><p className="footnote">Muestra de hasta 50 registros dentro de la región consultada. Sin cobertura USGS fuera de EE.UU.</p><p className="small">{payload?.features?.length||0} registros recibidos. JSON incluye códigos, unidades y fechas originales.</p></>}
              </>}
              {NATIONAL.includes(view) && (
                <>
                  <p className="footnote">{payload?.agency || "Servicio oficial directo"}. {payload?.scope || "Seleccioná coordenadas dentro del país de la agencia."}</p>
                  {sources[view]?.status === "recibido" && !payload?.observations?.length && <p className="error">Sin observaciones en esta ubicación y período. No se sustituyen por datos de otro país.</p>}
                  {(payload?.observations || []).slice(0,35).map((o: Data,i: number)=><div className="soil" key={i}><span style={{fontSize:10,maxWidth:"60%",overflowWrap:"anywhere"}}>{o.variable}<small style={{display:"block"}}>{o.station} · {fmt(o.distance_km)} km</small><small style={{display:"block"}}>{o.observed_at || "Sin fecha"}</small><small style={{display:"block"}}>Calidad: {o.quality ?? "no informada"}</small></span><strong style={{fontSize:12}}>{fmt(o.value)}<small style={{display:"block"}}>{o.unit || "sin unidad"}</small></strong></div>)}
                  <p className="footnote">Se muestran hasta 35 valores; exportá JSON para ver toda la respuesta. La antigüedad y la distancia de cada registro importan.</p>
                </>
              )}
              {view==="indices" && payload?.catalog && <>
                <p className="footnote">ERA5 diario en el punto del lote · {payload.period?.[0]}–{payload.period?.[1]} · último año {payload.last_year} comparado con el promedio del período.</p>
                <div className="idx-table">
                  <div className="idx-head"><span>Índice</span><span>{payload.last_year}</span><span>Promedio</span><span>Dif.</span></div>
                  {payload.catalog.map((k:Data)=>{const last=(payload.years||[]).slice(-1)[0]||{};const v=last[k.key];const a=payload.anomaly_last_year?.[k.key];const isDate=k.unit==="fecha";return <div className="idx-row" key={k.key} title={`${k.description} · xclim: ${k.xclim}`}><span>{k.label}<small>{k.unit}</small></span><strong>{isDate?(v?String(v).slice(5).split("-").reverse().join("/"):"—"):fmt(v)}</strong><span>{isDate?"":fmt(payload.mean?.[k.key])}</span><span className={a==null||isDate?"":a>0?"up":a<0?"down":""}>{isDate||a==null?"":(a>0?"+":"")+fmt(a)}</span></div>})}
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
                {payload?.latest && <p className="footnote">Última escena válida: {(payload.latest.datetime||payload.latest.from||"").slice(0,10)} · {payload.area_ha} ha · {payload.latest.pixels??"s/d"} píxeles · {payload.sensor}</p>}
                {(payload?.series||[]).slice().reverse().map((r:Data,i:number)=><div className="soil" key={i}><span>{(r.datetime||r.from||"").slice(0,10)}<small style={{display:"block"}}>{r.status}{r.clear_fraction_lot!=null?` · ${Math.round(r.clear_fraction_lot*100)} % despejado`:""}</small></span><strong>{r.status==="válida"?fmt(r.ndvi_mean,2):"—"}</strong></div>,2)}
                {view==="ndvi" && payload?.latest && <label className="small" style={{display:"block",marginTop:10}}><input type="checkbox" checked={showNdvi} onChange={e=>setShowNdvi(e.target.checked)}/> Ver NDVI sobre el mapa (recortado al lote)</label>}
                <p className="footnote">Escala: menos de 0,2 suelo desnudo o agua · 0,2–0,5 vegetación rala o pastura seca · más de 0,5 vegetación activa. No reemplaza la recorrida a campo.</p>
              </>}
              {view === "metnorway" && <><p className="footnote">MET Norway · conexión directa · pronóstico modelado. Actualizado: {payload?.properties?.meta?.updated_at || "Sin fecha"}</p>{Object.entries(payload?.properties?.timeseries?.[0]?.data?.instant?.details || {}).map(([key,value])=><div className="soil" key={key}><span style={{fontSize:10,maxWidth:"65%"}}>{key.replaceAll("_"," ")}</span><strong style={{fontSize:12}}>{fmt(value)} <small>{payload?.properties?.meta?.units?.[key]}</small></strong></div>)}<p className="footnote">Hora válida: {payload?.properties?.timeseries?.[0]?.time || "Sin fecha"}. Datos MET Norway, CC BY 4.0.</p></>}
              {view === "variables" && (
                <>
                  <div className="keygrid">
                    {[
                      ["Temperatura", "temperature_2m", "°C"],
                      ["Humedad", "relative_humidity_2m", "%"],
                      ["Viento 10 m", "wind_speed_10m", "km/h"],
                      ["Presión", "surface_pressure", "hPa"],
                    ].map(([label, key, unit]) => (
                      <div className="key" key={key}>
                        <span>{label}</span>
                        <strong>{fmt(cur[key])}</strong>
                        <em>{unit}</em>
                      </div>
                    ))}
                  </div>
                  <div className="soil">
                    <span>Suelo 0–1 cm</span>
                    <strong>
                      {fmt(
                        weather?.hourly?.soil_moisture_0_to_1cm?.[soilIndex],
                        3,
                      )}{" "}
                      <small>m³/m³</small>
                    </strong>
                  </div>
                  <details style={{ marginTop: 12 }}>
                    <summary className="small">
                      37 variables horarias · explorar valores
                    </summary>
                    <p className="footnote">
                      Hora: {weather?.hourly?.time?.[soilIndex] || "Sin fecha"}.
                      Unidades entregadas por la fuente. Valores nulos se
                      muestran como sin dato.
                    </p>
                    {Object.entries(weather?.hourly || {})
                      .filter(([key]) => key !== "time")
                      .map(([key, values]) => (
                        <div className="soil" key={key}>
                          <span
                            style={{
                              fontSize: 10,
                              overflowWrap: "anywhere",
                              maxWidth: "65%",
                            }}
                          >
                            {key.replaceAll("_", " ")}
                          </span>
                          <strong style={{ fontSize: 12 }}>
                            {fmt((values as any[])?.[soilIndex], 3)}{" "}
                            <small>{weather?.hourly_units?.[key]}</small>
                          </strong>
                        </div>
                      ))}
                  </details>
                  <p className="footnote">
                    Open-Meteo · {cur.time || "sin fecha"} ·{" "}
                    {weather?.timezone || "sin zona"}. Grilla:{" "}
                    {fmt(weather?.latitude, 4)} / {fmt(weather?.longitude, 4)}.
                    Condiciones modeladas.
                  </p>
                </>
              )}
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
              <button
                style={{ width: "100%", marginTop: 13 }}
                onClick={() => void load(view)}
              >
                Reintentar / Actualizar fuente
              </button>
            </div>
          </section>
          <section className="panel block">
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
          <section className="panel block lot-manager">
            <div className="section-title">LOTES DEL ESTABLECIMIENTO</div>
            <p className="footnote">Cada polígono conserva límites, superficie y contexto de análisis. Seleccioná un lote para consultar todas las fuentes sobre ese territorio.</p>
            <div className="lot-list">{lots.length===0?<span className="small">Todavía no hay lotes delimitados.</span>:lots.map(l=><button key={l.id} className={selectedLotId===l.id?"active":""} onClick={()=>{setSelectedLotId(l.id);setVertices(l.vertices);currentPoints.current=l.vertices;poly.current=lotLayers.current[l.id];setPoint(l.center);setCoords(l.center.map(v=>v.toFixed(6)));mapRef.current?.fitBounds(lotLayers.current[l.id].getBounds(),{padding:[40,40]})}}><strong>{l.name}</strong><span>{l.areaHa.toFixed(2)} ha</span></button>)}</div>
            {(()=>{const l=lots.find(x=>x.id===selectedLotId); if(!l) return null; const c=l.compactness; const nb=l.ftw?.neighborhood; return <div className="lot-vars">
              <div className="lot-vars-title">Variables del lote</div>
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
            {selectedLotId&&<button className="primary" style={{width:"100%",marginTop:10}} onClick={()=>void askDots("Analizá integralmente el lote seleccionado: clima, agua, suelo, vegetación, riesgos, ENSO y trazabilidad. No inventes variables faltantes.")}>{agentBusy?"Analizando fuentes…":"Analizar lote seleccionado"}</button>}
          </section>
          <section className="panel block operations">
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
            <p>{vertices.length} vértices. {drawMode==="rectangle"?"Marcá 2 esquinas opuestas o 4 vértices.":"Marcá al menos tres puntos."}</p>
            <div className="row">
              <button
                className="primary"
                disabled={drawMode==="rectangle" ? !(vertices.length===2||vertices.length===4) : vertices.length < 3}
                onClick={()=>finish()}
              >
                Finalizar
              </button>
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
            <div className="indice">
              {fmt(thi)} <small>índice</small>
            </div>
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
        <section className="charts">
          {view==="indices" && payload?.years ? <>
            <section className="panel chart"><h2>Lluvia anual y días de lluvia intensa</h2><p className="small">ERA5 · mm por año · días con 20 mm o más</p><Chart dates={payload.years.map((r:Data)=>String(r.year))} unit="mm" series={[{name:"Lluvia anual",values:payload.years.map((r:Data)=>r.prcptot),type:"bar",color:"#06b6d4"}]}/></section>
            <section className="panel chart"><h2>Heladas y calor extremo</h2><p className="small">Días por año · mínima menor a 0 °C · máxima de 35 °C o más</p><Chart dates={payload.years.map((r:Data)=>String(r.year))} unit="días" series={[{name:"Heladas",values:payload.years.map((r:Data)=>r.frost_days),color:"#93c5fd"},{name:"Máx ≥ 35 °C",values:payload.years.map((r:Data)=>r.tx35),color:"#fd9c91"},{name:"Racha seca",values:payload.years.map((r:Data)=>r.cdd),color:"#e9bd72"}]}/></section>
          </> : view==="teleconexiones" && payload?.indices ? <>
            {[["Pacífico ecuatorial · El Niño",["nino34","oni","meiv2"]],["Hemisferio sur y Atlántico",["aao","soi","tsa"]]].map(([title,keys]:any)=><section className="panel chart" key={title}><h2>{title}</h2><p className="small">NOAA PSL · últimos 12 meses publicados</p><Chart dates={(payload.indices[keys[0]]?.data?.last12||[]).map((r:Data)=>r.period)} unit="índice" series={keys.map((k:string,i:number)=>({name:payload.indices[k]?.data?.name||k,values:(payload.indices[k]?.data?.last12||[]).map((r:Data)=>r.value),color:["#06b6d4","#e9bd72","#a7a5ff"][i]}))}/></section>)}
          </> : NDVI_VIEWS.includes(view) ? <section className="panel chart"><h2>NDVI del lote · serie</h2><p className="small">{payload?.sensor||"Sentinel-2"} · media zonal dentro del polígono · escenas nubladas en el lote excluidas</p><Chart dates={(payload?.series||[]).filter((r:Data)=>r.status==="válida").map((r:Data)=>(r.datetime||r.from||"").slice(0,10))} unit="NDVI" series={[{name:"NDVI medio",values:(payload?.series||[]).filter((r:Data)=>r.status==="válida").map((r:Data)=>r.ndvi_mean??null),color:"#19b98a"}]}/></section> : view==="ina" ? <><section className="panel chart"><h2>{inaSeries==="37299"?"Temperatura observada":"Río Paraná · altura observada"}</h2><p className="small">INA · Bella Vista · serie {inaSeries} · fechas originales</p><Chart dates={(payload?.data||[]).map((r:Data)=>r.timestart)} unit={payload?.responseHeader?.seriesmetadata?.unit_abrev||"m"} series={[{name:"Altura",values:(payload?.data||[]).map((r:Data)=>r.valor??null),color:"#06b6d4"}]}/></section><section className="panel chart"><h2>Estación hidrométrica</h2><p className="footnote">Nivel del río medido en una estación; no describe inundación del lote. Para evaluar riesgo hacen falta relieve, umbrales y delimitación de la cuenca.</p></section></> : view==="aire" ? <>{["pm2_5","pm10"].map((k,i)=><section className="panel chart" key={k}><h2>{i===0?"Partículas PM2.5":"Partículas PM10"}</h2><p className="small">CAMS · pronóstico modelado · UTC</p><Chart dates={payload?.hourly?.time||[]} unit={payload?.hourly_units?.[k]||""} series={[{name:k,values:payload?.hourly?.[k]||[],color:i===0?"#06b6d4":"#b7c989"}]}/></section>)}</> : NATIONAL.includes(view) ? (
            <>
              {[(view==="eccc"?"TEMP":view==="nws"?"temperature":"air_temperature"), (view==="eccc"?"WIND_SPEED":view==="nws"?"windSpeed":"wind_speed")].map((variable,i)=>{
                const rows=(payload?.observations||[]).filter((o:Data)=>o.variable===variable).sort((a:Data,b:Data)=>String(a.observed_at).localeCompare(String(b.observed_at)));
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
                <div className="chart-legend">
                  <span>
                    <i />
                    Mínima
                  </span>
                  <span className="second">
                    <i />
                    Máxima
                  </span>
                </div>
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
                <div className="chart-legend">
                  <span>
                    <i />
                    Precipitación
                  </span>
                  <span className="et">
                    <i />
                    ET₀
                  </span>
                </div>
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
function PublicHeader({onDemo}:{onDemo:()=>void}){return <header className="site-header"><Brand/><nav><SiteLink to="/producto">Cómo funciona</SiteLink><SiteLink to="/modulos">Módulos</SiteLink><SiteLink to="/panel">Panel regional</SiteLink><SiteLink to="/tecnologia">Fuentes y datos</SiteLink><SiteLink to="/conexiones">APIs y accesos</SiteLink><button className="nav-demo" onClick={onDemo}>Demo</button></nav><div className="site-head-actions"><SiteLink to="/acceso" className="ghost-link">Ingresar</SiteLink><button className="demo-btn" onClick={onDemo}>Abrir Observatorio →</button></div></header>}
const sourceGroups=[
 ["ARGENTINA",["CONAE · SAOCOM","SMN","INA"]],
 ["EUROPA",["Copernicus · Sentinel","ECMWF · C3S","EUMETSAT","DLR · Alemania","CNES · Francia"]],
 ["AMÉRICAS",["NASA","NOAA","USGS · Landsat","INPE · Brasil","ECCC · Canadá"]],
 ["ASIA-PACÍFICO",["JAXA · Japón","ISRO · India","KMA · Corea","CMA · FengYun","BOM · Australia"]],
 ["GLOBAL",["IRI · Columbia","FAO · WaPOR","Digital Earth Africa","ISRIC · SoilGrids"]]
];
const tech=sourceGroups.flatMap(([,xs])=>xs);
function SourceStrip(){return <section className="source-strip"><span>FUENTES OFICIALES<br/>Y TRAZABLES</span>{["CONAE · SAOCOM","Copernicus · Sentinel","NASA · NOAA","USGS · Landsat","INPE · Brasil","JAXA · Japón","FengYun · China","IRI · Columbia","FAO · WaPOR"].map((x,i)=><b key={x} className={i===0?'arg-source':''}>{x}</b>)}</section>}
function Home({onDemo}:{onDemo:()=>void}){return <div className="public-site"><PublicHeader onDemo={onDemo}/><main>
 <section className="cover-hero"><img src="/dots-hero.jpg" alt="Satélite observando lotes de un campo ganadero con índice de vegetación"/><div className="cover-shade"></div><div className="cover-copy"><div className="cover-kicker">INTELIGENCIA TERRITORIAL PARA LA GESTIÓN GANADERA</div><h1>Conocé tu campo<br/><em>como nunca antes.</em></h1><p>Unificamos el lote real con observación satelital, clima, suelo, agua, pasturas, riesgos e historia. Cada dato conserva su fuente, fecha y alcance.</p><div className="cover-actions"><button onClick={onDemo}>Ver demostración →</button><SiteLink to="/producto">Cómo funciona DOTS</SiteLink></div><div className="truth-row"><span>DATOS REALES</span><span>POLÍGONOS REALES</span><span>FUENTES TRAZABLES</span></div></div></section>
 <SourceStrip/>
 <section className="home-intro editorial"><div><span className="section-tag">UN CAMPO · UNA LECTURA</span><h2>Del límite del potrero a la decisión.</h2></div><p>DOTS no reemplaza la recorrida ni el análisis profesional. Ordena información dispersa alrededor de una unidad territorial concreta y muestra qué fue observado, modelado, calculado o pronosticado.</p></section>
 <section className="journey"><article><b>01</b><h3>Delimitá</h3><p>Triángulo, rectángulo o polígono libre. Superficie, perímetro y centroide.</p></article><article><b>02</b><h3>Observá</h3><p>Escenas, clima, agua, suelo, vegetación y riesgos sobre el mismo territorio.</p></article><article><b>03</b><h3>Compará</h3><p>Fechas, modelos y fuentes sin perder procedencia ni calidad.</p></article><article><b>04</b><h3>Decidí</h3><p>Hallazgos, alertas, tareas e Informe Territorial DOTS unificado.</p></article></section>
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
    <PageHero eyebrow="PANEL REGIONAL" title="El clima de la zona, abierto a todos." lead="El Niño, heladas, calor y lluvia de los últimos diez años para las principales zonas ganaderas. Datos oficiales consultados en el momento."/>
    <div className="rp-tabs">{REGIONS.map(r=><button key={r[0]} className={r[0]===reg[0]?"active":""} onClick={()=>setReg(r)}>{r[1]}</button>)}</div>
    {err && <p className="rp-error">{err} No se muestran valores supuestos.</p>}
    <section className="rp-enso">
      <div><span className="section-tag">EL NIÑO · NOAA</span><h2>{tele?.enso_consensus?`Fase ${tele.enso_consensus}`:"Consultando…"}</h2><p>{tele?.enso_agreement?`${tele.enso_agreement} índices del Pacífico coinciden. Último dato: ${tele?.indices?.nino34?.data?.period||""}.`:"Niño 3.4, ONI y MEI v2."}</p></div>
      <div className="rp-telegrid">{Object.entries(tele?.indices||{}).filter(([,e]:any)=>e?.status==="recibido").slice(0,6).map(([k,e]:any)=><article key={k}><span>{e.data.name}</span><b>{fmt(e.data.value,2)}</b><em>{e.data.phase}</em></article>)}</div>
    </section>
    <section className="rp-cards">{card("Lluvia "+(last?.year||""),"prcptot","mm")}{card("Días con helada","frost_days","días")}{card("Días con máxima ≥ 35 °C","tx35","días")}{card("Racha seca más larga","cdd","días")}</section>
    {idx?.years && <section className="rp-charts">
      <div className="rp-chart"><h3>Lluvia anual · {idx.period?.[0]}–{idx.period?.[1]}</h3><Chart dates={idx.years.map((r:Data)=>String(r.year))} unit="mm" series={[{name:"Lluvia",values:idx.years.map((r:Data)=>r.prcptot),type:"bar",color:"#19b98a"}]}/></div>
      <div className="rp-chart"><h3>Heladas y calor extremo</h3><Chart dates={idx.years.map((r:Data)=>String(r.year))} unit="días" series={[{name:"Heladas",values:idx.years.map((r:Data)=>r.frost_days),color:"#93c5fd"},{name:"Máx ≥ 35 °C",values:idx.years.map((r:Data)=>r.tx35),color:"#fd9c91"}]}/></div>
    </section>}
    <p className="rp-note">ERA5 (Copernicus) vía Open-Meteo, grilla de ~25 km; índices con definiciones xclim/ETCCDI. Teleconexiones: NOAA PSL. Para un lote puntual, usá el Observatorio.</p>
    <section className="demo-call"><div><span className="section-tag">TU CAMPO</span><h2>Bajá del panel regional a tu potrero.</h2><p>En el Observatorio los mismos datos se calculan para el lote que dibujes, con NDVI y focos térmicos.</p></div><button onClick={onDemo}>Abrir Observatorio →</button></section>
  </main><SiteFooter/></div>;
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
function Contact({onDemo}:{onDemo:()=>void}){return <div className="public-site"><PublicHeader onDemo={onDemo}/><main className="inner"><PageHero eyebrow="CONTACTO" title="DOTS / Campo" lead="El canal comercial se habilitará cuando esté conectado a un destino real. No simulamos envíos."/><section className="contact-box"><div><h2>Inteligencia territorial para la gestión ganadera.</h2><p>Productores, técnicos, organizaciones y aliados tecnológicos.</p></div><div className="contact-form"><label>Nombre<input placeholder="Tu nombre"/></label><label>Correo<input type="email" placeholder="nombre@correo.com"/></label><label>Consulta<textarea placeholder="Contanos qué necesitás"></textarea></label><button type="button" disabled>Canal en preparación</button></div></section></main><SiteFooter/></div>}
function Access({onDemo}:{onDemo:()=>void}){return <div className="public-site"><PublicHeader onDemo={onDemo}/><main className="inner access-page"><PageHero eyebrow="ACCESO" title="Observatorio DOTS" lead="La autenticación real se incorporará con permisos por establecimiento. La demostración no simula una cuenta de usuario."/><button className="big-demo" onClick={onDemo}>Entrar a la demostración →</button></main><SiteFooter/></div>}
function SiteFooter(){return <footer className="site-footer"><Brand/><p>Inteligencia territorial para la gestión ganadera.</p><div><SiteLink to="/producto">Cómo funciona</SiteLink><SiteLink to="/tecnologia">Fuentes</SiteLink><SiteLink to="/conexiones">APIs</SiteLink><SiteLink to="/demo">Demo</SiteLink></div></footer>}

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
  if(path==="/modulos")return <Modules onDemo={openDemo}/>;
  if(path==="/panel")return <RegionalPanel onDemo={openDemo}/>;
  if(path==="/tecnologia")return <Technology onDemo={openDemo}/>;
  if(path==="/conexiones")return <ApiConnections onDemo={openDemo}/>;
  if(path==="/casos")return <Cases onDemo={openDemo}/>;
  if(path==="/precios")return <Pricing onDemo={openDemo}/>;
  if(path==="/blog")return <Blog onDemo={openDemo}/>;
  if(path==="/contacto")return <Contact onDemo={openDemo}/>;
  if(path==="/acceso")return <Access onDemo={openDemo}/>;
  return <Home onDemo={openDemo}/>;
}
createRoot(document.getElementById("root")!).render(<App />);
