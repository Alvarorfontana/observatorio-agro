/**
 * El Niño en Sudamérica, ahora: mapa y tabla de ~80 localidades con la lluvia de los últimos 90 días, lo que El Niño
 * fuerte trajo históricamente y el pronóstico de 16 días. Datos de /api/fuentes/enso-sudamerica (ERA5 + NOAA).
 */
import React, { useMemo, useState } from "react";
import { SA_VIEW, SA_COUNTRIES, saXY } from "./samerica";

type Row = {
  id: string; name: string; country: string; lat: number; lon: number;
  obs90_mm: number | null; normal90_mm: number | null; now90_pct: number | null;
  obs30_mm: number | null; now30_pct: number | null;
  next16_mm: number | null; normal16_mm: number | null; next16_pct: number | null;
  expected_pct: number | null; expected_n: number | null; expected_wetter: number | null; signal: string;
};
export type NinoNowData = {
  places: Row[]; counts: Record<string, number>; season: string;
  phase_now?: { oni: number; phase: string; period: string } | null;
  window: { from: string; to: string; forecast_from: string };
  reference: { available: boolean; built?: string; period?: string };
};

const METRICS: [keyof Row, string, string][] = [
  ["now90_pct", "Ahora · últimos 90 días", "Lluvia de los últimos 90 días respecto de lo normal para esas fechas (ERA5)."],
  ["expected_pct", "Lo que trae El Niño fuerte", "Lluvia de la temporada en los El Niño fuertes desde 1991, respecto de los años neutrales."],
  ["next16_pct", "Próximos 16 días", "Lluvia pronosticada por los modelos globales respecto de lo normal."],
  ["now30_pct", "Último mes", "Lluvia de los últimos 30 días respecto de lo normal."],
];
const BINS: [number, string, string][] = [
  [-50, "#8c510a", "−50 % o menos"], [-25, "#d8a35a", "−50 a −25 %"], [-10, "#f1dfb6", "−25 a −10 %"],
  [10, "#e4e7ec", "cerca de lo normal"], [25, "#bfe3de", "+10 a +25 %"], [50, "#4fa9a0", "+25 a +50 %"], [Infinity, "#01665e", "+50 % o más"],
];
const color = (v: number | null | undefined) => v == null ? "none" : (BINS.find(([t]) => v <= t) || BINS[BINS.length - 1])[1];
const sgn = (v: number | null | undefined, u = " %") => v == null ? "—" : `${v > 0 ? "+" : ""}${v}${u}`;
const SIGNAL_CLS: Record<string, string> = { "ya se nota": "yes", "por ahora va al revés": "rev", "todavía no se nota": "wait", "El Niño no cambia mucho acá": "none" };
const ddmm = (iso?: string) => iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}` : "";

export function NinoNowSA({ data, onPick }: { data: NinoNowData | null | { error: string }; onPick?: (id: string) => void }) {
  const [metric, setMetric] = useState<keyof Row>("now90_pct");
  const [country, setCountry] = useState("Todos");
  const [sort, setSort] = useState<"name" | "metric">("metric");
  const [hover, setHover] = useState<Row | null>(null);
  const [pdfPlace, setPdfPlace] = useState("corrientes");
  const d = data && "places" in data ? data : null;
  const countries = useMemo(() => d ? ["Todos", ...Array.from(new Set(d.places.map(p => p.country)))] : ["Todos"], [d]);
  if (!data) return <section className="nino-now-sa"><p className="small">Consultando la lluvia de 80 localidades de Sudamérica…</p></section>;
  if (!d) return <section className="nino-now-sa"><p className="error">{(data as any).error || "No se pudo consultar"}</p></section>;
  const rows = d.places.filter(p => country === "Todos" || p.country === country)
    .slice().sort((a, b) => sort === "name" ? 0 : ((b[metric] as number ?? -999) - (a[metric] as number ?? -999)));
  const [, mLabel, mHelp] = METRICS.find(m => m[0] === metric)!;
  const pdf = d.places.find(p => p.id === pdfPlace) || d.places[0];
  const total = d.places.length;
  return <section className="nino-now-sa">
    <div className="nn-head">
      <div>
        <span className="section-tag">EN VIVO · {total} LOCALIDADES</span>
        <h3>¿Ya se nota El Niño en la lluvia?</h3>
        <p>Comparamos lo que llovió en los últimos 90 días ({ddmm(d.window.from)} al {ddmm(d.window.to)}) con lo que El Niño fuerte trajo en cada lugar en {d.season}. Así se ve dónde la señal ya llegó, dónde todavía no y dónde, por ahora, va al revés.</p>
      </div>
      <div className="nn-counts">
        {[["ya se nota", "yes"], ["todavía no se nota", "wait"], ["por ahora va al revés", "rev"], ["El Niño no cambia mucho acá", "none"]].map(([k, c]) =>
          <div key={k} className={c}><b>{d.counts[k] || 0}</b><span>{k}</span></div>)}
      </div>
    </div>
    {!d.reference.available && <p className="nn-warn">Se está calculando la lluvia normal e histórica de cada localidad (35 años por lugar). Los colores del mapa y los porcentajes aparecen cuando termina; mientras tanto, la tabla muestra los milímetros caídos en los últimos 90 días.</p>}
    <div className="nn-metrics" role="tablist">{METRICS.map(([k, l]) => <button key={k} role="tab" aria-selected={metric === k} className={metric === k ? "on" : ""} onClick={() => setMetric(k)}>{l}</button>)}</div>
    <div className="nn-grid">
      <figure className="nn-map">
        <svg viewBox={`0 0 ${SA_VIEW.w} ${SA_VIEW.h}`} role="img" aria-label={`Mapa de Sudamérica: ${mLabel}`}>
          <rect width={SA_VIEW.w} height={SA_VIEW.h} fill="#eef5f8" />
          {SA_COUNTRIES.map(c => <path key={c.id} d={c.d} fill="#fbfaf7" stroke="#c9cfd6" strokeWidth={0.7} />)}
          {d.places.map(p => {
            const [x, y] = saXY(p.lon, p.lat); const v = p[metric] as number | null;
            return <g key={p.id} onMouseEnter={() => setHover(p)} onMouseLeave={() => setHover(null)} onClick={() => onPick?.(p.id)} style={{ cursor: onPick ? "pointer" : "default" }}>
              <circle cx={x} cy={y} r={hover?.id === p.id ? 9 : 7} fill={v == null ? "#fff" : color(v)} stroke={v == null ? "#98a2b3" : "#344054"} strokeWidth={v == null ? 1 : 0.6} strokeDasharray={v == null ? "2 2" : undefined} />
              <title>{`${p.name} (${p.country}): ${sgn(v)}`}</title>
            </g>;
          })}
          {hover && (() => {
            const [x, y] = saXY(hover.lon, hover.lat); const left = x > SA_VIEW.w / 2;
            return <g transform={`translate(${left ? x - 170 : x + 12},${Math.min(Math.max(y - 30, 4), SA_VIEW.h - 70)})`} pointerEvents="none">
              <rect width="158" height="62" rx="6" fill="#101828" opacity=".92" />
              <text x="9" y="17" fill="#fff" fontSize="12" fontWeight="700">{hover.name}</text>
              <text x="9" y="33" fill="#d0d5dd" fontSize="10.5">90 días: {sgn(hover.now90_pct)} · Niño fuerte: {sgn(hover.expected_pct)}</text>
              <text x="9" y="49" fill="#d0d5dd" fontSize="10.5">Próx. 16 días: {hover.next16_mm ?? "—"} mm ({sgn(hover.next16_pct)})</text>
            </g>;
          })()}
        </svg>
        <figcaption>{mHelp} Círculo vacío: sin dato o temporada seca (menos de 5 mm normales).</figcaption>
      </figure>
      <div className="nn-side">
        <div className="nn-legend">{BINS.map(([, c, l]) => <span key={l}><i style={{ background: c }} />{l}</span>)}</div>
        <div className="nn-explain">
          <p><b className="yes">Ya se nota</b> la lluvia va en el mismo sentido que en los Niño fuertes del pasado (15 % o más).</p>
          <p><b className="wait">Todavía no se nota</b> la lluvia está cerca de lo normal: la señal suele llegar con la primavera y el verano.</p>
          <p><b className="rev">Por ahora va al revés</b> llueve al contrario de lo que El Niño suele traer.</p>
          <p><b className="none">No cambia mucho acá</b> en ese lugar los Niño fuertes no movieron la lluvia más de 10 %.</p>
        </div>
        <div className="nn-report">
          <b>Informe El Niño en PDF</b>
          <p className="small">Cadena del Pacífico, historia del lugar desde 1991, lluvia de los últimos 90 días, pronóstico de 16 días, recomendaciones y la tabla de Sudamérica.</p>
          <label>Localidad <select value={pdfPlace} onChange={e => setPdfPlace(e.target.value)}>{d.places.map(p => <option key={p.id} value={p.id}>{p.name} · {p.country}</option>)}</select></label>
          <a className="nn-btn" href={`/api/fuentes/enso-informe?lat=${pdf.lat}&lon=${pdf.lon}&nombre=${encodeURIComponent(pdf.name)}`} download>Descargar informe</a>
          <p className="small">Para un lote propio, generalo desde el tablero (vista El Niño en tu lote).</p>
        </div>
      </div>
    </div>
    <div className="nn-table-tools">
      <label>País <select value={country} onChange={e => setCountry(e.target.value)}>{countries.map(c => <option key={c}>{c}</option>)}</select></label>
      <label>Ordenar <select value={sort} onChange={e => setSort(e.target.value as any)}><option value="metric">por {mLabel.toLowerCase()}</option><option value="name">por país</option></select></label>
    </div>
    <div className="nn-table" role="table">
      <div className="nn-tr nn-th" role="row"><span>Localidad</span><span>Últimos 90 días</span><span>Último mes</span><span>Niño fuerte (histórico)</span><span>Próximos 16 días</span><span>Lectura</span></div>
      {rows.map(p => <div className="nn-tr" role="row" key={p.id} onClick={() => onPick?.(p.id)}>
        <span><b>{p.name}</b><small>{p.country}</small></span>
        <span><i style={{ background: color(p.now90_pct) }} />{sgn(p.now90_pct)}<small>{p.obs90_mm ?? "—"} mm de {p.normal90_mm ?? "—"}</small></span>
        <span>{sgn(p.now30_pct)}<small>{p.obs30_mm ?? "—"} mm</small></span>
        <span><i style={{ background: color(p.expected_pct) }} />{sgn(p.expected_pct)}<small>{p.expected_n ? `${p.expected_wetter} de ${p.expected_n} más lluviosas` : ""}</small></span>
        <span>{p.next16_mm ?? "—"} mm<small>{sgn(p.next16_pct)}</small></span>
        <span className={"nn-sig " + (SIGNAL_CLS[p.signal] || "none")}>{p.signal}</span>
      </div>)}
    </div>
    <p className="footnote">Lluvia observada: Copernicus ERA5 (grilla de ~25 km, ~6 días de demora). Normal: promedio 1991-2020. Pronóstico: modelos globales vía Open-Meteo. Referencia El Niño: temporadas desde 1991 según el ONI de NOAA{d.reference.built ? `, calculada el ${d.reference.built}` : ""}. Es diagnóstico, no pronóstico estacional.</p>
  </section>;
}
