// Panel "Cuenca del Plata": El Niño semanal, lluvia en las cabeceras, ríos, tiempos de traslado y qué hacer.
import { useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";

type Data = Record<string, any>;
import { analizarFrentes, sudestada, SUDESTADA, tono as tonoF, HOURLY as F_HOURLY, DAILY as F_DAILY } from "./frentes";
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

// Colores del producto global de crecidas MODIS/VIIRS (NASA LANCE) tal como los sirve GIBS
const FLOOD_CLASSES: [string, string][] = [["#00e5ff", "Agua habitual"], ["#ffd400", "Anegamiento recurrente"], ["#ff1a1a", "Agua fuera de lo habitual"], ["#9e9e9e", "Sin dato (nubes o relieve)"]];

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

// Parte para WhatsApp: texto formal, sin emojis, con datos verificables y su fuente.
function shareText(s: Data, arrivals: Data[], actions: string[], wx?: Data | null) {
  const i = s.ina || {}; const lvl = levelOf(s) || "Sin dato"; const country = COUNTRY(s.id);
  const hoy = new Date().toLocaleDateString("es-AR", { day: "2-digit", month: "2-digit", year: "numeric" });
  const L: string[] = ["*DOTS · SISTEMA DE ALERTA DE CRECIDAS*", `*Parte de situación hidrométrica · ${s.place}* (río ${s.river})`, `Emitido el ${hoy}`, "", `*Nivel: ${lvl.toUpperCase()}*`, ""];
  if (i.height != null) {
    L.push(`Altura del río: *${nf(i.height, 2)} m* (lectura del ${dm(i.date)}${i.gauge ? `, ${i.gauge}` : ""})`);
    if (i.alert != null) L.push(`Nivel de alerta: ${nf(i.alert, 2)} m`);
    if (i.evac != null) L.push(`Nivel de evacuación: ${nf(i.evac, 2)} m`);
    if (i.to_alert != null) L.push(i.to_alert <= 0 ? `Situación: supera el nivel de alerta en ${nf(-i.to_alert, 2)} m${i.evac != null && i.height >= i.evac ? " y alcanzó el de evacuación" : ""}.` : `Situación: ${nf(i.to_alert, 2)} m por debajo del nivel de alerta.`);
    if (i.trend_m_day != null) L.push(`Tendencia de los últimos 7 días: ${i.trend_m_day > 0.005 ? `en ascenso, ${nf(i.trend_m_day * 100, 0)} cm por día` : i.trend_m_day < -0.005 ? `en descenso, ${nf(-i.trend_m_day * 100, 0)} cm por día` : "estable"}${i.days_to_alert ? `; de mantenerse, alcanzaría la alerta en unos ${i.days_to_alert} días` : ""}.`);
    const fc = (i.forecast || []).slice(-1)[0];
    if (fc) L.push(`Pronóstico oficial del INA al ${dm(fc.date)}: ${nf(fc.central, 2)} m (rango ${nf(fc.min, 2)} a ${nf(fc.max, 2)} m).`);
  } else {
    L.push(`Sin escala oficial en esta localidad. Caudal estimado (GloFAS): ${s.discharge != null ? `${nf(s.discharge)} m³/s${s.ratio != null ? `, ${nf(s.ratio, 1)} veces lo normal para la fecha` : ""}` : "sin dato"}.`);
  }
  if (arrivals.length) {
    L.push("", "*Aportes previstos desde las cabeceras*");
    arrivals.slice(0, 4).forEach(a => L.push(`- ${a.name} (${a.level.toLowerCase()}): repunte estimado entre el ${dm(a.window[0])} y el ${dm(a.window[1])}.`));
  }
  if (wx?.eventos?.length) {
    L.push("", `*Avisos meteorológicos, próximos 5 días (${wx.nivel.toLowerCase()})*`);
    wx.eventos.forEach((e: Data) => L.push(`- ${e.tipo} (${e.cuando}): ${e.texto}`));
  }
  if (actions.length) { L.push("", "*Recomendaciones*"); actions.slice(0, 4).forEach(t => L.push(`- ${t}`)); }
  L.push("", `*Teléfonos de emergencia (${country})*: ${EMERGENCY[country].slice(0, 3).map(([n, t]) => `${n} ${t}`).join(" · ")}`,
    "", `Informe completo en PDF: ${location.origin}/alertas`,
    `_Fuente: INA (escalas de Prefectura Naval), ECMWF, GFS y Copernicus GloFAS${wx?.eventos?.length ? "; avisos meteorológicos con reglas de DOTS sobre Open-Meteo (los oficiales son del SMN)" : ""}. Información orientativa: las órdenes de evacuación las emite Defensa Civil._`);
  return L.join("\n");
}

// Tarjeta en imagen (1080×1350): parte formal para compartir
function drawCard(s: Data, arrivals: Data[], wx?: Data | null): HTMLCanvasElement {
  const i = s.ina || {}; const lvl = levelOf(s) || "Sin dato"; const country = COUNTRY(s.id);
  const W = 1080, H = 1350, M = 72, cv = document.createElement("canvas"); cv.width = W; cv.height = H;
  const g = cv.getContext("2d")!; const col = LEVEL_COLOR[lvl] || "#667085";
  const F = (w: number, px: number) => `${w} ${px}px "IBM Plex Sans", Inter, system-ui, sans-serif`;
  const INK = "#101828", INK2 = "#344054", MUTED = "#667085", RULE = "#d0d5dd", NAVY = "#0b2b33";
  const hoy = new Date().toLocaleDateString("es-AR", { day: "2-digit", month: "2-digit", year: "numeric" });
  const text = (t: string, x: number, y: number, font: string, fill = INK, align: CanvasTextAlign = "left") => { g.font = font; g.fillStyle = fill; g.textAlign = align; g.fillText(t, x, y); g.textAlign = "left"; };
  const rule = (y: number, c = RULE, w = 2) => { g.fillStyle = c; g.fillRect(M, y, W - 2 * M, w); };
  g.fillStyle = "#ffffff"; g.fillRect(0, 0, W, H);
  // encabezado institucional
  g.fillStyle = NAVY; g.fillRect(0, 0, W, 132);
  text("DOTS · SISTEMA DE ALERTA DE CRECIDAS", M, 62, F(700, 26), "#ffffff");
  text("Parte de situación hidrométrica", M, 104, F(400, 28), "#b8c7cc");
  text(`Emitido el ${hoy}`, W - M, 104, F(400, 26), "#b8c7cc", "right");
  g.fillStyle = col; g.fillRect(0, 132, W, 10);
  // localidad y nivel
  const name = s.place.length > 22 ? s.place.slice(0, 22) + "…" : s.place;
  text(name, M, 236, F(700, 70));
  text(`Río ${s.river} · ${country}`, M, 284, F(400, 30), MUTED);
  g.strokeStyle = col; g.lineWidth = 4; g.strokeRect(W - M - 330, 178, 330, 118);
  text("NIVEL", W - M - 165, 218, F(600, 22), MUTED, "center");
  text(lvl.toUpperCase(), W - M - 165, 272, F(700, lvl.length > 8 ? 42 : 52), col, "center");
  rule(324);
  // tabla de cifras
  let y = 380;
  const row = (k: string, v: string, c = INK) => { text(k, M, y, F(400, 28), INK2); text(v, W - M, y, F(600, 30), c, "right"); y += 22; rule(y, "#eaecf0"); y += 40; };
  if (i.height != null) {
    row(`Altura del río (${dm(i.date)})`, `${nf(i.height, 2)} m`);
    if (i.alert != null) row("Nivel de alerta", `${nf(i.alert, 2)} m`, "#b54708");
    if (i.evac != null) row("Nivel de evacuación", `${nf(i.evac, 2)} m`, "#b42318");
    if (i.to_alert != null) row(i.to_alert <= 0 ? "Por encima de la alerta" : "Margen hasta la alerta", `${nf(Math.abs(i.to_alert), 2)} m`, i.to_alert <= 0 ? "#b42318" : INK);
    if (i.trend_m_day != null) row("Tendencia (7 días)", i.trend_m_day > 0.005 ? `+${nf(i.trend_m_day * 100, 0)} cm/día` : i.trend_m_day < -0.005 ? `−${nf(-i.trend_m_day * 100, 0)} cm/día` : "estable");
    const fc = (i.forecast || []).slice(-1)[0];
    if (fc) row(`Pronóstico INA al ${dm(fc.date)}`, `${nf(fc.central, 2)} m (${nf(fc.min, 2)}–${nf(fc.max, 2)})`);
    // gráfico sobrio
    const obs: Data[] = i.series || [], fcs: Data[] = i.forecast || [];
    if (obs.length > 1) {
      const top = y + 10, bot = Math.min(y + 300, 1080), L0 = M + 56, R0 = W - M;
      const all = [...obs.map(o => o.h), ...fcs.flatMap(f => [f.min, f.max]), i.alert, i.evac].filter((v: any) => v != null);
      const lo = Math.floor(Math.min(...all) - 0.3), hi = Math.ceil(Math.max(...all) + 0.3), n = obs.length + fcs.length;
      const X = (k: number) => L0 + (k / Math.max(1, n - 1)) * (R0 - L0), Y = (v: number) => bot - ((v - lo) / (hi - lo || 1)) * (bot - top);
      g.lineWidth = 1.5;
      for (let k = 0; k <= 4; k++) { const v = lo + (k * (hi - lo)) / 4; g.strokeStyle = "#eaecf0"; g.beginPath(); g.moveTo(L0, Y(v)); g.lineTo(R0, Y(v)); g.stroke(); text(nf(v, 1), L0 - 12, Y(v) + 8, F(400, 22), MUTED, "right"); }
      const hline = (v: number | null | undefined, c: string, dash: number[], lab: string) => { if (v == null) return; g.strokeStyle = c; g.lineWidth = 3; g.setLineDash(dash); g.beginPath(); g.moveTo(L0, Y(v)); g.lineTo(R0, Y(v)); g.stroke(); g.setLineDash([]); text(lab, R0, Y(v) - 10, F(600, 21), c, "right"); };
      hline(i.evac, "#b42318", [], "evacuación"); hline(i.alert, "#b54708", [12, 8], "alerta");
      const li = obs.length - 1;
      if (fcs.length) { g.strokeStyle = "#475467"; g.lineWidth = 4; g.setLineDash([10, 8]); g.beginPath(); g.moveTo(X(li), Y(obs[li].h)); fcs.forEach((f, k) => g.lineTo(X(li + 1 + k), Y(f.central))); g.stroke(); g.setLineDash([]); }
      g.strokeStyle = "#1f5f99"; g.lineWidth = 5; g.beginPath(); obs.forEach((o, k) => k ? g.lineTo(X(k), Y(o.h)) : g.moveTo(X(k), Y(o.h))); g.stroke();
      text(dm(obs[0].date), L0, bot + 34, F(400, 22), MUTED); text(dm((fcs.slice(-1)[0] || obs[li]).date), R0, bot + 34, F(400, 22), MUTED, "right");
      text("— altura medida (INA)   - - pronóstico INA", L0, bot + 70, F(400, 21), MUTED);
      y = bot + 110;
    }
  } else {
    row("Escala oficial", "no disponible");
    if (s.discharge != null) row("Caudal estimado (GloFAS)", `${nf(s.discharge)} m³/s`);
  }
  if (arrivals.length && y < 1120) {
    text("Aportes previstos desde las cabeceras", M, y, F(600, 26)); y += 38;
    arrivals.slice(0, 2).forEach(a => { text(`${a.name} (${a.level.toLowerCase()}): repunte entre el ${dm(a.window[0])} y el ${dm(a.window[1])}`, M, y, F(400, 24), INK2); y += 34; });
  }
  if (wx?.eventos?.length && y < 1150) {
    text("Avisos meteorológicos (5 días)", M, y, F(600, 26)); y += 36;
    wx.eventos.slice(0, Math.max(1, Math.floor((1170 - y) / 32))).forEach((e: Data) => { text(`${e.tipo} · ${e.cuando} · ${e.nivel.toLowerCase()}`, M, y, F(400, 24), e.nivel === "Alerta" ? "#b42318" : "#b54708"); y += 32; });
  }
  // pie: teléfonos y fuente
  rule(1190, INK, 2);
  text(`Emergencias (${country}): ${EMERGENCY[country].slice(0, 3).map(([n, t]) => `${n} ${t}`).join(" · ")}`, M, 1238, F(600, 26), INK);
  text("Fuente: INA (escalas de Prefectura Naval), ECMWF, GFS y Copernicus GloFAS.", M, 1280, F(400, 21), MUTED);
  text(`Información orientativa: las evacuaciones las dispone Defensa Civil · ${location.host}/alertas`, M, 1312, F(400, 21), MUTED);
  return cv;
}
async function shareCard(s: Data, arrivals: Data[], wx?: Data | null) {
  const cv = drawCard(s, arrivals, wx);
  const blob: Blob | null = await new Promise(r => cv.toBlob(b => r(b), "image/png"));
  if (!blob) return;
  const file = new File([blob], `alerta-${s.place.replace(/[^\w]+/g, "-")}.png`, { type: "image/png" });
  const nav: any = navigator;
  if (nav.canShare && nav.canShare({ files: [file] })) { try { await nav.share({ files: [file], title: `Alerta de crecida · ${s.place}`, text: `Parte de situación hidrométrica · ${s.place}: nivel ${levelOf(s) || "sin dato"}` }); return; } catch { /* cancelado */ } }
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = file.name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 4000);
}

// ¿Cómo está mi localidad?
function Locality({ stations, alerts, actions, weather }: { stations: Data[]; alerts: Data[]; actions: Data; weather?: Data | null }) {
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
  const wx: Data | null = weather?.stations?.[s.id] || null;
  const wa = `https://wa.me/?text=${encodeURIComponent(shareText(s, arrivals, act, wx))}`;
  return <div className="cp-block cp-local">
    <h3>¿Cómo está mi localidad? <small>Elegí tu ciudad: altura de hoy, niveles oficiales, tendencia y qué hacer</small></h3>
    <div className="cp-local-card">
      <div className="cp-local-head">
        <select value={s.id} onChange={e => pick(e.target.value)} aria-label="Elegí tu localidad">
          {RIVER_ORDER.map(rn => <optgroup key={rn} label={`Río ${rn}`}>{stations.filter(x => x.river === rn).map(x => <option key={x.id} value={x.id}>{x.place}{levelOf(x) && levelOf(x) !== "Normal" ? ` · ${levelOf(x)}` : ""}</option>)}</optgroup>)}
        </select>
        {lvl && <span className={`cp-big-level ${LEVEL_TONE[lvl]}`}>{lvl}</span>}
        <div className="cp-share">
          <a className="cp-pdf-local" href={`/api/fuentes/localidad-informe?id=${s.id}`} download>Informe de {s.place} · PDF</a>
          <a className="cp-wa" href={wa} target="_blank" rel="noreferrer">Enviar parte por WhatsApp</a>
          <button className="cp-img" onClick={() => void shareCard(s, arrivals, wx)}>Compartir imagen</button>
        </div>
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
      {wx && <div className={`cp-local-wx ${wx.nivel === "Alerta" ? "risk" : wx.nivel === "Atención" ? "alert" : "ok"}`}><b>Temporales y frentes · próximos 5 días</b>
        {wx.eventos.length ? wx.eventos.map((e: Data) => <p key={e.tipo}><span className={`cp-chip ${e.nivel === "Alerta" ? "risk" : "alert"}`}>{e.nivel}</span> <b>{e.tipo}</b> ({e.cuando}): {e.texto}</p>)
          : <p>Sin caídas bruscas de presión, frentes fríos, ráfagas fuertes ni calor extremo a la vista. Presión mínima prevista {Math.round(wx.pmin)} hPa.</p>}</div>}
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
  const mapRef = useRef<L.Map | null>(null);
  const floodRef = useRef<L.TileLayer.WMS | null>(null);
  const [gfm, setGfm] = useState<Data | null>(null);
  const [showFlood, setShowFlood] = useState(true);
  useEffect(() => {
    fetch("/api/fuentes/gfm-capas", { signal: AbortSignal.timeout(30000) }).then(r => r.json()).then(j => { if (j.status === "recibido") setGfm(j.data); }).catch(() => { /* sin GFM */ });
  }, []);
  useEffect(() => {
    if (!ref.current) return;
    const map = L.map(ref.current, { scrollWheelZoom: false, attributionControl: true }).setView([-28.5, -57.5], 5);
    mapRef.current = map;
    // Fondo: mapa con relieve, ríos, rutas y ciudades; o satélite con nombres encima
    const esri = (svc: string) => `https://server.arcgisonline.com/ArcGIS/rest/services/${svc}/MapServer/tile/{z}/{y}/{x}`;
    const topo = L.tileLayer(esri("World_Topo_Map"), { maxZoom: 16, attribution: "Esri, HERE, Garmin, USGS, © OpenStreetMap" });
    const sat = L.layerGroup([
      L.tileLayer(esri("World_Imagery"), { maxZoom: 17, attribution: "Esri, Maxar, Earthstar Geographics" }),
      L.tileLayer(esri("Reference/World_Boundaries_and_Places"), { maxZoom: 17 }),
    ]);
    topo.addTo(map);
    L.control.layers({ "Mapa": topo, "Satélite": sat }, undefined, { position: "topright", collapsed: false }).addTo(map);
    // Nombres: siempre los que están en atención o peor; todos al acercar
    const showAll = () => ref.current?.classList.toggle("cp-labels-all", map.getZoom() >= 7);
    map.on("zoomend", showAll);
    map.createPane("flood"); map.getPane("flood")!.style.zIndex = "350";
    const pts: L.LatLngExpression[] = [];
    stations.forEach(s => {
      if (s.lat == null) return;
      const lvl = levelOf(s) || "Normal"; const i = s.ina || {};
      const m = L.circleMarker([s.lat, s.lon], { radius: lvl === "Normal" ? 6 : 9, color: "#fff", weight: 2, fillColor: LEVEL_COLOR[lvl] || "#98a2b3", fillOpacity: 0.95 }).addTo(map);
      m.bindPopup(`<b>${s.place}</b> · río ${s.river}<br>${lvl}${i.height != null ? ` · ${nf(i.height, 2)} m (alerta ${nf(i.alert, 2)})` : ""}`);
      m.bindTooltip(s.place, { permanent: true, direction: "right", offset: [8, 0], className: `cp-lbl${lvl === "Normal" ? " cp-lbl-normal" : ""}` });
      if (onPick) m.on("click", () => onPick(s.id));
      pts.push([s.lat, s.lon]);
    });
    if (pts.length) map.fitBounds(L.latLngBounds(pts).pad(0.15));
    showAll();
    return () => { map.remove(); mapRef.current = null; floodRef.current = null; };
  }, [stations]);
  // Agua de crecida de Copernicus GFM: el navegador pide el mapa directo a EODC
  useEffect(() => {
    const map = mapRef.current;
    floodRef.current?.remove(); floodRef.current = null;
    if (!map || !gfm?.flood || !showFlood) return;
    const opts: any = { layers: gfm.flood, format: "image/png", transparent: true, opacity: 0.85, pane: "flood", attribution: "Copernicus GFM (EMS) · EODC" };
    if (gfm.date) opts.time = gfm.date;
    floodRef.current = L.tileLayer.wms(gfm.wms, opts).addTo(map);
  }, [gfm, showFlood, stations]);
  return <div className="cp-block">
    <h3>Mapa de alertas <small>34 localidades pintadas por nivel · acercá para ver todos los nombres · tocá un punto para ver el detalle</small></h3>
    <div className="cp-mapbox"><div ref={ref} className="cp-leaflet" /><div className="cp-map-legend">{["Normal", "Atención", "Alerta", "Evacuación"].map(l => <span key={l}><i style={{ background: LEVEL_COLOR[l] }} />{l}</span>)}</div></div>
    {gfm?.flood && <p className="cp-note"><label style={{ cursor: "pointer" }}><input type="checkbox" checked={showFlood} onChange={e => setShowFlood(e.target.checked)} /> Mostrar agua de crecida detectada por radar (Copernicus GFM{gfm.date ? `, ${dm(gfm.date)}` : ""})</label>. Acercá el mapa para verla: marca el agua fuera de su lugar habitual a 20 m de resolución.</p>}
  </div>;
}

// Portada: crecidas en vivo (INA) con gráfico de cuánto del nivel de alerta alcanzó cada puerto
const go = (to: string) => (e: React.MouseEvent) => { e.preventDefault(); history.pushState({}, "", to); dispatchEvent(new PopStateEvent("popstate")); scrollTo(0, 0); };
export function AlertasPortada() {
  const [d, setD] = useState<Data | null>(null), [err, setErr] = useState(false);
  useEffect(() => {
    let live = true;
    fetch("/api/fuentes/alertas-resumen").then(r => r.json()).then(j => { if (live) j.status === "recibido" ? setD(j.data) : setErr(true); }).catch(() => live && setErr(true));
    return () => { live = false; };
  }, []);
  const c = d?.counts || {};
  const head = !d ? (err ? "Sistema de Alerta de Crecidas" : "Consultando los ríos…")
    : c["Evacuación"] ? `Crecida: ${c["Evacuación"]} ${c["Evacuación"] === 1 ? "localidad" : "localidades"} en evacuación${c.Alerta ? ` y ${c.Alerta} en alerta` : ""}.`
    : c.Alerta ? `Crecida: ${c.Alerta} ${c.Alerta === 1 ? "localidad" : "localidades"} en alerta${c["Atención"] ? ` y ${c["Atención"]} en atención` : ""}.`
    : c["Atención"] ? `Ríos en atención en ${c["Atención"]} ${c["Atención"] === 1 ? "localidad" : "localidades"}.` : "Ríos sin alertas por ahora.";
  const tone = c["Evacuación"] ? "risk" : c.Alerta ? "alert" : c["Atención"] ? "warn" : "ok";
  const top: Data[] = (d?.stations || []).slice(0, 8);
  const max = Math.max(130, ...top.map(r => r.evac && r.alert ? Math.round(100 * r.evac / r.alert) + 10 : 0), ...top.map(r => (r.pct_alert || 0) + 5));
  const last = d?.stations?.map((r: Data) => r.date).sort().slice(-1)[0];
  return <section className={`ap ap-${tone}`} aria-label="Crecidas en vivo">
    <div className="ap-copy">
      <span className="ap-kicker"><i /> EN VIVO · CRECIDAS DE LA CUENCA DEL PLATA</span>
      <h2>{head}</h2>
      <p>Altura de los ríos Paraná, Paraguay, Uruguay e Iguazú contra los niveles oficiales de alerta y evacuación, lluvia que viene en Brasil, Paraguay y Bolivia, y cuándo llegaría el agua a cada localidad.</p>
      {d && <div className="ap-counts">
        {[["Evacuación", "risk"], ["Alerta", "alert"], ["Atención", "warn"], ["Normal", "ok"]].map(([l, t]) => <span key={l} className={t}><b>{c[l] || 0}</b>{l === "Normal" ? "normales" : l.toLowerCase()}</span>)}
        <span className="rise"><b>{d.rising}</b>subiendo</span>
      </div>}
      {d?.weather && ((d.weather.counts?.Alerta || 0) + (d.weather.counts?.["Atención"] || 0) > 0 || d.weather.sudestada?.nivel !== "Normal") && <p className="ap-wx">
        <b>Avisos meteorológicos:</b> {(d.weather.counts?.Alerta || 0) + (d.weather.counts?.["Atención"] || 0)} localidades con temporal, frente o calor en 5 días{d.weather.top?.length ? ` (${d.weather.top.slice(0, 3).map((w: Data) => `${w.place}: ${w.eventos.map((e: Data) => e.tipo.toLowerCase()).join(", ")}`).join("; ")})` : ""}{d.weather.sudestada && d.weather.sudestada.nivel !== "Normal" ? `. Sudestada en el Río de la Plata (${d.weather.sudestada.nivel.toLowerCase()}), ${d.weather.sudestada.desde} a ${d.weather.sudestada.hasta}` : ""}.</p>}
      <div className="ap-actions">
        <a href="/alertas" onClick={go("/alertas")} className="primary">Ver el Sistema de Alerta de Crecidas →</a>
        <a href="/alertas" onClick={go("/alertas")}>¿Cómo está mi localidad?</a>
        <a href="/api/fuentes/cuenca-informe" download>Informe PDF ↓</a>
      </div>
    </div>
    <div className="ap-chart">
      <div className="ap-chart-head"><b>Cuánto del nivel de alerta alcanzó cada puerto</b><span>altura de hoy · INA, escalas de Prefectura{last ? ` · ${dm(last)}` : ""}</span></div>
      {top.length ? <ul>
        {top.map(r => { const ev = r.evac && r.alert ? (100 * r.evac) / r.alert : null;
          return <li key={r.id}>
            <span className="ap-name"><b>{r.place}</b><small>río {r.river}</small></span>
            <span className="ap-bar">
              <i className={`fill ${LEVEL_TONE[r.level] || "ok"}`} style={{ width: `${Math.min(100, (100 * (r.pct_alert || 0)) / max)}%` }} />
              <i className="mk mk-alert" style={{ left: `${(100 * 100) / max}%` }} title="nivel de alerta" />
              {ev && <i className="mk mk-evac" style={{ left: `${(100 * ev) / max}%` }} title="nivel de evacuación" />}
            </span>
            <span className="ap-val"><b>{nf(r.height, 2)} m</b><small>alerta {nf(r.alert, 2)}{r.trend_m_day != null ? ` · ${r.trend_m_day > 0.005 ? "↑" : r.trend_m_day < -0.005 ? "↓" : "→"}` : ""}</small></span>
          </li>; })}
      </ul> : <p className="ap-wait">{err ? "El INA no respondió. Abrí el sistema de alertas para ver el resto de los datos." : "Cargando alturas del INA…"}</p>}
      <div className="ap-legend"><span><i className="mk-alert" /> nivel de alerta</span><span><i className="mk-evac" /> nivel de evacuación</span></div>
    </div>
  </section>;
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

// Tránsito de una crecida entre dos puertos (desfases medios de 20 años)
function Transito({ stations }: { stations: Data[] }) {
  const [a, setA] = useState("parana-corrientes"), [b, setB] = useState("parana-rosario"), [r, setR] = useState<Data | null>(null), [busy, setBusy] = useState(false);
  const calc = async () => {
    setBusy(true); setR(null);
    try { setR(await (await fetch(`/api/fuentes/transito-crecida?desde=${a}&hasta=${b}`)).json()); } catch { setR({ error: "No se pudo calcular." }); }
    setBusy(false);
  };
  const opts = (id: string, set: (v: string) => void) => <select value={id} onChange={e => { set(e.target.value); setR(null); }}>{RIVER_ORDER.map(rn => <optgroup key={rn} label={`Río ${rn}`}>{stations.filter(x => x.river === rn).map(x => <option key={x.id} value={x.id}>{x.place}</option>)}</optgroup>)}</select>;
  const d = r?.data;
  return <div className="cp-block">
    <h3>¿Cuándo llega la crecida? <small>Elegí un puerto de origen y uno río abajo · desfase medio entre puertos</small></h3>
    <div className="cp-transit"><label>Desde {opts(a, setA)}</label><label>Hasta {opts(b, setB)}</label><button className="cult-go" onClick={() => void calc()} disabled={busy}>{busy ? "Calculando…" : "Calcular"}</button></div>
    {r && (r.status !== "recibido" ? <p className="cp-note">{r.error || "Sin dato."}</p> : <>
      <p className="cp-transit-res">Lo que hoy pasa por <b>{d.desde}</b> llega a <b>{d.hasta}</b> en {d.dias == null ? <b>— (hay tramos todavía en cálculo)</b> : <b>{d.dias < 0.5 ? "el mismo día" : `unos ${nf(d.dias)} días`}</b>}.</p>
      <div className="cp-table-wrap"><table className="cp-table"><thead><tr><th>Tramo</th><th>Días</th><th>Ajuste</th></tr></thead><tbody>
        {d.tramos.map((t: Data) => <tr key={t.desde + t.hasta}><td>{t.desde} → {t.hasta}</td><td>{t.dias == null ? "en cálculo" : nf(t.dias)}</td><td>{t.corr == null ? "—" : t.corr >= 0.7 ? "firme" : t.corr >= 0.5 ? "aceptable" : "débil"}</td></tr>)}
      </tbody></table></div>
      <p className="cp-note">Desfase que maximiza la correlación entre los caudales diarios de cada par de puertos ({d.periodo || "20 años"}). Es un promedio: con el río muy alto la onda puede viajar distinto, y las represas cambian los tiempos. Orientativo.</p>
    </>)}
  </div>;
}

// Ciclones activos y alertas de la ONU en los países de la cuenca
function Extremos() {
  const [d, setD] = useState<Data | null>(null), [err, setErr] = useState("");
  useEffect(() => { fetch("/api/fuentes/eventos-extremos?lat=-28.5&lon=-58.5", { signal: AbortSignal.timeout(40000) }).then(r => r.json()).then(j => j.status === "recibido" ? setD(j.data) : setErr(j.error || "Sin datos")).catch(() => setErr("No respondió")); }, []);
  return <div className="cp-block">
    <h3>Eventos extremos en la región <small>Ciclones activos (NOAA IBTrACS) y alertas de desastres de la ONU (GDACS)</small></h3>
    {err && <p className="cp-note">Las fuentes internacionales no respondieron ahora: {err}.</p>}
    {!d && !err && <p className="cp-note">Consultando NOAA y GDACS…</p>}
    {d && <>
      {d.near.length ? <div className="cp-table-wrap"><table className="cp-table"><thead><tr><th>Sistema</th><th>Categoría</th><th>Viento</th><th>Distancia al Litoral</th><th>Última posición</th></tr></thead><tbody>
        {d.near.map((x: Data) => <tr key={x.id}><td>{x.name}</td><td>{x.category}</td><td>{x.wind_kmh ? `${nf(x.wind_kmh)} km/h` : "—"}</td><td>{nf(x.distance_km)} km</td><td>{x.time.slice(0, 16)} UTC</td></tr>)}</tbody></table></div>
        : <p className="cp-note">No hay ciclones activos a menos de 2.500 km. {d.cyclones.length ? `En el mundo hay ${d.cyclones.length} activos, todos lejos.` : ""}</p>}
      {d.gdacs.length ? <ul className="cp-gdacs">{d.gdacs.map((g: Data) => <li key={g.link + g.title}><span className={`cp-chip ${g.level === "Rojo" ? "risk" : g.level === "Naranja" ? "alert" : "ok"}`}>{g.level}</span> <b>{g.type}</b> · {g.countries.join(", ")} · <a href={g.link} target="_blank" rel="noreferrer">{g.title}</a></li>)}</ul>
        : <p className="cp-note">GDACS no tiene alertas activas en Argentina, Uruguay, Paraguay, Brasil, Bolivia ni Chile.</p>}
      <p className="cp-note">IBTrACS se actualiza varias veces por semana, no al minuto; GDACS casi en tiempo real. Para avisos oficiales en Argentina: SMN y Defensa Civil.</p>
    </>}
  </div>;
}

// Temporales y frentes en las 34 localidades (presión, frentes fríos, ráfagas y calor)
const ORD_W = { Alerta: 0, "Atención": 1, Normal: 2 } as Record<string, number>;
const wxRows = (w: Data) => (Object.values(w.stations || {}) as Data[]).map((x: Data) => ({ s: { id: x.id, place: x.place, river: x.river }, a: { ...x, pminCuando: x.pmin_cuando } }))
  .sort((x: Data, y: Data) => ORD_W[x.a.nivel] - ORD_W[y.a.nivel] || x.a.pmin - y.a.pmin);
function Temporales({ stations, weather }: { stations: Data[]; weather?: Data | null }) {
  const [rows, setRows] = useState<Data[] | null>(weather?.stations ? wxRows(weather) : null), [err, setErr] = useState(""), [all, setAll] = useState(false);
  useEffect(() => {
    if (weather?.stations) { setRows(wxRows(weather)); return; }
    const st = stations.filter(s => s.lat != null);
    const u = `https://api.open-meteo.com/v1/forecast?latitude=${st.map(s => s.lat).join(",")}&longitude=${st.map(s => s.lon).join(",")}&past_days=1&forecast_days=5&timezone=America%2FArgentina%2FBuenos_Aires&hourly=${F_HOURLY}&daily=${F_DAILY}`;
    fetch(u, { signal: AbortSignal.timeout(40000) }).then(r => r.ok ? r.json() : Promise.reject()).then(j => {
      const arr = Array.isArray(j) ? j : [j];
      const ord = { Alerta: 0, "Atención": 1, Normal: 2 } as Record<string, number>;
      setRows(st.map((s, i) => ({ s, a: analizarFrentes(arr[i]) })).sort((x, y) => ord[x.a.nivel] - ord[y.a.nivel] || x.a.pmin - y.a.pmin));
    }).catch(() => setErr("Open-Meteo no respondió."));
  }, [stations, weather]);
  const con = rows?.filter(r => r.a.nivel !== "Normal") || [];
  const ver = all ? rows || [] : con;
  return <div className="cp-block">
    <h3>Temporales y frentes <small>Presión, cambios bruscos de temperatura, ráfagas y calor · próximos 5 días en las 34 localidades</small></h3>
    {err && <p className="cp-note">{err}</p>}
    {!rows && !err && <p className="cp-note">Analizando el pronóstico hora por hora…</p>}
    {rows && <>
      <p className="cp-transit-res">{con.length ? <><b>{con.length} {con.length === 1 ? "localidad" : "localidades"}</b> con avisos de temporal o frente en los próximos días.</> : "Sin temporales ni frentes bruscos a la vista en los próximos 5 días."}</p>
      {ver.length > 0 && <div className="cp-table-wrap"><table className="cp-table"><thead><tr><th>Localidad</th><th>Nivel</th><th>Qué se espera</th><th>Presión mínima</th></tr></thead><tbody>
        {ver.map(({ s, a }) => <tr key={s.id}><td>{s.place}<small className="cp-sub-note">río {s.river}</small></td><td><span className={`cp-chip ${tonoF(a.nivel) === "risk" ? "risk" : tonoF(a.nivel) === "warn" ? "alert" : ""}`}>{a.nivel}</span></td>
          <td style={{ whiteSpace: "normal" }}>{a.eventos.length ? a.eventos.map((e: Data) => <div key={e.tipo}><b>{e.tipo}</b> ({e.cuando}): {e.texto}</div>) : "—"}</td><td>{Math.round(a.pmin)} hPa<small className="cp-sub-note">{a.pminCuando}</small></td></tr>)}
      </tbody></table></div>}
      <button className="cp-more" onClick={() => setAll(v => !v)}>{all ? "Ver sólo las que tienen aviso" : "Ver las 34 localidades"}</button>
      <p className="cp-note">Reglas declaradas sobre el pronóstico de Open-Meteo: caída de presión de 3 hPa o más en 3 horas (5 o más, alerta) y de 14 hPa en 24 horas (ciclogénesis explosiva a estas latitudes); frente frío si la máxima baja 8 °C o más de un día al otro (12 o más, alerta); ráfagas de 60 km/h o más (80, alerta); calor extremo con 3 días seguidos de máxima de 35 °C y mínima de 22 °C o más. Orientativo: los avisos oficiales son los del SMN.</p>
    </>}
  </div>;
}

function Sudestada({ data }: { data?: Data | null }) {
  const [a, setA] = useState<Data | null>(data || null), [err, setErr] = useState("");
  useEffect(() => {
    if (data) { setA(data); return; }
    const [la, lo] = SUDESTADA.punto;
    fetch(`https://api.open-meteo.com/v1/forecast?latitude=${la}&longitude=${lo}&forecast_days=5&timezone=America%2FArgentina%2FBuenos_Aires&hourly=wind_speed_10m,wind_direction_10m,wind_gusts_10m`, { signal: AbortSignal.timeout(30000) })
      .then(r => r.ok ? r.json() : Promise.reject()).then(j => setA(sudestada(j))).catch(() => setErr("Open-Meteo no respondió."));
  }, [data]);
  return <div className="cp-block">
    <h3>Sudestada en el Río de la Plata <small>Viento del sudeste que sube el agua en la costa y frena la salida del Paraná y el Uruguay · próximos 5 días</small></h3>
    {err && <p className="cp-note">{err}</p>}
    {!a && !err && <p className="cp-note">Analizando el viento sobre el estuario…</p>}
    {a && <p className="cp-transit-res"><span className={`cp-chip ${tonoF(a.nivel) === "risk" ? "risk" : tonoF(a.nivel) === "warn" ? "alert" : ""}`}>{a.nivel}</span> {a.horas ? <b>{a.desde} a {a.hasta}. </b> : null}{a.texto}</p>}
    <p className="cp-note">Regla declarada sobre el viento pronosticado en el centro del Río de la Plata: {SUDESTADA.horas} horas seguidas o más de viento del este al sur de {SUDESTADA.viento[0]} km/h es atención; de {SUDESTADA.viento[1]} km/h, o con ráfagas de {SUDESTADA.rafaga} km/h, alerta. No calcula la altura del agua: la pronostica el <a href="https://www.hidro.gob.ar/oceanografia/alturashorarias.asp" target="_blank" rel="noreferrer">Servicio de Hidrografía Naval</a>, que es la fuente oficial.</p>
  </div>;
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
  const wxSt: Data[] = Object.values(res?.weather?.stations || {}), wxOn = wxSt.filter(w => w.nivel !== "Normal"), sud = res?.weather?.sudestada;
  const levels: string[] = [...(rv?.stations || []).flatMap((s: Data) => [s.danger, s.peak_danger]), ...al.map(a => a.level), ...wxSt.map(w => w.nivel), sud?.nivel].filter(Boolean);
  const worst = ["Peligro", "Alerta", "Atención", "Normal"].find(l => levels.map(x => x === "Evacuación" ? "Peligro" : x).includes(l));

  return <section className="cp" aria-label="Cuenca del Plata">
    <div className="cp-intro">
      <span className="section-tag">DOTS · SISTEMA DE ALERTA DE CRECIDAS · CUENCA DEL PLATA</span>
      <h2>Sistema de Alerta de Crecidas</h2>
      <p className="cp-sub">De la lluvia en Brasil, Paraguay y Bolivia a la crecida en tu costa: Iguazú, Paraná, Paraguay, Bermejo y Uruguay.</p>
      <a className="cp-pdf" href="/api/fuentes/cuenca-informe" download>Informe general de la cuenca · PDF ↓</a>
      <p>Las crecidas del Paraná y del Uruguay nacen en las cabeceras: el sur de Brasil, el Alto Paraná y el Pantanal. El Niño carga de lluvia esa zona en primavera y verano. Acá se sigue la cadena completa: el océano, la lluvia que viene, los ríos hoy y cuánto tarda el agua en llegar.</p>
    </div>
    {err && <p className="rp-error">{err} No se muestran valores supuestos.</p>}
    {!res && !err && <p className="cp-loading">Consultando NOAA, ECMWF, GFS y GloFAS…</p>}

    {rv?.stations && <Summary stations={rv.stations} />}
    {rv?.stations && <Locality key={pickKey} stations={rv.stations} alerts={al} actions={rv.actions} weather={res?.weather} />}
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
      {(wxOn.length > 0 || (sud && sud.nivel !== "Normal")) && <div className="cp-wx-strip"><b>Avisos meteorológicos</b>
        {sud && sud.nivel !== "Normal" && <p><span className={`cp-chip ${sud.nivel === "Alerta" ? "risk" : "alert"}`}>{sud.nivel}</span> <b>Sudestada en el Río de la Plata</b> ({sud.desde} a {sud.hasta}): {sud.texto}</p>}
        {wxOn.sort((x, y) => ORD_W[x.nivel] - ORD_W[y.nivel]).slice(0, 6).map(w => <p key={w.id}><span className={`cp-chip ${w.nivel === "Alerta" ? "risk" : "alert"}`}>{w.nivel}</span> <b>{w.place}</b>: {w.eventos.map((e: Data) => `${e.tipo.toLowerCase()} (${e.cuando})`).join(", ")}</p>)}
        {wxOn.length > 6 && <p className="cp-note">Y {wxOn.length - 6} localidades más: ver "Temporales y frentes".</p>}
      </div>}
      <p className="cp-note">Qué hacer en cada nivel: ver "Qué hacer según el nivel" más abajo. Cómo se calcula: probabilidad de superar 100 y 200 mm en 15 días y lluvia contra la normal de la época. Si el río de salida ya viene alto o las represas sueltan mucho, la alerta sube un escalón. La ventana de llegada suma la respuesta típica de cada cuenca y los días de traslado aguas abajo. Es orientativo: no reemplaza las alertas del INA, la Prefectura ni Defensa Civil.</p>
    </div>}

    {rv?.stations && <AlertMap stations={rv.stations} onPick={id => { try { localStorage.setItem("dots-localidad", id); } catch { /* sin almacenamiento */ } setPickKey(k => k + 1); document.querySelector(".cp-local")?.scrollIntoView({ behavior: "smooth" }); }} />}
    {rv?.stations && <Transito stations={rv.stations} />}
    {rv?.stations && <Temporales stations={rv.stations} weather={res?.weather} />}
      <Sudestada data={res?.weather?.sudestada} />
    <Extremos />

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
      <div className="cp-maps2"><GibsImg m={res.maps.zone} alt="Imagen satelital de la zona en alerta" /><GibsImg m={res.maps.flood} alt="Agua detectada por satélite en los últimos 3 días" /><GibsImg m={res.maps.rain} alt="Lluvia satelital sobre la Cuenca del Plata" /></div>
      {res.maps.flood && <div className="cp-swatches" aria-label="Leyenda del mapa de crecidas">{FLOOD_CLASSES.map(([c, l]) => <span key={l}><i style={{ background: c }} />{l}</span>)}</div>}
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
