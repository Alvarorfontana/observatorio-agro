/**
 * DOTS · Meteograma de la localidad.
 * Idea tomada de los meteogramas de weathermodels.com (Ryan Maue): toda la semana de un punto en una sola lámina,
 * con paneles apilados que comparten el eje de tiempo. Datos horarios de Open-Meteo (sin clave, desde el navegador),
 * modelo "best match" (combina ECMWF, GFS, ICON y otros según la zona).
 */
import { useEffect, useRef, useState } from "react";
import * as echarts from "echarts/core";
import { LineChart, BarChart } from "echarts/charts";
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, MarkAreaComponent, AxisPointerComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";

echarts.use([LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, MarkAreaComponent, AxisPointerComponent, CanvasRenderer]);

type Data = Record<string, any>;
const TZ = "America%2FArgentina%2FBuenos_Aires";
const HOURLY = "temperature_2m,dew_point_2m,relative_humidity_2m,precipitation,precipitation_probability,wind_speed_10m,wind_gusts_10m,wind_direction_10m,cloud_cover,et0_fao_evapotranspiration";
const nf = (v: unknown, d = 0) => v == null || !Number.isFinite(Number(v)) ? "—" : Number(v).toLocaleString("es-AR", { minimumFractionDigits: d, maximumFractionDigits: d });
const DIAS = ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"];
const dia = (iso: string) => `${DIAS[new Date(iso.slice(0, 10) + "T12:00:00").getDay()]} ${iso.slice(8, 10)}/${iso.slice(5, 7)}`;
const vals = (a: (number | null)[]) => a.filter((x): x is number => x != null && Number.isFinite(x));

/** Resumen diario a partir del pronóstico horario (exportado para pruebas). */
export function resumenDiario(h: Data) {
  const dias: Record<string, number[]> = {};
  (h.time as string[]).forEach((t, i) => (dias[t.slice(0, 10)] ||= []).push(i));
  return Object.entries(dias).map(([f, idx]) => {
    const pick = (k: string) => vals(idx.map(i => h[k]?.[i] ?? null));
    const tt = pick("temperature_2m"), ll = pick("precipitation"), pp = pick("precipitation_probability"), rf = pick("wind_gusts_10m"), hr = pick("relative_humidity_2m"), et = pick("et0_fao_evapotranspiration");
    return {
      f, tmin: tt.length ? Math.min(...tt) : null, tmax: tt.length ? Math.max(...tt) : null,
      lluvia: ll.reduce((s, x) => s + x, 0), prob: pp.length ? Math.max(...pp) : null,
      rafaga: rf.length ? Math.max(...rf) : null, hrmax: hr.length ? Math.max(...hr) : null,
      et0: et.reduce((s, x) => s + x, 0),
      helada: tt.length ? Math.min(...tt) <= 0 : false,
      rocio: idx.some(i => h.temperature_2m?.[i] != null && h.dew_point_2m?.[i] != null && h.temperature_2m[i] - h.dew_point_2m[i] <= 1),
    };
  });
}

export function Meteograma({ place }: { place: Data }) {
  const [d, setD] = useState<Data | null>(null), [err, setErr] = useState("");
  const ref = useRef<HTMLDivElement | null>(null);
  const url = `https://api.open-meteo.com/v1/forecast?latitude=${place.lat}&longitude=${place.lon}&forecast_days=7&timezone=${TZ}&hourly=${HOURLY}`;

  useEffect(() => {
    setD(null); setErr("");
    fetch(url, { signal: AbortSignal.timeout(30000) }).then(r => r.ok ? r.json() : Promise.reject()).then(setD)
      .catch(() => setErr("El servicio de pronóstico no respondió. Probá de nuevo en unos minutos."));
  }, [url]);

  useEffect(() => {
    if (!d || !ref.current) return;
    const el = ref.current, h = d.hourly;
    const css = getComputedStyle(el), v = (n: string, f: string) => css.getPropertyValue(n).trim() || f;
    const txt = v("--ta-text-2", "#c6c6c6"), line = v("--ta-border", "#333333");
    const ser = (k: string) => (h.time as string[]).map((t, i) => [t, h[k]?.[i] ?? null]);
    const N = 4, top = 30, gap = 34, alto = 118;
    const grids = Array.from({ length: N }, (_, i) => ({ left: 48, right: 48, top: top + i * (alto + gap), height: alto }));
    const xAxis = grids.map((_, i) => ({ type: "time" as const, gridIndex: i, axisLabel: { show: i === N - 1, color: txt, fontSize: 10 }, axisLine: { lineStyle: { color: line } }, splitLine: { show: true, lineStyle: { color: line, opacity: 0.35 } } }));
    const yA = (gi: number, name: string, extra: Data = {}) => ({ type: "value" as const, gridIndex: gi, name, nameTextStyle: { color: txt, fontSize: 10 }, axisLabel: { color: txt, fontSize: 10 }, splitLine: { lineStyle: { color: line, opacity: 0.35 } }, ...extra });
    const yAxis = [
      yA(0, "°C", { scale: true }),
      yA(1, "mm/h", { min: 0 }), yA(1, "%", { min: 0, max: 100, position: "right", splitLine: { show: false } }),
      yA(2, "km/h", { min: 0 }),
      yA(3, "%", { min: 0, max: 100 }),
    ];
    const ahora = { silent: true, symbol: "none", label: { show: false }, lineStyle: { color: txt, type: "dashed" as const }, data: [{ xAxis: Date.now() }] };
    const ch = echarts.init(el);
    ch.setOption({
      animation: false,
      axisPointer: { link: [{ xAxisIndex: "all" }] },
      tooltip: { trigger: "axis", valueFormatter: (x: unknown) => nf(x, 1) },
      legend: { top: 0, textStyle: { color: txt, fontSize: 11 } },
      grid: grids, xAxis, yAxis,
      series: [
        { name: "Temperatura", type: "line", xAxisIndex: 0, yAxisIndex: 0, showSymbol: false, data: ser("temperature_2m"), lineStyle: { color: "#ff8389", width: 2 }, itemStyle: { color: "#ff8389" },
          markLine: { ...ahora, data: [{ xAxis: Date.now() }, { yAxis: 0, lineStyle: { color: "#78a9ff", type: "solid" } }] } },
        { name: "Punto de rocío", type: "line", xAxisIndex: 0, yAxisIndex: 0, showSymbol: false, data: ser("dew_point_2m"), lineStyle: { color: "#3ddbd9", width: 1.5 }, itemStyle: { color: "#3ddbd9" } },
        { name: "Lluvia", type: "bar", xAxisIndex: 1, yAxisIndex: 1, data: ser("precipitation"), itemStyle: { color: "#33b1ff" }, barMaxWidth: 4, markLine: ahora },
        { name: "Probabilidad de lluvia", type: "line", xAxisIndex: 1, yAxisIndex: 2, showSymbol: false, data: ser("precipitation_probability"), lineStyle: { color: "#be95ff", width: 1, type: "dotted" }, itemStyle: { color: "#be95ff" } },
        { name: "Viento", type: "line", xAxisIndex: 2, yAxisIndex: 3, showSymbol: false, data: ser("wind_speed_10m"), lineStyle: { color: "#42be65", width: 2 }, itemStyle: { color: "#42be65" },
          markLine: { ...ahora, data: [{ xAxis: Date.now() }, { yAxis: 15, lineStyle: { color: "#f1c21b", type: "dashed" } }] } },
        { name: "Ráfagas", type: "line", xAxisIndex: 2, yAxisIndex: 3, showSymbol: false, data: ser("wind_gusts_10m"), lineStyle: { color: "#f1c21b", width: 1 }, itemStyle: { color: "#f1c21b" } },
        { name: "Nubosidad", type: "line", xAxisIndex: 3, yAxisIndex: 4, showSymbol: false, areaStyle: { opacity: 0.25 }, data: ser("cloud_cover"), lineStyle: { color: "#a8a8a8", width: 1 }, itemStyle: { color: "#a8a8a8" }, markLine: ahora },
        { name: "Humedad relativa", type: "line", xAxisIndex: 3, yAxisIndex: 4, showSymbol: false, data: ser("relative_humidity_2m"), lineStyle: { color: "#4589ff", width: 1.5 }, itemStyle: { color: "#4589ff" } },
      ],
    });
    const ro = new ResizeObserver(() => ch.resize()); ro.observe(el);
    return () => { ro.disconnect(); ch.dispose(); };
  }, [d]);

  if (err) return <p className="cult-err">{err}</p>;
  if (!d) return <p className="cp-note">Consultando…</p>;
  const res = resumenDiario(d.hourly);
  return <>
    <p className="cp-note">Toda la semana de {place.name || "este punto"} en una sola lámina. Los cuatro paneles comparten la hora: pasá el dedo o el mouse y se leen juntos. La línea punteada vertical es «ahora».</p>
    <div ref={ref} style={{ width: "100%", height: 30 + 4 * (118 + 34) + 10 }} />
    <div className="cult-table"><table>
      <thead><tr><th>Día</th><th>Mín / máx °C</th><th>Lluvia mm</th><th>Prob.</th><th>Ráfaga km/h</th><th>ET₀ mm</th><th>Atención</th></tr></thead>
      <tbody>{res.map(r => <tr key={r.f}>
        <td>{dia(r.f)}</td><td>{nf(r.tmin, 1)} / {nf(r.tmax, 1)}</td><td>{nf(r.lluvia, 1)}</td><td>{nf(r.prob)} %</td><td>{nf(r.rafaga)}</td><td>{nf(r.et0, 1)}</td>
        <td>{[r.helada && "helada", r.rocio && "rocío o niebla", (r.rafaga ?? 0) >= 60 && "ráfagas fuertes", r.lluvia >= 30 && "lluvia intensa"].filter(Boolean).join(" · ") || "—"}</td>
      </tr>)}</tbody>
    </table></div>
    <div className="cult-table"><table>
      <caption style={{ textAlign: "left", fontWeight: 600, padding: "6px 0" }}>Rangos de lectura</caption>
      <thead><tr><th>Panel</th><th>Cómo se lee</th><th>Límites</th></tr></thead>
      <tbody>
        <tr><td>Temperatura y punto de rocío</td><td>Línea azul horizontal = 0 °C (helada meteorológica). Cuando las dos curvas se tocan (diferencia de 1 °C o menos) hay rocío, niebla o escarcha y la hoja queda mojada: más riesgo de enfermedades.</td><td>Temperatura a 2 m en abrigo; en el suelo y en bajos puede hacer 2 a 4 °C menos (helada agronómica).</td></tr>
        <tr><td>Lluvia y probabilidad</td><td>Barras: mm por hora (más de 10 mm/h es fuerte). Línea punteada: chance de que llueva en esa hora, de 0 a 100 %.</td><td>El modelo reparte la lluvia en celdas de 2 a 11 km: una tormenta puntual puede no aparecer o caer en el campo de al lado.</td></tr>
        <tr><td>Viento y ráfagas</td><td>Línea amarilla a 15 km/h: por encima, no se recomienda pulverizar (deriva). Ráfagas de 60 km/h o más pueden voltear cultivos y dañar instalaciones.</td><td>Viento a 10 m de altura sobre terreno abierto; cortinas y relieve lo cambian.</td></tr>
        <tr><td>Nubosidad y humedad</td><td>Nubosidad: porcentaje de cielo cubierto. Humedad relativa sobre 90 % por varias horas favorece hongos y demora el secado de grano y forraje.</td><td>La nubosidad es la menos precisa de las variables del modelo.</td></tr>
      </tbody>
    </table></div>
    <p className="cp-note">Fuente: Open-Meteo (CC-BY 4.0), modelo combinado según la zona (ECMWF, GFS, ICON y otros), resolución horaria. Es pronóstico, no medición: los primeros 3 días son los más confiables y después del día 5 conviene leerlo como tendencia. Los avisos oficiales son del SMN.</p>
  </>;
}
