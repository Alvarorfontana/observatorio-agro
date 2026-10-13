/**
 * DOTS · Labores y riesgos del lote (portado de AgroClima v3, informes especializados).
 * Pulverización (delta T, viento, humedad, lluvia), siembra (suelo 0–7 cm), cosecha y secado,
 * peligro de incendio con el índice FWI canadiense (fórmulas CFS 1992), lavado de agroquímicos
 * a 48 h y heladas de los últimos 30 años. Datos de Open-Meteo (pronóstico y ERA5).
 */
import { useEffect, useState } from "react";
import { CULTIVOS } from "./Cultivos";

type Data = Record<string, any>;
const nf = (v: unknown, d = 0) => v == null || !Number.isFinite(Number(v)) ? "—" : Number(v).toLocaleString("es-AR", { minimumFractionDigits: d, maximumFractionDigits: d });
const dm = (iso: string) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;
const DIAS = ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"];
const dia = (iso: string) => `${DIAS[new Date(iso + "T12:00:00").getDay()]} ${dm(iso)}`;

export const ESP = {
  pulverizacion: { vientoIdeal: 20, vientoMax: 30, hrMin: 40, hrMax: 85, dtIdealMin: 2, dtIdealMax: 8, dtMax: 10, lluviaProb: 30 },
  siembra: { tempSueloExtra: 2, humMin: 0.15, humMax: 0.45, lluviaProb: 60 },
  cosecha: { hrMax: 70, vientoMin: 5, lluviaProb: 30 },
  lavado: { foliar: 10, herbicida: 20, suelo: 30 } as Record<string, number>,
};

// ── índice FWI canadiense (Van Wagner 1987 / CFS). Largo efectivo del día para el DMC (Le, horas) y factor de
// largo del día para el DC (Lf) de las tablas oficiales, corridos seis meses para el hemisferio sur.
const LE: Record<number, number> = { 1: 12.4, 2: 10.9, 3: 9.4, 4: 8.0, 5: 7.0, 6: 6.0, 7: 6.5, 8: 7.5, 9: 9.0, 10: 12.8, 11: 13.9, 12: 13.9 };
const LF: Record<number, number> = { 1: 6.4, 2: 5.0, 3: 2.4, 4: 0.4, 5: -1.6, 6: -1.6, 7: -1.6, 8: -1.6, 9: -1.6, 10: 0.9, 11: 3.8, 12: 5.8 };
export type FwiEstado = { ffmc: number; dmc: number; dc: number };
export function fwiDia(e: FwiEstado, d: { t: number; rh: number; wind: number; rain: number; mes: number }) {
  const T = Math.max(-1.1, d.t), H = Math.min(100, Math.max(0, d.rh)), W = Math.max(0, d.wind), rf = d.rain;
  let m = 147.2 * (101 - e.ffmc) / (59.5 + e.ffmc);
  if (rf > 0.5) {
    const r = rf - 0.5;
    let mr = m + 42.5 * r * Math.exp(-100 / (251 - m)) * (1 - Math.exp(-6.93 / r));
    if (m > 150) mr += 0.0015 * (m - 150) ** 2 * Math.sqrt(r);
    m = Math.min(mr, 250);
  }
  const ed = 0.942 * H ** 0.679 + 11 * Math.exp((H - 100) / 10) + 0.18 * (21.1 - T) * (1 - Math.exp(-0.115 * H));
  const ew = 0.618 * H ** 0.753 + 10 * Math.exp((H - 100) / 10) + 0.18 * (21.1 - T) * (1 - Math.exp(-0.115 * H));
  if (m > ed) { const ko = 0.424 * (1 - (H / 100) ** 1.7) + 0.0694 * Math.sqrt(W) * (1 - (H / 100) ** 8); m = ed + (m - ed) * 10 ** (-ko * 0.581 * Math.exp(0.0365 * T)); }
  else if (m < ew) { const k1 = 0.424 * (1 - ((100 - H) / 100) ** 1.7) + 0.0694 * Math.sqrt(W) * (1 - ((100 - H) / 100) ** 8); m = ew - (ew - m) * 10 ** (-k1 * 0.581 * Math.exp(0.0365 * T)); }
  const ffmc = 59.5 * (250 - m) / (147.2 + m);
  // DMC
  let P = e.dmc;
  if (rf > 1.5) {
    const re = 0.92 * rf - 1.27, mo = 20 + Math.exp(5.6348 - e.dmc / 43.43);
    const b = e.dmc <= 33 ? 100 / (0.5 + 0.3 * e.dmc) : e.dmc <= 65 ? 14 - 1.3 * Math.log(e.dmc) : 6.2 * Math.log(e.dmc) - 17.2;
    const mr = mo + 1000 * re / (48.77 + b * re);
    P = Math.max(0, 244.72 - 43.43 * Math.log(mr - 20));
  }
  const K = T > -1.1 ? 1.894 * (T + 1.1) * (100 - H) * (LE[d.mes] ?? 1) * 1e-6 : 0;
  const dmc = P + 100 * K;
  // DC
  let D = e.dc;
  if (rf > 2.8) { const rd = 0.83 * rf - 1.27, Qo = 800 * Math.exp(-e.dc / 400), Qr = Qo + 3.937 * rd; D = Math.max(0, 400 * Math.log(800 / Qr)); }
  const V = Math.max(0, 0.36 * (T + 2.8) + (LF[d.mes] ?? 8));
  const dc = D + 0.5 * V;
  // ISI, BUI, FWI
  const fW = Math.exp(0.05039 * W), fF = 91.9 * Math.exp(-0.1386 * m) * (1 + m ** 5.31 / 4.93e7), isi = 0.208 * fW * fF;
  let bui = dmc <= 0.4 * dc ? 0.8 * dmc * dc / (dmc + 0.4 * dc) : dmc - (1 - 0.8 * dc / (dmc + 0.4 * dc)) * (0.92 + (0.0114 * dmc) ** 1.7);
  if (!(bui > 0)) bui = 0;
  const fD = bui > 80 ? 1000 / (25 + 108.64 * Math.exp(-0.023 * bui)) : 0.626 * bui ** 0.809 + 2;
  const B = 0.1 * isi * fD, fwi = B > 1 ? Math.exp(2.72 * (0.434 * Math.log(B)) ** 0.647) : B;
  return { ffmc, dmc, dc, isi, bui, fwi };
}
export const fwiClase = (f: number) => f >= 32 ? ["Extremo", "risk"] : f >= 21 ? ["Muy alto", "risk"] : f >= 12 ? ["Alto", "alert"] : f >= 5 ? ["Moderado", "warn"] : ["Bajo", "ok"];
const FWI_RECO: Record<string, string> = {
  Bajo: "Precauciones habituales: chispas de maquinaria y quemas sólo con permiso.",
  Moderado: "Vigilar trabajos con chispas (amoladoras, soldaduras) y pasturas secas.",
  Alto: "El fuego se propaga con facilidad en pastizales: evitar quemas, maquinaria con matafuegos, no estacionar sobre pasto seco.",
  "Muy alto": "Propagación rápida: suspender quemas y trabajos de riesgo, definir vías de escape, alejar hacienda y maquinaria del pasto seco.",
  Extremo: "Peligro extremo: ninguna actividad con fuego o chispas; coordinar con bomberos y tener cortafuegos listos.",
};

// ── heladas de 30 años (ERA5): primera y última helada de cada año, por día del año
export function heladasStats(time: string[], tmin: number[]) {
  const anios: Record<string, number[]> = {};
  time.forEach((f, i) => { if (tmin[i] != null && tmin[i] <= 0) (anios[f.slice(0, 4)] ||= []).push(i); });
  const doy = (f: string) => Math.round((Date.parse(f) - Date.parse(f.slice(0, 4) + "-01-01")) / 864e5) + 1;
  const ys = Object.keys(anios).sort(), total = new Set(time.map(f => f.slice(0, 4))).size;
  if (!ys.length) return { total, conHelada: 0 } as Data;
  const prim = ys.map(y => doy(time[anios[y][0]])), ult = ys.map(y => doy(time[anios[y][anios[y].length - 1]]));
  const dias = ys.map(y => anios[y].length);
  const q = (a: number[], p: number) => { const s = [...a].sort((x, z) => x - z); return s[Math.min(s.length - 1, Math.floor(p * s.length))]; };
  const fecha = (d: number) => { const t = new Date(Date.UTC(2001, 0, d)); return t.toLocaleDateString("es-AR", { day: "numeric", month: "long", timeZone: "UTC" }); };
  return { total, conHelada: ys.length, primera: fecha(q(prim, .5)), primeraTemprana: fecha(q(prim, .1)), ultima: fecha(q(ult, .5)), ultimaTardia: fecha(q(ult, .9)),
           diasMedia: Math.round(dias.reduce((a, b) => a + b, 0) / ys.length), libre: 365 - (q(ult, .5) - q(prim, .5) + 1), desde: time[0].slice(0, 4), hasta: time[time.length - 1].slice(0, 4) };
}

function promHoras(h: Data, v: string, fecha: string, h0: number, h1: number) {
  let s = 0, n = 0;
  (h.time || []).forEach((t: string, i: number) => { const hr = +t.slice(11, 13); if (t.startsWith(fecha) && hr >= h0 && hr <= h1 && h[v]?.[i] != null) { s += h[v][i]; n++; } });
  return n ? s / n : null;
}

const TABS = [["pulverizacion", "Pulverización"], ["siembra", "Siembra"], ["cosecha", "Cosecha"], ["incendio", "Incendio (FWI)"], ["lavado", "Lavado de agroquímicos"], ["heladas", "Heladas 30 años"]] as const;
const V = { ok: "Apto", warn: "Marginal", risk: "No apto" } as Record<string, string>;

export function Labores({ place, cultivo }: { place: Data; cultivo: string }) {
  const [tab, setTab] = useState<string>("pulverizacion");
  const [d, setD] = useState<Data | null>(null), [err, setErr] = useState("");
  const [hel, setHel] = useState<Data | null>(null), [helBusy, setHelBusy] = useState(false);
  const [fApl, setFApl] = useState(""), [tipoApl, setTipoApl] = useState("foliar");
  const c = CULTIVOS[cultivo];
  useEffect(() => {
    setD(null); setErr(""); setHel(null);
    const u = `https://api.open-meteo.com/v1/forecast?latitude=${place.lat}&longitude=${place.lon}&past_days=45&forecast_days=7&timezone=America%2FArgentina%2FBuenos_Aires`
      + "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max,sunshine_duration,soil_temperature_0_to_7cm_mean,soil_moisture_0_to_7cm_mean"
      + "&hourly=temperature_2m,dew_point_2m,relative_humidity_2m,wind_speed_10m";
    fetch(u, { signal: AbortSignal.timeout(30000) }).then(r => r.ok ? r.json() : Promise.reject()).then(setD).catch(() => setErr("Open-Meteo no respondió para las labores. Probá de nuevo."));
  }, [place.lat, place.lon]);
  const cargarHeladas = async () => {
    setHelBusy(true);
    try {
      const y = new Date().getFullYear() - 1;
      const r = await fetch(`https://archive-api.open-meteo.com/v1/archive?latitude=${place.lat}&longitude=${place.lon}&start_date=${y - 29}-01-01&end_date=${y}-12-31&daily=temperature_2m_min&timezone=America%2FArgentina%2FBuenos_Aires`, { signal: AbortSignal.timeout(45000) });
      const j = await r.json(); setHel(heladasStats(j.daily.time, j.daily.temperature_2m_min));
    } catch { setHel({ error: true }); }
    setHelBusy(false);
  };
  if (err) return <section className="cult-sec"><h3>Labores y riesgos</h3><p className="cult-err">{err}</p></section>;
  if (!d) return <section className="cult-sec"><h3>Labores y riesgos</h3><p className="cp-note">Consultando el pronóstico hora por hora…</p></section>;
  const dd = d.daily, hh = d.hourly, hoy = new Date().toISOString().slice(0, 10);
  const k = Math.max(0, dd.time.findIndex((t: string) => t >= hoy)), fut = dd.time.slice(k) as string[];
  const at = (v: string, f: string) => dd[v]?.[dd.time.indexOf(f)];
  let cuerpo: any = null, nota = "";
  if (tab === "pulverizacion") {
    const P = ESP.pulverizacion;
    const filas = fut.map(f => {
      const tM = promHoras(hh, "temperature_2m", f, 9, 12), td = promHoras(hh, "dew_point_2m", f, 9, 12), rh = promHoras(hh, "relative_humidity_2m", f, 6, 18);
      const dt = tM != null && td != null ? tM - td : null, v = at("wind_speed_10m_max", f), pp = at("precipitation_probability_max", f) ?? 0;
      let tone = "ok", mot = "";
      if (v != null && v > P.vientoMax) { tone = "risk"; mot = "viento"; }
      else if (dt != null && (dt < P.dtIdealMin || dt > P.dtMax)) { tone = "risk"; mot = dt < P.dtIdealMin ? "delta T bajo: riesgo de inversión y deriva" : "delta T alto: evaporación de gotas"; }
      else if (pp >= 60) { tone = "risk"; mot = "lluvia probable"; }
      else if (rh != null && (rh < P.hrMin || rh > P.hrMax)) { tone = "warn"; mot = `humedad ${nf(rh)} %`; }
      else if ((v != null && v > P.vientoIdeal) || (dt != null && dt > P.dtIdealMax) || pp >= P.lluviaProb) { tone = "warn"; mot = "cerca del límite"; }
      return [dia(f), nf(v), nf(rh), nf(dt, 1), `${nf(pp)} %`, tone, mot];
    });
    cuerpo = <Tabla cab={["Día", "Viento máx. km/h", "Humedad media %", "Delta T 9–12 h", "Prob. lluvia"]} filas={filas} />;
    nota = `Delta T = temperatura menos punto de rocío entre las 9 y las 12. Ideal entre ${P.dtIdealMin} y ${P.dtIdealMax} °C: por debajo hay riesgo de inversión térmica y deriva; por encima, las gotas se evaporan. Viento ideal hasta ${P.vientoIdeal} km/h, tope ${P.vientoMax}.`;
  } else if (tab === "siembra") {
    const S = ESP.siembra, tReq = c.tbase + S.tempSueloExtra;
    const filas = fut.map(f => {
      const ts = at("soil_temperature_0_to_7cm_mean", f), hs = at("soil_moisture_0_to_7cm_mean", f), pp = at("precipitation_probability_max", f) ?? 0;
      let tone = "risk", mot = "";
      if (ts == null || hs == null) { tone = "warn"; mot = "sin dato de suelo"; }
      else if (ts >= tReq && hs >= S.humMin && hs <= S.humMax && pp < S.lluviaProb) tone = "ok";
      else if (ts >= tReq - 1 && hs >= S.humMin) { tone = "warn"; mot = ts < tReq ? "suelo apenas frío" : hs > S.humMax ? "suelo muy húmedo" : "lluvia probable"; }
      else mot = ts < tReq - 1 ? "suelo frío" : "suelo seco";
      return [dia(f), nf(ts, 1), nf(hs, 2), `${nf(pp)} %`, tone, mot];
    });
    cuerpo = <Tabla cab={["Día", "Suelo 0–7 cm °C", "Humedad suelo m³/m³", "Prob. lluvia"]} filas={filas} verd={{ ok: "Favorable", warn: "A observar", risk: "No" }} />;
    nota = `Favorable para ${c.nombre.toLowerCase()} si el suelo (0–7 cm) está a ${tReq} °C o más (temperatura base ${c.tbase} °C + ${S.tempSueloExtra}), con humedad entre ${S.humMin} y ${S.humMax} m³/m³ y sin lluvia probable.`;
  } else if (tab === "cosecha") {
    const C = ESP.cosecha;
    const filas = fut.map(f => {
      const p = at("precipitation_sum", f) ?? 0, pp = at("precipitation_probability_max", f) ?? 0, rh = promHoras(hh, "relative_humidity_2m", f, 10, 17), v = at("wind_speed_10m_max", f), sol = at("sunshine_duration", f);
      const tone = p === 0 && pp < C.lluviaProb && (rh == null || rh <= C.hrMax) && (v == null || v >= C.vientoMin) ? "ok" : p < 2 && pp < 50 ? "warn" : "risk";
      return [dia(f), nf(p, 1), `${nf(pp)} %`, nf(rh), nf(v), nf(sol != null ? sol / 3600 : null, 1), tone, ""];
    });
    cuerpo = <Tabla cab={["Día", "Lluvia mm", "Prob. lluvia", "Humedad 10–17 h %", "Viento km/h", "Horas de sol"]} filas={filas} />;
    nota = `Apto si no llueve, la humedad diurna queda en ${C.hrMax} % o menos y hay algo de viento (${C.vientoMin} km/h o más) para secar.`;
  } else if (tab === "incendio") {
    let e: FwiEstado = { ffmc: 85, dmc: 6, dc: 15 }; const filas: any[] = [], serie: number[] = [];
    dd.time.forEach((f: string, i: number) => {
      const t = promHoras(hh, "temperature_2m", f, 12, 12) ?? (dd.temperature_2m_max[i] + dd.temperature_2m_min[i]) / 2;
      const rh = promHoras(hh, "relative_humidity_2m", f, 12, 12) ?? 60, w = promHoras(hh, "wind_speed_10m", f, 12, 12) ?? dd.wind_speed_10m_max[i] ?? 10;
      const r = fwiDia(e, { t, rh, wind: w, rain: dd.precipitation_sum[i] ?? 0, mes: +f.slice(5, 7) }); e = { ffmc: r.ffmc, dmc: r.dmc, dc: r.dc }; serie.push(r.fwi);
      if (i >= k - 3) { const [cl, tone] = fwiClase(r.fwi); filas.push([dia(f) + (i >= k ? "" : " (obs.)"), nf(dd.precipitation_sum[i], 1), nf(w), nf(r.ffmc), nf(r.dmc), nf(r.dc), nf(r.isi, 1), nf(r.bui), nf(r.fwi, 1), tone, cl]); }
    });
    const maxF = Math.max(...serie.slice(k)), [clMax] = fwiClase(maxF);
    cuerpo = <>
      <div className={`cult-alert ${fwiClase(maxF)[1]}`}><b>Peligro máximo de la semana: {clMax} (FWI {nf(maxF, 1)})</b><p className="reco">{FWI_RECO[clMax]}</p></div>
      <Tabla cab={["Día", "Lluvia mm", "Viento km/h", "FFMC", "DMC", "DC", "ISI", "BUI", "FWI"]} filas={filas.map(f => [...f.slice(0, 9), f[9], f[10]])} verdTexto />
    </>;
    nota = "Índice canadiense de peligro de incendio (FWI, Servicio Forestal de Canadá), usado también en Chile, España y Australia. Se arma con 45 días de clima observado más el pronóstico, con valores de mediodía. FFMC: humedad del pasto fino; DMC y DC: sequía del mantillo y profunda; ISI: velocidad de propagación; BUI: combustible disponible. Clases: bajo menos de 5, moderado 5 a 12, alto 12 a 21, muy alto 21 a 32, extremo más de 32.";
  } else if (tab === "lavado") {
    const umb = ESP.lavado[tipoApl], i0 = fApl ? fut.indexOf(fApl) : -1;
    const r48 = i0 >= 0 ? fut.slice(i0, i0 + 2).reduce((s, f) => s + (at("precipitation_sum", f) ?? 0), 0) : null;
    cuerpo = <>
      <div className="cult-grid" style={{ gridTemplateColumns: "1fr 1fr", maxWidth: 560 }}>
        <label>Día de aplicación<select value={fApl} onChange={e => setFApl(e.target.value)}><option value="">Elegí un día</option>{fut.map(f => <option key={f} value={f}>{dia(f)}</option>)}</select></label>
        <label>Producto<select value={tipoApl} onChange={e => setTipoApl(e.target.value)}><option value="foliar">Foliar: fungicida, insecticida (umbral 10 mm)</option><option value="herbicida">Herbicida (umbral 20 mm)</option><option value="suelo">Aplicación al suelo (umbral 30 mm)</option></select></label>
      </div>
      {r48 != null && <div className={`cult-alert ${r48 < umb ? "ok" : "risk"}`} style={{ marginTop: 10 }}><b>{r48 < umb ? "Ventana segura" : "Riesgo de lavado o escurrimiento"}: {nf(r48, 1)} mm en 48 h (umbral {umb} mm)</b><p className="reco">{r48 < umb ? "La lluvia prevista no debería lavar el producto." : "Conviene reprogramar la aplicación o revisar la etiqueta del producto."}</p></div>}
    </>;
    nota = "Suma la lluvia pronosticada del día de aplicación y el siguiente, y la compara con umbrales de referencia: foliar 10 mm, herbicida 20 mm, al suelo 30 mm. Siempre manda la etiqueta del producto.";
  } else {
    cuerpo = hel == null ? <button className="cult-pdf no-print" onClick={() => void cargarHeladas()} disabled={helBusy}>{helBusy ? "Analizando 30 años de mínimas…" : "Calcular heladas de los últimos 30 años"}</button>
      : hel.error ? <p className="cult-err">El archivo histórico no respondió. Probá de nuevo.</p>
      : !hel.conHelada ? <p>En {hel.total} años no hubo ningún día con mínima de 0 °C o menos en esta localidad.</p>
      : <Tabla cab={["Estadística", "Valor"]} filas={[
          ["Años con al menos una helada", `${hel.conHelada} de ${hel.total} (${hel.desde}–${hel.hasta})`],
          ["Primera helada, año típico", hel.primera], ["Primera helada, 1 de cada 10 años antes del", hel.primeraTemprana],
          ["Última helada, año típico", hel.ultima], ["Última helada, 1 de cada 10 años después del", hel.ultimaTardia],
          ["Días con helada por año (promedio)", String(hel.diasMedia)], ["Período libre de heladas (año típico)", `${hel.libre} días`]].map(r => [...r, "", ""])} sinVeredicto />;
    nota = `Heladas = días con temperatura mínima de 0 °C o menos (ERA5 vía Open-Meteo, a 2 m del suelo; en el pasto puede helar con 2 o 3 °C en el abrigo). El umbral de daño para ${c.nombre.toLowerCase()} es ${c.helada} °C.`;
  }
  return <section className="cult-sec cult-labores">
    <h3>Labores y riesgos de la semana</h3>
    <div className="cult-tabs no-print">{TABS.map(([id, t]) => <button key={id} className={tab === id ? "on" : ""} onClick={() => setTab(id)}>{t}</button>)}</div>
    <h4 className="print-only">{TABS.find(t => t[0] === tab)?.[1]}</h4>
    {cuerpo}
    <p className="cp-note">{nota} Reglas declaradas, basadas en AgroClima v3; calibrables por zona y por asesor.</p>
  </section>;
}

function Tabla({ cab, filas, verd = V, verdTexto, sinVeredicto }: { cab: string[]; filas: any[][]; verd?: Record<string, string>; verdTexto?: boolean; sinVeredicto?: boolean }) {
  return <div className="cult-table"><table>
    <thead><tr>{cab.map(h => <th key={h}>{h}</th>)}{!sinVeredicto && <th>{verdTexto ? "Clase" : "Veredicto"}</th>}</tr></thead>
    <tbody>{filas.map((f, i) => { const n = f.length, tone = f[n - 2], mot = f[n - 1]; return <tr key={i}>
      {f.slice(0, n - 2).map((x: any, j: number) => <td key={j}>{x}</td>)}
      {!sinVeredicto && <td><span className={`cult-chip ${tone}`}>{verdTexto ? mot : verd[tone]}</span>{!verdTexto && mot ? <small> {mot}</small> : null}</td>}
    </tr>; })}</tbody>
  </table></div>;
}
