/**
 * DOTS · Informe de cultivo (módulo agrícola, basado en AgroClima v3).
 * Por localidad, cultivo y fecha de siembra (incluye las alertas de la página de alertas de AgroClima): lluvia y evapotranspiración de los últimos 30 días y los próximos 7,
 * temperaturas con umbral de helada del cultivo, grados día desde la siembra, alertas y carilla interpretativa.
 * Datos: Open-Meteo (ERA5 + modelos de pronóstico), consultados desde el navegador. Sin datos simulados.
 */
import { useEffect, useRef, useState } from "react";
import * as echarts from "echarts/core";
import { Labores } from "./Labores";

type Data = Record<string, any>;
const nf = (v: unknown, d = 0) => v == null || !Number.isFinite(Number(v)) ? "—" : Number(v).toLocaleString("es-AR", { minimumFractionDigits: d, maximumFractionDigits: d });
const dm = (iso: string) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;
const dmS = dm;
const lista = (xs: string[]) => xs.length === 1 ? xs[0] : `${xs.slice(0, -1).join(", ")} y ${xs[xs.length - 1]}`;

export const CULTIVOS: Record<string, { nombre: string; tbase: number; helada: number }> = {
  maiz: { nombre: "Maíz", tbase: 10, helada: 2 },
  soja: { nombre: "Soja", tbase: 10, helada: 2 },
  trigo: { nombre: "Trigo", tbase: 0, helada: -2 },
  girasol: { nombre: "Girasol", tbase: 6, helada: 0 },
  sorgo: { nombre: "Sorgo", tbase: 10, helada: 2 },
  arroz: { nombre: "Arroz", tbase: 12, helada: 5 },
};
const UMBRAL = { calor: 35, calorFuerte: 38, lluvia: 30, lluviaFuerte: 50, deficit: -20, exceso: 40, viento: 30, hongosHR: 85, vpd: 2.5 };

type Alerta = { nivel: "Peligro" | "Alerta" | "Atención" | "Normal"; titulo: string; texto: string; reco: string };

export function analizar(d: Data, cultivo: string, siembra: string, hoy = new Date().toISOString().slice(0, 10)) {
  const c = CULTIVOS[cultivo];
  const t: string[] = d.daily.time;
  const P: number[] = d.daily.precipitation_sum, E: number[] = d.daily.et0_fao_evapotranspiration;
  const TX: number[] = d.daily.temperature_2m_max, TN: number[] = d.daily.temperature_2m_min;
  const k = Math.max(0, t.findIndex(x => x >= hoy));
  const sum = (a: number[], i: number, j: number) => a.slice(i, j).reduce((s, v) => s + (v ?? 0), 0);
  const obs = { lluvia: sum(P, Math.max(0, k - 30), k), et0: sum(E, Math.max(0, k - 30), k) };
  const fut = { lluvia: sum(P, k, t.length), et0: sum(E, k, t.length),
    tmin: Math.min(...TN.slice(k).filter(v => v != null)), tmax: Math.max(...TX.slice(k).filter(v => v != null)) };
  const bal30 = obs.lluvia - obs.et0, bal7 = fut.lluvia - fut.et0;
  // grados día desde la siembra (o desde hace 30 días si no hay fecha), con la temperatura base del cultivo
  const desde = siembra && siembra <= t[t.length - 1] ? siembra : t[Math.max(0, k - 30)];
  let acc = 0; const gdd: { fecha: string; v: number; pron: boolean }[] = [];
  t.forEach((f, i) => { if (f >= desde && TX[i] != null && TN[i] != null) { acc += Math.max(0, (TX[i] + TN[i]) / 2 - c.tbase); gdd.push({ fecha: f, v: Math.round(acc), pron: i >= k }); } });
  const gddHoy = gdd.filter(g => !g.pron).slice(-1)[0]?.v ?? 0, gddFin = gdd.slice(-1)[0]?.v ?? 0;
  const sinceArchive = siembra && siembra < t[0];
  const al: Alerta[] = [];
  if (fut.tmin < c.helada) al.push({ nivel: fut.tmin < c.helada - 2 ? "Peligro" : "Alerta", titulo: "Helada", texto: `Mínima pronosticada de ${nf(fut.tmin, 1)} °C el ${lista(t.slice(k).filter((_, j) => TN[k + j] < c.helada).map(dm))}; el umbral de daño para ${c.nombre.toLowerCase()} es ${c.helada} °C.`, reco: "Seguir el pronóstico diario y evitar labores que expongan el cultivo; evaluar el estado después del evento." });
  if (fut.tmax >= UMBRAL.calorFuerte) al.push({ nivel: "Alerta", titulo: "Calor extremo", texto: `Máxima pronosticada de ${nf(fut.tmax, 1)} °C el ${lista(t.slice(k).filter((_, j) => TX[k + j] >= UMBRAL.calorFuerte).map(dm))}.`, reco: "Riesgo de estrés térmico, más grave en floración. Priorizar el agua disponible." });
  else if (fut.tmax >= UMBRAL.calor) al.push({ nivel: "Atención", titulo: "Temperaturas altas", texto: `Máxima pronosticada de ${nf(fut.tmax, 1)} °C.`, reco: "Monitorear el estrés térmico en las horas de más calor." });
  if (fut.lluvia >= UMBRAL.lluviaFuerte) al.push({ nivel: "Alerta", titulo: "Lluvia abundante", texto: `${nf(fut.lluvia)} mm pronosticados en 7 días.`, reco: "Riesgo de anegamiento y de piso para la maquinaria. Revisar drenajes y caminos." });
  else if (fut.lluvia >= UMBRAL.lluvia) al.push({ nivel: "Atención", titulo: "Lluvia importante", texto: `${nf(fut.lluvia)} mm pronosticados en 7 días.`, reco: "Planificar las labores en torno a la ventana de lluvia." });
  if (bal30 <= UMBRAL.deficit && bal7 <= 0) al.push({ nivel: bal30 <= 2 * UMBRAL.deficit ? "Alerta" : "Atención", titulo: "Déficit de agua", texto: `En 30 días llovieron ${nf(obs.lluvia)} mm contra ${nf(obs.et0)} mm de demanda atmosférica (balance ${nf(bal30)} mm), y la semana que viene no lo compensa.`, reco: "Revisar la humedad del perfil antes de sembrar o fertilizar." });
  if (bal30 >= UMBRAL.exceso) al.push({ nivel: "Atención", titulo: "Exceso de agua", texto: `Balance de 30 días de +${nf(bal30)} mm.`, reco: "Suelos saturados: cuidar el tránsito de maquinaria y los bajos." });
  // días del pronóstico con cada condición (fechas exactas)
  const fdias = (pred: (i: number) => boolean) => t.slice(k).map((f, j) => pred(k + j) ? dmS(f) : null).filter(Boolean) as string[];
  const W: number[] = d.daily.wind_speed_10m_max || [], HX: number[] = d.daily.relative_humidity_2m_max || [], HN: number[] = d.daily.relative_humidity_2m_min || [];
  const ventoso = fdias(i => (W[i] ?? 0) >= UMBRAL.viento);
  if (ventoso.length) al.push({ nivel: "Atención", titulo: "Viento fuerte", texto: `Viento máximo de ${UMBRAL.viento} km/h o más el ${lista(ventoso)} (pico de ${nf(Math.max(...W.slice(k)))} km/h).`, reco: "Evitar pulverizar esos días por deriva; buscar ventanas de viento calmo, temprano a la mañana." });
  const lluviosos = t.slice(k).filter((_, j) => (P[k + j] ?? 0) > 1).length;
  const humedos = fdias(i => (HX[i] ?? 0) >= UMBRAL.hongosHR && (P[i] ?? 0) > 1);
  if (lluviosos >= 3 && humedos.length >= 2) al.push({ nivel: "Atención", titulo: "Riesgo de enfermedades fúngicas", texto: `${lluviosos} días con lluvia y humedad alta (más de ${UMBRAL.hongosHR} %) el ${lista(humedos)}: ambiente favorable para hongos foliares.`, reco: "Monitorear royas y manchas foliares; evaluar un fungicida preventivo según el estado del cultivo." });
  // VPD de la tarde: temperatura máxima con la humedad mínima del día
  const vpd = (i: number) => { const T = TX[i], H = HN[i]; if (T == null || H == null) return 0; const es = 0.6108 * Math.exp(17.27 * T / (T + 237.3)); return es * (1 - H / 100); };
  const secos = fdias(i => vpd(i) >= UMBRAL.vpd);
  if (secos.length) al.push({ nivel: "Atención", titulo: "Aire muy seco (VPD alto)", texto: `Déficit de presión de vapor de la tarde de ${nf(UMBRAL.vpd, 1)} kPa o más el ${lista(secos)} (máximo ${nf(Math.max(...t.slice(k).map((_, j) => vpd(k + j))), 1)} kPa).`, reco: "Las plantas cierran estomas y frenan el crecimiento; si coincide con floración, el riesgo para el rinde es mayor." });
  const fuego = fdias(i => (TX[i] ?? 0) >= 30 && (HN[i] ?? 100) <= 30 && (W[i] ?? 0) >= 25 && (P[i] ?? 0) < 1);
  if (fuego.length) al.push({ nivel: "Alerta", titulo: "Condiciones de incendio", texto: `Calor (30 °C o más), aire seco (humedad de 30 % o menos) y viento (25 km/h o más) sin lluvia el ${lista(fuego)}.`, reco: "No hacer quemas; preparar cortafuegos y avisar a bomberos ante cualquier foco." });
  if (!al.length) al.push({ nivel: "Normal", titulo: "Sin alertas", texto: "No hay heladas, calor extremo ni lluvias fuertes en el pronóstico de 7 días.", reco: "Seguir el calendario planificado." });
  const orden = ["Peligro", "Alerta", "Atención", "Normal"];
  al.sort((a, b) => orden.indexOf(a.nivel) - orden.indexOf(b.nivel));
  return { c, k, t, obs, fut, bal30, bal7, gdd, gddHoy, gddFin, desde, sinceArchive, alertas: al };
}

function Chart({ option, height = 240 }: { option: Data; height?: number }) {
  const ref = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (!ref.current) return;
    const ch = echarts.init(ref.current, undefined, { renderer: "canvas" });
    ch.setOption(option);
    const ro = new ResizeObserver(() => ch.resize()); ro.observe(ref.current);
    return () => { ro.disconnect(); ch.dispose(); };
  }, [option]);
  return <div ref={ref} style={{ width: "100%", height }} />;
}

const TONE: Record<string, string> = { Normal: "ok", "Atención": "warn", Alerta: "alert", Peligro: "risk" };

export function CultivosPanel() {
  const [q, setQ] = useState(""), [places, setPlaces] = useState<Data[]>([]), [place, setPlace] = useState<Data | null>(null);
  const [lote, setLote] = useState(""), [cultivo, setCultivo] = useState("soja"), [siembra, setSiembra] = useState("");
  const [busy, setBusy] = useState(""), [err, setErr] = useState(""), [res, setRes] = useState<Data | null>(null);

  const buscar = async () => {
    setErr(""); setPlaces([]);
    const m = q.match(/(-?\d+(?:\.\d+)?)[,\s]+(-?\d+(?:\.\d+)?)/);
    if (m) { setPlace({ lat: +m[1], lon: +m[2], name: `${m[1]}, ${m[2]}` }); return; }
    if (q.trim().length < 2) { setErr("Escribí una localidad o coordenadas."); return; }
    setBusy("Buscando la localidad…");
    try {
      const r = await fetch("/api/fuentes/geocode?q=" + encodeURIComponent(q.trim()), { signal: AbortSignal.timeout(20000) });
      const j = await r.json();
      const rows = (j.results || []).map((x: Data) => ({ lat: +x.lat, lon: +x.lon, name: String(x.display_name || "").split(",").slice(0, 3).join(",") }));
      if (!rows.length) setErr("No encontré esa localidad. Probá con otro nombre o con coordenadas (lat, lon).");
      else if (rows.length === 1) setPlace(rows[0]); else setPlaces(rows);
    } catch { setErr("El buscador no respondió. Probá de nuevo o escribí coordenadas."); }
    setBusy("");
  };

  const generar = async () => {
    if (!place) { setErr("Primero elegí la localidad."); return; }
    setErr(""); setBusy("Consultando Open-Meteo…"); setRes(null);
    try {
      const today = new Date().toISOString().slice(0, 10);
      const past = siembra && siembra < today ? Math.min(92, Math.ceil((Date.parse(today) - Date.parse(siembra)) / 864e5) + 1) : 31;
      const u = `https://api.open-meteo.com/v1/forecast?latitude=${place.lat}&longitude=${place.lon}&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,et0_fao_evapotranspiration,wind_speed_10m_max,relative_humidity_2m_mean,relative_humidity_2m_max,relative_humidity_2m_min&past_days=${Math.max(31, past)}&forecast_days=7&timezone=America%2FArgentina%2FBuenos_Aires`;
      const r = await fetch(u, { signal: AbortSignal.timeout(30000) });
      if (!r.ok) throw new Error();
      const d = await r.json();
      setRes({ d, a: analizar(d, cultivo, siembra, today), place, lote: lote.trim() || "Lote sin nombre", cultivo, siembra, today });
    } catch { setErr("Open-Meteo no respondió. Probá de nuevo en unos minutos."); }
    setBusy("");
  };

  return <div className="cultivos">
    <section className="cp-block cult-form no-print">
      <h3>Generador de informe <small>Elegí la localidad, el cultivo y la fecha de siembra · datos en vivo de Open-Meteo</small></h3>
      <div className="cult-grid">
        <label>Localidad o coordenadas
          <span className="cult-search"><input value={q} onChange={e => { setQ(e.target.value); setPlace(null); }} onKeyDown={e => e.key === "Enter" && void buscar()} placeholder="Ej.: Bella Vista, Corrientes · o -28.5, -59.05" /><button onClick={() => void buscar()}>Buscar</button></span>
          {place && <em>Seleccionada: {place.name}</em>}
          {places.length > 1 && !place && <span className="cult-places">{places.map(p => <button key={p.name + p.lat} onClick={() => { setPlace(p); setPlaces([]); }}>{p.name}</button>)}</span>}
        </label>
        <label>Nombre del campo o lote<input value={lote} onChange={e => setLote(e.target.value)} placeholder="Ej.: Lote Norte" /></label>
        <label>Cultivo<select value={cultivo} onChange={e => setCultivo(e.target.value)}>{Object.entries(CULTIVOS).map(([k, v]) => <option key={k} value={k}>{v.nombre}</option>)}</select></label>
        <label>Fecha de siembra<input type="date" value={siembra} onChange={e => setSiembra(e.target.value)} /><em>Opcional: para los grados día desde la siembra</em></label>
      </div>
      <div className="cult-actions">
        <button className="cult-go" onClick={() => void generar()} disabled={!!busy}>Generar informe</button>
        {res && <button className="cult-pdf" onClick={() => window.print()}>Descargar PDF</button>}
        {busy && <span className="cp-note">{busy}</span>}
        {err && <span className="cult-err">{err}</span>}
      </div>
    </section>
    {res && <Informe r={res} />}
  </div>;
}

function Informe({ r }: { r: Data }) {
  const { a, d, place, lote, today } = r; const c = a.c;
  const fechas: string[] = d.daily.time, k = a.k;
  const lab = fechas.map(dm);
  const fc = (i: number) => i >= k;
  const markFc = { silent: true, itemStyle: { color: "rgba(122,90,248,.07)" }, data: [[{ xAxis: lab[k] }, { xAxis: lab[lab.length - 1] }]] };
  const base = { grid: { left: 44, right: 16, top: 28, bottom: 28 }, tooltip: { trigger: "axis" }, legend: { top: 0, textStyle: { fontSize: 11 } },
    xAxis: { type: "category", data: lab, axisLabel: { fontSize: 10 } } };
  const lluvia = { ...base, yAxis: { type: "value", name: "mm", nameTextStyle: { fontSize: 10 } },
    series: [{ name: "Lluvia", type: "bar", data: d.daily.precipitation_sum.map((v: number, i: number) => ({ value: v, itemStyle: { color: fc(i) ? "#7a5af8" : "#1f5f99" } })), markArea: markFc },
             { name: "Evapotranspiración (ET₀)", type: "line", data: d.daily.et0_fao_evapotranspiration, symbol: "none", lineStyle: { color: "#dc6803", width: 2 }, itemStyle: { color: "#dc6803" } }] };
  const temp = { ...base, yAxis: { type: "value", name: "°C", nameTextStyle: { fontSize: 10 } },
    series: [{ name: "Máxima", type: "line", data: d.daily.temperature_2m_max, symbol: "none", lineStyle: { color: "#d92d20" }, itemStyle: { color: "#d92d20" }, markArea: markFc },
             { name: "Mínima", type: "line", data: d.daily.temperature_2m_min, symbol: "none", lineStyle: { color: "#1f5f99" }, itemStyle: { color: "#1f5f99" },
               markLine: { symbol: "none", silent: true, lineStyle: { color: "#1f5f99", type: "dashed" }, label: { formatter: `helada ${c.nombre.toLowerCase()} ${c.helada} °C`, fontSize: 10 }, data: [{ yAxis: c.helada }] } }] };
  const gdd = { ...base, xAxis: { ...base.xAxis, data: a.gdd.map((g: Data) => dm(g.fecha)) }, yAxis: { type: "value", name: "°C·día", nameTextStyle: { fontSize: 10 } },
    series: [{ name: `Grados día (base ${c.tbase} °C)`, type: "line", areaStyle: { color: "rgba(3,152,85,.12)" }, symbol: "none", lineStyle: { color: "#039855" }, itemStyle: { color: "#039855" },
               data: a.gdd.map((g: Data) => g.v) }] };
  const hum = { ...base, yAxis: [{ type: "value", name: "%", max: 100, nameTextStyle: { fontSize: 10 } }, { type: "value", name: "km/h", nameTextStyle: { fontSize: 10 } }],
    series: [{ name: "Humedad relativa media", type: "line", data: d.daily.relative_humidity_2m_mean, symbol: "none", lineStyle: { color: "#0f9fa6" }, itemStyle: { color: "#0f9fa6" }, markArea: markFc },
             { name: "Viento máximo", type: "line", yAxisIndex: 1, data: d.daily.wind_speed_10m_max, symbol: "none", lineStyle: { color: "#667085" }, itemStyle: { color: "#667085" } }] };
  const worst = ["Peligro", "Alerta", "Atención", "Normal"].find(l => a.alertas.some((x: Alerta) => x.nivel === l)) || "Normal";
  const carilla = [
    `En los últimos 30 días llovieron ${nf(a.obs.lluvia)} mm frente a ${nf(a.obs.et0)} mm de evapotranspiración de referencia: balance de ${a.bal30 >= 0 ? "+" : ""}${nf(a.bal30)} mm${a.bal30 <= UMBRAL.deficit ? ", con el perfil probablemente secándose" : a.bal30 >= UMBRAL.exceso ? ", con suelos probablemente saturados" : ""}.`,
    `Para los próximos 7 días se esperan ${nf(a.fut.lluvia)} mm, con temperaturas entre ${nf(a.fut.tmin, 1)} y ${nf(a.fut.tmax, 1)} °C.`,
    r.siembra ? `Desde la siembra del ${dm(r.siembra)} el ${c.nombre.toLowerCase()} acumuló ${nf(a.gddHoy)} grados día (base ${c.tbase} °C); con el pronóstico llegaría a ${nf(a.gddFin)} en una semana.${a.sinceArchive ? " La siembra es anterior a los 92 días disponibles: el acumulado arranca más tarde y subestima el total." : ""}`
      : `Sin fecha de siembra: los grados día se cuentan desde el ${dm(a.desde)} (${nf(a.gddHoy)} acumulados a hoy, base ${c.tbase} °C).`,
  ];
  return <article className="cult-report">
    <header className={`cult-band ${TONE[worst]}`}>
      <div><small>DOTS · INFORME DE CULTIVO</small><h2>{place.name}</h2><p>{c.nombre} · {lote}{r.siembra ? ` · siembra ${dm(r.siembra)}` : ""}</p></div>
      <div className="cult-band-lvl"><small>SITUACIÓN</small><b>{worst === "Normal" ? "SIN ALERTAS" : worst.toUpperCase()}</b></div>
    </header>
    <p className="cp-note">Informe del {dm(today)}/{today.slice(0, 4)} · {nf(place.lat, 3)}, {nf(place.lon, 3)} · datos observados hasta ayer y pronóstico a 7 días.</p>
    <div className="cult-kpis">
      <div><span>Lluvia 30 días</span><b>{nf(a.obs.lluvia)} mm</b><em>ET₀ {nf(a.obs.et0)} mm</em></div>
      <div><span>Balance 30 días</span><b className={a.bal30 <= UMBRAL.deficit ? "neg" : ""}>{a.bal30 >= 0 ? "+" : ""}{nf(a.bal30)} mm</b><em>lluvia menos ET₀</em></div>
      <div><span>Lluvia próximos 7 días</span><b>{nf(a.fut.lluvia)} mm</b><em>balance {a.bal7 >= 0 ? "+" : ""}{nf(a.bal7)} mm</em></div>
      <div><span>Mín. y máx. pronosticadas</span><b>{nf(a.fut.tmin, 1)} / {nf(a.fut.tmax, 1)} °C</b><em>helada {c.nombre.toLowerCase()}: {c.helada} °C</em></div>
      <div><span>Grados día</span><b>{nf(a.gddHoy)}</b><em>{r.siembra ? "desde la siembra" : `desde el ${dm(a.desde)}`} · base {c.tbase} °C</em></div>
    </div>
    <section className="cult-sec"><h3>Lectura de la situación</h3>{carilla.map((t, i) => <p key={i}>{t}</p>)}</section>
    <section className="cult-sec"><h3>Alertas y recomendaciones</h3>
      {a.alertas.map((x: Alerta) => <div key={x.titulo} className={`cult-alert ${TONE[x.nivel]}`}><b>{x.nivel === "Normal" ? x.titulo : `${x.nivel}: ${x.titulo}`}</b><p>{x.texto}</p><p className="reco">Recomendación: {x.reco}</p></div>)}
    </section>
    <section className="cult-sec cult-charts">
      <div><h4>Lluvia y evapotranspiración</h4><Chart option={lluvia} /></div>
      <div><h4>Temperaturas</h4><Chart option={temp} /></div>
      <div><h4>Grados día acumulados</h4><Chart option={gdd} /></div>
      <div><h4>Humedad y viento</h4><Chart option={hum} /></div>
    </section>
    <Labores place={place} cultivo={r.cultivo} />
    <p className="cp-note">Sombreado violeta: pronóstico. Fuente: Open-Meteo (ERA5 y modelos de pronóstico), CC-BY 4.0. Grados día: (máxima + mínima) / 2 − temperatura base del cultivo. La ET₀ es la demanda de una pastura de referencia, no el consumo real del cultivo. Basado en AgroClima v3. Información orientativa: no reemplaza el monitoreo a campo.</p>
  </article>;
}
