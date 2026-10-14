/**
 * Ilustraciones de la página El Niño (SVG propio):
 *  - PacificSection: corte del Pacífico ecuatorial, año normal vs. El Niño (vientos, agua cálida, termoclina, nubes).
 *  - SAImpactMap: Sudamérica (Natural Earth, dominio público) con zonas de más y menos lluvia y los caminos de la humedad.
 */
import React, { useState } from "react";
import { SA_VIEW, SA_COUNTRIES, SA_RIVERS, saXY } from "./samerica";

function Cloud({ x, y, s = 1, rain = true }: { x: number; y: number; s?: number; rain?: boolean }) {
  return <g transform={`translate(${x},${y}) scale(${s})`}>
    <ellipse cx="0" cy="0" rx="34" ry="16" fill="#e8eef2" />
    <ellipse cx="-20" cy="4" rx="20" ry="13" fill="#dfe7ec" />
    <ellipse cx="22" cy="5" rx="22" ry="12" fill="#d5dfe6" />
    <ellipse cx="2" cy="-12" rx="20" ry="14" fill="#f2f6f8" />
    {rain && [-22, -10, 2, 14, 26].map((dx, i) => <line key={i} x1={dx} y1={18} x2={dx - 6} y2={40} stroke="#57a6ff" strokeWidth="2.5" strokeLinecap="round" opacity=".85" />)}
  </g>;
}

function WindArrow({ x, y, len, dir, w = 6, color = "#ffffff" }: { x: number; y: number; len: number; dir: 1 | -1; w?: number; color?: string }) {
  const x2 = x + dir * len;
  return <g stroke={color} strokeWidth={w} strokeLinecap="round" fill="none">
    <path d={`M${x},${y} C${x + dir * len * 0.3},${y - 10} ${x + dir * len * 0.6},${y + 10} ${x2},${y}`} />
    <path d={`M${x2 - dir * 16},${y - 12} L${x2},${y} L${x2 - dir * 16},${y + 12}`} />
  </g>;
}

export function PacificSection() {
  const [nino, setNino] = useState(true);
  const W = 900, SEA = 215, H = 450;
  return <figure className="nino-fig">
    <div className="nino-toggle" role="tablist" aria-label="Comparar">
      <button role="tab" aria-selected={!nino} className={!nino ? "on" : ""} onClick={() => setNino(false)}>Año normal</button>
      <button role="tab" aria-selected={nino} className={nino ? "on nino" : ""} onClick={() => setNino(true)}>Con El Niño</button>
    </div>
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={nino ? "Corte del Pacífico durante El Niño" : "Corte del Pacífico en un año normal"}>
      <defs>
        <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#0d3b4f" /><stop offset="1" stopColor="#1f6f8b" /></linearGradient>
        <linearGradient id="deep" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#1b5f8c" /><stop offset="1" stopColor="#0a2a45" /></linearGradient>
        <linearGradient id="warmN" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stopColor="#ff5a3d" /><stop offset=".55" stopColor="#ff9a3d" /><stop offset="1" stopColor="#ffc46b" stopOpacity=".6" /></linearGradient>
        <linearGradient id="warmE" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stopColor="#ff9a3d" /><stop offset=".5" stopColor="#ff5a3d" /><stop offset="1" stopColor="#ff3d2e" /></linearGradient>
      </defs>
      <rect width={W} height={SEA} fill="url(#sky)" />
      <rect y={SEA} width={W} height={H - SEA} fill="url(#deep)" />
      {/* tierras */}
      <path d={`M0,${SEA - 30} C40,${SEA - 55} 70,${SEA - 20} 95,${SEA - 8} L95,${H} L0,${H}Z`} fill="#3d6b4f" />
      
      <path d={`M${W},${SEA - 120} L${W - 30},${SEA - 95} L${W - 55},${SEA - 30} L${W - 70},${SEA - 6} L${W - 70},${H} L${W},${H}Z`} fill="#6b5a3d" />
      

      {/* AÑO NORMAL */}
      <g className="nino-layer" style={{ opacity: nino ? 0 : 1 }}>
        <path d={`M95,${SEA} L830,${SEA} L830,${SEA + 18} C620,${SEA + 30} 360,${SEA + 85} 95,${SEA + 135}Z`} fill="url(#warmN)" />
        <path d={`M95,${SEA + 140} C360,${SEA + 92} 620,${SEA + 40} 830,${SEA + 22}`} stroke="#a9d8ff" strokeWidth="3" strokeDasharray="8 7" fill="none" />
        <text x="430" y={SEA + 100} className="nino-lbl small" transform={`rotate(-9 430 ${SEA + 100})`}>termoclina: límite agua cálida / fría</text>
        <path d={`M800,${SEA + 120} C790,${SEA + 80} 800,${SEA + 45} 815,${SEA + 22}`} stroke="#bfe3ff" strokeWidth="5" fill="none" markerEnd="" />
        <text x="760" y={SEA + 150} className="nino-lbl small" textAnchor="middle">sube agua fría del fondo</text>
        {[0, 1, 2].map(i => <WindArrow key={i} x={760 - i * 40} y={SEA - 95 + i * 22} len={320} dir={-1} w={6 - i} />)}
        <text x="450" y={SEA - 14} className="nino-lbl strong" textAnchor="middle">← Alisios fuertes: empujan el agua cálida hacia el oeste</text>
        <Cloud x={170} y={70} s={1.15} /><Cloud x={260} y={92} s={0.9} />
        <text x="210" y={24} className="nino-lbl" textAnchor="middle">tormentas sobre Indonesia</text>
        <text x="800" y={40} className="nino-lbl small" textAnchor="middle">cielo seco frente a Perú</text>
      </g>

      {/* EL NIÑO */}
      <g className="nino-layer" style={{ opacity: nino ? 1 : 0 }}>
        <path d={`M95,${SEA} L830,${SEA} L830,${SEA + 75} C620,${SEA + 70} 360,${SEA + 72} 95,${SEA + 80}Z`} fill="url(#warmE)" />
        <path d={`M95,${SEA + 84} C360,${SEA + 76} 620,${SEA + 74} 830,${SEA + 79}`} stroke="#a9d8ff" strokeWidth="3" strokeDasharray="8 7" fill="none" />
        <text x="460" y={SEA + 100} className="nino-lbl small" textAnchor="middle">la termoclina se aplana: no sube agua fría frente a Perú</text>
        {[0, 1].map(i => <WindArrow key={i} x={150 + i * 40} y={SEA - 80 + i * 24} len={200} dir={1} w={4} color="#ffd36b" />)}
        <WindArrow x={840} y={SEA - 50} len={60} dir={-1} w={3} color="#ffffff" />
        <text x="450" y={SEA - 14} className="nino-lbl strong" textAnchor="middle">Alisios débiles y ráfagas del oeste →: el agua cálida viaja hacia América</text>
        <Cloud x={520} y={78} s={1.0} /><Cloud x={640} y={92} s={1.15} /><Cloud x={760} y={74} s={0.95} />
        <text x="640" y={26} className="nino-lbl" textAnchor="middle">las tormentas se mudan hacia América</text>
        <rect x="430" y={SEA + 4} width="220" height="30" rx="6" fill="none" stroke="#fff" strokeWidth="2" strokeDasharray="5 4" />
        <text x="540" y={SEA + 24} className="nino-lbl" textAnchor="middle">zona Niño 3.4</text>
        <text x="200" y={40} className="nino-lbl small" textAnchor="middle">Indonesia y Australia: más seco</text>
      </g>
      <text x="10" y={SEA + 40} className="nino-lbl">Indonesia</text><text x="10" y={SEA + 58} className="nino-lbl">Australia</text>
      <text x={W - 35} y={SEA + 110} textAnchor="middle" className="nino-lbl" transform={`rotate(-90 ${W - 35} ${SEA + 110})`}>Sudamérica</text>
      <text x="10" y={H - 8} className="nino-lbl small">Esquema ilustrativo · escalas exageradas</text>
    </svg>
    <figcaption>{nino
      ? "Con El Niño los alisios se apagan, el agua cálida se acumula en el centro y el este del Pacífico y las tormentas se corren hacia América. Ese cambio reorganiza los vientos que traen la lluvia al sur del continente."
      : "En un año normal los alisios soplan del este, amontonan el agua cálida junto a Indonesia y dejan subir agua fría frente a Perú. Las grandes tormentas están del otro lado del océano."}</figcaption>
  </figure>;
}

const ZONES: { lon: number; lat: number; rx: number; ry: number; kind: "wet" | "dry"; label: string[]; side: "L" | "R"; at: number }[] = [
  { lon: -57, lat: -29, rx: 7.5, ry: 6.5, kind: "wet", label: ["Litoral, NEA, sur de Brasil,", "Uruguay y Paraguay:", "más lluvia y crecidas"], side: "R", at: -25 },
  { lon: -79.5, lat: -3.5, rx: 2.4, ry: 3.4, kind: "wet", label: ["Costa de Ecuador y", "norte de Perú: lluvias", "torrenciales"], side: "L", at: -4 },
  { lon: -61, lat: -4, rx: 10, ry: 6, kind: "dry", label: ["Amazonia: menos lluvia,", "ríos bajos, incendios"], side: "R", at: 0 },
  { lon: -69, lat: 7, rx: 6, ry: 3.6, kind: "dry", label: ["Colombia y Venezuela:", "más seco"], side: "L", at: 8 },
  { lon: -40, lat: -8, rx: 4.5, ry: 4, kind: "dry", label: ["Noreste de Brasil:", "más seco"], side: "R", at: -9 },
  { lon: -67.5, lat: -17.5, rx: 3.2, ry: 3, kind: "dry", label: ["Altiplano: lluvias", "más pobres"], side: "L", at: -17.5 },
];

export function SAImpactMap() {
  const { w, h } = SA_VIEW;
  const P = (lon: number, lat: number) => saXY(lon, lat);
  const jet = [P(-80, -31), P(-62, -29.5), P(-44, -31.5)];
  const llj = [P(-63, -8), P(-64.5, -16), P(-62, -22), P(-60, -25.5)];
  const pad = 215;
  return <figure className="nino-fig map">
    <svg viewBox={`-${pad} -10 ${w + pad * 2} ${h + 20}`} role="img" aria-label="Mapa de Sudamérica con el impacto típico de El Niño">
      <defs>
        <filter id="soft" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="9" /></filter>
        <marker id="ah" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10z" fill="#7c3aed" /></marker>
        <marker id="ah2" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10z" fill="#0f766e" /></marker>
      </defs>
      <rect x={-pad} y={-10} width={w + pad * 2} height={h + 20} fill="#eaf4fb" />
      {SA_COUNTRIES.map(c => <path key={c.id} d={c.d} fill="#fbfaf6" stroke="#b9c3c9" strokeWidth="0.9"><title>{c.name}</title></path>)}
      {ZONES.map((z, i) => { const [x, y] = P(z.lon, z.lat); return <ellipse key={i} cx={x} cy={y} rx={z.rx * SA_VIEW.k * SA_VIEW.scale} ry={z.ry * SA_VIEW.scale}
        fill={z.kind === "wet" ? "#2f80ed" : "#f2994a"} opacity=".42" filter="url(#soft)" />; })}
      {SA_RIVERS.map(r => <path key={r.name} d={r.d} fill="none" stroke="#2f80ed" strokeWidth={r.name.startsWith("Paran") || r.name.startsWith("Urug") ? 2.4 : 1.4} opacity=".85"><title>{r.name}</title></path>)}
      <path d={`M${llj[0][0]},${llj[0][1]} C${llj[1][0]},${llj[1][1]} ${llj[2][0]},${llj[2][1]} ${llj[3][0]},${llj[3][1]}`} stroke="#0f766e" strokeWidth="5" fill="none" strokeDasharray="2 9" strokeLinecap="round" markerEnd="url(#ah2)" />
      <text x={llj[1][0] + 10} y={llj[1][1]} className="map-lbl teal">humedad del Amazonas</text>
      <path d={`M${jet[0][0]},${jet[0][1]} Q${jet[1][0]},${jet[1][1] - 18} ${jet[2][0]},${jet[2][1]}`} stroke="#7c3aed" strokeWidth="4" fill="none" markerEnd="url(#ah)" />
      <text x={jet[2][0] - 10} y={jet[2][1] + 22} textAnchor="end" className="map-lbl violet">corriente en chorro reforzada</text>
      {(() => { const [x, y] = P(-58.8, -27.5); return <g><circle cx={x} cy={y} r="4.5" fill="#10222b" /><text x={x - 8} y={y - 8} textAnchor="end" className="map-lbl">Corrientes</text></g>; })()}
      {ZONES.map((z, i) => { const [x, y] = P(z.lon, z.lat); const ly = P(0, z.at)[1]; const lx = z.side === "R" ? w + 8 : -8;
        return <g key={"l" + i}><line x1={x} y1={y} x2={z.side === "R" ? lx - 3 : lx + 3} y2={ly} stroke="#667085" strokeWidth="0.8" />
          <text x={lx} y={ly - (z.label.length - 1) * 7} textAnchor={z.side === "R" ? "start" : "end"} className={"map-lbl " + z.kind}>
            {z.label.map((t, j) => <tspan key={j} x={lx} dy={j ? 14 : 0}>{t}</tspan>)}</text></g>; })}
    </svg>
    <div className="nino-legend"><span><i className="wet" />más lluvia</span><span><i className="dry" />menos lluvia</span><span><i className="llj" />humedad que baja del Amazonas</span><span><i className="jet" />corriente en chorro reforzada</span></div>
    <figcaption>Impacto típico de El Niño en primavera y verano. Las zonas son aproximadas y cada evento es distinto. Contornos: Natural Earth.</figcaption>
  </figure>;
}
