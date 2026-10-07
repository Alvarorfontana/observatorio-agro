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
function App() {
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
    [agentResult, setAgentResult] = useState<Data | null>(null);
  const mapEl = useRef<HTMLDivElement>(null),
    mapRef = useRef<L.Map | null>(null),
    marker = useRef<L.CircleMarker | null>(null),
    poly = useRef<L.Polygon | null>(null),
    line = useRef<L.Polyline | null>(null),
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
      currentPoints.current = [
        ...currentPoints.current,
        [e.latlng.lat, e.latlng.lng],
      ];
      setVertices(currentPoints.current);
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
  async function askDots(prompt = agentPrompt) {
    setAgentBusy(true);
    setAgentResult(null);
    try {
      const r = await fetch("/api/fuentes/agentic", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lat: point[0], lon: point[1], prompt, polygon: poly.current ? vertices : null, inaSeries }),
        signal: AbortSignal.timeout(60000),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw Error(data.error || "DOTS Agentic no respondió");
      setAgentResult(data);
      setAgentPrompt(prompt);
      notify("Análisis Agentic completado con trazabilidad de fuentes.");
    } catch (e) { notify((e as Error).message); } finally { setAgentBusy(false); }
  }
  async function agentPdf() {
    setPdfBusy(true);
    try {
      const r = await fetch("/api/fuentes/agentic/pdf", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lat: point[0], lon: point[1], prompt: agentPrompt, polygon: poly.current ? vertices : null, inaSeries, nombre: "DOTS / Informe inteligente del lote" }),
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
        <div className="brand">
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
            {point[0] === -28.507
              ? "BELLA VISTA / CORRIENTES"
              : "LOTE / PUNTO SELECCIONADO"}
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
            <p className="small location">
              Zona rural de Bella Vista, Corrientes. Consultá el punto o
              delimitá el lote.
            </p>
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
              {poly.current
                ? vertices.length + " vértices / centroide aproximado"
                : "Sin lote delimitado"}
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
            {agentResult && <div className="agent-result">
              <div className="confidence"><strong>{agentResult.confidence?.score}/100</strong><span>CONFIANZA {String(agentResult.confidence?.label||"").toUpperCase()}</span></div>
              <p>{agentResult.summary}</p>
              {(agentResult.findings||[]).map((x:Data,i:number)=><div className="agent-finding" key={i}><b>{x.topic}</b><span>{x.text}</span></div>)}
              <h3>Recomendaciones</h3>
              {(agentResult.recommendations||[]).map((x:string,i:number)=><p className="small" key={i}>• {x}</p>)}
              {!!agentResult.warnings?.length && <details><summary className="warning">Límites y advertencias ({agentResult.warnings.length})</summary>{agentResult.warnings.map((x:string,i:number)=><p className="footnote" key={i}>• {x}</p>)}</details>}
              <details><summary className="small">Ver evidencia y fuentes</summary>{(agentResult.evidence||[]).map((e:Data,i:number)=><div className="evidence-row" key={i}><b>{e.source}</b><span>{e.status}</span><small>{e.consulted_at?.slice(0,19)||"sin fecha"}</small></div>)}</details>
              <button className="primary" onClick={()=>void agentPdf()} disabled={pdfBusy}><FileText className="icon" />{pdfBusy?"Generando…":"Generar PDF inteligente"}</button>
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
      {toast && (
        <div className="toast show" role="status" aria-live="polite">
          {toast}
        </div>
      )}
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
