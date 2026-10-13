/**
 * DOTS · Temporales y frentes: presión atmosférica, cambios bruscos de temperatura, ráfagas y calor extremo.
 * Reglas declaradas sobre el pronóstico horario de Open-Meteo (modelos ECMWF, GFS y otros, mejor combinación).
 * Orientativo: los avisos oficiales son del SMN.
 */
export type Data = Record<string, any>;
export const UMB = {
  caida3h: [3, 5],          // hPa en 3 horas (atención, alerta)
  caida24h: 14,             // hPa en 24 h: ciclogénesis explosiva a ~30° S (24 hPa × sen 30° / sen 60°)
  frente: [8, 12],          // °C de caída de la máxima de un día al siguiente
  rafaga: [60, 80],         // km/h
  calor: { tmax: 35, tmin: 22, dias: 3 },
};
export const HOURLY = "pressure_msl,temperature_2m,wind_gusts_10m,wind_direction_10m,precipitation";
export const DAILY = "temperature_2m_max,temperature_2m_min,wind_gusts_10m_max,precipitation_sum";
const ORD = ["Normal", "Atención", "Alerta"];
const peor = (a: string, b: string) => ORD.indexOf(a) >= ORD.indexOf(b) ? a : b;
export const tono = (n: string) => n === "Alerta" ? "risk" : n === "Atención" ? "warn" : "ok";
const dm = (iso: string) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;
const hm = (iso: string) => `${dm(iso)} ${iso.slice(11, 16)}`;

export function analizarFrentes(d: Data, hoy = new Date(Date.now() - 3 * 3600e3).toISOString().slice(0, 13)) {   // hora de Argentina
  const h = d.hourly, dd = d.daily;
  const t: string[] = h.time, P: number[] = h.pressure_msl;
  const k0 = Math.max(0, t.findIndex(x => x.slice(0, 13) >= hoy));
  const eventos: { nivel: string; tipo: string; cuando: string; texto: string }[] = [];
  // presión: mayor caída en 3 h y en 24 h desde ahora
  let c3 = { v: 0, i: -1 }, c24 = { v: 0, i: -1 };
  for (let i = Math.max(3, k0); i < t.length; i++) {
    if (P[i] != null && P[i - 3] != null && P[i - 3] - P[i] > c3.v) c3 = { v: P[i - 3] - P[i], i };
    if (i >= 24 && P[i] != null && P[i - 24] != null && P[i - 24] - P[i] > c24.v) c24 = { v: P[i - 24] - P[i], i };
  }
  const pmin = Math.min(...P.slice(k0).filter(x => x != null)), imin = P.indexOf(pmin);
  if (c24.v >= UMB.caida24h) eventos.push({ nivel: "Alerta", tipo: "Ciclogénesis", cuando: hm(t[c24.i]), texto: `La presión cae ${c24.v.toFixed(1).replace(".", ",")} hPa en 24 h: posible ciclón extratropical intenso, con temporal de viento y lluvia.` });
  if (c3.v >= UMB.caida3h[0]) eventos.push({ nivel: c3.v >= UMB.caida3h[1] ? "Alerta" : "Atención", tipo: "Caída de presión", cuando: hm(t[c3.i]), texto: `Baja ${c3.v.toFixed(1).replace(".", ",")} hPa en 3 horas: se acerca un frente o una baja; ráfagas y tormentas probables.` });
  // frentes fríos: caída de la máxima de un día al otro
  const kd = Math.max(1, dd.time.findIndex((x: string) => x >= hoy.slice(0, 10)));
  let fr = { v: 0, i: -1 };
  for (let i = kd; i < dd.time.length; i++) { const v = dd.temperature_2m_max[i - 1] - dd.temperature_2m_max[i]; if (v > fr.v) fr = { v, i }; }
  if (fr.v >= UMB.frente[0]) eventos.push({ nivel: fr.v >= UMB.frente[1] ? "Alerta" : "Atención", tipo: "Frente frío", cuando: dm(dd.time[fr.i]), texto: `La máxima baja ${Math.round(fr.v)} °C de un día al otro (de ${Math.round(dd.temperature_2m_max[fr.i - 1])} a ${Math.round(dd.temperature_2m_max[fr.i])} °C): cambio brusco de tiempo.` });
  // ráfagas
  const gmax = Math.max(...dd.wind_gusts_10m_max.slice(kd - 1).filter((x: number) => x != null)), ig = dd.wind_gusts_10m_max.indexOf(gmax);
  if (gmax >= UMB.rafaga[0]) eventos.push({ nivel: gmax >= UMB.rafaga[1] ? "Alerta" : "Atención", tipo: "Ráfagas", cuando: dm(dd.time[ig]), texto: `Ráfagas de hasta ${Math.round(gmax)} km/h.` });
  // calor extremo sostenido
  let run = 0, ini = -1, calor: [number, number] | null = null;
  for (let i = kd - 1; i < dd.time.length; i++) {
    if (dd.temperature_2m_max[i] >= UMB.calor.tmax && dd.temperature_2m_min[i] >= UMB.calor.tmin) { if (!run) ini = i; run++; if (run >= UMB.calor.dias) calor = [ini, i]; } else run = 0;
  }
  if (calor) eventos.push({ nivel: "Alerta", tipo: "Calor extremo", cuando: `${dm(dd.time[calor[0]])} al ${dm(dd.time[calor[1]])}`, texto: `${calor[1] - calor[0] + 1} días seguidos con máximas de ${UMB.calor.tmax} °C o más y mínimas de ${UMB.calor.tmin} °C o más.` });
  const nivel = eventos.reduce((a, e) => peor(a, e.nivel), "Normal");
  return { nivel, eventos, pmin, pminCuando: imin >= 0 ? hm(t[imin]) : "", caida3h: c3.v, caida24h: c24.v, frente: fr.v, rafaga: gmax };
}

/**
 * Sudestada en el Río de la Plata: viento persistente del este al sur que frena la salida del río y sube el agua
 * en la costa argentina (Delta, San Fernando, Buenos Aires, Quilmes). Regla declarada sobre el viento horario
 * pronosticado en el centro del estuario; la altura oficial del agua la pronostica el Servicio de Hidrografía Naval (SHN).
 */
export const SUDESTADA = { punto: [-34.85, -57.4] as [number, number], dir: [80, 190], viento: [30, 45], horas: 12, rafaga: 70 };
export function sudestada(d: Data, hoy = new Date(Date.now() - 3 * 3600e3).toISOString().slice(0, 13)) {
  const h = d.hourly, t: string[] = h.time, v: number[] = h.wind_speed_10m, g: number[] = h.wind_direction_10m, r: number[] = h.wind_gusts_10m || [];
  const k0 = Math.max(0, t.findIndex(x => x.slice(0, 13) >= hoy));
  const dentro = (i: number, lim: number) => g[i] != null && v[i] != null && g[i] >= SUDESTADA.dir[0] && g[i] <= SUDESTADA.dir[1] && v[i] >= lim;
  const racha = (lim: number) => {   // tramo más largo de horas seguidas con viento del sector y por encima del límite
    let best = { n: 0, i: -1, j: -1 }, n = 0, ini = -1;
    for (let i = k0; i < t.length; i++) { if (dentro(i, lim)) { if (!n) ini = i; n++; if (n > best.n) best = { n, i: ini, j: i }; } else n = 0; }
    return best;
  };
  const fuerte = racha(SUDESTADA.viento[1]), mod = racha(SUDESTADA.viento[0]);
  const tramo = fuerte.n >= SUDESTADA.horas ? fuerte : mod;
  const gmax = tramo.n ? Math.max(...r.slice(tramo.i, tramo.j + 1).filter(x => x != null), 0) : 0;
  const vmax = tramo.n ? Math.max(...v.slice(tramo.i, tramo.j + 1)) : Math.max(...v.slice(k0).filter((x, i) => dentro(i + k0, 0)), 0);
  const nivel = fuerte.n >= SUDESTADA.horas || (mod.n >= SUDESTADA.horas && gmax >= SUDESTADA.rafaga) ? "Alerta" : mod.n >= SUDESTADA.horas ? "Atención" : "Normal";
  const texto = nivel === "Normal" ? "Sin viento persistente del sudeste sobre el Río de la Plata en los próximos días."
    : `Viento del ${["este", "sudeste", "sur"][Math.min(2, Math.round((((tramo.i >= 0 ? g[tramo.i] : 135) - 90) / 45)))] ?? "sudeste"} durante ${tramo.n} horas seguidas, con máximas de ${Math.round(vmax)} km/h${gmax ? ` y ráfagas de ${Math.round(gmax)} km/h` : ""}: el agua puede subir en la costa del Delta, San Fernando, Buenos Aires y Quilmes, y frenar la bajada del Paraná y el Uruguay.`;
  return { nivel, texto, horas: tramo.n, desde: tramo.n ? hm(t[tramo.i]) : "", hasta: tramo.n ? hm(t[tramo.j]) : "", vmax, gmax };
}
