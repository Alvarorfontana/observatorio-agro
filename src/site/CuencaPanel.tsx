// Panel "Cuenca del Plata": El Niño semanal, lluvia en las cabeceras, ríos, tiempos de traslado y qué hacer.
import { useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";

type Data = Record<string, any>;
const nf = (v: unknown, d = 0) => v == null || !Number.isFinite(Number(v)) ? "—" : Number(v).toLocaleString("es-AR", { minimumFractionDigits: d, maximumFractionDigits: d });
const dm = (iso?: string | null) => iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}` : "—";
const sign = (v: number | null | undefined, d = 1) => v == null ? "—" : `${v > 0 ? "+" : ""}${nf(v, d)}`;
const LEVEL_TONE: Record<string, string> = { Normal: "ok", "Atención": "warn", Alerta: "alert", Peligro: "risk", "Evacuación": "risk" };
const m2 = (v: unknown) => v == null ? "—" : `${nf(v, 2)} m`;
const my = (iso?: string | null) => iso ? `${["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"][Number(iso.slice(5, 7)) - 1]} ${iso.slice(0, 4)}` : "";
export function predText(p: Data | null | undefined) {
  if (!p) return "";
  if (p.kind === "altura") return `Con ${nf(p.rain10_mm)} mm en 10 días, el río en ${p.place} podría subir unos ${nf(p.rise_m, 1)} m: de ${nf(p.from_m, 2)} a ${nf(p.to_m, 2)} m${p.alert_m != null ? ` (alerta ${nf(p.alert_m, 2)} m, evacuación ${nf(p.evac_m, 2)} m)` : ""}.`;
  return `Con ${nf(p.rain10_mm)} mm en 10 días, el caudal en ${p.place} podría subir unos ${nf(p.rise_q)} m³/s: de ${nf(p.from_q)} a ${nf(p.to_q)} m³/s.`;
}
const STATE_TONE = (s?: string | null) => !s ? "" : /extra|muy alto/.test(s) ? "risk" : /alto/.test(s) ? "warn" : /bajo/.test(s) ? "low" : "ok";

function Spark({ values, height = 44 }: { values: (number | null)[]; height?: number }) {
  const vs = values.filter((v): v is number => v != null);
  if (vs.length < 2) return null;
  const lo = Math.min(0, ...vs), hi = Math.max(0.5, ...vs), w = 160;
  const y = (v: number) => height - 4 - ((v - lo) / (hi - lo || 1)) * (height - 8);
  const pts = values.map((v, i) => v == null ? null : `${(i / (values.length - 1)) * w},${y(v)}`).filter(Boolean).join(" ");
  return <svg className="cp-spark" viewBox={`0 0 ${w} ${height}`} preserveAspectRatio="none" aria-hidden="true">
    <line x1="0" x2={w} y1={y(0.5)} y2={y(0.5)} className="cp-spark-ref" />
    <polyline points={pts} />
  </svg>;
}

// Imagen de NASA GIBS: prueba las capas en orden y se oculta si ninguna responde
function GibsImg({ m, alt }: { m: Data; alt: string }) {
  const [i, setI] = useState(0), [gone, setGone] = useState(false), [ovl, setOvl] = useState(true);
  if (!m || gone) return null;
  const layers: string[] = m.layers || [];
  return <figure className="cp-map">
    <div className="cp-map-img">
      {m.base && <img src={m.base} alt="" aria-hidden="true" />}
      <img src={layers[i]} alt={alt} className={m.base ? "over" : ""} onError={() => i + 1 < layers.length ? setI(i + 1) : setGone(true)} />
      {m.overlay && ovl && <img src={m.overlay} alt="" aria-hidden="true" className="over" onError={() => setOvl(false)} />}
    </div>
    <figcaption><b>{m.title}</b> · {dm(m.date)} — {m.caption}</figcaption>
  </figure>;
}

function ProbBar({ label, value }: { label: string; value: number | null | undefined }) {
  return <div className="cp-prob"><span>{label}</span><i><b style={{ width: `${Math.max(0, Math.min(100, value ?? 0))}%` }} /></i><em>{nf(value)} %</em></div>;
}

const RIVER_ORDER = ["Iguazú", "Paraná", "Paraguay", "Bermejo", "Uruguay"];
const GROUPS = ["Iguazú", "Uruguay", "Paraná", "Paraguay", "Bermejo y Pilcomayo"];
const OFFICIAL: [string, [string, string, string][]][] = [
  ["Argentina", [["INA · Sistema de Alerta", "pronósticos de altura del Paraná, Paraguay, Uruguay e Iguazú", "https://www.ina.gob.ar/alerta/"],
    ["Prefectura Naval", "alturas diarias por puerto, con niveles de alerta y evacuación", "https://contenidosweb.prefecturanaval.gob.ar/alturas/"]]],
  ["Brasil", [["ANA · Sala de Situação Iguaçu-Uruguai", "boletines diarios de las cuencas del Iguazú y el Uruguay", "https://www.gov.br/ana/pt-br/sala-de-situacao/iguacu-uruguai"],
    ["SGB · Alertas SACE", "alertas hidrológicos y tiempos de retorno de crecidas", "https://www.sgb.gov.br/sace/"],
    ["ONS · datos hidrológicos", "caudales diarios de las represas (abiertos)", "https://dados.ons.org.br/dataset/dados-hidrologicos-res"]]],
  ["Paraguay", [["DMH · Meteorología e Hidrología", "niveles del río Paraguay y pronósticos", "https://www.meteorologia.gov.py/"]]],
  ["Bolivia", [["SENAMHI", "pronóstico hidrológico: Pilcomayo y Bermejo, que bajan al Paraguay", "https://senamhi.gob.bo/"]]],
  ["Uruguay", [["INUMET", "meteorología y avisos", "https://www.inumet.gub.uy/"], ["CTM Salto Grande", "caudales y operación de la represa del río Uruguay", "https://www.saltogrande.org/"]]],
  ["Regional y satélites", [["CIC Plata", "comité de los cinco países de la cuenca", "https://cicplata.org/"],
    ["GloFAS · Copernicus", "alerta global de crecidas (el modelo que usa este panel)", "https://global-flood.emergency.copernicus.eu/"],
    ["Hydroweb (CNES)", "altura de ríos medida por satélite en más de 22.800 puntos", "https://www.theia-land.fr/en/blog/hydroweb-more-than-22800-stations-on-the-worlds-rivers/"],
    ["SWOT (NASA · CNES)", "satélite que mide la altura del agua de ríos y lagunas", "https://swot.jpl.nasa.gov/"]]],
];


const LEVEL_COLOR: Record<string, string> = { Normal: "#19b98a", "Atención": "#f0a020", Alerta: "#e8590c", "Evacuación": "#d92d20", Peligro: "#d92d20" };
const EMERGENCY: Record<string, [string, string][]> = {
  Argentina: [["Defensa Civil", "103"], ["Prefectura Naval", "106"], ["Emergencias", "911"], ["Bomberos", "100"], ["SAME", "107"]],
  Brasil: [["Defesa Civil", "199"], ["Bombeiros", "193"], ["SAMU", "192"]],
  Paraguay: [["Emergencias", "911"]],
  Uruguay: [["Emergencias", "911"]],
};
const COUNTRY = (id: string) => id === "paraguay-bahianegra" || id === "paraguay-concepcion" ? "Paraguay" : id === "uruguay-fraybentos" ? "Uruguay" : "Argentina";
const levelOf = (s: Data) => s?.ina?.level || s?.danger || null;

// Resumen de la cuenca: cuántos puertos en cada nivel y cuántos subiendo
function Summary({ stations }: { stations: Data[] }) {
  const withH = stations.filter(s => s.ina?.height != null);
  const count = (l: string) => withH.filter(s => s.ina.level === l).length;
  const rising = withH.filter(s => (s.ina.trend_m_day ?? 0) > 0.01).length;
  return <div className="cp-summary">
    {[["Evacuación", "risk"], ["Alerta", "alert"], ["Atención", "warn"], ["Normal", "ok"]].map(([l, t]) =>
      <article key={l} className={t}><b>{count(l)}</b><span>{l === "Evacuación" ? "en evacuación" : l === "Normal" ? "normales" : `en ${l.toLowerCase()}`}</span></article>)}
    <article className="rise"><b>{rising}<small> de {withH.length}</small></b><span>puertos con el río subiendo</span></article>
  </div>;
}

// Regla: aguas bajas · hoy · alerta · evacuación
function Ruler({ i }: { i: Data }) {
  if (i.height == null || i.alert == null) return null;
  const lo = Math.min(i.low ?? i.height, i.height) - 0.5, hi = Math.max((i.evac ?? i.alert) + 1, i.height + 0.5);
  const pos = (v: number) => `${((v - lo) / (hi - lo)) * 100}%`;
  return <div className="cp-ruler" aria-label="Altura de hoy frente a los niveles oficiales">
    <div className="track">
      <i className="z-ok" style={{ left: 0, width: pos(i.alert - (i.attention ?? 1)) }} />
      <i className="z-warn" style={{ left: pos(i.alert - (i.attention ?? 1)), width: `calc(${pos(i.alert)} - ${pos(i.alert - (i.attention ?? 1))})` }} />
      <i className="z-alert" style={{ left: pos(i.alert), width: `calc(${pos(i.evac ?? i.alert)} - ${pos(i.alert)})` }} />
      <i className="z-risk" style={{ left: pos(i.evac ?? i.alert), right: 0 }} />
      <b className="now" style={{ left: pos(i.height) }}><em>{nf(i.height, 2)} m</em></b>
    </div>
    <div className="marks">
      {i.low != null && <span style={{ left: pos(i.low) }}>aguas bajas {nf(i.low, 2)}</span>}
      <span style={{ left: pos(i.alert) }}>alerta {nf(i.alert, 2)}</span>
      {i.evac != null && <span style={{ left: pos(i.evac) }}>evacuación {nf(i.evac, 2)}</span>}
    </div>
  </div>;
}

// Gráfico: alturas de los últimos días, pronóstico del INA y líneas de alerta y evacuación
function HeightChart({ i }: { i: Data }) {
  const box = useRef<HTMLDivElement | null>(null);
  const [W, setW] = useState(640);
  useEffect(() => {
    if (!box.current) return;
    const ro = new ResizeObserver(e => setW(Math.max(280, Math.round(e[0].contentRect.width))));
    ro.observe(box.current); return () => ro.disconnect();
  }, []);
  const obs: Data[] = i.series || [], fc: Data[] = i.forecast || [];
  if (obs.length < 2) return <div ref={box} />;
  const H = W < 500 ? 200 : 240, P = { l: 40, r: 10, t: 14, b: 24 };
  const days = [...obs.map(o => o.date), ...fc.map(f => f.date)];
  const t0 = new Date(days[0]).getTime(), t1 = new Date(days[days.length - 1]).getTime() || t0 + 1;
  const vals = [...obs.map(o => o.h), ...fc.flatMap(f => [f.min, f.max]), i.alert, i.evac].filter((v): v is number => v != null);
  const lo = Math.floor(Math.min(...vals) - 0.3), hi = Math.ceil(Math.max(...vals) + 0.3);
  const x = (d: string) => P.l + ((new Date(d).getTime() - t0) / (t1 - t0 || 1)) * (W - P.l - P.r);
  const y = (v: number) => P.t + (1 - (v - lo) / (hi - lo || 1)) * (H - P.t - P.b);
  const ticks = Array.from({ length: 5 }, (_, k) => lo + (k * (hi - lo)) / 4);
  const last = obs[obs.length - 1];
  return <div ref={box}><svg className="cp-hchart" width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Altura del río y pronóstico">
    {ticks.map(v => <g key={v}><line x1={P.l} x2={W - P.r} y1={y(v)} y2={y(v)} className="grid" /><text x={P.l - 6} y={y(v) + 4} textAnchor="end">{nf(v, 1)}</text></g>)}
    {i.evac != null && <><line x1={P.l} x2={W - P.r} y1={y(i.evac)} y2={y(i.evac)} className="evac" /><text x={W - P.r} y={y(i.evac) - 4} textAnchor="end" className="lab-evac">evacuación {nf(i.evac, 2)} m</text></>}
    {i.alert != null && <><line x1={P.l} x2={W - P.r} y1={y(i.alert)} y2={y(i.alert)} className="alert" /><text x={W - P.r} y={y(i.alert) - 4} textAnchor="end" className="lab-alert">alerta {nf(i.alert, 2)} m</text></>}
    {fc.length > 0 && <polygon className="fc-band" points={[...fc.map(f => `${x(f.date)},${y(f.max)}`), ...fc.slice().reverse().map(f => `${x(f.date)},${y(f.min)}`), `${x(last.date)},${y(last.h)}`].join(" ")} />}
    {fc.length > 0 && <polyline className="fc" points={[`${x(last.date)},${y(last.h)}`, ...fc.map(f => `${x(f.date)},${y(f.central)}`)].join(" ")} />}
    <polyline className="obs" points={obs.map(o => `${x(o.date)},${y(o.h)}`).join(" ")} />
    {obs.map(o => <circle key={o.date} cx={x(o.date)} cy={y(o.h)} r={2.5} className="obs-dot" />)}
    {fc.map(f => <circle key={f.date} cx={x(f.date)} cy={y(f.central)} r={3.5} className="fc-dot" />)}
    {[days[0], last.date, ...fc.map(f => f.date)].filter((d, k, a) => a.indexOf(d) === k).map((d, k, a) => <text key={d} x={x(d)} y={H - 6} textAnchor={k === 0 ? "start" : k === a.length - 1 ? "end" : "middle"}>{dm(d)}</text>)}
  </svg></div>;
}

function shareText(s: Data, arrivals: Data[]) {
  const i = s.ina || {}; const lvl = levelOf(s) || "sin dato";
  const lines = [`⚠️ DOTS · Sistema de Alerta de Crecidas`, `${s.place} (río ${s.river}): ${lvl.toUpperCase()}`];
  if (i.height != null) lines.push(`Altura ${nf(i.height, 2)} m el ${dm(i.date)}. Alerta ${nf(i.alert, 2)} m · evacuación ${nf(i.evac, 2)} m.`);
  if (i.trend_m_day != null) lines.push(`Tendencia: ${i.trend_m_day > 0 ? "sube" : "baja"} ${nf(Math.abs(i.trend_m_day) * 100, 0)} cm por día${i.days_to_alert ? `; a este ritmo llegaría a la alerta en ~${i.days_to_alert} días` : ""}.`);
  const fc = (i.forecast || []).slice(-1)[0]; if (fc) lines.push(`Pronóstico INA al ${dm(fc.date)}: ${nf(fc.central, 2)} m (${nf(fc.min, 2)}–${nf(fc.max, 2)}).`);
  arrivals.slice(0, 2).forEach(a => lines.push(`Lluvia en ${a.name}: repunte esperado entre el ${dm(a.window[0])} y el ${dm(a.window[1])}.`));
  lines.push(`Ante una evacuación seguí a Defensa Civil (103) y Prefectura (106).`, `Más datos: ${location.origin}/alertas`);
  return lines.join("\n");
}

// ¿Cómo está mi localidad?
function Locality({ stations, alerts, actions }: { stations: Data[]; alerts: Data[]; actions: Data }) {
  const order = ["Evacuación", "Alerta", "Atención"];
  const initial = useMemo(() => {
    let id = ""; try { id = localStorage.getItem("dots-localidad") || ""; } catch { /* sin almacenamiento */ }
    if (stations.some(s => s.id === id)) return id;
    const worst = stations.filter(s => order.includes(levelOf(s))).sort((a, b) => order.indexOf(levelOf(a)) - order.indexOf(levelOf(b)))[0];
    return worst?.id || "parana-corrientes";
  }, [stations]);
  const [sel, setSel] = useState(initial);
  const s = stations.find(x => x.id === sel) || stations[0];
  if (!s) return null;
  const i = s.ina || {}; const lvl = levelOf(s);
  const arrivals = alerts.filter(a => a.level !== "Normal").flatMap(a => (a.arrivals || []).filter((x: Data) => x.place === s.place && x.window).map((x: Data) => ({ name: a.name, level: a.level, window: x.window })));
  const act = actions?.[lvl === "Evacuación" ? "Peligro" : lvl || "Normal"] || [];
  const country = COUNTRY(s.id);
  const pick = (id: string) => { setSel(id); try { localStorage.setItem("dots-localidad", id); } catch { /* sin almacenamiento */ } };
  const wa = `https://wa.me/?text=${encodeURIComponent(shareText(s, arrivals))}`;
  return <div className="cp-block cp-local">
    <h3>¿Cómo está mi localidad? <small>Elegí tu ciudad: altura de hoy, niveles oficiales, tendencia y qué hacer</small></h3>
    <div className="cp-local-card">
      <div className="cp-local-head">
        <select value={s.id} onChange={e => pick(e.target.value)} aria-label="Elegí tu localidad">
          {RIVER_ORDER.map(rn => <optgroup key={rn} label={`Río ${rn}`}>{stations.filter(x => x.river === rn).map(x => <option key={x.id} value={x.id}>{x.place}{levelOf(x) && levelOf(x) !== "Normal" ? ` · ${levelOf(x)}` : ""}</option>)}</optgroup>)}
        </select>
        {lvl && <span className={`cp-big-level ${LEVEL_TONE[lvl]}`}>{lvl}</span>}
        <a className="cp-wa" href={wa} target="_blank" rel="noreferrer">Compartir por WhatsApp</a>
      </div>
      {i.height != null ? <>
        <div className="cp-local-kpis">
          <div><span>Altura hoy</span><b>{nf(i.height, 2)} m</b><em>{dm(i.date)}{i.gauge ? ` · ${i.gauge}` : ""}</em></div>
          <div><span>Falta para la alerta</span><b className={i.to_alert != null && i.to_alert <= 0 ? "cp-red" : ""}>{i.to_alert == null ? "—" : i.to_alert <= 0 ? "superada" : `${nf(i.to_alert, 2)} m`}</b><em>alerta {nf(i.alert, 2)} m · evacuación {nf(i.evac, 2)} m</em></div>
          <div><span>Tendencia</span><b>{i.trend_m_day == null ? "—" : `${i.trend_m_day > 0 ? "↑" : i.trend_m_day < 0 ? "↓" : "→"} ${nf(Math.abs(i.trend_m_day) * 100, 0)} cm/día`}</b><em>{i.days_to_alert ? `a este ritmo, alerta en ~${i.days_to_alert} días` : i.trend_m_day != null && i.trend_m_day <= 0.005 ? "estable o bajando" : "lejos de la alerta"}</em></div>
          <div><span>Pronóstico INA</span><b>{(i.forecast || []).length ? `${nf(i.forecast.slice(-1)[0].central, 2)} m` : "—"}</b><em>{(i.forecast || []).length ? `al ${dm(i.forecast.slice(-1)[0].date)} · ${nf(i.forecast.slice(-1)[0].min, 2)}–${nf(i.forecast.slice(-1)[0].max, 2)} m` : "sin pronóstico oficial para este puerto"}</em></div>
        </div>
        <Ruler i={{ ...i, attention: s.river === "Iguazú" || s.river === "Uruguay" ? 2 : 1 }} />
        <HeightChart i={i} />
        <p className="cp-legend"><i className="l-obs" /> altura medida (INA) <i className="l-fc" /> pronóstico INA y rango <i className="l-alert" /> alerta <i className="l-evac" /> evacuación</p>
      </> : <p className="cp-note">Esta localidad no tiene escala del INA. Nivel según el caudal (GloFAS): {s.discharge != null ? `${nf(s.discharge)} m³/s${s.ratio != null ? `, ${nf(s.ratio, 1)} veces lo normal` : ""}` : "sin dato"}.</p>}
      {arrivals.length > 0 && <div className="cp-local-arrivals"><b>Crecida en camino</b>{arrivals.map(a => <p key={a.name}><span className={`cp-chip ${LEVEL_TONE[a.level]}`}>{a.level}</span> lluvia en {a.name}: repunte esperado entre el <strong>{dm(a.window[0])}</strong> y el <strong>{dm(a.window[1])}</strong>.</p>)}</div>}
      <div className="cp-local-foot">
        <div><b>Qué hacer ahora</b><ul>{act.map((t: string) => <li key={t}>{t}</li>)}</ul></div>
        <div><b>Teléfonos de emergencia · {country}</b><ul className="cp-phones">{EMERGENCY[country].map(([n, t]) => <li key={t}><a href={`tel:${t}`}>{t}</a> {n}</li>)}</ul></div>
      </div>
    </div>
  </div>;
}

// Mapa de alertas: localidades pintadas por nivel
function AlertMap({ stations, onPick }: { stations: Data[]; onPick?: (id: string) => void }) {
  const ref = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (!ref.current) return;
    const map = L.map(ref.current, { scrollWheelZoom: false, attributionControl: true }).setView([-28.5, -57.5], 5);
    L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png", { maxZoom: 12, attribution: "© OpenStreetMap · © CARTO" }).addTo(map);
    const pts: L.LatLngExpression[] = [];
    stations.forEach(s => {
      if (s.lat == null) return;
      const lvl = levelOf(s) || "Normal"; const i = s.ina || {};
      const m = L.circleMarker([s.lat, s.lon], { radius: lvl === "Normal" ? 6 : 9, color: "#fff", weight: 2, fillColor: LEVEL_COLOR[lvl] || "#98a2b3", fillOpacity: 0.95 }).addTo(map);
      m.bindTooltip(`<b>${s.place}</b> · río ${s.river}<br>${lvl}${i.height != null ? ` · ${nf(i.height, 2)} m (alerta ${nf(i.alert, 2)})` : ""}`, { direction: "top" });
      if (onPick) m.on("click", () => onPick(s.id));
      pts.push([s.lat, s.lon]);
    });
    if (pts.length) map.fitBounds(L.latLngBounds(pts).pad(0.15));
    return () => { map.remove(); };
  }, [stations]);
  return <div className="cp-block">
    <h3>Mapa de alertas <small>34 localidades pintadas por nivel · tocá un punto para ver el detalle</small></h3>
    <div className="cp-mapbox"><div ref={ref} className="cp-leaflet" /><div className="cp-map-legend">{["Normal", "Atención", "Alerta", "Evacuación"].map(l => <span key={l}><i style={{ background: LEVEL_COLOR[l] }} />{l}</span>)}</div></div>
  </div>;
}

// Aviso compacto para el panel regional: lleva a la página del sistema de alertas
export function AlertasTeaser() {
  return <section className="cp cp-teaser">
    <div className="cp-intro">
      <span className="section-tag">NUEVO · SISTEMA DE ALERTA DE CRECIDAS</span>
      <h2>¿Viene agua? Alertas por lluvia en Brasil, Paraguay y Bolivia.</h2>
      <p>34 localidades del Iguazú, Paraná, Paraguay, Bermejo y Uruguay con su altura de hoy contra los niveles oficiales, el pronóstico del INA y cuándo llegaría la crecida.</p>
      <a className="cp-pdf static" href="/alertas" onClick={e => { e.preventDefault(); history.pushState({}, "", "/alertas"); dispatchEvent(new PopStateEvent("popstate")); scrollTo(0, 0); }}>Ver el sistema de alertas →</a>
    </div>
  </section>;
}

export function CuencaPanel() {
  const [res, setRes] = useState<Data | null>(null), [err, setErr] = useState(""), [pickKey, setPickKey] = useState(0);
  useEffect(() => {
    let live = true;
    fetch("/api/fuentes/cuenca").then(r => r.json()).then(j => { if (!live) return; if (j.status === "recibido") setRes(j.data); else setErr(j.error || "Las fuentes no respondieron."); })
      .catch(() => live && setErr("No se pudo consultar la cuenca."));
    return () => { live = false; };
  }, []);
  const nino = res?.nino, hw = res?.headwaters, rv = res?.rivers, dm2 = res?.dams, al: Data[] = res?.alerts || [];
  const active = al.filter(a => a.level !== "Normal");
  const levels: string[] = [...(rv?.stations || []).flatMap((s: Data) => [s.danger, s.peak_danger]), ...al.map(a => a.level)].filter(Boolean);
  const worst = ["Peligro", "Alerta", "Atención", "Normal"].find(l => levels.map(x => x === "Evacuación" ? "Peligro" : x).includes(l));

  return <section className="cp" aria-label="Cuenca del Plata">
    <div className="cp-intro">
      <span className="section-tag">DOTS · SISTEMA DE ALERTA DE CRECIDAS · CUENCA DEL PLATA</span>
      <h2>Sistema de Alerta de Crecidas</h2>
      <p className="cp-sub">De la lluvia en Brasil, Paraguay y Bolivia a la crecida en tu costa: Iguazú, Paraná, Paraguay, Bermejo y Uruguay.</p>
      <a className="cp-pdf" href="/api/fuentes/cuenca-informe" download>Descargar informe PDF ↓</a>
      <p>Las crecidas del Paraná y del Uruguay nacen en las cabeceras: el sur de Brasil, el Alto Paraná y el Pantanal. El Niño carga de lluvia esa zona en primavera y verano. Acá se sigue la cadena completa: el océano, la lluvia que viene, los ríos hoy y cuánto tarda el agua en llegar.</p>
    </div>
    {err && <p className="rp-error">{err} No se muestran valores supuestos.</p>}
    {!res && !err && <p className="cp-loading">Consultando NOAA, ECMWF, GFS y GloFAS…</p>}

    {rv?.stations && <Summary stations={rv.stations} />}
    {rv?.stations && <Locality key={pickKey} stations={rv.stations} alerts={al} actions={rv.actions} />}
    {res?.alerts && <div className="cp-block cp-alerts">
      <h3>Alertas activas · lluvia en las cabeceras <small>Se recalcula con cada pronóstico · lluvia ECMWF + GFS, estado del río y represas</small></h3>
      {active.length ? <div className="cp-alert-list">{active.map(a => <article key={a.basin} className={LEVEL_TONE[a.level]}>
        <div className="cp-head"><span className={`cp-chip ${LEVEL_TONE[a.level]}`}>{a.level}</span><b>{a.name}</b><small>{a.where}</small></div>
        <p className="cp-alert-rain">{a.median_mm != null ? `${nf(a.median_mm)} mm esperados en 15 días` : ""}{a.rain_from ? ` · lluvia fuerte entre el ${dm(a.rain_from)} y el ${dm(a.rain_to)}` : ""}</p>
        {a.prediction && <div className="cp-pred"><span>Cálculo lluvia → crecida</span><p>{predText(a.prediction)}</p>
          <small>{a.prediction.kind === "altura" ? `${nf(a.prediction.per10mm_m, 2)} m por cada 10 mm` : `${nf(a.prediction.per10mm_q)} m³/s por cada 10 mm`} · {a.prediction.cases} episodios en 20 años{a.prediction.rain_alert_mm ? ` · en el pasado, con ~${nf(a.prediction.rain_alert_mm)} mm pasó el nivel de alerta` : ""}{a.prediction.rain_evac_mm ? ` y con ~${nf(a.prediction.rain_evac_mm)} mm el de evacuación` : ""}.</small></div>}
        <ul className="cp-why">{a.why.map((w: string) => <li key={w}>{w}</li>)}</ul>
        {a.arrivals?.length > 0 && <div className="cp-arrivals"><span>Cuándo llegaría la crecida</span>
          <ol>{a.arrivals.map((x: Data) => <li key={x.place}><b>{x.place}</b><em>{x.window ? `${dm(x.window[0])} al ${dm(x.window[1])}` : "—"}</em></li>)}</ol></div>}
      </article>)}</div>
        : <p className="cp-calm">Sin alertas: el pronóstico no muestra lluvias fuera de lo común en las cabeceras para los próximos 15 días.</p>}
      {al.filter(a => a.level === "Normal").length > 0 && <p className="cp-note">Sin alerta: {al.filter(a => a.level === "Normal").map(a => a.name).join(" · ")}.</p>}
      <p className="cp-note">Qué hacer en cada nivel: ver "Qué hacer según el nivel" más abajo. Cómo se calcula: probabilidad de superar 100 y 200 mm en 15 días y lluvia contra la normal de la época. Si el río de salida ya viene alto o las represas sueltan mucho, la alerta sube un escalón. La ventana de llegada suma la respuesta típica de cada cuenca y los días de traslado aguas abajo. Es orientativo: no reemplaza las alertas del INA, la Prefectura ni Defensa Civil.</p>
    </div>}

    {rv?.stations && <AlertMap stations={rv.stations} onPick={id => { try { localStorage.setItem("dots-localidad", id); } catch { /* sin almacenamiento */ } setPickKey(k => k + 1); document.querySelector(".cp-local")?.scrollIntoView({ behavior: "smooth" }); }} />}

    {nino && <div className="cp-block">
      <h3>El Niño esta semana <small>NOAA CPC · semana del {dm(nino.week)} · anomalía contra 1991–2020</small></h3>
      <div className={res?.maps?.sst ? "cp-nino-wrap" : ""}>
      {res?.maps?.sst && <div><GibsImg m={res.maps.sst} alt="Anomalía de temperatura del mar en el Pacífico" />
        <div className="cp-scale"><span>más frío</span><i /><span>más cálido</span></div></div>}
      <div className="cp-nino">
        {nino.regions.map((r: Data) => <article key={r.id} className={r.id === "nino34" || r.id === "nino12" ? "main" : ""}>
          <span>{r.name}</span><b>{sign(r.anom)} °C</b><em>{r.phase}</em>
          <small>{r.change_4w != null ? `${sign(r.change_4w)} en 4 semanas` : ""}</small>
          {(r.id === "nino34" || r.id === "nino12") && <Spark values={nino.series[r.id]} />}
        </article>)}
      </div>
      </div>
      <p className="cp-note">Niño 3.4 es la referencia oficial. Niño 1+2 es el "Niño costero", frente a Perú y Ecuador. Cuando se calienta fuerte, suele anticipar más lluvia en el Litoral. {nino.note}</p>
    </div>}

    {hw && <div className="cp-block">
      <h3>Lluvia en las 21 subcuencas que aportan · próximos 15 días <small>{hw.models} · {hw.basins?.find((b: Data) => b.members)?.members || ""} corridas · mediana y probabilidad</small></h3>
      <div className="cp-groups">
        {GROUPS.map(g => { const bs = hw.basins.filter((b: Data) => b.group === g); if (!bs.length) return null;
          return <article key={g}><div className="cp-head"><b>{g}</b></div>
            <table className="cp-sub"><tbody>{bs.map((b: Data) => { const lv = al.find(a => a.basin === b.id)?.level;
              return <tr key={b.id}>
                <td><b>{b.name}</b><span>{b.where}</span></td>
                <td className="num">{b.status === "recibido" ? <><strong>{nf(b.median_mm)}</strong> mm<span>{b.ratio != null ? `${nf(b.ratio, 1)}× normal` : `${nf(b.p10_mm)}–${nf(b.p90_mm)}`}</span></> : "—"}</td>
                <td className="bar"><ProbBar label="≥100" value={b.p_ge100} /></td>
                <td>{lv && lv !== "Normal" ? <span className={`cp-chip ${LEVEL_TONE[lv]}`}>{lv}</span> : <span className="cp-chip ok">Normal</span>}</td>
              </tr>; })}</tbody></table>
          </article>; })}
      </div>
      <p className="cp-note">Cada subcuenca se representa con puntos del pronóstico dentro de ella; la lluvia es el promedio. "≥100" es la probabilidad de superar 100 mm en 15 días entre las {hw.basins?.find((b: Data) => b.members)?.members || 82} corridas.</p>
    </div>}

    {res?.maps && (res.maps.zone || res.maps.rain) && <div className="cp-block">
      <h3>Imágenes de la zona <small>NASA GIBS · día anterior · las nubes pueden tapar el suelo</small></h3>
      <div className="cp-maps2"><GibsImg m={res.maps.zone} alt="Imagen satelital de la zona en alerta" /><GibsImg m={res.maps.rain} alt="Lluvia satelital sobre la Cuenca del Plata" /></div>
    </div>}

    {dm2?.dams && <div className="cp-block">
      <h3>Represas de Brasil · agua medida <small>ONS (Operador Nacional do Sistema Elétrico) · datos abiertos diarios · m³/s</small></h3>
      <div className="cp-dams">
        {dm2.dams.map((d: Data) => <article key={d.id}>
          <div className="cp-head"><b>{d.name}</b><span>río {d.river}</span></div>
          {d.status === "recibido" ? <>
            <div className="cp-mm"><strong>{nf(d.outflow)}</strong><small> m³/s sueltos</small></div>
            <p className="cp-vs">Entran {nf(d.inflow)} · {d.change_7d_pct != null ? `${sign(d.change_7d_pct, 0)} % en 7 días` : ""}</p>
            {d.level && <span className={`cp-chip ${STATE_TONE(d.level)}`}>{d.level}{d.ratio != null ? ` · ${nf(d.ratio, 1)}× lo normal` : ""}</span>}
            <Spark values={d.series?.outflow || []} />
            <footer>{d.note} · dato del {dm(d.date)}</footer>
          </> : <p className="cp-note">Sin dato del ONS.</p>}
        </article>)}
      </div>
      <p className="cp-note">{dm2.note} Es la señal más temprana medida: lo que sueltan Salto Caxias e Itaipú llega a Cataratas y Posadas en uno o dos días.</p>
    </div>}

    {rv && <div className="cp-block">
      <h3>Cifras de referencia por localidad <small>Altura del río (INA, escalas de Prefectura) contra los niveles oficiales · caudal (GloFAS) contra lo normal · {rv.stations.length} localidades</small></h3>
      {RIVER_ORDER.map(rn => { const rows = rv.stations.filter((s: Data) => s.river === rn); if (!rows.length) return null;
        return <div className="cp-table-wrap cp-ref" key={rn}><table className="cp-table">
          <thead><tr><th>Río {rn}</th><th>Altura hoy</th><th>7 días</th><th>Aguas bajas</th><th>Alerta</th><th>Evacuación</th><th>Falta para alerta</th><th>Pronóstico INA</th><th>Récord 20 años</th><th>Caudal hoy · normal</th><th>Nivel</th></tr></thead>
          <tbody>{rows.map((s: Data) => { const i = s.ina || {}; const fc = (i.forecast || []).slice(-1)[0]; const lvl = s.danger || s.peak_danger;
            return <tr key={s.id}>
              <td><b>{s.place}</b>{i.gauge && <span className="cp-sub-note">{i.gauge}</span>}</td>
              <td className="strong">{m2(i.height)}{i.date && <span className="cp-sub-note">{dm(i.date)}</span>}</td>
              <td>{i.change_7d != null ? `${sign(i.change_7d, 2)} m` : "—"}</td>
              <td>{m2(i.low)}</td><td>{m2(i.alert)}</td><td>{m2(i.evac)}</td>
              <td>{i.to_alert != null ? (i.to_alert <= 0 ? <b className="cp-red">superado</b> : `${nf(i.to_alert, 2)} m`) : "—"}</td>
              <td>{fc ? <>{nf(fc.central, 2)} m<span className="cp-sub-note">{dm(fc.date)} · {nf(fc.min, 2)}–{nf(fc.max, 2)}</span></> : "—"}</td>
              <td>{s.height_record ? <>{m2(s.height_record.value)}<span className="cp-sub-note">{my(s.height_record.date)}</span></> : s.thresholds?.max ? <>{nf(s.thresholds.max)} m³/s<span className="cp-sub-note">{my(s.thresholds.max_date)}</span></> : "en cálculo"}</td>
              <td>{s.status === "recibido" ? <>{nf(s.discharge)}<span className="cp-sub-note">{s.normal != null ? `normal ${nf(s.normal)} · ${nf(s.ratio, 1)}×` : "normal en cálculo"}</span></> : "—"}</td>
              <td>{lvl ? <span className={`cp-chip ${LEVEL_TONE[lvl]}`}>{lvl}</span> : "—"}</td>
            </tr>; })}</tbody></table></div>; })}
      <p className="cp-note">Alturas en metros sobre el cero de cada escala (no son comparables entre puertos). Niveles de alerta y evacuación: oficiales, publicados por el INA para las escalas de la Prefectura. "Atención" = a menos de 1 m del nivel de alerta (2 m en el Iguazú y el Uruguay, que crecen más rápido). Pronóstico INA del {dm(rv.ina_forecast_issued)}: valor central y rango. Donde no hay escala del INA, el nivel sale del caudal: crecidas de 2, 5 y 20 años del propio río.</p>
    </div>}

    {rv?.travel && <div className="cp-block">
      <h3>¿Cuánto tarda en llegar el agua? <small>Desfase estadístico entre estaciones · GloFAS {rv.lags_period || "2001–2020"}</small></h3>
      <div className="cp-chains">
        {rv.travel.map((ch: Data) => <article key={ch.id}>
          <div className="cp-head"><b>{ch.name}</b>{ch.head_peak && <span>Pico de cabecera pronosticado: {dm(ch.head_peak)}</span>}</div>
          <ol>{ch.rows.map((r: Data, i: number) => <li key={r.id}>
            <i className={`cp-dot ${LEVEL_TONE[r.level_peak || r.level_now] || ""}`} />
            <div><b>{r.place}</b><span>{i === 0 ? "cabecera" : r.days_from_head != null ? `+${nf(r.days_from_head)} días${r.leg_corr != null ? ` · confianza ${r.leg_corr >= 0.6 ? "alta" : r.leg_corr >= 0.35 ? "media" : "baja"}` : ""}` : "en cálculo"}</span></div>
            <em>{r.arrival ? `llegaría ~${dm(r.arrival)}` : r.glofas_peak_date ? `pico GloFAS ${dm(r.glofas_peak_date)}` : ""}</em>
          </li>)}</ol>
        </article>)}
      </div>
      <p className="cp-note">El tiempo de cada tramo es el desfase en días en que lo que sube aguas arriba mejor se repite aguas abajo, medido en 20 años. La onda se atenúa al bajar y se suma con otros ríos: la fecha es orientativa. El pronóstico GloFAS de cada estación ya incluye ese recorrido.</p>
    </div>}

    {rv?.actions && <div className="cp-block">
      <h3>Qué hacer según el nivel <small>Umbrales: crecidas de 2, 5 y 20 años del propio río (los que usa GloFAS)</small></h3>
      <div className="cp-actions">
        {["Normal", "Atención", "Alerta", "Peligro"].map(l => <article key={l} className={`${LEVEL_TONE[l]} ${worst === l ? "now" : ""}`}>
          <b>{l}</b>{worst === l && <span>nivel más alto hoy en la cuenca</span>}
          <ul>{(rv.actions[l] || []).map((a: string) => <li key={a}>{a}</li>)}</ul>
        </article>)}
      </div>
      <p className="cp-note">Orientativo para el campo. Las alturas oficiales de alerta y evacuación de cada puerto las fijan la <a href="https://contenidosweb.prefecturanaval.gob.ar/alturas/" target="_blank" rel="noreferrer">Prefectura Naval</a> y el <a href="https://www.ina.gob.ar/alerta/" target="_blank" rel="noreferrer">INA</a>; ante una evacuación, seguí a Defensa Civil.</p>
    </div>}
    <div className="cp-block">
      <h3>Fuentes oficiales por país <small>Alturas, alertas y boletines que DOTS no reemplaza</small></h3>
      <div className="cp-countries">
        {OFFICIAL.map(([country, items]) => <article key={country}><b>{country}</b><ul>{items.map(([name, what, url]) => <li key={name}><a href={url} target="_blank" rel="noreferrer">{name}</a><span>{what}</span></li>)}</ul></article>)}
      </div>
    </div>
  </section>;
}
