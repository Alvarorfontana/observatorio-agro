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
  Layers,
  Download,
  FileText,
  Droplets,
  Thermometer,
  TriangleAlert,
  Focus,
  Plus,
  Minus,
} from "lucide-react";
import "./styles.css";
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
const RESEARCH = ["aire","elevacion","ina","usgs","nasa-catalogo","productos-nasa","landsat","radar","firms"];
const NATIONAL = ["smn", "inmet", "dmc", "eccc", "nws"];
const SOURCES = [
  ["aire","Aire · CAMS","Open-Meteo / Copernicus"],
  ["elevacion","Relieve del terreno","Open-Meteo / DEM"],
  ["ina","Río Paraná · Bella Vista","INA / estación elegida"],
  ["usgs","Agua · Estados Unidos","USGS / OGC"],
  ["nasa-catalogo","Productos MODIS","NASA / CMR catálogo"],
  ["productos-nasa","Inventario NASA","AppEEARS catálogo"],
  ["landsat","Escenas Landsat","Planetary Computer catálogo"],
  ["radar","Radar Sentinel-1","Copernicus catálogo"],
  ["firms","Incendios · FIRMS","NASA / requiere clave"],
  ["variables", "Clima y suelo", "Open-Meteo"],
  ["modelos", "Comparar modelos globales", "Open-Meteo / 7 proveedores"],
  ["escenas", "Escenas satelitales", "Earth Search / Sentinel-2"],
  ["historico", "Histórico reciente", "NASA POWER"],
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
    [waterType,setWaterType] = useState("bebedero");
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
    noticeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
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
  const changeView = (key: string) => {
    setView(key);
    if (!sources[key]) void load(key);
  };
  const startDraw = () => {
    poly.current?.remove();
    poly.current = null;
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
  const finish = () => {
    try {
      const points = currentPoints.current;
      if (
        crosses(points) ||
        new Set(points.map((p) => p.join(","))).size !== points.length
      )
        throw Error(
          "Hay lados cruzados o vértices repetidos. Cancelá y delimitá nuevamente.",
        );
      const center = centroid(points);
      poly.current = L.polygon(points, {
        color: "#57dce0",
        fillOpacity: 0.12,
        dashArray: "5,5",
      })
        .addTo(mapRef.current!)
        .bindTooltip("LOTE EN ANÁLISIS", {
          permanent: true,
          direction: "center",
        });
      stopDraw();
      setCoords(center.map((v) => v.toFixed(6)));
      setPoint(center);
    } catch (e) {
      notify((e as Error).message);
    }
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
        body: JSON.stringify({ lat: point[0], lon: point[1], prompt, polygon: poly.current ? vertices : null, inaSeries, waterAssets }),
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
  async function agentPdf() {
    setPdfBusy(true);
    try {
      const r = await fetch("/api/fuentes/agentic/pdf", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lat: point[0], lon: point[1], prompt: agentPrompt, polygon: poly.current ? vertices : null, inaSeries, waterAssets, nombre: "DOTS / Informe técnico del lote", analysis: agentResult }),
        signal: AbortSignal.timeout(60000),
      });
      if (!r.ok) throw Error("No se pudo generar el informe Agentic");
      const blob=await r.blob();
      if ((await blob.slice(0,5).text()) !== "%PDF-") throw Error("Respuesta PDF inválida");
      download(blob,"DOTS-informe-agentic.pdf");
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
          nombre: "DOTS / Informe puntual del lote",
          lat: point[0],
          lon: point[1],
        }),
        signal: AbortSignal.timeout(45000),
      });
      if (!r.ok) throw Error("El servidor no pudo generar el PDF");
      const blob = await r.blob();
      if ((await blob.slice(0, 5).text()) !== "%PDF-")
        throw Error("Respuesta PDF inválida");
      download(blob, "DOTS-informe.pdf");
      notify(
        "Informe PDF descargado. Incluye alcance, fuente y fechas de clima.",
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
    <div className="whole">
      <header className="panel">
        <div className="brand" onClick={onHome} style={{cursor:"pointer"}} title="Volver a DOTS">
          <div className="mark">
            <Satellite size={23} />
          </div>
          <div>
            <strong>
              DOTS<span style={{ color: "var(--cyan)" }}> / CAMPO</span>
            </strong>
            <small>OBSERVATORIO GANADERO · GIS OPERATIVO</small>
          </div>
        </div>
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
      <main className="app">
        <div id="map" ref={mapEl} />
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
              <div className="water-add"><select value={waterType} onChange={e=>setWaterType(e.target.value)}><option>bebedero</option><option>tajamar</option><option>represa</option><option>molino</option><option>perforación</option><option>tanque australiano</option><option>bomba</option><option>cañería</option><option>arroyo</option><option>canal</option></select><button type="button" onClick={()=>{const item={type:waterType,lat:point[0],lon:point[1],source:'declarado por usuario'};setWaterAssets(v=>[...v,item]);L.circleMarker(point,{radius:7,color:'#4bd6e5',fillOpacity:.85}).addTo(mapRef.current!).bindTooltip(waterType.toUpperCase(),{permanent:false});notify('Infraestructura registrada: '+waterType)}}>+ En punto actual</button></div>
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
            <details style={{marginTop:12}}><summary className="small">Agua, aire y nuevas misiones · 9 servicios</summary><div style={{marginTop:10}}>{SOURCES.filter(([key])=>RESEARCH.includes(key)).map(([key,label])=><button key={key} className={"data-button "+(view===key?"active":"")} onClick={()=>changeView(key)}>{label}<span>{sources[key]?.status.toUpperCase()||"CONSULTAR"}</span></button>)}</div></details>
            <a className="small" href="/CONEXIONES-INVESTIGACION.md" target="_blank" rel="noreferrer">Matriz de 20 servicios y activación</a>
            <div style={{ marginTop: 18 }}>
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
                {["nasa-catalogo","productos-nasa","landsat","radar"].includes(view) && <><p className="footnote">Catálogo y metadatos. Todavía no se extraen valores de NDVI, temperatura de superficie ni píxeles de radar.</p>{(payload?.features||payload?.feed?.entry||Object.values(payload||{})).slice(0,5).map((item:any,i:number)=><div className="soil" key={i}><span style={{overflowWrap:"anywhere"}}>{item?.id||item?.title||item?.long_name||item?.short_name||"Producto NASA"}<small style={{display:"block"}}>{item?.properties?.datetime||item?.time_start||"Metadatos de catálogo"}</small></span></div>)}</>}
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
          <section className="panel block operations">
            <div className="tag">OPERACIONES DEL LOTE</div>
            <div className="actions">
              <button onClick={startDraw}>
                <Layers className="icon" />
                Delimitar
              </button>
              <button
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
                Datos JSON
              </button>
              <button
                className="primary"
                onClick={() => void pdf()}
                disabled={pdfBusy}
              >
                <FileText className="icon" />
                {pdfBusy ? "Generando…" : "Informe de clima PDF"}
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
        <div className="panel toolbar">
          <button
            className={layer === "base" ? "active" : ""}
            onClick={() => setLayer("base")}
            aria-pressed={layer === "base"}
          >
            Mapa satelital
          </button>
          <button
            className={layer === "modis" ? "active" : ""}
            onClick={() => setLayer("modis")}
            aria-pressed={layer === "modis"}
          >
            NASA MODIS
          </button>
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
            ? "ESRI WORLD IMAGERY / FECHA DE CAPTURA VARIABLE"
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
        {drawing && (
          <div className="panel message show">
            <p>{vertices.length} vértices. Marcá al menos tres puntos.</p>
            <div className="row">
              <button
                className="primary"
                disabled={vertices.length < 3}
                onClick={finish}
              >
                Finalizar
              </button>
              <button onClick={stopDraw}>Cancelar</button>
            </div>
          </div>
        )}
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
              <p>
                Sin cálculo conectado. Se requieren bandas roja e infrarroja y
                máscara de nubes.
              </p>
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
          {view==="ina" ? <><section className="panel chart"><h2>{inaSeries==="37299"?"Temperatura observada":"Río Paraná · altura observada"}</h2><p className="small">INA · Bella Vista · serie {inaSeries} · fechas originales</p><Chart dates={(payload?.data||[]).map((r:Data)=>r.timestart)} unit={payload?.responseHeader?.seriesmetadata?.unit_abrev||"m"} series={[{name:"Altura",values:(payload?.data||[]).map((r:Data)=>r.valor??null),color:"#06b6d4"}]}/></section><section className="panel chart"><h2>Estación hidrométrica</h2><p className="footnote">Nivel del río medido en una estación; no describe inundación del lote. Para evaluar riesgo hacen falta relieve, umbrales y delimitación de la cuenca.</p></section></> : view==="aire" ? <>{["pm2_5","pm10"].map((k,i)=><section className="panel chart" key={k}><h2>{i===0?"Partículas PM2.5":"Partículas PM10"}</h2><p className="small">CAMS · pronóstico modelado · UTC</p><Chart dates={payload?.hourly?.time||[]} unit={payload?.hourly_units?.[k]||""} series={[{name:k,values:payload?.hourly?.[k]||[],color:i===0?"#06b6d4":"#b7c989"}]}/></section>)}</> : NATIONAL.includes(view) ? (
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
        <div className="map-bottom">
          WGS84 · {fmt(point[0], 5)} / {fmt(point[1], 5)} ·{" "}
          {poly.current
            ? "LÍMITE DELIMITADO POR EL USUARIO"
            : "SIN LÍMITES CATASTRALES"}
        </div>
      </main>
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
const navItems=[["/producto","Producto"],["/soluciones","Soluciones"],["/tecnologia","Tecnología"],["/ganaderia","Ganadería"],["/casos","Casos de uso"],["/precios","Precios"],["/blog","Blog"],["/contacto","Contacto"]];
function Brand(){return <SiteLink to="/" className="site-brand"><span className="site-mark"><Satellite size={22}/></span><span><b>DOTS</b><small>DATOS · OBSERVACIÓN · TERRITORIO · SATÉLITE</small></span></SiteLink>}
function PublicHeader({onDemo}:{onDemo:()=>void}){return <header className="site-header"><Brand/><nav>{navItems.map(([to,label])=><SiteLink key={to} to={to}>{label}</SiteLink>)}</nav><div className="site-head-actions"><SiteLink to="/acceso" className="ghost-link">Iniciar sesión</SiteLink><button className="demo-btn" onClick={onDemo}>Ver demostración →</button></div></header>}
const tech=["CONAE · SAOCOM","Copernicus · Sentinel","NASA","NOAA","ECMWF","SMN Argentina","INMET Brasil","JMA Japón","BOM Australia"];
function SourceStrip(){return <section className="source-strip"><span>TECNOLOGÍA ARGENTINA<br/>Y FUENTES GLOBALES</span>{tech.map((x,i)=><b key={x} className={i===0?'arg-source':''}>{x}</b>)}</section>}
function Home({onDemo}:{onDemo:()=>void}){return <div className="public-site"><PublicHeader onDemo={onDemo}/><main>
  <section className="cover-hero"><img src="/dots-portada.png" alt="Campo ganadero y tecnología satelital DOTS"/><div className="cover-shade"></div><div className="cover-copy"><div className="cover-kicker">TECNOLOGÍA SATELITAL ARGENTINA PARA LA GANADERÍA DEL FUTURO</div><h1>Más datos.<br/>Mejores decisiones.<br/><em>Campos más productivos.</em></h1><p>Integramos imágenes satelitales, clima, suelos, agua, pasturas y ganado para gestionar cada establecimiento con información trazable y útil.</p><div className="cover-actions"><button onClick={onDemo}>Ver demostración →</button><SiteLink to="/producto">Conocer DOTS</SiteLink></div></div></section>
  <section className="home-intro"><div><span className="section-tag">DOTS / CAMPO</span><h2>Un gemelo digital para entender el establecimiento completo.</h2></div><p>El lote deja de ser un punto en un mapa. DOTS lo relaciona con vegetación, humedad, agua, suelo, clima, ganado, infraestructura, riesgos e historia para transformar información dispersa en decisiones de manejo.</p></section>
  <section className="cap-grid">{[[MapPinned,"Lotes y potreros","Límites, superficie, evolución y comparación."],[Droplets,"Agua e infraestructura","Bebederos, tajamares, represas, molinos y cobertura."],[Layers,"Pasturas y suelos","NDVI, humedad, textura, carbono y nutrientes disponibles."],[Thermometer,"Clima y ganado","Pronósticos, THI, carga, rotación y bienestar."],[TriangleAlert,"Riesgos","Sequía, focos térmicos, exceso hídrico y alertas."],[FileText,"Informes DOTS","Diagnóstico, evidencia, recomendaciones y trazabilidad."]].map(([Icon,t,d]:any)=><article key={t}><Icon/><h3>{t}</h3><p>{d}</p></article>)}</section>
  <section className="demo-call"><div><span className="section-tag">DEMOSTRACIÓN INTERACTIVA</span><h2>Del satélite al potrero.</h2><p>Entrá al Observatorio, marcá un punto o delimitá un lote y consultá las fuentes disponibles desde una sola interfaz.</p></div><button onClick={onDemo}>Abrir Observatorio →</button></section>
  <SourceStrip/>
</main><SiteFooter/></div>}
function PageHero({eyebrow,title,lead}:{eyebrow:string;title:string;lead:string}){return <section className="page-hero"><span className="section-tag">{eyebrow}</span><h1>{title}</h1><p>{lead}</p></section>}
const cards={
 producto:[["01","Delimitá","Definí el establecimiento y sus potreros directamente sobre el mapa."],["02","Observá","Superponé satélite, clima, suelo, agua, vegetación y riesgo."],["03","Compará","Leé cambios temporales, fuentes y modelos sin perder trazabilidad."],["04","Decidí","DOTS resume hallazgos, límites, recomendaciones e informe técnico."]],
 soluciones:[["Lotes y potreros","Superficie, perímetro, centroides, historial y análisis por unidad de manejo."],["Pasturas","Sentinel-2, escenas, evolución e índices cuando exista procesamiento raster verificable."],["Agua","Lluvia, balance, ríos y futura gestión de bebederos, tajamares, represas y cañerías."],["Suelos","Humedad, temperatura, relieve y propiedades modeladas con fuente y profundidad declaradas."],["Ganado","THI, carga y rotación cuando el productor incorpora inventario y movimientos."],["Riesgos","FIRMS, sequía, calor, excesos hídricos y alertas con alcance explícito."]],
 ganaderia:[["Potrero como unidad","Cada análisis parte del lote real y su historia."],["Agua para el rodeo","Distancias, cobertura y estado de infraestructura hídrica."],["Pastura y carga","Cruce de condición forrajera con ocupación y presión de pastoreo."],["Bienestar térmico","THI y condiciones meteorológicas para anticipar estrés por calor."],["Rotación","Entrada, salida, descanso y recuperación de cada potrero."],["Tareas","Del diagnóstico a inspecciones, movimientos y acciones verificables."]]
};
function InfoPage({kind,onDemo}:{kind:"producto"|"soluciones"|"ganaderia";onDemo:()=>void}){const cfg:any={producto:["PRODUCTO","El campo, entendido como un sistema.","DOTS conecta territorio, observación satelital y fuentes ambientales para construir una lectura integral del establecimiento."],soluciones:["SOLUCIONES","Una plataforma para cada capa del campo.","Módulos especializados que se cruzan entre sí: el valor no está en una variable aislada, sino en la relación entre todas."],ganaderia:["GANADERÍA","Inteligencia territorial para manejar mejor el rodeo.","Pasturas, agua, clima, carga, rotación y riesgo reunidos alrededor del potrero, la unidad donde ocurre la decisión."]}[kind];return <div className="public-site"><PublicHeader onDemo={onDemo}/><main className="inner"><PageHero eyebrow={cfg[0]} title={cfg[1]} lead={cfg[2]}/><section className="info-grid">{cards[kind].map(([n,t,d])=><article key={t}><span>{n}</span><h2>{t}</h2><p>{d}</p></article>)}</section>{kind==="producto"&&<section className="product-shot"><img src="/evidencia/Preview.png" alt="Vista del Observatorio DOTS"/><div><span className="section-tag">OBSERVATORIO</span><h2>El mapa es el centro operativo.</h2><p>La plataforma actual ya combina mapa satelital, delimitación, fuentes de investigación, gráficos y exportación. La web pública explica el producto; el Observatorio concentra el trabajo técnico.</p><button onClick={onDemo}>Probar demostración</button></div></section>}<SourceStrip/></main><SiteFooter/></div>}
function Technology({onDemo}:{onDemo:()=>void}){return <div className="public-site"><PublicHeader onDemo={onDemo}/><main className="inner"><PageHero eyebrow="TECNOLOGÍA" title="Argentina primero. El mundo como respaldo." lead="DOTS integra fuentes nacionales e internacionales, conserva procedencia y fecha, y evita presentar como medición aquello que sólo es modelo, catálogo o inferencia."/><section className="tech-grid">{tech.map((t,i)=><article key={t}><span>{String(i+1).padStart(2,'0')}</span><h2>{t}</h2><p>{i===0?'Radar y observación argentina como capa estratégica para suelo y territorio.':'Fuente complementaria dentro de una arquitectura multifuente y auditable.'}</p></article>)}</section><section className="method-banner"><h2>OBSERVADO · MODELADO · CALCULADO · PRONOSTICADO</h2><p>Cada resultado debe indicar qué es, de dónde proviene, cuándo fue consultado y qué limitaciones tiene.</p></section></main><SiteFooter/></div>}
function Cases({onDemo}:{onDemo:()=>void}){return <div className="public-site"><PublicHeader onDemo={onDemo}/><main className="inner"><PageHero eyebrow="CASOS DE USO" title="Preguntas reales del campo." lead="DOTS está pensado para responder preguntas operativas, no para llenar una pantalla de indicadores."/><section className="case-list">{["¿Qué potrero perdió vigor y desde cuándo?","¿Dónde falta cobertura de agua para el rodeo?","¿La lluvia prevista compensa la evapotranspiración?","¿Hay riesgo térmico para el ganado esta semana?","¿Cómo cambió este lote frente al mismo período del año anterior?","¿Qué fuentes coinciden y cuáles divergen?"].map((x,i)=><article key={x}><b>0{i+1}</b><h2>{x}</h2><p>DOTS cruza las capas disponibles, explicita la calidad de evidencia y conserva los datos faltantes como faltantes.</p></article>)}</section></main><SiteFooter/></div>}
function Pricing({onDemo}:{onDemo:()=>void}){return <div className="public-site"><PublicHeader onDemo={onDemo}/><main className="inner"><PageHero eyebrow="PLANES" title="Una plataforma que puede crecer con el establecimiento." lead="La arquitectura comercial queda preparada sin simular todavía un cobro que no está conectado."/><section className="pricing-grid"><article><span>DEMO</span><h2>Explorar</h2><p>Recorrido del Observatorio y un establecimiento demostrativo.</p><b>Sin cargo</b><button onClick={onDemo}>Ver demo</button></article><article className="featured"><span>PRODUCTOR</span><h2>Gestión de campo</h2><p>Lotes, fuentes, históricos, alertas, informes y gestión territorial.</p><b>Próximamente</b><SiteLink to="/contacto">Solicitar información</SiteLink></article><article><span>PROFESIONAL</span><h2>Multiestablecimiento</h2><p>Más campos, comparación, equipos técnicos y reportes avanzados.</p><b>Próximamente</b><SiteLink to="/contacto">Contactar</SiteLink></article></section></main><SiteFooter/></div>}
function Blog({onDemo}:{onDemo:()=>void}){return <div className="public-site"><PublicHeader onDemo={onDemo}/><main className="inner"><PageHero eyebrow="CUADERNO DOTS" title="Territorio, satélites y ganadería explicados con claridad." lead="Espacio editorial para metodología, fuentes, casos, nuevas capas y lectura del contexto agroclimático."/><section className="blog-grid">{[["SATÉLITES","Qué puede observar Sentinel-2 y qué no"],["ARGENTINA","SAOCOM y el valor del radar para el territorio"],["GANADERÍA","THI: cómo leer el estrés térmico sin simplificarlo"],["AGUA","Del milímetro de lluvia a la disponibilidad real"],["SUELOS","Por qué nitrógeno modelado no es análisis de laboratorio"],["METODOLOGÍA","Cómo DOTS diferencia dato, cálculo e interpretación"]].map(([k,t])=><article key={t}><span>{k}</span><h2>{t}</h2><p>Próxima publicación del Cuaderno DOTS.</p></article>)}</section></main><SiteFooter/></div>}
function Contact({onDemo}:{onDemo:()=>void}){return <div className="public-site"><PublicHeader onDemo={onDemo}/><main className="inner"><PageHero eyebrow="CONTACTO" title="Conversemos sobre tu campo o tu proyecto." lead="La versión pública puede recibir consultas de productores, técnicos, organizaciones y potenciales aliados tecnológicos."/><section className="contact-box"><div><h2>DOTS / Campo</h2><p>Inteligencia territorial para la gestión ganadera.</p><p className="muted">El formulario y el correo definitivo se conectarán cuando definamos el canal público del proyecto.</p></div><div className="contact-form"><label>Nombre<input placeholder="Tu nombre"/></label><label>Correo<input type="email" placeholder="nombre@correo.com"/></label><label>Consulta<textarea placeholder="Contanos qué necesitás"></textarea></label><button type="button">Preparar consulta</button></div></section></main><SiteFooter/></div>}
function Access({onDemo}:{onDemo:()=>void}){return <div className="public-site"><PublicHeader onDemo={onDemo}/><main className="inner access-page"><PageHero eyebrow="ACCESO" title="Observatorio DOTS" lead="La autenticación real se incorporará junto con los planes y permisos por establecimiento. Mientras tanto, podés entrar a la demostración."/><button className="big-demo" onClick={onDemo}>Entrar a la demostración →</button></main><SiteFooter/></div>}
function SiteFooter(){return <footer className="site-footer"><Brand/><p>Inteligencia territorial para la gestión ganadera.</p><div><SiteLink to="/tecnologia">Tecnología</SiteLink><SiteLink to="/producto">Producto</SiteLink><SiteLink to="/contacto">Contacto</SiteLink></div></footer>}
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
  if(path==="/tecnologia")return <Technology onDemo={openDemo}/>;
  if(path==="/casos")return <Cases onDemo={openDemo}/>;
  if(path==="/precios")return <Pricing onDemo={openDemo}/>;
  if(path==="/blog")return <Blog onDemo={openDemo}/>;
  if(path==="/contacto")return <Contact onDemo={openDemo}/>;
  if(path==="/acceso")return <Access onDemo={openDemo}/>;
  return <Home onDemo={openDemo}/>;
}
createRoot(document.getElementById("root")!).render(<App />);
