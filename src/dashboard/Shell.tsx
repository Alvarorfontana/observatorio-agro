/**
 * Estructura de panel DOTS basada en el modelo de TailAdmin
 * (https://github.com/TailAdmin/free-react-tailwind-admin-dashboard, licencia MIT, © 2023 TailAdmin).
 * Se porta el diseño (menú lateral colapsable, encabezado fijo, tarjetas de métricas) a CSS propio
 * en src/dashboard.css, sin Tailwind, para convivir con los estilos existentes de DOTS.
 */
import React from "react";
import {
  LayoutDashboard, Layers, Satellite, Sprout, Waves, CircleDot, Beef, CloudSun,
  Flame, Gauge, FileText, Network, Thermometer, ChevronsLeft, X, Hexagon,
} from "lucide-react";

export type NavItem = {
  key: string;
  label: string;
  icon: React.ReactNode;
  onClick?: () => void;
  soon?: boolean;
};

export function buildNav(go: (k: string) => void, draw: () => void, pdf: () => void): { title: string; items: NavItem[] }[] {
  return [
    { title: "Observatorio", items: [
      { key: "variables", label: "Resumen del lote", icon: <LayoutDashboard />, onClick: () => go("variables") },
      { key: "__draw", label: "Lotes y potreros", icon: <Layers />, onClick: draw },
      { key: "escenas", label: "Satélites", icon: <Satellite />, onClick: () => go("escenas") },
      { key: "ndvi", label: "Vegetación · NDVI", icon: <Sprout />, onClick: () => go("ndvi") },
      { key: "rios", label: "Agua y ríos", icon: <Waves />, onClick: () => go("rios") },
      { key: "suelo", label: "Suelos", icon: <CircleDot />, onClick: () => go("suelo") },
      { key: "__ganado", label: "Ganado", icon: <Beef />, soon: true },
    ]},
    { title: "Clima y riesgo", items: [
      { key: "modelos", label: "Clima · modelos", icon: <CloudSun />, onClick: () => go("modelos") },
      { key: "firms", label: "Riesgos · focos", icon: <Flame />, onClick: () => go("firms") },
      { key: "indices", label: "Índices agroclimáticos", icon: <Thermometer />, onClick: () => go("indices") },
      { key: "teleconexiones", label: "El Niño · teleconexiones", icon: <Gauge />, onClick: () => go("teleconexiones") },
    ]},
    { title: "Salidas", items: [
      { key: "plataformas", label: "Fuentes y APIs", icon: <Network />, onClick: () => go("plataformas") },
      { key: "__pdf", label: "Informe PDF", icon: <FileText />, onClick: pdf },
    ]},
  ];
}

export function ObsSidebar({ groups, active, collapsed, mobileOpen, onCollapse, onCloseMobile, onHome }: {
  groups: { title: string; items: NavItem[] }[];
  active: string;
  collapsed: boolean;
  mobileOpen: boolean;
  onCollapse: () => void;
  onCloseMobile: () => void;
  onHome: () => void;
}) {
  return (
    <>
      <aside className={"ta-sidebar" + (collapsed ? " is-collapsed" : "") + (mobileOpen ? " is-open" : "")} aria-label="Módulos DOTS">
        <div className="ta-logo">
          <button className="ta-logo-btn" onClick={onHome} title="Volver a DOTS">
            <span className="ta-logo-mark"><Hexagon /></span>
            <span className="ta-logo-text"><b>DOTS <em>/ CAMPO</em></b><small>Observatorio ganadero</small></span>
          </button>
          <button className="ta-icon-btn ta-close" onClick={onCloseMobile} aria-label="Cerrar menú"><X /></button>
        </div>
        <nav className="ta-nav">
          {groups.map(g => (
            <div key={g.title} className="ta-nav-group">
              <h3 className="ta-nav-title"><span>{g.title}</span></h3>
              <ul>
                {g.items.map(it => (
                  <li key={it.key}>
                    <button
                      className={"ta-menu-item " + (active === it.key ? "is-active" : "")}
                      onClick={() => { it.onClick?.(); onCloseMobile(); }}
                      disabled={it.soon}
                      title={it.label}
                      aria-current={active === it.key ? "page" : undefined}
                    >
                      <span className="ta-menu-icon">{it.icon}</span>
                      <span className="ta-menu-text">{it.label}</span>
                      {it.soon && <span className="ta-badge">Pronto</span>}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>
        <button className="ta-menu-item ta-collapse" onClick={onCollapse} title={collapsed ? "Expandir menú" : "Contraer menú"}>
          <span className="ta-menu-icon"><ChevronsLeft /></span>
          <span className="ta-menu-text">Contraer menú</span>
        </button>
      </aside>
      {mobileOpen && <div className="ta-backdrop" onClick={onCloseMobile} />}
    </>
  );
}

export type Metric = {
  key: string;
  label: string;
  value: string;
  unit?: string;
  hint: string;
  icon: React.ReactNode;
  tone?: "ok" | "warn" | "risk" | "idle";
  onClick?: () => void;
};

export function MetricCards({ items }: { items: Metric[] }) {
  return (
    <section className="ta-metrics" aria-label="Indicadores del lote">
      {items.map(m => (
        <button key={m.key} className={"ta-metric tone-" + (m.tone || "idle")} onClick={m.onClick}>
          <span className="ta-metric-icon">{m.icon}</span>
          <span className="ta-metric-body">
            <span className="ta-metric-label">{m.label}</span>
            <span className="ta-metric-value">{m.value}{m.unit && <small> {m.unit}</small>}</span>
            <span className="ta-metric-hint">{m.hint}</span>
          </span>
        </button>
      ))}
    </section>
  );
}
