/**
 * El Niño · pronóstico: probabilidades oficiales de NOAA (RONI), MEI.v2, gráficos de Columbia (CCSR/IRI) y la
 * tendencia de lluvia y temperatura de los próximos meses en las localidades ribereñas (ECMWF SEAS5).
 * Datos de /api/enso/pronostico, que arma todos los días la tarea «El Niño: pronósticos».
 */
import React, { useEffect, useMemo, useState } from "react";

type Prob = { season: string; year: number | null; la_nina: number; neutral: number; el_nino: number };
type Month = { mes: string; lluvia_anomalia_mm: number | null; temp_anomalia_c: number | null };
type Place = { id: string; place: string; river: string; meses: Month[] };
type Data = {
  actualizado?: string;
  cpc?: { estado: string; emitido?: string; alerta?: string; sinopsis?: string; probabilidades?: Prob[]; url?: string; nota?: string; motivo?: string };
  ccsr_iri?: { estado: string; emitido?: string; graficos?: Record<string, string>; modelos?: { dinamicos: number; estadisticos: number }; url?: string };
  mei?: { estado: string; ultimo?: { mei: number; nombre: string }; url?: string; nota?: string };
  estacional?: { estado: string; localidades?: Place[]; nota?: string; fuente?: string };
  error?: string;
};

const SEASON_ES: Record<string, string> = { DJF: "dic–feb", JFM: "ene–mar", FMA: "feb–abr", MAM: "mar–may", AMJ: "abr–jun", MJJ: "may–jul",
  JJA: "jun–ago", JAS: "jul–sep", ASO: "ago–oct", SON: "sep–nov", OND: "oct–dic", NDJ: "nov–ene" };
const MES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
const fmt = (v: number | null | undefined, d = 0) => v == null ? "—" : new Intl.NumberFormat("es-AR", { maximumFractionDigits: d, minimumFractionDigits: d }).format(v);
const signed = (v: number | null | undefined, d = 0) => v == null ? "—" : (v > 0 ? "+" : "") + fmt(v, d);
const mesLabel = (m: string) => `${MES[+m.slice(5, 7) - 1]} ${m.slice(2, 4)}`;

function rainColor(v: number | null) {
  if (v == null) return "#eef2f3";
  if (v >= 100) return "#1f5fa8"; if (v >= 50) return "#4a8fd4"; if (v >= 15) return "#a9cdee";
  if (v > -15) return "#f1f3f2"; if (v > -50) return "#f3d19c"; return "#d9893a";
}

function readingOf(p: Place) {
  const next = p.meses.slice(0, 3).map(m => m.lluvia_anomalia_mm).filter((v): v is number => v != null);
  if (!next.length) return "Sin dato.";
  const sum = next.reduce((a, b) => a + b, 0);
  if (sum >= 150) return `Mucha más lluvia que lo normal en los próximos tres meses (unos ${fmt(sum)} mm de más): riesgo de anegamientos y de crecida en arroyos y ríos de la zona.`;
  if (sum >= 45) return `Más lluvia que lo normal en los próximos tres meses (unos ${fmt(sum)} mm de más).`;
  if (sum <= -45) return `Menos lluvia que lo normal en los próximos tres meses (unos ${fmt(-sum)} mm de menos).`;
  return "Lluvia cerca de lo normal en los próximos tres meses.";
}

const ALERT_ES: Record<string, string> = { "El Niño Advisory": "Aviso de El Niño: El Niño en curso", "La Niña Advisory": "Aviso de La Niña: La Niña en curso",
  "El Niño Watch": "Vigilancia de El Niño: puede formarse en los próximos meses", "La Niña Watch": "Vigilancia de La Niña: puede formarse en los próximos meses",
  "Final El Niño Advisory": "Fin de El Niño", "Final La Niña Advisory": "Fin de La Niña", "Not Active": "Sin alerta: condiciones neutrales" };

function headline(probs: Prob[]) {
  const sure = probs.filter(p => p.el_nino >= 90);
  const last = sure.length ? sure[sure.length - 1] : null;
  const turn = probs.find(p => p.neutral >= Math.max(p.el_nino, p.la_nina));
  const parts: string[] = [];
  if (last) parts.push(`NOAA da ${last.el_nino >= 99 ? "prácticamente por seguro" : `más del 90 % de probabilidad de`} que El Niño siga hasta ${SEASON_ES[last.season] || last.season}.`);
  else { const top = probs[0]; parts.push(`Para ${SEASON_ES[top.season] || top.season}, NOAA da ${top.el_nino} % de probabilidad de El Niño, ${top.neutral} % neutral y ${top.la_nina} % de La Niña.`); }
  if (turn) parts.push(`El paso a condiciones neutrales se vuelve lo más probable en ${SEASON_ES[turn.season] || turn.season} (${turn.neutral} %).`);
  return parts.join(" ");
}

export function EnsoForecast() {
  const [d, setD] = useState<Data | null>(null);
  const [place, setPlace] = useState("parana-corrientes");
  useEffect(() => {
    let live = true;
    fetch("/api/enso/pronostico").then(r => r.json()).then(j => { if (live) setD(j); }).catch(() => live && setD({ error: "No se pudo consultar el pronóstico." }));
    return () => { live = false; };
  }, []);
  const thisMonth = new Date().toISOString().slice(0, 7);
  const places = useMemo(() => (d?.estacional?.localidades || []).map(p => ({ ...p, meses: p.meses.filter(m => m.mes >= thisMonth).slice(0, 6) })), [d, thisMonth]);
  const sel = useMemo(() => places.find(p => p.id === place) || places[0], [places, place]);
  if (!d) return <section className="enso-fc"><p>Consultando el pronóstico…</p></section>;
  if (d.error && !d.cpc) return <section className="enso-fc"><p>{d.error}</p></section>;
  const probs = d.cpc?.probabilidades || [];
  const months = sel?.meses || [];
  return <section className="enso-fc" aria-labelledby="enso-fc-title">
    <div className="enso-fc-head">
      <span className="section-tag">PRONÓSTICO</span>
      <h2 id="enso-fc-title">Qué viene: probabilidades oficiales y lluvia de los próximos meses</h2>
      {probs.length > 0 && <p className="enso-fc-syn"><b>{ALERT_ES[d.cpc?.alerta || ""] || "NOAA"}.</b> {headline(probs)}</p>}
      {d.cpc?.sinopsis && <details className="enso-fc-orig"><summary>Texto original de NOAA (en inglés)</summary><p>{d.cpc.sinopsis}</p></details>}
    </div>

    <div className="enso-fc-grid">
      <article className="enso-fc-card wide">
        <h3>Probabilidad de El Niño, neutral y La Niña por trimestre</h3>
        <small>NOAA CPC · emitido {d.cpc?.emitido || "—"} · se clasifica con el RONI</small>
        {probs.length ? <div className="enso-fc-bars" role="img" aria-label="Probabilidades por trimestre">
          {probs.map(p => <div className="enso-fc-row" key={p.season}>
            <span className="enso-fc-s">{SEASON_ES[p.season] || p.season}</span>
            <div className="enso-fc-bar">
              {p.la_nina > 0 && <i className="nina" style={{ width: p.la_nina + "%" }} title={`La Niña ${p.la_nina} %`} />}
              {p.neutral > 0 && <i className="neutral" style={{ width: p.neutral + "%" }} title={`Neutral ${p.neutral} %`} />}
              {p.el_nino > 0 && <i className="nino" style={{ width: p.el_nino + "%" }} title={`El Niño ${p.el_nino} %`} />}
            </div>
            <b>{p.el_nino} %</b>
          </div>)}
          <div className="enso-fc-legend"><span><i className="nino" />El Niño</span><span><i className="neutral" />Neutral</span><span><i className="nina" />La Niña</span></div>
        </div> : <p>{d.cpc?.motivo || "Sin dato de NOAA por ahora."}</p>}
        <p className="enso-fc-note">{d.cpc?.nota}</p>
      </article>

      <article className="enso-fc-card">
        <h3>MEI.v2 · índice multivariado</h3>
        <small>NOAA PSL · océano y atmósfera juntos</small>
        <b className="enso-fc-big">{signed(d.mei?.ultimo?.mei, 2)}</b>
        <span>{d.mei?.ultimo?.nombre || ""}</span>
        <p className="enso-fc-note">+0,5 o más: El Niño. Más de +2: evento muy fuerte. {d.mei?.estado !== "recibido" ? "Sin dato por ahora." : ""}</p>
      </article>

      {d.ccsr_iri?.graficos && <article className="enso-fc-card">
        <h3>Pronóstico de Columbia (CCSR/IRI)</h3>
        <small>{d.ccsr_iri.modelos ? `${d.ccsr_iri.modelos.dinamicos} modelos dinámicos y ${d.ccsr_iri.modelos.estadisticos} estadísticos` : "Multimodelo"} · {d.ccsr_iri.emitido || ""}</small>
        {Object.entries(d.ccsr_iri.graficos).map(([k, url]) => <a key={k} href={d.ccsr_iri?.url || url} target="_blank" rel="noreferrer">
          <img src={url} alt={`Gráfico de ${k} del pronóstico ENSO de Columbia`} loading="lazy" /></a>)}
        <p className="enso-fc-note">Gráficos tal cual los publica Columbia. Tocá para ver el original.</p>
      </article>}
    </div>

    {places.length > 0 && <article className="enso-fc-card enso-fc-local">
      <div className="enso-fc-local-head">
        <div><h3>Lluvia y temperatura de los próximos meses</h3>
          <small>ECMWF SEAS5 (pronóstico estacional europeo) · milímetros por encima o por debajo de lo normal de cada mes</small></div>
        <label>Localidad<select value={sel?.id} onChange={e => setPlace(e.target.value)}>
          {places.map(p => <option key={p.id} value={p.id}>{p.place} · río {p.river}</option>)}</select></label>
      </div>
      <div className="enso-fc-months">{months.map(m => <div key={m.mes} style={{ background: rainColor(m.lluvia_anomalia_mm) }} className={(m.lluvia_anomalia_mm ?? 0) >= 50 ? "dark" : ""}>
        <span>{mesLabel(m.mes)}</span><b>{signed(m.lluvia_anomalia_mm)} mm</b><small>{signed(m.temp_anomalia_c, 1)} °C</small></div>)}</div>
      {sel && <p className="enso-fc-read">{readingOf(sel)}</p>}
      <details><summary>Ver todas las localidades</summary>
        <div className="enso-fc-table"><table><thead><tr><th>Localidad</th>{(places[0]?.meses || []).map(m => <th key={m.mes}>{mesLabel(m.mes)}</th>)}</tr></thead>
          <tbody>{places.map(p => <tr key={p.id}><td>{p.place}</td>{p.meses.map(m => <td key={m.mes} style={{ background: rainColor(m.lluvia_anomalia_mm) }} className={(m.lluvia_anomalia_mm ?? 0) >= 50 ? "dark" : ""}>{signed(m.lluvia_anomalia_mm)}</td>)}</tr>)}</tbody></table></div>
      </details>
      <p className="enso-fc-note">{d.estacional?.nota}</p>
    </article>}
    <p className="enso-fc-note">Actualizado {d.actualizado ? d.actualizado.replace("T", " ").replace("Z", " UTC") : "—"}. Un pronóstico estacional es una probabilidad para la zona, no el tiempo de un día puntual.</p>
  </section>;
}
