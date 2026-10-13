/**
 * Vista "Tablero" del lote — modelo de dashboard de Carbon Design System (IBM):
 * página completa en grilla de 16 columnas, mosaicos planos con cifras grandes,
 * gráficos grandes y una tabla de fuentes. La identidad sigue siendo DOTS.
 * Usa exactamente los mismos datos que el resto del observatorio: no calcula nada nuevo
 * salvo agregaciones visibles (sumas, balances) y nunca reemplaza un faltante.
 */
import React, { useEffect, useRef } from "react";
import * as echarts from "echarts/core";

type Data = Record<string, any>;
type Tone = "ok" | "warn" | "risk" | "idle";
type Src = { status: string; payload?: Data; error?: string };

const fmt = (v: unknown, d = 1) =>
  v !== null && v !== undefined && Number.isFinite(Number(v))
    ? Number(v).toLocaleString("es-AR", { minimumFractionDigits: d, maximumFractionDigits: d })
    : "—";
const sum = (a: unknown[] = []) => a.reduce((s: number, x) => s + (Number(x) || 0), 0);
const dm = (iso: string) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;

function readTheme(el: React.RefObject<HTMLElement | null>) {
  const css = el.current ? getComputedStyle(el.current) : null;
  const v = (n: string, d: string) => css?.getPropertyValue(n).trim() || d;
  const light = css?.getPropertyValue("--ta-is-light").trim() === "1";
  return {
    light, text: v("--ta-text", "#f4f4f4"), text2: v("--ta-text-2", "#c6c6c6"), text3: v("--ta-text-3", "#8d8d8d"),
    grid: v("--ta-border", "#333"), layer: v("--ta-layer-2", "#393939"),
    // paleta categórica de Carbon (oscuro / claro), con el turquesa DOTS primero
    c: light ? ["#007d79", "#0f62fe", "#d02670", "#8a3ffc", "#a8a8a8"] : ["#3ddbd9", "#78a9ff", "#ff7eb6", "#be95ff", "#8d8d8d"],
    ok: v("--ta-ok", "#42be65"), warn: v("--ta-warn", "#f1c21b"), risk: v("--ta-risk", "#fa4d56"),
  };
}

/** Gráfico ECharts con estilo Carbon: ejes finos, sin cajas, leyenda arriba a la derecha. */
function EChart({ option, height = 260, label }: { option: (t: ReturnType<typeof readTheme>) => Data; height?: number; label: string }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const t = readTheme(ref);
    const chart = echarts.init(ref.current, undefined, { renderer: "canvas" });
    const o = option(t);
    chart.setOption({
      animation: false,
      textStyle: { fontFamily: "IBM Plex Sans", color: t.text2 },
      tooltip: { trigger: "axis", backgroundColor: t.layer, borderWidth: 0, padding: [8, 10], textStyle: { color: t.text, fontSize: 12 } },
      legend: { top: 0, right: 0, icon: "rect", itemWidth: 10, itemHeight: 10, itemGap: 14, textStyle: { color: t.text2, fontSize: 11 } },
      grid: { left: 44, right: 14, top: 36, bottom: 28 },
      ...o,
    });
    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(ref.current);
    return () => { ro.disconnect(); chart.dispose(); };
  });
  return <div ref={ref} style={{ height }} role="img" aria-label={label} />;
}
const axis = (t: ReturnType<typeof readTheme>, data?: string[], name?: string) => ({
  x: { type: "category", data, axisLine: { lineStyle: { color: t.grid } }, axisTick: { show: false }, axisLabel: { color: t.text3, fontSize: 11, hideOverlap: true } },
  y: { type: "value", name, scale: true, splitNumber: 4, nameTextStyle: { color: t.text3, fontSize: 10, align: "left" }, axisLabel: { color: t.text3, fontSize: 11 }, splitLine: { lineStyle: { color: t.grid } } },
});

function Tile({ label, value, unit, tone = "idle", word, hint, span = 4, onClick }: { label: string; value: string; unit?: string; tone?: Tone; word?: string; hint?: string; span?: number; onClick?: () => void }) {
  const El: any = onClick ? "button" : "div";
  return (
    <El className={`db-tile db-span-${span} tone-${tone}`} onClick={onClick}>
      <span className="db-tile-label">{label}</span>
      <span className="db-tile-value">{value}{unit && value !== "—" && <small>{unit}</small>}</span>
      <span className="db-tile-foot">{word && tone !== "idle" && <b className={`db-word tone-${tone}`}>{word}</b>}{hint}</span>
    </El>
  );
}
function Card({ title, sub, span = 8, children, action }: { title: string; sub?: string; span?: number; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <section className={`db-card db-span-${span}`}>
      <div className="db-head"><div><h3>{title}</h3>{sub && <p>{sub}</p>}</div>{action}</div>
      {children}
    </section>
  );
}
function Empty({ text, button, onClick, busy }: { text: string; button?: string; onClick?: () => void; busy?: boolean }) {
  return <div className="db-empty"><p>{text}</p>{button && <button onClick={onClick} disabled={busy}>{busy ? "Consultando…" : button}</button>}</div>;
}

export function LotDashboard({ weather, sources, lot, thi, terrain, onLoad, onTerrain, onOpen, hasLot, labels = {}, water = null, cloudOn = false, hasKey = false, onCloud }: {
  weather: Data | undefined; sources: Record<string, Src>; lot: Data | null; thi: number | null; terrain: Data | null;
  onLoad: (key: string) => void; onTerrain: () => void; onOpen: (key: string) => void; hasLot: boolean; labels?: Record<string, string>;
  water?: Data | null; cloudOn?: boolean; hasKey?: boolean; onCloud?: () => void;
}) {
  const cur = weather?.current || {}, d = weather?.daily || {}, h = weather?.hourly || {};
  const days: string[] = (d.time || []).map(dm);
  const rain7 = d.precipitation_sum ? sum(d.precipitation_sum) : null;
  const et7 = d.et0_fao_evapotranspiration ? sum(d.et0_fao_evapotranspiration) : null;
  const bal = rain7 != null && et7 != null ? rain7 - et7 : null;
  const ndvi = sources.ndvi?.payload?.data;
  const nser: Data[] = (ndvi?.series || []).filter((r: Data) => r.status === "válida" && r.ndvi_mean != null);
  const nd = ndvi?.latest?.ndvi_mean != null ? Number(ndvi.latest.ndvi_mean) : null;
  const ll = sources.lluvia?.payload?.data;
  const rec: Data[] = ll?.recent || [];
  const i0 = Math.max(0, (h.time || []).findIndex((t: string) => t >= String(cur.time || "").slice(0, 13) + ":00"));
  const soilKeys = Object.keys(h).filter(k => k.startsWith("soil_moisture_")).sort((a, b) => parseInt(a.split("_")[2]) - parseInt(b.split("_")[2]));
  const soil0 = soilKeys.length ? h[soilKeys[0]]?.[i0] : null;
  const busy = (k: string) => sources[k]?.status === "consultando" || ll?.status === "en proceso" && k === "lluvia";

  // THI diario (máximo de la tarde) a partir del pronóstico horario
  const thiDay = (d.time || []).map((day: string) => {
    let mx: number | null = null;
    (h.time || []).forEach((t: string, k: number) => {
      if (!t.startsWith(day)) return;
      const T = h.temperature_2m?.[k], RH = h.relative_humidity_2m?.[k];
      if (T == null || RH == null) return;
      const v = 1.8 * T + 32 - (0.55 - 0.0055 * RH) * (1.8 * T - 26);
      mx = mx == null ? v : Math.max(mx, v);
    });
    return mx == null ? null : Math.round((mx as number) * 10) / 10;
  });
  let acc = 0;
  const cum = (d.time || []).map((_: string, k: number) => { acc += (Number(d.precipitation_sum?.[k]) || 0) - (Number(d.et0_fao_evapotranspiration?.[k]) || 0); return Math.round(acc * 10) / 10; });
  const tTone = (v: number | null): Tone => v == null ? "idle" : v >= 35 ? "risk" : v >= 32 ? "warn" : "ok";
  const thiTone: Tone = thi == null ? "idle" : thi >= 79 ? "risk" : thi >= 72 ? "warn" : "ok";
  const balTone: Tone = bal == null ? "idle" : bal < -30 ? "risk" : bal < -15 ? "warn" : "ok";
  const ndTone: Tone = nd == null ? "idle" : nd >= 0.5 ? "ok" : nd >= 0.3 ? "warn" : "risk";

  const statusRows = Object.entries(sources).filter(([, s]) => s && s.status);
  // Por qué un recuadro está vacío: consultando, falló (con el motivo) o la fuente respondió sin dato
  const why = (k: string, idle: string) => {
    const s = sources[k];
    if (s?.status === "consultando") return { text: "Consultando la fuente…", failed: false };
    if (s?.status === "sin dato") return { text: `La fuente no devolvió datos: ${s.error || "sin respuesta"}. No se reemplaza por otro valor.`, failed: true };
    if (s?.payload?.status === "sin dato") return { text: `La fuente respondió sin dato válido${s.payload.error ? `: ${s.payload.error}` : ""}. No se reemplaza por otro valor.`, failed: true };
    return { text: idle, failed: false };
  };
  const wx = why("variables", "Esperando el pronóstico de Open-Meteo…");
  const wn = why("ndvi", hasLot ? "Preparando el NDVI de este lote…" : "Dibujá o seleccioná un lote para ver su NDVI.");
  const wl = why("lluvia", hasLot ? "Preparando la lluvia observada del lote…" : "Dibujá o seleccioná un lote para ver su lluvia observada.");
  const sw = sources["humedad-nasa"]?.payload?.data;
  const wsw = why("humedad-nasa", "Consultando la humedad de suelo de NASA…");
  const swTone: Tone = sw?.percentile == null ? "idle" : sw.percentile < 10 || sw.percentile > 90 ? "risk" : sw.percentile < 30 || sw.percentile > 70 ? "warn" : "ok";
  const env = water?.entorno;
  const km = (m: number | null | undefined) => m == null ? "—" : m < 1000 ? `${fmt(m, 0)} m` : `${fmt(m / 1000, 1)} km`;
  const wr = why("relieve", hasLot ? "Preparando el relieve de este lote…" : "Dibujá o seleccioná un lote para ver su relieve.");

  return (
    <div className="db-grid">
      {/* Fila 1: cifras clave */}
      <Tile span={4} label="Temperatura ahora" value={fmt(cur.temperature_2m)} unit="°C" tone={tTone(cur.temperature_2m ?? null)} word={({ risk: "Calor extremo", warn: "Calor", ok: "Normal", idle: "" } as Record<Tone, string>)[tTone(cur.temperature_2m ?? null)]} hint={`Humedad ${fmt(cur.relative_humidity_2m, 0)} % · viento ${fmt(cur.wind_speed_10m, 0)} km/h`} onClick={() => onOpen("variables")} />
      <Tile span={4} label="Estrés del rodeo (THI)" value={fmt(thi)} tone={thiTone} word={thiTone === "risk" ? "Peligro" : thiTone === "warn" ? "Alerta" : "Sin estrés"} hint="72 alerta · 79 peligro" onClick={() => onOpen("variables")} />
      <Tile span={4} label="Balance de agua · 7 días" value={bal == null ? "—" : `${bal > 0 ? "+" : ""}${fmt(bal, 0)}`} unit="mm" tone={balTone} word={bal == null ? "" : bal < -30 ? "Déficit marcado" : bal < -15 ? "Balance negativo" : bal < 10 ? "Equilibrado" : "Excedente"} hint={`Lluvia ${fmt(rain7, 0)} mm · evapotranspiración ${fmt(et7, 0)} mm`} onClick={() => onOpen("variables")} />
      <Tile span={4} label="Vigor del pasto (NDVI)" value={fmt(nd, 2)} tone={ndTone} word={({ risk: "Vigor bajo", warn: "Vigor medio", ok: "Vigor alto", idle: "" } as Record<Tone, string>)[ndTone]} hint={nd != null ? `Sentinel-2 · ${String(ndvi?.latest?.datetime || "").slice(0, 10)}` : hasLot ? "Tocá para calcular" : "Dibujá un lote"} onClick={() => hasLot && (nd == null ? onLoad("ndvi") : onOpen("ndvi"))} />

      {/* Fila 2: clima de la semana */}
      <Card span={10} title="Temperatura y estrés del rodeo" sub="Próximos 7 días · mínima, máxima y THI máximo de la tarde · Open-Meteo">
        {days.length ? <EChart label="Temperaturas y THI de la semana" option={t => {
          const a = axis(t, days, "°C");
          return {
            xAxis: a.x, yAxis: [a.y, { ...a.y, name: "", position: "right", splitLine: { show: false }, min: 60, max: 90 }],
            grid: { left: 44, right: 40, top: 36, bottom: 28 },
            series: [
              { name: "Máxima", type: "bar", color: t.c[0], data: d.temperature_2m_max, barMaxWidth: 18, itemStyle: { color: (p: any) => p.value >= 35 ? t.risk : t.c[0] } },
              { name: "Mínima", type: "bar", data: d.temperature_2m_min, barMaxWidth: 18, itemStyle: { color: t.c[4] } },
              { name: "THI máx.", type: "line", yAxisIndex: 1, data: thiDay, symbolSize: 6, lineStyle: { width: 2, color: t.c[2] }, itemStyle: { color: t.c[2] },
                markLine: { silent: true, symbol: "none", label: { color: t.text3, fontSize: 10, formatter: "{b}", position: "insideStartTop" }, lineStyle: { type: "dashed", color: t.warn }, data: [{ yAxis: 72, name: "alerta" }, { yAxis: 79, name: "peligro", lineStyle: { color: t.risk } }] } },
            ],
          };
        }} /> : <Empty text={wx.text} button={wx.failed ? "Reintentar" : undefined} onClick={() => onLoad("variables")} />}
      </Card>
      <Card span={6} title="Agua del suelo" sub="Humedad volumétrica por profundidad · m³/m³ · ahora">
        {soilKeys.length ? <EChart height={260} label="Humedad del suelo por profundidad" option={t => ({
          legend: { show: false },
          grid: { left: 70, right: 30, top: 10, bottom: 24 },
          xAxis: { type: "value", min: 0, max: 0.5, axisLabel: { color: t.text3, fontSize: 11 }, splitLine: { lineStyle: { color: t.grid } } },
          yAxis: { type: "category", inverse: true, data: soilKeys.map(k => k.replace("soil_moisture_", "").replace("_to_", "–").replace("cm", " cm")), axisLine: { lineStyle: { color: t.grid } }, axisTick: { show: false }, axisLabel: { color: t.text2, fontSize: 11 } },
          series: [{ type: "bar", data: soilKeys.map(k => h[k]?.[i0]), barMaxWidth: 16, itemStyle: { color: (p: any) => p.value < 0.12 ? t.warn : t.c[1] }, label: { show: true, position: "right", color: t.text2, fontSize: 11, formatter: (p: any) => fmt(p.value, 2) } }],
          tooltip: { trigger: "item" },
        })} /> : <Empty text={weather ? "Open-Meteo no informó humedad de suelo para esta grilla." : wx.text} />}
      </Card>

      {/* Fila 3: agua y pasto */}
      <Card span={8} title="Balance de agua diario" sub="Lluvia contra evapotranspiración · línea: balance acumulado · mm">
        {days.length ? <EChart label="Balance de agua" option={t => {
          const a = axis(t, days, "mm");
          return { xAxis: a.x, yAxis: { ...a.y, scale: false }, series: [
            { name: "Lluvia", type: "bar", data: d.precipitation_sum, barMaxWidth: 16, itemStyle: { color: t.c[1] } },
            { name: "Evapotranspiración", type: "bar", data: (d.et0_fao_evapotranspiration || []).map((x: number) => x == null ? null : -x), barMaxWidth: 16, itemStyle: { color: t.c[4] } },
            { name: "Balance acumulado", type: "line", data: cum, symbolSize: 6, lineStyle: { width: 2, color: t.text }, itemStyle: { color: t.text } },
          ] };
        }} /> : <Empty text={wx.text} button={wx.failed ? "Reintentar" : undefined} onClick={() => onLoad("variables")} />}
      </Card>
      <Card span={8} title="Vigor del pasto (NDVI)" sub="Sentinel-2 · media dentro del lote · escenas nubladas excluidas">
        {nser.length ? <EChart label="NDVI del lote" option={t => {
          const a = axis(t, nser.map(r => dm(String(r.datetime || r.from))), "NDVI");
          return { legend: { show: false }, xAxis: a.x, yAxis: { ...a.y, min: 0, max: 1, scale: false }, series: [
            { name: "NDVI", type: "line", data: nser.map(r => r.ndvi_mean), symbolSize: 7, lineStyle: { width: 2.5, color: t.c[0] }, itemStyle: { color: t.c[0] }, areaStyle: { color: t.c[0], opacity: 0.14 },
              markArea: { silent: true, itemStyle: { color: t.light ? "rgba(0,0,0,.03)" : "rgba(255,255,255,.03)" }, data: [[{ yAxis: 0.5 }, { yAxis: 1 }]] } },
          ] };
        }} /> : <Empty text={wn.text} button={hasLot && !busy("ndvi") ? (wn.failed ? "Reintentar" : "Calcular NDVI") : undefined} onClick={() => onLoad("ndvi")} busy={busy("ndvi")} />}
      </Card>

      {/* Fila 4: lluvia histórica y relieve */}
      <Card span={10} title="Lluvia observada contra lo normal" sub="CHIRPS · últimos 12 meses · mm · normal = mediana 1991–2020">
        {rec.length ? <EChart label="Lluvia observada contra normal" option={t => {
          const a = axis(t, rec.map(r => `${String(r.period).slice(5, 7)}/${String(r.period).slice(2, 4)}`), "mm");
          return { xAxis: a.x, yAxis: { ...a.y, scale: false }, series: [
            { name: "Observada", type: "bar", color: t.c[1], data: rec.map(r => r.mm), barMaxWidth: 16, itemStyle: { color: (p: any) => { const n = rec[p.dataIndex]?.normal; return n != null && p.value < n * 0.6 ? t.warn : t.c[1]; } } },
            { name: "Normal", type: "line", step: "middle", data: rec.map(r => r.normal), symbol: "none", lineStyle: { width: 2, type: "dashed", color: t.text2 }, itemStyle: { color: t.text2 } },
          ] };
        }} /> : <Empty text={ll?.status === "en proceso" ? `CHIRPS está calculando la lluvia del lote${ll.progress != null ? ` (${ll.progress} %)` : ""}. Puede tardar uno o dos minutos.` : wl.text} button={ll?.status === "en proceso" || !hasLot || busy("lluvia") ? undefined : wl.failed ? "Reintentar" : "Consultar lluvia"} onClick={() => onLoad("lluvia")} busy={busy("lluvia")} />}
      </Card>
      <Card span={6} title="Relieve y anegamiento" sub="Copernicus DEM 30 m · % del lote por propensión">
        {terrain?.riskPct ? <>
          <EChart height={190} label="Propensión a anegarse" option={t => ({
            legend: { show: false }, grid: { left: 54, right: 40, top: 6, bottom: 20 },
            xAxis: { type: "value", max: 100, axisLabel: { color: t.text3, fontSize: 11, formatter: "{value} %" }, splitLine: { lineStyle: { color: t.grid } } },
            yAxis: { type: "category", inverse: true, data: ["Baja", "Media", "Alta"], axisLine: { lineStyle: { color: t.grid } }, axisTick: { show: false }, axisLabel: { color: t.text2 } },
            series: [{ type: "bar", barMaxWidth: 18, data: [{ value: terrain.riskPct.bajo, itemStyle: { color: t.ok } }, { value: terrain.riskPct.medio, itemStyle: { color: t.warn } }, { value: terrain.riskPct.alto, itemStyle: { color: t.risk } }],
              label: { show: true, position: "right", color: t.text2, fontSize: 11, formatter: (p: any) => fmt(p.value, 0) + " %" } }],
            tooltip: { trigger: "item" },
          })} />
          <dl className="db-facts"><div><dt>Posición</dt><dd>{String(terrain.positionLabel || "").replace(/^./, (c: string) => c.toUpperCase())}</dd></div><div><dt>Bajos ≥ 10 cm</dt><dd>{fmt(terrain.depressionHa, 1)} ha</dd></div><div><dt>Desnivel</dt><dd>{fmt(terrain.relief, 1)} m</dd></div></dl>
        </> : <Empty text={wr.text} button={hasLot && !busy("relieve") ? (wr.failed ? "Reintentar" : "Analizar relieve") : undefined} onClick={onTerrain} busy={busy("relieve")} />}
      </Card>

      {/* Fila 5: humedad de NASA contra lo normal y entorno del lote */}
      <Card span={10} title="Humedad del suelo contra lo normal" sub="NASA POWER (MERRA-2) · zona de raíces 0–100 cm · % de saturación · banda gris: rango normal del mes (20 años)">
        {sw?.series?.length ? <div className="db-water">
          <dl className="db-facts db-facts-4">
            <div><dt>Zona de raíces</dt><dd>{fmt(sw.root_pct, 0)} %</dd></div>
            <div><dt>Normal del mes</dt><dd>{fmt(sw.normal_pct, 0)} %</dd></div>
            <div><dt>Estado</dt><dd><b className={`db-word tone-${swTone}`}>{sw.category || "—"}</b></dd></div>
            <div><dt>Cambio 30 días</dt><dd>{sw.change_30d_pts == null ? "—" : `${sw.change_30d_pts > 0 ? "+" : ""}${fmt(sw.change_30d_pts, 0)} pts`}</dd></div>
          </dl>
          <EChart height={200} label="Humedad de la zona de raíces y rango normal" option={t => {
            const a = axis(t, sw.series.map((r: Data) => dm(String(r.date))), "%");
            const band = sw.normal_range;
            return { legend: { show: false }, xAxis: a.x, yAxis: { ...a.y, min: 0, max: 100, scale: false }, series: [
              { name: "Zona de raíces", type: "line", data: sw.series.map((r: Data) => r.root_pct), symbol: "none", lineStyle: { width: 2.5, color: t.c[1] }, itemStyle: { color: t.c[1] },
                markArea: band ? { silent: true, itemStyle: { color: t.light ? "rgba(0,0,0,.06)" : "rgba(255,255,255,.07)" }, data: [[{ yAxis: band.p10 }, { yAxis: band.p90 }]] } : undefined },
            ] };
          }} />
          <p className="db-note">Segunda opinión, independiente de la humedad de Open-Meteo. Último dato del {dm(String(sw.date))}; NASA publica con unos días de demora. Percentil {fmt(sw.percentile, 0)} frente a {fmt(sw.years, 0)} años.</p>
        </div> : <Empty text={wsw.text} button={wsw.failed ? "Reintentar" : undefined} onClick={() => onLoad("humedad-nasa")} busy={busy("humedad-nasa")} />}
      </Card>
      <Card span={6} title="Entorno del lote" sub="Overture Maps · caminos, construcciones y departamento · se actualiza con cada versión mensual">
        {env ? <>
          <dl className="db-facts">
            <div><dt>Ubicación</dt><dd>{[env.departamento, env.provincia].filter(Boolean).join(", ") || "—"}</dd></div>
            <div><dt>Camino más cercano</dt><dd>{env.camino_mas_cercano_m === 0 ? "Pasa por el lote" : km(env.camino_mas_cercano_m)}</dd></div>
            <div><dt>Ruta más cercana</dt><dd>{env.ruta_mas_cercana_m === 0 ? "Pasa por el lote" : env.ruta_mas_cercana_m == null ? "Más de 6 km" : km(env.ruta_mas_cercana_m)}</dd></div>
            <div><dt>Caminos dentro del lote</dt><dd>{fmt((env.caminos_km?.caminos_lote || 0) + (env.caminos_km?.rutas_lote || 0), 1)} km</dd></div>
            <div><dt>Construcciones en el lote</dt><dd>{fmt(env.construcciones_lote, 0)}{env.techo_m2_lote ? ` · ${fmt(env.techo_m2_lote, 0)} m² de techo` : ""}</dd></div>
            <div><dt>Construcciones a 2 km</dt><dd>{fmt(env.construcciones_2km, 0)}</dd></div>
          </dl>
          <p className="db-note">Datos abiertos de OpenStreetMap, Microsoft y Google reunidos por Overture (versión {env.release}). Pueden faltar caminos internos o galpones nuevos.</p>
        </> : <Empty text={!hasLot ? "Seleccioná un lote para ver su entorno." : !cloudOn ? "El entorno se calcula en el procesamiento semanal, que todavía no está activado en este sitio." : !hasKey ? "Guardá tus lotes en la nube para que el procesamiento semanal calcule caminos y construcciones." : "El entorno aparece después del próximo procesamiento semanal."}
          button={hasLot && cloudOn && !hasKey ? "Ir a guardar lotes" : undefined} onClick={onCloud} />}
      </Card>

      {/* Fila 6: agua detectada por satélite (procesamiento semanal con geoai) */}
      <Card span={16} title="Agua detectada por satélite" sub="Procesamiento semanal · Sentinel-2 · geoai (modelo OmniWaterMask) · aguadas, tajamares y bajos con agua dentro del lote">
        {water?.status === "recibido" || water?.stale ? <div className="db-water">
          <dl className="db-facts db-facts-4">
            <div><dt>Agua en el lote</dt><dd>{fmt(water.water_ha, 1)} ha</dd></div>
            <div><dt>Cuerpos de agua</dt><dd>{fmt(water.water_bodies, 0)}</dd></div>
            <div><dt>Parte del lote</dt><dd>{fmt(water.water_pct, 1)} %</dd></div>
            <div><dt>Imagen del</dt><dd>{water.scene?.date ? dm(water.scene.date) + "/" + water.scene.date.slice(2, 4) : "—"}{water.stale ? " · anterior" : ""}</dd></div>
          </dl>
          {(water.history || []).length > 1 ? <EChart height={220} label="Evolución del agua y del NDVI" option={t => {
            const hs: Data[] = water.history; const a = axis(t, hs.map(h => dm(String(h.scene_date))), "ha");
            return { xAxis: a.x, yAxis: [{ ...a.y, scale: false }, { ...a.y, name: "", position: "right", min: 0, max: 1, splitLine: { show: false } }], grid: { left: 44, right: 40, top: 36, bottom: 28 },
              series: [{ name: "Agua (ha)", type: "bar", barMaxWidth: 16, data: hs.map(h => h.water_ha), itemStyle: { color: t.c[1] } },
                       { name: "NDVI", type: "line", yAxisIndex: 1, data: hs.map(h => h.ndvi), lineStyle: { width: 2, color: t.c[0] }, itemStyle: { color: t.c[0] } }] };
          }} /> : <p className="db-note">El gráfico de evolución aparece desde la segunda semana procesada. En la vista Mapa el agua detectada se dibuja en azul sobre el lote.</p>}
        </div> : <Empty text={!hasLot ? "Seleccioná un lote para ver el agua detectada." : !cloudOn ? "El procesamiento semanal todavía no está activado en este sitio." : !hasKey ? "Guardá tus lotes en la nube (pestaña Lote) para que entren en el procesamiento de cada lunes." : water?.status === "pendiente" ? "Este lote todavía no pasó por el procesamiento semanal. Los resultados aparecen después del próximo lunes." : water?.status === "sin dato" ? `Sin resultado: ${water.reason || water.error || "la fuente no respondió"}.` : "Buscando resultados…"}
          button={hasLot && cloudOn && !hasKey ? "Ir a guardar lotes" : undefined} onClick={onCloud} />}
      </Card>

      {/* Fila 7: trazabilidad */}
      <Card span={16} title="Fuentes consultadas" sub={`${statusRows.filter(([, s]) => s.status === "recibido").length} con respuesta válida · ${statusRows.filter(([, s]) => s.status === "sin dato").length} sin dato · ningún faltante se reemplaza`}>
        <div className="db-table-wrap"><table className="db-table">
          <thead><tr><th>Fuente</th><th>Estado</th><th>Consulta</th><th></th></tr></thead>
          <tbody>{statusRows.map(([k, s]) => <tr key={k}>
            <td>{labels[k] || k.replaceAll("-", " ").replace(/^./, c => c.toUpperCase())}</td>
            <td><span className={`src-state st-${s.status.replace(" ", "-")}`}>{s.status}</span>{s.error && <small> {s.error}</small>}</td>
            <td>{String(s.payload?.consulted_at || "").replace("T", " ").slice(0, 16) || "—"}</td>
            <td><button className="db-link" onClick={() => onOpen(k)}>Ver detalle</button></td>
          </tr>)}</tbody>
        </table></div>
      </Card>
      {lot && <p className="db-foot">Lote {lot.name} · {fmt(lot.areaHa, 1)} ha · datos modelados y satelitales con fuente y fecha · no reemplaza la recorrida a campo.</p>}
    </div>
  );
}
