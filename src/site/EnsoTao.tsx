/**
 * El Niño bajo el mar: corte del Pacífico ecuatorial (0 a 300 m) con las boyas TAO/TRITON de NOAA PMEL.
 * Colores: anomalía de temperatura frente al promedio 1993–2020; líneas: isoterma de 20 °C ahora y normal.
 * Datos de /api/enso/tao (tarea «El Niño: boyas TAO»).
 */
import React, { useEffect, useMemo, useState } from "react";

type Pt = { prof: number; temp: number; anom: number | null };
type Buoy = { longitud: number; lon: number; nombre: string; desde: string; hasta: string; perfil: Pt[]; isoterma20_m: number | null; isoterma20_normal_m: number | null };
type Data = { actualizado?: string; fuente?: string; url?: string; normal?: string; nota?: string; boyas?: Buoy[];
  resumen?: { anom_este_0_150m: number | null; anom_oeste_80_200m: number | null; ultimo_dato: string }; error?: string };

const W = 760, H = 330, L = 46, R = 14, T = 14, B = 40, MAXD = 300;
let LON0 = 130, LON1 = 270;
const x = (lon360: number) => L + (lon360 - LON0) / (LON1 - LON0) * (W - L - R);
const y = (d: number) => T + Math.min(d, MAXD) / MAXD * (H - T - B);
const num = (v: number, d = 1) => new Intl.NumberFormat("es-AR", { maximumFractionDigits: d, minimumFractionDigits: d }).format(v);
const fmt = (v: number | null | undefined, d = 1) => v == null ? "—" : (v > 0 ? "+" : "") + new Intl.NumberFormat("es-AR", { maximumFractionDigits: d, minimumFractionDigits: d }).format(v);
const STEPS: [number, string][] = [[-4, "#5e2a84"], [-3, "#2c3e94"], [-2, "#3d6fc4"], [-1, "#8fb7e3"], [-0.5, "#d6e6f5"], [0.5, "#f6f6f2"], [1, "#fbd9b3"], [2, "#f7a35c"], [3, "#e8603c"], [4, "#c0392b"], [99, "#7a1f1a"]];
const color = (a: number | null) => a == null ? "#e9edef" : (STEPS.find(([hi]) => a < hi) || STEPS[STEPS.length - 1])[1];

function at(p: Pt[], d: number): number | null {
  const pts = p.filter(q => q.anom != null).sort((a, b) => a.prof - b.prof);
  if (!pts.length || d < pts[0].prof - 15 || d > pts[pts.length - 1].prof + 40) return null;
  if (d <= pts[0].prof) return pts[0].anom;
  for (let i = 1; i < pts.length; i++) if (d <= pts[i].prof) {
    const a = pts[i - 1], b = pts[i]; return a.anom! + (b.anom! - a.anom!) * (d - a.prof) / (b.prof - a.prof);
  }
  return pts[pts.length - 1].anom;
}

function reading(d: Data) {
  const r = d.resumen; if (!r) return "";
  const out: string[] = [];
  if (r.anom_este_0_150m != null) out.push(r.anom_este_0_150m >= 1 ? `En el Pacífico este, de 0 a 150 m, el agua está ${fmt(r.anom_este_0_150m)} °C más caliente que lo normal: es el calor de El Niño acumulado frente a Sudamérica.` : r.anom_este_0_150m <= -1 ? `En el Pacífico este el agua está ${num(-r.anom_este_0_150m)} °C más fría que lo normal, típico de La Niña.` : "En el Pacífico este, la temperatura bajo la superficie está cerca de lo normal.");
  if (r.anom_oeste_80_200m != null && r.anom_oeste_80_200m <= -1) out.push(`En el oeste, entre 80 y 200 m, ya hay agua ${num(-r.anom_oeste_80_200m)} °C más fría que lo normal. Si esa agua fría avanza hacia el este por debajo, anuncia que El Niño empezará a debilitarse en los próximos meses.`);
  return out.join(" ");
}

export function EnsoTao() {
  const [d, setD] = useState<Data | null>(null);
  useEffect(() => { let live = true; fetch("/api/enso/tao").then(r => r.json()).then(j => live && setD(j)).catch(() => live && setD({ error: "No se pudo consultar las boyas." })); return () => { live = false; }; }, []);
  const buoys = useMemo(() => (d?.boyas || []).filter(b => b.longitud >= 130 && b.longitud <= 270).sort((a, b) => a.longitud - b.longitud), [d]);
  if (buoys.length) { LON0 = buoys[0].longitud - 7; LON1 = buoys[buoys.length - 1].longitud + 7; }
  if (!d) return null;
  if (!buoys.length) return <section className="enso-tao"><span className="section-tag">BAJO EL MAR</span><h2>El Pacífico por dentro</h2><p>{d.error || "Sin datos de las boyas por ahora."}</p></section>;
  const edges = buoys.map((b, i) => [i ? (b.longitud + buoys[i - 1].longitud) / 2 : b.longitud - 6, i < buoys.length - 1 ? (b.longitud + buoys[i + 1].longitud) / 2 : b.longitud + 6]);
  const depths = Array.from({ length: 30 }, (_, i) => i * 10);
  const line = (k: "isoterma20_m" | "isoterma20_normal_m") => buoys.filter(b => b[k] != null).map(b => `${x(b.longitud).toFixed(1)},${y(b[k]!).toFixed(1)}`).join(" ");
  return <section className="enso-tao" aria-labelledby="enso-tao-title">
    <span className="section-tag">BAJO EL MAR</span>
    <h2 id="enso-tao-title">El Pacífico por dentro: dónde está el calor y el frío</h2>
    <p className="enso-tao-lead">Corte de la línea del ecuador, de Asia (izquierda) a Sudamérica (derecha), desde la superficie hasta 300 m. Lo miden las boyas TAO de NOAA ancladas en el océano.</p>
    <div className="enso-tao-fig">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Anomalía de temperatura bajo el mar en el Pacífico ecuatorial">
        {buoys.map((b, i) => depths.map(dp => <rect key={b.longitud + "-" + dp} x={x(edges[i][0])} y={y(dp)} width={x(edges[i][1]) - x(edges[i][0]) + 0.5} height={y(dp + 10) - y(dp) + 0.5} fill={color(at(b.perfil, dp + 5))} />))}
        <polyline points={line("isoterma20_normal_m")} fill="none" stroke="#10222b" strokeWidth="1.6" strokeDasharray="5 4" />
        <polyline points={line("isoterma20_m")} fill="none" stroke="#10222b" strokeWidth="2.4" />
        {[0, 50, 100, 150, 200, 250, 300].map(dp => <g key={dp}><line x1={L - 4} x2={L} y1={y(dp)} y2={y(dp)} stroke="#5f6e73" /><text x={L - 7} y={y(dp) + 4} textAnchor="end" fontSize="11" fill="#5f6e73">{dp} m</text></g>)}
        {buoys.map(b => <g key={"l" + b.longitud}><line x1={x(b.longitud)} x2={x(b.longitud)} y1={H - B} y2={H - B + 4} stroke="#5f6e73" /><text x={x(b.longitud)} y={H - B + 16} textAnchor="middle" fontSize="10.5" fill="#3b4a50">{b.nombre}</text></g>)}
        <text x={L} y={H - 6} fontSize="11" fill="#5f6e73">← Asia · Oceanía</text><text x={W - R} y={H - 6} fontSize="11" fill="#5f6e73" textAnchor="end">Sudamérica →</text>
      </svg>
    </div>
    <div className="enso-tao-legend">
      {STEPS.slice(0, -1).map(([hi, c], i) => <span key={hi}><i style={{ background: c }} />{i === 0 ? `< ${fmt(hi, 0)}` : `${fmt(STEPS[i - 1][0], STEPS[i - 1][0] % 1 ? 1 : 0)} a ${fmt(hi, hi % 1 ? 1 : 0)}`}</span>)}
      <span><i style={{ background: STEPS[STEPS.length - 1][1] }} />&gt; +4 °C</span>
      <span><b className="ln" />isoterma de 20 °C hoy</span><span><b className="ln dash" />normal</span>
    </div>
    <p className="enso-tao-read">{reading(d)}</p>
    <p className="enso-tao-note">{d.nota} Datos hasta el {d.resumen?.ultimo_dato?.split("-").reverse().join("/")}; normal: {d.normal}. Fuente: <a href={d.url} target="_blank" rel="noreferrer">{d.fuente}</a>.</p>
  </section>;
}
