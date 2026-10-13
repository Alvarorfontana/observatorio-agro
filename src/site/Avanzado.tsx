/**
 * DOTS · Clima avanzado de la localidad (portado y corregido de AgroClima v3).
 * Pronóstico de 16 días, comparador de dos localidades, viento en altura (ECMWF), potencial de tormentas severas
 * (CAPE, índice de levantamiento y cortante), calidad del aire (CAMS) y lavado de nitratos (ecuación de Burns, 1974).
 * Todo con Open-Meteo, sin clave, desde el navegador.
 */
import { useEffect, useRef, useState, type ReactNode } from "react";
import * as echarts from "echarts/core";
import { CULTIVOS } from "./Cultivos";
import { analizarFrentes, tono as tonoF, HOURLY as F_HOURLY, DAILY as F_DAILY, UMB } from "./frentes";

type Data = Record<string, any>;
const nf = (v: unknown, d = 0) => v == null || !Number.isFinite(Number(v)) ? "—" : Number(v).toLocaleString("es-AR", { minimumFractionDigits: d, maximumFractionDigits: d });
const dm = (iso: string) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;
const DIAS = ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"];
const dia = (iso: string) => `${DIAS[new Date(iso.slice(0, 10) + "T12:00:00").getDay()]} ${dm(iso)}`;
const TZ = "America%2FArgentina%2FBuenos_Aires";
const get = (u: string) => fetch(u, { signal: AbortSignal.timeout(30000) }).then(r => r.ok ? r.json() : Promise.reject(new Error(String(r.status))));
const max = (a: (number | null)[]) => { const v = a.filter((x): x is number => x != null); return v.length ? Math.max(...v) : null; };
const sum = (a: (number | null)[]) => a.reduce<number>((s, x) => s + (x ?? 0), 0);
const rumbo = (g: number | null) => g == null ? "—" : ["norte", "noreste", "este", "sudeste", "sur", "sudoeste", "oeste", "noroeste"][Math.round(((g % 360) + 360) % 360 / 45) % 8];

// ── tormentas severas: umbrales declarados (CAPE J/kg, cortante 10 m–500 hPa en km/h)
export function tormenta(cape: number | null, li: number | null, shear: number | null) {
  const c = cape ?? 0, s = shear ?? 0;
  let nivel = "Bajo", tone = "ok", txt = "Atmósfera estable o con poca energía para tormentas.";
  if (c >= 500 || (li != null && li <= -2)) { nivel = "Moderado"; tone = "warn"; txt = "Puede haber tormentas aisladas."; }
  if (c >= 1500 && s >= 55) { nivel = "Alto"; tone = "alert"; txt = "Energía y viento en altura suficientes para tormentas organizadas, con granizo y ráfagas."; }
  if (c >= 2500 && s >= 70) { nivel = "Muy alto"; tone = "risk"; txt = "Ingredientes de supercelda: granizo grande, ráfagas destructivas y, en casos, tornados."; }
  return { nivel, tone, txt };
}

// ── lavado de nitratos: balance de agua en la capa y ecuación de Burns (1974): f = [P / (P + θcc)]^h
export function lavadoNitratos(p: { lluvia: number[]; et0: number[]; kc: number; zcm: number; tcc: number; tact: number; nppm: number; dap: number; naporte: number }) {
  const zmm = p.zcm * 10;
  let deficit = Math.max(0, (p.tcc - p.tact) * zmm), drena = 0;
  const dias = p.lluvia.map((P, i) => {
    const etc = (p.et0[i] ?? 0) * p.kc;
    const neto = (P ?? 0) - etc;
    let d = 0;
    if (neto > 0) { const recarga = Math.min(deficit, neto); deficit -= recarga; d = neto - recarga; } else deficit = Math.min(p.tcc * zmm, deficit - neto);
    drena += d; return { P: P ?? 0, etc, d };
  });
  const nSuelo = p.nppm * p.dap * p.zcm * 0.1;                 // kg N/ha: ppm N-NO3 × densidad × espesor (cm) × 0,1
  const nTot = nSuelo + (p.naporte || 0);
  const Pcm = drena / 10;
  const f = Pcm > 0 ? (Pcm / (Pcm + p.tcc)) ** p.zcm : 0;
  return { dias, drenaje: drena, nSuelo, nTot, f, nLavado: nTot * f };
}

const TABS = [["d16", "Pronóstico 16 días"], ["presion", "Presión y frentes"], ["comp", "Comparar localidades"], ["viento", "Viento en altura"], ["tormentas", "Tormentas severas"], ["aire", "Calidad del aire"], ["nitratos", "Lavado de nitratos"]] as const;

export function Avanzado({ place, cultivo }: { place: Data; cultivo: string }) {
  const [tab, setTab] = useState("d16");
  return <section className="cult-sec cult-avz">
    <h3>Clima avanzado</h3>
    <div className="cult-tabs no-print">{TABS.map(([id, t]) => <button key={id} className={tab === id ? "on" : ""} onClick={() => setTab(id)}>{t}</button>)}</div>
    {tab === "d16" && <D16 place={place} />}
    {tab === "presion" && <Presion place={place} />}
    {tab === "comp" && <Comparar place={place} />}
    {tab === "viento" && <Viento place={place} />}
    {tab === "tormentas" && <Tormentas place={place} />}
    {tab === "aire" && <Aire place={place} />}
    {tab === "nitratos" && <Nitratos place={place} cultivo={cultivo} />}
  </section>;
}

function useData(u: string) {
  const [d, setD] = useState<Data | null>(null), [err, setErr] = useState("");
  useEffect(() => { setD(null); setErr(""); get(u).then(setD).catch(() => setErr("El servicio no respondió. Probá de nuevo en unos minutos.")); }, [u]);
  return { d, err, wait: !d && !err };
}
const Wait = ({ err }: { err: string }) => err ? <p className="cult-err">{err}</p> : <p className="cp-note">Consultando…</p>;

function T({ cab, filas }: { cab: string[]; filas: (string | ReactNode)[][] }) {
  return <div className="cult-table"><table><thead><tr>{cab.map(h => <th key={h}>{h}</th>)}</tr></thead><tbody>{filas.map((f, i) => <tr key={i}>{f.map((x, j) => <td key={j}>{x}</td>)}</tr>)}</tbody></table></div>;
}
const Chip = ({ t, tone }: { t: string; tone: string }) => <span className={`cult-chip ${tone}`}>{t}</span>;

function D16({ place }: { place: Data }) {
  const { d, err, wait } = useData(`https://api.open-meteo.com/v1/forecast?latitude=${place.lat}&longitude=${place.lon}&forecast_days=16&timezone=${TZ}&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max`);
  if (wait || !d) return <Wait err={err} />;
  const dd = d.daily;
  return <>
    <T cab={["Día", "Mín °C", "Máx °C", "Lluvia mm", "Prob. lluvia", "Viento máx km/h", ""]} filas={dd.time.map((f: string, i: number) => [dia(f), nf(dd.temperature_2m_min[i], 1), nf(dd.temperature_2m_max[i], 1), nf(dd.precipitation_sum[i], 1), `${nf(dd.precipitation_probability_max[i])} %`, nf(dd.wind_speed_10m_max[i]), i >= 7 ? <Chip t="tendencia" tone="warn" /> : ""])} />
    <p className="cp-note">Lluvia total en 16 días: {nf(sum(dd.precipitation_sum))} mm. Después del día 7 la incertidumbre crece mucho: usalo como tendencia, no para programar labores.</p>
  </>;
}

function Presion({ place }: { place: Data }) {
  const { d, err, wait } = useData(`https://api.open-meteo.com/v1/forecast?latitude=${place.lat}&longitude=${place.lon}&past_days=1&forecast_days=5&timezone=${TZ}&hourly=${F_HOURLY}&daily=${F_DAILY}`);
  const ref = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (!d || !ref.current) return;
    const h = d.hourly, ch = echarts.init(ref.current);
    const ser = (k: string) => h.time.map((t: string, i: number) => [t, h[k][i]]);
    ch.setOption({ grid: { left: 46, right: 46, top: 30, bottom: 28 }, tooltip: { trigger: "axis" }, legend: { top: 0, textStyle: { color: "#c9d6d9", fontSize: 11 } },
      xAxis: { type: "time", axisLabel: { color: "#9fb2b6", fontSize: 10 } },
      yAxis: [{ type: "value", scale: true, name: "hPa", nameTextStyle: { color: "#9fb2b6" }, axisLabel: { color: "#9fb2b6" }, splitLine: { lineStyle: { color: "rgba(255,255,255,.08)" } } },
              { type: "value", scale: true, name: "°C", nameTextStyle: { color: "#9fb2b6" }, axisLabel: { color: "#9fb2b6" }, splitLine: { show: false } }],
      series: [{ name: "Presión a nivel del mar", type: "line", showSymbol: false, data: ser("pressure_msl"), lineStyle: { color: "#43d6c5", width: 2 }, itemStyle: { color: "#43d6c5" },
                 markLine: { silent: true, symbol: "none", label: { color: "#9fb2b6", formatter: "ahora" }, lineStyle: { color: "#9fb2b6", type: "dashed" }, data: [{ xAxis: Date.now() }] } },
               { name: "Temperatura", type: "line", yAxisIndex: 1, showSymbol: false, data: ser("temperature_2m"), lineStyle: { color: "#f0a35e", width: 1.5 }, itemStyle: { color: "#f0a35e" } }] });
    const ro = new ResizeObserver(() => ch.resize()); ro.observe(ref.current);
    return () => { ro.disconnect(); ch.dispose(); };
  }, [d]);
  if (wait || !d) return <Wait err={err} />;
  const a = analizarFrentes(d);
  return <>
    <div className={`cult-alert ${tonoF(a.nivel)}`}><b>{a.nivel === "Normal" ? "Sin cambios bruscos a la vista en 5 días" : `${a.nivel}: ${a.eventos.map(e => e.tipo.toLowerCase()).join(", ")}`}</b>
      <p className="reco">Presión mínima prevista {nf(a.pmin, 1)} hPa ({a.pminCuando}). Mayor caída: {nf(a.caida3h, 1)} hPa en 3 h y {nf(a.caida24h, 1)} hPa en 24 h.</p></div>
    <div ref={ref} style={{ width: "100%", height: 240 }} />
    {a.eventos.length > 0 && <T cab={["Fenómeno", "Cuándo", "Qué se espera", "Nivel"]} filas={a.eventos.map(e => [e.tipo, e.cuando, e.texto, <Chip t={e.nivel} tone={tonoF(e.nivel)} />])} />}
    <p className="cp-note">Reglas declaradas sobre el pronóstico horario de Open-Meteo: caída de presión de {UMB.caida3h[0]} hPa en 3 h (atención) o {UMB.caida3h[1]} hPa (alerta); {UMB.caida24h} hPa en 24 h como señal de ciclogénesis a esta latitud; frente frío si la máxima baja {UMB.frente[0]} °C o más de un día al otro ({UMB.frente[1]} °C, alerta); ráfagas de {UMB.rafaga[0]} y {UMB.rafaga[1]} km/h; calor extremo con {UMB.calor.dias} días de máximas ≥ {UMB.calor.tmax} °C y mínimas ≥ {UMB.calor.tmin} °C. Es orientativo: <b>los avisos oficiales son del SMN</b>.</p>
  </>;
}

function Comparar({ place }: { place: Data }) {
  const [q, setQ] = useState(""), [b, setB] = useState<Data | null>(null), [opts, setOpts] = useState<Data[]>([]), [msg, setMsg] = useState("");
  const [res, setRes] = useState<Data[] | null>(null);
  const buscar = async () => {
    setMsg(""); setOpts([]);
    try { const j = await get("/api/fuentes/geocode?q=" + encodeURIComponent(q.trim())); const rows = (j.results || []).map((x: Data) => ({ lat: +x.lat, lon: +x.lon, name: String(x.display_name || "").split(",").slice(0, 2).join(",") }));
      if (!rows.length) setMsg("No encontré esa localidad."); else if (rows.length === 1) setB(rows[0]); else setOpts(rows);
    } catch { setMsg("El buscador no respondió."); }
  };
  useEffect(() => {
    if (!b) return; setRes(null);
    const u = (p: Data) => `https://api.open-meteo.com/v1/forecast?latitude=${p.lat}&longitude=${p.lon}&forecast_days=7&timezone=${TZ}&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,et0_fao_evapotranspiration,wind_speed_10m_max`;
    Promise.all([get(u(place)), get(u(b))]).then(rs => setRes(rs.map((r, i) => { const dd = r.daily; const ll = sum(dd.precipitation_sum), et = sum(dd.et0_fao_evapotranspiration);
      return { name: i ? b.name : place.name, ll, et, bal: ll - et, tmin: Math.min(...dd.temperature_2m_min), tmax: Math.max(...dd.temperature_2m_max), v: max(dd.wind_speed_10m_max), dLl: dd.precipitation_sum.filter((x: number) => x >= 1).length }; }))).catch(() => setMsg("Open-Meteo no respondió."));
  }, [b, place.lat, place.lon]);
  return <>
    <div className="cult-search no-print" style={{ maxWidth: 520 }}><input value={q} onChange={e => { setQ(e.target.value); setB(null); }} onKeyDown={e => e.key === "Enter" && void buscar()} placeholder="Segunda localidad para comparar" /><button onClick={() => void buscar()}>Buscar</button></div>
    {opts.length > 1 && !b && <span className="cult-places">{opts.map(o => <button key={o.name + o.lat} onClick={() => { setB(o); setOpts([]); }}>{o.name}</button>)}</span>}
    {msg && <p className="cult-err">{msg}</p>}
    {res && <T cab={["Próximos 7 días", res[0].name, res[1].name]} filas={[
      ["Lluvia", `${nf(res[0].ll)} mm`, `${nf(res[1].ll)} mm`], ["Días con lluvia", String(res[0].dLl), String(res[1].dLl)],
      ["Evapotranspiración (ET₀)", `${nf(res[0].et)} mm`, `${nf(res[1].et)} mm`], ["Balance", `${nf(res[0].bal)} mm`, `${nf(res[1].bal)} mm`],
      ["Mínima", `${nf(res[0].tmin, 1)} °C`, `${nf(res[1].tmin, 1)} °C`], ["Máxima", `${nf(res[0].tmax, 1)} °C`, `${nf(res[1].tmax, 1)} °C`], ["Viento máximo", `${nf(res[0].v)} km/h`, `${nf(res[1].v)} km/h`]]} />}
    {!b && !opts.length && <p className="cp-note">Buscá otra localidad o campo para comparar el pronóstico de la semana con {place.name}.</p>}
  </>;
}

function Viento({ place }: { place: Data }) {
  const { d, err, wait } = useData(`https://api.open-meteo.com/v1/ecmwf?latitude=${place.lat}&longitude=${place.lon}&forecast_days=3&timezone=${TZ}&hourly=wind_speed_10m,wind_speed_850hPa,wind_speed_700hPa,wind_speed_500hPa,wind_direction_850hPa,wind_direction_500hPa`);
  if (wait || !d) return <Wait err={err} />;
  const h = d.hourly;
  const dirMedia = (a: number[]) => { const v = a.filter(x => x != null); if (!v.length) return null; let sx = 0, sy = 0; v.forEach(g => { sx += Math.sin(g * Math.PI / 180); sy += Math.cos(g * Math.PI / 180); }); return (Math.atan2(sx, sy) * 180 / Math.PI + 360) % 360; };
  const fila = (n: string, v: number | null, dir: number | null, fuerte: number) => [n, `${nf(v)} km/h`, rumbo(dir), <Chip t={v == null ? "—" : v >= fuerte ? "Fuerte" : v >= fuerte * 0.65 ? "Moderado" : "Débil"} tone={v == null ? "ok" : v >= fuerte ? "risk" : v >= fuerte * 0.65 ? "warn" : "ok"} />];
  const v850 = max(h.wind_speed_850hPa);
  return <>
    <T cab={["Nivel", "Viento máximo en 3 días", "Viene del", "Lectura"]} filas={[
      fila("Superficie (10 m)", max(h.wind_speed_10m), null, 40), fila("850 hPa (≈ 1.500 m)", v850, dirMedia(h.wind_direction_850hPa), 60),
      fila("700 hPa (≈ 3.000 m)", max(h.wind_speed_700hPa), null, 80), fila("500 hPa (≈ 5.500 m)", max(h.wind_speed_500hPa), dirMedia(h.wind_direction_500hPa), 100)]} />
    <p className="cp-note">{v850 != null && v850 >= 60 ? "Hay un chorro intenso cerca de los 1.500 m: ráfagas fuertes en superficie y deriva alta; no conviene pulverizar ni hacer aplicaciones aéreas. " : ""}Modelo IFS de ECMWF (el mismo que usa Windy) vía Open-Meteo, en km/h. La dirección es de dónde viene el viento.</p>
  </>;
}

function Tormentas({ place }: { place: Data }) {
  const { d, err, wait } = useData(`https://api.open-meteo.com/v1/forecast?latitude=${place.lat}&longitude=${place.lon}&forecast_days=3&timezone=${TZ}&hourly=cape,lifted_index,wind_speed_10m,wind_direction_10m,wind_speed_500hPa,wind_direction_500hPa,precipitation`);
  if (wait || !d) return <Wait err={err} />;
  const h = d.hourly, dias: Record<string, number[]> = {};
  h.time.forEach((t: string, i: number) => (dias[t.slice(0, 10)] ||= []).push(i));
  const vec = (s: number, g: number) => [s * Math.sin(g * Math.PI / 180), s * Math.cos(g * Math.PI / 180)];
  const filas = Object.entries(dias).map(([f, idx]) => {
    const cape = max(idx.map(i => h.cape[i])), li = Math.min(...idx.map(i => h.lifted_index?.[i]).filter((x: number) => x != null));
    const shear = max(idx.map(i => { const a = vec(h.wind_speed_10m[i], h.wind_direction_10m[i]), b = vec(h.wind_speed_500hPa?.[i], h.wind_direction_500hPa?.[i]); return h.wind_speed_500hPa?.[i] == null ? null : Math.hypot(b[0] - a[0], b[1] - a[1]); }));
    const t = tormenta(cape, Number.isFinite(li) ? li : null, shear);
    return { f, cape, li: Number.isFinite(li) ? li : null, shear, ll: sum(idx.map(i => h.precipitation[i])), ...t };
  });
  const peor = [...filas].sort((a, b) => ["Bajo", "Moderado", "Alto", "Muy alto"].indexOf(b.nivel) - ["Bajo", "Moderado", "Alto", "Muy alto"].indexOf(a.nivel))[0];
  return <>
    {peor && <div className={`cult-alert ${peor.tone}`}><b>Potencial máximo: {peor.nivel.toLowerCase()} ({dia(peor.f)})</b><p className="reco">{peor.txt}</p></div>}
    <T cab={["Día", "Energía (CAPE) J/kg", "Índice de levantamiento", "Cortante 10 m–5.500 m km/h", "Lluvia mm", "Potencial"]} filas={filas.map(x => [dia(x.f), nf(x.cape), nf(x.li, 1), nf(x.shear), nf(x.ll, 1), <Chip t={x.nivel} tone={x.tone} />])} />
    <p className="cp-note">Ingredientes de las tormentas severas: energía disponible (CAPE; más de 1.500 J/kg es mucha), inestabilidad (índice de levantamiento negativo) y cambio del viento con la altura (cortante; más de 55 km/h organiza las tormentas). Es un aviso temprano de 12 a 72 h con reglas declaradas: <b>no reemplaza los alertas del SMN</b> ni el radar.</p>
  </>;
}

function Aire({ place }: { place: Data }) {
  const { d, err, wait } = useData(`https://air-quality-api.open-meteo.com/v1/air-quality?latitude=${place.lat}&longitude=${place.lon}&forecast_days=3&timezone=${TZ}&hourly=uv_index,pm2_5,pm10,ozone,aerosol_optical_depth`);
  if (wait || !d) return <Wait err={err} />;
  const h = d.hourly, dias: Record<string, number[]> = {};
  h.time.forEach((t: string, i: number) => (dias[t.slice(0, 10)] ||= []).push(i));
  const uvTxt = (u: number | null) => u == null ? ["—", "ok"] : u >= 11 ? ["Extremo", "risk"] : u >= 8 ? ["Muy alto", "risk"] : u >= 6 ? ["Alto", "alert"] : u >= 3 ? ["Moderado", "warn"] : ["Bajo", "ok"];
  const pmTxt = (p: number | null) => p == null ? ["—", "ok"] : p > 75 ? ["Muy malo", "risk"] : p > 37.5 ? ["Malo", "alert"] : p > 15 ? ["Regular", "warn"] : ["Bueno", "ok"];
  const filas = Object.entries(dias).map(([f, idx]) => {
    const uv = max(idx.map(i => h.uv_index[i])), pm = idx.map(i => h.pm2_5[i]).filter((x: number) => x != null), pmMed = pm.length ? sum(pm) / pm.length : null, o3 = max(idx.map(i => h.ozone[i]));
    const [u, ut] = uvTxt(uv), [p, pt] = pmTxt(pmMed);
    return [dia(f), nf(uv, 1), <Chip t={u} tone={ut} />, nf(pmMed, 1), <Chip t={p} tone={pt} />, nf(o3)];
  });
  return <>
    <T cab={["Día", "UV máximo", "Radiación UV", "PM2,5 µg/m³ (media)", "Humo y partículas", "Ozono máx µg/m³"]} filas={filas} />
    <p className="cp-note">Pronóstico CAMS (Copernicus) vía Open-Meteo. UV en la escala de la OMS: con 8 o más, trabajar a la sombra en las horas centrales y proteger trasplantes. PM2,5 alto suele indicar humo de incendios o quemas: cuidar a la gente y a la hacienda con problemas respiratorios. El ozono por encima de unos 120 µg/m³ sostenido puede dañar hojas de cultivos sensibles (soja, trigo).</p>
  </>;
}

function Inp({ l, v, s, st = 1, suf }: { l: string; v: number; s: (n: number) => void; st?: number; suf: string }) {
  return <label>{l}<span className="cult-num"><input type="number" step={st} value={Number.isFinite(v) ? v : ""} onChange={e => s(parseFloat(e.target.value))} /><em>{suf}</em></span></label>;
}
const TEXT: Record<string, [string, number]> = { arenoso: ["Arenoso", 0.15], franco_arenoso: ["Franco arenoso", 0.22], franco: ["Franco", 0.30], franco_limoso: ["Franco limoso", 0.33], franco_arcilloso: ["Franco arcilloso", 0.36], arcilloso: ["Arcilloso", 0.40] };
const KC: Record<string, number> = { maiz: 1.2, soja: 1.15, trigo: 1.15, girasol: 1.1, sorgo: 1.05, arroz: 1.2 };

function Nitratos({ place, cultivo }: { place: Data; cultivo: string }) {
  const { d, err, wait } = useData(`https://api.open-meteo.com/v1/forecast?latitude=${place.lat}&longitude=${place.lon}&past_days=7&forecast_days=7&timezone=${TZ}&daily=precipitation_sum,et0_fao_evapotranspiration,soil_moisture_0_to_7cm_mean`);
  const [nppm, setN] = useState<number>(NaN), [dap, setDap] = useState(1.25), [z, setZ] = useState(60), [tex, setTex] = useState("franco"), [nap, setNap] = useState(0), [kc, setKc] = useState(KC[cultivo] ?? 1.1), [tact, setTact] = useState<number>(NaN);
  if (wait || !d) return <Wait err={err} />;
  const dd = d.daily, tcc = TEXT[tex][1];
  const hoy = new Date().toISOString().slice(0, 10), k = Math.max(0, dd.time.findIndex((t: string) => t >= hoy));
  const smHoy = dd.soil_moisture_0_to_7cm_mean?.[k - 1] ?? null;
  const tA = Number.isFinite(tact) ? tact : smHoy != null ? Math.min(tcc, smHoy) : tcc;
  const r = Number.isFinite(nppm) ? lavadoNitratos({ lluvia: dd.precipitation_sum.slice(k), et0: dd.et0_fao_evapotranspiration.slice(k), kc, zcm: z, tcc, tact: tA, nppm, dap, naporte: nap }) : null;
  const nivel = r ? (r.f < 0.05 ? ["Bajo", "ok"] : r.f < 0.2 ? ["Moderado", "warn"] : r.f < 0.4 ? ["Alto", "alert"] : ["Muy alto", "risk"]) : null;
  return <>
    <div className="cult-grid cult-grid4">
      <Inp l="N de nitratos en el análisis" v={nppm} s={setN} st={0.5} suf="ppm N-NO₃" />
      <Inp l="Profundidad muestreada" v={z} s={setZ} suf="cm" />
      <label>Textura<select value={tex} onChange={e => setTex(e.target.value)}>{Object.entries(TEXT).map(([k2, [t]]) => <option key={k2} value={k2}>{t}</option>)}</select></label>
      <Inp l="Densidad aparente" v={dap} s={setDap} st={0.05} suf="g/cm³" />
      <Inp l="Fertilización prevista" v={nap} s={setNap} suf="kg N/ha" />
      <Inp l={`Coeficiente del cultivo (${CULTIVOS[cultivo].nombre.toLowerCase()})`} v={kc} s={setKc} st={0.05} suf="Kc" />
      <Inp l="Humedad actual (opcional)" v={tact} s={setTact} st={0.01} suf="m³/m³" />
    </div>
    {!r ? <p className="cp-note">Cargá el nitrógeno de nitratos de tu análisis de suelo para calcular el riesgo de la semana.</p> : <>
      <div className="cult-kpis" style={{ marginTop: 12 }}>
        <div><span>Nitrógeno en la capa</span><b>{nf(r.nTot)} kg N/ha</b><em>{nf(r.nSuelo)} del suelo{nap ? ` + ${nf(nap)} a aplicar` : ""}</em></div>
        <div><span>Agua que drena en 7 días</span><b>{nf(r.drenaje)} mm</b><em>por debajo de {z} cm</em></div>
        <div><span>Fracción que se lava</span><b>{nf(r.f * 100, 1)} %</b><em>ecuación de Burns</em></div>
        <div><span>Nitrógeno que se perdería</span><b className={r.f >= 0.2 ? "neg" : ""}>{nf(r.nLavado, 1)} kg N/ha</b><em>riesgo {nivel![0].toLowerCase()}</em></div>
      </div>
      <div className={`cult-alert ${nivel![1]}`} style={{ marginTop: 10 }}><b>Riesgo de lavado {nivel![0].toLowerCase()}</b><p className="reco">{r.f >= 0.2 ? "Conviene postergar la fertilización nitrogenada o fraccionarla hasta que pase la lluvia." : r.drenaje > 0 ? "Hay algo de drenaje, pero la pérdida esperada es chica." : "La lluvia de la semana no alcanza a llenar el perfil: no se espera lavado."}</p></div>
    </>}
    <p className="cp-note">Balance diario de agua en la capa (lluvia menos evapotranspiración del cultivo = ET₀ × Kc) con la capacidad de campo de la textura; lo que excede, drena. La fracción lavada sale de la ecuación de Burns (1974): f = [P / (P + θcc)]^h, con P el agua drenada en cm, θcc la capacidad de campo y h la profundidad en cm. Si no cargás la humedad actual, se usa la del modelo de Open-Meteo para los primeros 7 cm. Es una alerta, no una recomendación de fertilización.</p>
  </>;
}
