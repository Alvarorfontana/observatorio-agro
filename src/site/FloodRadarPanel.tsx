import React, { useState } from "react";
import "./FloodRadarPanel.css";

export type FloodRadarReport = {
  status?: string;
  before_date?: string;
  after_date?: string;
  area_ha?: { new_water?: number; persistent_water?: number; receded_water?: number; persistent_land?: number };
  coverage_fraction?: number;
  new_water_fraction?: number;
  paired_valid_pixels?: number;
  source?: string;
  image_before_url?: string;
  image_after_url?: string;
  change_map_url?: string;
};

type Props = { report?: FloodRadarReport | null; location?: string; onRefresh?: () => void; loading?: boolean };
const fmt = (v?: number, digits = 1) => v == null || !Number.isFinite(v) ? "—" : v.toLocaleString("es-AR", { maximumFractionDigits: digits });
const METRICS = [
  { key: "new_water", label: "Agua nueva", tone: "cyan", hint: "Apareció entre las dos pasadas" },
  { key: "persistent_water", label: "Agua persistente", tone: "blue", hint: "Presente en ambas fechas" },
  { key: "receded_water", label: "Agua retirada", tone: "amber", hint: "Detectada antes, ausente después" },
] as const;

export function FloodRadarPanel({ report, location = "Área seleccionada", onRefresh, loading = false }: Props) {
  const [view, setView] = useState<"change" | "before" | "after">("change");
  const areas = report?.area_ha;
  const valid = report?.status === "ESTIMATE_NOT_VALIDATED" && !!areas;
  const total = valid ? METRICS.reduce((sum, m) => sum + Math.max(0, areas?.[m.key] ?? 0), 0) : 0;
  const images = { change: report?.change_map_url, before: report?.image_before_url, after: report?.image_after_url };
  const image = images[view];
  const [failed, setFailed] = useState<string[]>([]);
  return <section className="frp" aria-label="Observatorio radar de inundaciones">
    <header className="frp-header">
      <div><div className="frp-eyebrow"><span className="frp-pulse" /> DOTS CAMPO / OBSERVATORIO SATELITAL</div>
        <h2>Radar de inundaciones <span>SAR</span></h2>
        <p>Detección multitemporal de agua superficial · Sentinel-1 · {location}</p></div>
      <div className="frp-header-right"><span className="frp-status">{loading ? "Procesando" : valid ? "Estimación sin validar" : "Sin análisis disponible"}</span>
        {onRefresh && <button type="button" className="frp-refresh" onClick={onRefresh} disabled={loading}>{loading ? "Consultando…" : "Actualizar análisis ↗"}</button>}</div>
    </header>
    <div className="frp-metrics">
      {METRICS.map(m => <article key={m.key} className={`frp-metric frp-${m.tone}`}>
        <div className="frp-metric-title"><i />{m.label}</div>
        <div className="frp-number">{valid ? fmt(areas?.[m.key]) : "—"} <small>ha</small></div>
        <p>{m.hint}</p></article>)}
      <article className="frp-metric frp-neutral"><div className="frp-metric-title">Cobertura analizada</div>
        <div className="frp-number">{valid ? fmt((report?.coverage_fraction ?? 0) * 100, 0) : "—"} <small>%</small></div>
        <p>Píxeles comparables entre escenas</p></article>
    </div>
    <div className="frp-workspace">
      <div className="frp-map-panel">
        <div className="frp-panel-top"><div><b>Comparación de imágenes</b><span>{report?.before_date || "Fecha inicial pendiente"} → {report?.after_date || "Fecha final pendiente"}</span></div>
          <div className="frp-tabs" role="group" aria-label="Visualización">
            {([["change","Cambio"],["before","Antes"],["after","Después"]] as const).map(([id,label]) => <button key={id} type="button" aria-pressed={view === id} className={view === id ? "active" : ""} onClick={() => setView(id)}>{label}</button>)}
          </div></div>
        <div className="frp-map-frame">
          {image && !failed.includes(image) ? <img key={image} src={image} alt={view === "change" ? "Mapa georreferenciado de cambios de agua" : `Imagen satelital ${view === "before" ? "anterior" : "posterior"}`} onError={() => setFailed(v => [...v,image])} /> :
          <div className="frp-empty"><div className="frp-orbit" aria-hidden="true"><div className="frp-orbit-core">◈</div></div>
            <b>Imagen satelital pendiente</b><span>{valid ? "Las métricas están disponibles, pero todavía no se entregó un mapa georreferenciado." : "Seleccioná un lote y ejecutá un análisis con dos pasadas Sentinel-1 comparables."}</span></div>}
          <span className="frp-map-stamp">SENTINEL-1 · SAR C-BAND</span>
        </div>
        <div className="frp-legend"><span><i className="new"/> Agua nueva</span><span><i className="permanent"/> Agua persistente</span><span><i className="receded"/> Agua retirada</span><span><i className="nodata"/> Sin dato</span></div>
      </div>
      <aside className="frp-analysis">
        <div className="frp-side-title">ANÁLISIS DE SUPERFICIE <span>01 / 02</span></div>
        <h3>Distribución del agua</h3>
        {valid && total > 0 ? <><div className="frp-stacked" aria-label="Distribución de superficie detectada">{METRICS.map(m => <div key={m.key} className={`frp-seg frp-${m.tone}`} style={{width:`${100 * (areas?.[m.key] ?? 0) / total}%`}} />)}</div>
          {METRICS.map(m => <div className="frp-breakdown" key={m.key}><span><i className={`frp-dot frp-${m.tone}`}/>{m.label}</span><strong>{fmt(areas?.[m.key])} ha</strong></div>)}</> :
          <div className="frp-side-empty">Sin superficies medidas. El gráfico aparecerá al recibir un análisis válido.</div>}
        <div className="frp-rule"/>
        <div className="frp-side-title">TRAZABILIDAD <span>02 / 02</span></div>
        <dl className="frp-details"><div><dt>Fuente</dt><dd>{report?.source || "Sentinel-1 / pendiente de vincular"}</dd></div><div><dt>Píxeles válidos</dt><dd>{valid ? fmt(report?.paired_valid_pixels, 0) : "—"}</dd></div><div><dt>Estado científico</dt><dd>{valid ? "Experimental" : "No disponible"}</dd></div></dl>
        <div className="frp-notice"><b>Interpretación responsable</b><p>Una señal de agua en radar no confirma profundidad ni riesgo de evacuación. Requiere verificación con GFM, estaciones hidrométricas y observaciones locales.</p></div>
      </aside>
    </div>
    <footer className="frp-footer"><span>DOTS CAMPO / GEOINTELLIGENCE</span><span>Resultados estimados · no sustituye alertas oficiales</span></footer>
  </section>;
}
