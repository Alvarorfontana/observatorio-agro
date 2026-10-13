/**
 * DOTS · Historia de vigor de 2 años (MODIS) y zonificación del lote por vigor (Sentinel-2), en el Observatorio.
 * Portado de AgroClima v3 y corregido: AgroClima leía el NDVI convirtiendo colores de una imagen de un solo píxel;
 * acá se usan los valores numéricos de MODIS (NASA ORNL DAAC) y la estadística real de Sentinel-2 dentro del lote.
 */
import { useEffect, useRef, useState } from "react";
import * as echarts from "echarts/core";
import L from "leaflet";

type Data = Record<string, any>;
type Point = [number, number];
const nf = (v: unknown, d = 0) => v == null || !Number.isFinite(Number(v)) ? "—" : Number(v).toLocaleString("es-AR", { minimumFractionDigits: d, maximumFractionDigits: d });

export function NdviExtra({ point, vertices, map }: { point: Point; vertices: Point[]; map: L.Map | null }) {
  const qs = (extra: Record<string, string>) => new URLSearchParams({ lat: String(point[0]), lon: String(point[1]), polygon: JSON.stringify(vertices), ...extra }).toString();
  const key = JSON.stringify(vertices);
  // ── historia de 2 años
  const [hist, setHist] = useState<Data | null>(null), [hBusy, setHBusy] = useState(false), [hErr, setHErr] = useState("");
  const chartRef = useRef<HTMLDivElement | null>(null);
  const cargarHist = async () => {
    setHBusy(true); setHErr("");
    try { const j = await (await fetch("/api/fuentes/ndvi-modis?" + qs({ days: "730" }), { signal: AbortSignal.timeout(58000) })).json(); j.status === "recibido" ? setHist(j.data) : setHErr(j.error || "Sin dato"); }
    catch { setHErr("MODIS no respondió. Probá de nuevo."); }
    setHBusy(false);
  };
  useEffect(() => { setHist(null); setZon(null); }, [key]);
  useEffect(() => {
    if (!hist || !chartRef.current) return;
    const rows = (hist.series || []).filter((r: Data) => r.status === "válida");
    const hoy = new Date(), corte = new Date(hoy.getTime() - 365 * 864e5).toISOString().slice(0, 10);
    const este = rows.filter((r: Data) => r.datetime.slice(0, 10) >= corte).map((r: Data) => [r.datetime.slice(0, 10), r.ndvi_mean]);
    const ant = rows.filter((r: Data) => r.datetime.slice(0, 10) < corte).map((r: Data) => { const d = new Date(Date.parse(r.datetime) + 365 * 864e5).toISOString().slice(0, 10); return [d, r.ndvi_mean]; });
    const ch = echarts.init(chartRef.current);
    ch.setOption({ grid: { left: 40, right: 12, top: 30, bottom: 28 }, tooltip: { trigger: "axis" }, legend: { top: 0, textStyle: { color: "#c9d6d9", fontSize: 11 } },
      xAxis: { type: "time", axisLabel: { color: "#9fb2b6", fontSize: 10 } }, yAxis: { type: "value", min: 0, max: 1, axisLabel: { color: "#9fb2b6" }, splitLine: { lineStyle: { color: "rgba(255,255,255,.08)" } } },
      series: [{ name: "Últimos 12 meses", type: "line", data: este, symbolSize: 5, lineStyle: { color: "#43d6c5", width: 2 }, itemStyle: { color: "#43d6c5" } },
               { name: "Año anterior (mismas fechas)", type: "line", data: ant, symbolSize: 4, lineStyle: { color: "#9fb2b6", type: "dashed" }, itemStyle: { color: "#9fb2b6" } }] });
    const ro = new ResizeObserver(() => ch.resize()); ro.observe(chartRef.current);
    return () => { ro.disconnect(); ch.dispose(); };
  }, [hist]);
  const resumen = (() => {
    if (!hist) return null;
    const rows = (hist.series || []).filter((r: Data) => r.status === "válida");
    if (!rows.length) return null;
    const ult = rows[rows.length - 1], f = Date.parse(ult.datetime) - 365 * 864e5;
    const prev = rows.reduce((b: Data | null, r: Data) => !b || Math.abs(Date.parse(r.datetime) - f) < Math.abs(Date.parse(b.datetime) - f) ? r : b, null);
    const mx = rows.reduce((a: Data, r: Data) => r.ndvi_mean > a.ndvi_mean ? r : a, rows[0]), mn = rows.reduce((a: Data, r: Data) => r.ndvi_mean < a.ndvi_mean ? r : a, rows[0]);
    const dif = prev && Math.abs(Date.parse(prev.datetime) - f) < 20 * 864e5 ? ult.ndvi_mean - prev.ndvi_mean : null;
    return { ult, mx, mn, dif };
  })();

  // ── zonificación
  const [zon, setZon] = useState<Data | null>(null), [zBusy, setZBusy] = useState(false), [zErr, setZErr] = useState("");
  const [dosis, setDosis] = useState<number[]>([100, 100, 100]);
  const overlay = useRef<L.ImageOverlay | null>(null);
  const cargarZonas = async () => {
    setZBusy(true); setZErr("");
    try { const j = await (await fetch("/api/fuentes/ndvi-zonas?" + qs({}), { signal: AbortSignal.timeout(58000) })).json(); j.status === "recibido" ? setZon(j.data) : setZErr(j.error || "Sin dato"); }
    catch { setZErr("Sentinel-2 no respondió. Probá de nuevo."); }
    setZBusy(false);
  };
  useEffect(() => {
    overlay.current?.remove(); overlay.current = null;
    if (!zon || !map) return;
    const lats = vertices.map(v => v[0]), lons = vertices.map(v => v[1]);
    const url = "/api/fuentes/ndvi-zonas-imagen?" + qs({ item: zon.item, cuts: zon.cuts.join(","), baseline: String(zon.processing_baseline || "") });
    overlay.current = L.imageOverlay(url, [[Math.min(...lats), Math.min(...lons)], [Math.max(...lats), Math.max(...lons)]], { opacity: 0.85, interactive: false }).addTo(map);
    return () => { overlay.current?.remove(); overlay.current = null; };
  }, [zon, map]);
  const totalN = zon ? zon.zones.reduce((s: number, z: Data, i: number) => s + z.ha * (dosis[i] || 0), 0) : 0;

  return <div className="ndvi-extra">
    <h4>Historia de vigor · 2 años</h4>
    {!hist && <button onClick={() => void cargarHist()} disabled={hBusy}>{hBusy ? "Consultando MODIS (≈ 30 s)…" : "Ver los últimos 2 años (MODIS)"}</button>}
    {hErr && <p className="error">{hErr}</p>}
    {hist && <>
      <div ref={chartRef} style={{ width: "100%", height: 220 }} />
      {resumen && <p className="footnote">Última lectura {resumen.ult.datetime.slice(0, 10)}: NDVI {nf(resumen.ult.ndvi_mean, 2)}{resumen.dif != null ? `, ${resumen.dif >= 0 ? "+" : ""}${nf(resumen.dif, 2)} contra la misma fecha del año anterior` : ""}. Máximo de los 2 años {nf(resumen.mx.ndvi_mean, 2)} ({resumen.mx.datetime.slice(0, 10)}), mínimo {nf(resumen.mn.ndvi_mean, 2)} ({resumen.mn.datetime.slice(0, 10)}).</p>}
      <p className="footnote">MODIS Terra MOD13Q1 (NASA ORNL DAAC): compuestos de 16 días a 250 m, {hist.interpretation_scope?.replace("Respaldo: ", "")} Los huecos son nubes.</p>
    </>}

    <h4 style={{ marginTop: 16 }}>Zonas de vigor del lote</h4>
    {!zon && <button onClick={() => void cargarZonas()} disabled={zBusy}>{zBusy ? "Buscando la última escena despejada…" : "Zonificar con Sentinel-2 (10 m)"}</button>}
    {zErr && <p className="error">{zErr}</p>}
    {zon && <>
      <div className="zone-rows">{zon.zones.map((z: Data, i: number) => <div key={z.zone} className="zone-row">
        <i style={{ background: z.color }} /><span><b>{z.name}</b><small>NDVI {z.from == null ? `menos de ${nf(z.to, 2)}` : z.to == null ? `más de ${nf(z.from, 2)}` : `${nf(z.from, 2)} a ${nf(z.to, 2)}`}</small></span>
        <span>{nf(z.ha, 1)} ha<small>{nf(z.pct, 0)} %</small></span>
        <label>Dosis <input type="number" value={dosis[i]} onChange={e => setDosis(d => d.map((x, j) => j === i ? parseFloat(e.target.value) || 0 : x))} /> kg/ha</label>
      </div>)}</div>
      <p className="footnote">Total del producto con estas dosis: {nf(totalN)} kg para {nf(zon.area_ha, 1)} ha. Escena del {String(zon.datetime).slice(0, 10)}, {nf(zon.clear_fraction_lot * 100)} % del lote despejado. Las zonas salen de agrupar el NDVI del lote en tres niveles (k-medias). <b>Antes de variar la dosis, recorré cada zona</b>: el vigor bajo puede venir de falta de nitrógeno, pero también de anegamiento, malezas o suelo, y cada causa pide otro manejo.</p>
    </>}
  </div>;
}
