/**
 * El Niño visto por satélite: clorofila del Pacífico (MODIS), humedad del suelo (SMAP) y lluvia (GPM IMERG).
 * Lee /api/fuentes/enso-satelites, que publica la tarea mensual «El Niño por satélite» (Earth Engine).
 * Cada serie es la diferencia mensual con el promedio del mismo mes en el período de referencia del producto.
 */
import { useEffect, useMemo, useState } from "react";

type Fila = [string, number, number | null, number | null];
type Region = { id: string; nombre: string; serie: Fila[]; ultimo: { mes: string; valor: number; normal: number | null; anomalia: number | null } | null };
type Capa = { banda: string; regiones: Region[] };
type Variable = { id: string; titulo: string; unidad?: string; modo?: "pct" | "dif"; fuente?: string; lectura?: string;
  referencia?: string; periodo?: [string, string] | null; capas?: Capa[]; error?: string };
type Datos = { generado: string; variables: Variable[] };

const BANDAS: Record<string, string> = { sm_surface: "Superficie · 0-5 cm", sm_rootzone: "Zona de raíces · 0-100 cm" };
// Períodos de El Niño según el ONI oficial de NOAA (trimestres con +0,5 °C o más)
const NINOS: [string, string, string][] = [["2009-07", "2010-03", "2009-10"], ["2015-03", "2016-05", "2015-16"], ["2023-05", "2024-04", "2023-24"]];
const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
const mesLargo = (k: string) => `${MESES[Number(k.slice(5, 7)) - 1]} de ${k.slice(0, 4)}`;
const num = (v: number, d = 1) => v.toLocaleString("es-AR", { minimumFractionDigits: d, maximumFractionDigits: d });

function anomTexto(v: Variable, a: number | null | undefined) {
  if (a == null) return "sin referencia";
  return v.modo === "pct" ? `${a > 0 ? "+" : ""}${num(a, 0)} %` : `${a > 0 ? "+" : ""}${num(a, 3)} ${v.unidad}`;
}
function tono(v: Variable, a: number | null | undefined) {
  if (a == null) return "#667085";
  const fuerte = v.modo === "pct" ? Math.abs(a) >= 25 : Math.abs(a) >= 0.04;
  const leve = v.modo === "pct" ? Math.abs(a) >= 10 : Math.abs(a) >= 0.015;
  if (!leve) return "#667085";
  const humedo = v.id === "clorofila" ? a < 0 : a > 0;          // menos clorofila = señal de El Niño
  return humedo ? (fuerte ? "#01665e" : "#4fa9a0") : (fuerte ? "#8c510a" : "#d8a35a");
}

function Grafico({ v, r }: { v: Variable; r: Region }) {
  const pts = r.serie.filter(f => f[3] != null) as [string, number, number, number][];
  if (pts.length < 6) return <p className="small">Todavía no hay suficientes meses con referencia para graficar.</p>;
  const W = 760, H = 220, L = 46, R = 10, T = 12, B = 26;
  const xs = pts.map(p => p[0]);
  const ext = Math.max(...pts.map(p => Math.abs(p[3])), v.modo === "pct" ? 20 : 0.02);
  const x = (i: number) => L + (i / (pts.length - 1)) * (W - L - R);
  const y = (a: number) => T + (1 - (a + ext) / (2 * ext)) * (H - T - B);
  const idx = (mes: string) => { const i = xs.findIndex(k => k >= mes); return i < 0 ? xs.length - 1 : i; };
  const path = pts.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p[3]).toFixed(1)}`).join("");
  const anios = xs.map((k, i) => [k, i] as const).filter(([k]) => k.endsWith("-01") && Number(k.slice(0, 4)) % (pts.length > 150 ? 5 : 2) === 0);
  const ticks = [-ext, -ext / 2, 0, ext / 2, ext];
  const u = pts[pts.length - 1];
  return <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${v.titulo} · ${r.nombre}: diferencia mensual con lo normal`} style={{ width: "100%", height: "auto", display: "block" }}>
    {NINOS.map(([a, b, n]) => xs[0] <= b && xs[xs.length - 1] >= a ? <g key={n}>
      <rect x={x(idx(a))} y={T} width={Math.max(2, x(idx(b)) - x(idx(a)))} height={H - T - B} fill="#c8102e" opacity={0.07} />
      <text x={x(idx(a)) + 3} y={T + 11} fontSize={10} fill="#a5001e">El Niño {n}</text></g> : null)}
    {ticks.map(t => <g key={t}><line x1={L} x2={W - R} y1={y(t)} y2={y(t)} stroke={t === 0 ? "#98a2b3" : "#eaecf0"} />
      <text x={L - 6} y={y(t) + 3} fontSize={10} textAnchor="end" fill="#667085">{v.modo === "pct" ? `${t > 0 ? "+" : ""}${num(t, 0)}%` : num(t, 2)}</text></g>)}
    {anios.map(([k, i]) => <text key={k} x={x(i)} y={H - 8} fontSize={10} textAnchor="middle" fill="#667085">{k.slice(0, 4)}</text>)}
    <path d={path} fill="none" stroke="#344054" strokeWidth={1.2} />
    <circle cx={x(pts.length - 1)} cy={y(u[3])} r={4} fill={tono(v, u[3])} />
  </svg>;
}

function Tarjeta({ v }: { v: Variable }) {
  const capas = v.capas || [];
  const [banda, setBanda] = useState(capas[0]?.banda || "");
  const capa = capas.find(c => c.banda === banda) || capas[0];
  const [reg, setReg] = useState(capa?.regiones[0]?.id || "");
  const r = capa?.regiones.find(x => x.id === reg) || capa?.regiones[0];
  if (v.error || !capa || !r) return <article className="nino-local" style={{ marginBottom: 16 }}>
    <h3 style={{ margin: "0 0 6px" }}>{v.titulo}</h3><p className="small">Sin dato por ahora{v.error ? `: ${v.error.slice(0, 160)}` : "."}</p></article>;
  const u = r.ultimo;
  return <article className="nino-local" style={{ marginBottom: 16 }}>
    <div style={{ display: "flex", flexWrap: "wrap", gap: "8px 18px", alignItems: "baseline", justifyContent: "space-between" }}>
      <h3 style={{ margin: 0 }}>{v.titulo}</h3>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        {capas.length > 1 && <label className="small">Capa<select value={capa.banda} onChange={e => setBanda(e.target.value)}>
          {capas.map(c => <option key={c.banda} value={c.banda}>{BANDAS[c.banda] || c.banda}</option>)}</select></label>}
        <label className="small">Región<select value={r.id} onChange={e => setReg(e.target.value)}>
          {capa.regiones.map(x => <option key={x.id} value={x.id}>{x.nombre}</option>)}</select></label>
      </div>
    </div>
    {u && <p style={{ margin: "10px 0 4px", fontSize: 15 }}>
      <b style={{ color: tono(v, u.anomalia), fontSize: 22 }}>{anomTexto(v, u.anomalia)}</b>{" "}
      respecto de lo normal en {mesLargo(u.mes)} · {num(u.valor, v.unidad === "mm" ? 0 : v.unidad === "mg/m³" ? 2 : 3)} {v.unidad}
      {u.normal != null && <span className="small"> (lo normal: {num(u.normal, v.unidad === "mm" ? 0 : v.unidad === "mg/m³" ? 2 : 3)})</span>}
    </p>}
    <Grafico v={v} r={r} />
    <p className="small" style={{ margin: "6px 0 0" }}>{v.lectura}</p>
    <p className="footnote" style={{ margin: "4px 0 0" }}>{v.fuente} vía Google Earth Engine. Referencia: promedio de cada mes en {v.referencia}.
      {v.id === "lluvia" && " El producto mensual definitivo sale con unos tres meses de demora."}</p>
  </article>;
}

export function NinoSatelites() {
  const [d, setD] = useState<Datos | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    const ctrl = new AbortController();
    fetch("/api/fuentes/enso-satelites", { signal: ctrl.signal }).then(r => r.json())
      .then(j => { if (j.data) setD(j.data); else setErr(j.error || "Sin datos todavía."); })
      .catch(e => { if (e.name !== "AbortError") setErr("No se pudo consultar."); });
    return () => ctrl.abort();
  }, []);
  const vars = useMemo(() => d?.variables || [], [d]);
  return <section style={{ maxWidth: 1200, margin: "0 auto 30px" }}>
    <p className="small" style={{ padding: "0 4px" }}>Tres satélites de la NASA miran lo que El Niño hace en el mar y en el suelo: la clorofila del Pacífico
      (cuánta vida hay en el agua), la humedad del suelo y la lluvia. Cada curva es la diferencia de cada mes con lo normal para ese mes; las franjas rojas
      son los El Niño anteriores. Rangos: dentro de ±10 % (o ±0,015 m³/m³ de humedad) es normal; más de ±25 % (o ±0,04) es un desvío fuerte.</p>
    {!d && <p className="small">{err || "Cargando las series satelitales…"}</p>}
    {vars.map(v => <Tarjeta key={v.id} v={v} />)}
    {d && <p className="footnote" style={{ padding: "0 4px" }}>Calculado el {new Date(d.generado).toLocaleDateString("es-AR")}. Las regiones del continente son provincias, estados o países completos (FAO GAUL).</p>}
  </section>;
}
