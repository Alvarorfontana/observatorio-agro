/**
 * Marcas de campo con ícono y color por tipo (íconos Lucide, licencia ISC).
 * Se dibujan como L.divIcon para que el mapa muestre de un vistazo qué es cada punto.
 */
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import L from "leaflet";
import {
  Eye, Beef, Droplet, Waves, Trees, TreePine, Fence, Warehouse, Wind, Flame, Thermometer, Sprout, Cylinder, DoorOpen, Stethoscope,
} from "lucide-react";

export type MarkerKind = {
  key: string;
  label: string;
  group: "Agua" | "Rodeo" | "Infraestructura" | "Vegetación" | "Riesgo" | "General";
  color: string;
  Icon: React.ComponentType<any>;
};

export const MARKER_KINDS: MarkerKind[] = [
  { key: "observación", label: "Observación", group: "General", color: "#98a2b3", Icon: Eye },
  { key: "ganado", label: "Ganado / rodeo", group: "Rodeo", color: "#f59e0b", Icon: Beef },
  { key: "sanidad", label: "Sanidad / animal enfermo", group: "Rodeo", color: "#f97066", Icon: Stethoscope },
  { key: "bebedero", label: "Bebedero", group: "Agua", color: "#22d3ee", Icon: Droplet },
  { key: "tajamar", label: "Tajamar / represa / aguada", group: "Agua", color: "#3b82f6", Icon: Waves },
  { key: "molino", label: "Molino / perforación", group: "Agua", color: "#60a5fa", Icon: Wind },
  { key: "tanque", label: "Tanque australiano", group: "Agua", color: "#38bdf8", Icon: Cylinder },
  { key: "árbol", label: "Árbol / sombra", group: "Vegetación", color: "#22c55e", Icon: TreePine },
  { key: "monte", label: "Monte / bosque", group: "Vegetación", color: "#15803d", Icon: Trees },
  { key: "vegetación", label: "Pastura / anomalía", group: "Vegetación", color: "#a3e635", Icon: Sprout },
  { key: "alambrado", label: "Alambrado", group: "Infraestructura", color: "#d6bcfa", Icon: Fence },
  { key: "tranquera", label: "Tranquera / acceso", group: "Infraestructura", color: "#c4b5fd", Icon: DoorOpen },
  { key: "corral", label: "Corral / manga / galpón", group: "Infraestructura", color: "#a78bfa", Icon: Warehouse },
  { key: "incendio", label: "Foco térmico / fuego", group: "Riesgo", color: "#ef4444", Icon: Flame },
  { key: "temperatura", label: "Calor / THI", group: "Riesgo", color: "#fb923c", Icon: Thermometer },
];

// Tipos de infraestructura hídrica ya existentes → tipo de marca
const WATER_ALIAS: Record<string, string> = {
  bebedero: "bebedero", tajamar: "tajamar", represa: "tajamar", arroyo: "tajamar", canal: "tajamar",
  molino: "molino", "perforación": "molino", bomba: "molino", "cañería": "bebedero", "tanque australiano": "tanque",
  agua: "bebedero",
};

export function kindOf(type: string): MarkerKind {
  const key = WATER_ALIAS[type] || type;
  return MARKER_KINDS.find(k => k.key === key) || MARKER_KINDS[0];
}

const cache = new Map<string, L.DivIcon>();
export function markerIcon(type: string, opts: { satellite?: boolean } = {}) {
  const k = kindOf(type);
  const id = k.key + (opts.satellite ? ":sat" : "");
  if (cache.has(id)) return cache.get(id)!;
  const svg = renderToStaticMarkup(<k.Icon size={15} strokeWidth={2.2} color="#0c111d" />);
  const icon = L.divIcon({
    className: "dots-pin-wrap",
    html: `<div class="dots-pin${opts.satellite ? " is-sat" : ""}" style="--pin:${k.color}"><span>${svg}</span></div>`,
    iconSize: [30, 38],
    iconAnchor: [15, 36],
    popupAnchor: [0, -32],
    tooltipAnchor: [12, -22],
  });
  cache.set(id, icon);
  return icon;
}

export function MarkerLegend({ types }: { types: string[] }) {
  const kinds = MARKER_KINDS.filter(k => types.some(t => kindOf(t).key === k.key));
  if (!kinds.length) return null;
  return (
    <div className="dots-legend" aria-label="Leyenda de marcas">
      {kinds.map(k => (
        <span key={k.key}><i style={{ background: k.color }}><k.Icon size={11} strokeWidth={2.4} color="#0c111d" /></i>{k.label}</span>
      ))}
    </div>
  );
}
