/**
 * Perfil de elevación del tramo marcado en el mapa.
 *
 * Se apoya en el mismo DEM Copernicus GLO-30 que el resto del observatorio
 * (src/dashboard/terrain.ts): no hay servidor de por medio ni clave de API.
 *
 * El perfil sigue la línea recta entre los dos puntos. Sirve para cortes
 * transversales (canal, camino, lomo) y para medir desniveles; no sigue el
 * cauce ni reemplaza un relevamiento topográfico.
 */
import { useEffect, useState } from "react";
import { loadDem } from "../dashboard/terrain";
import { distanceM, profileAlong, type TerrainProfile } from "../lib/terrainProfile";
import type { LatLon } from "../dashboard/terrainCore";

type Bbox = { w: number; s: number; e: number; n: number };

/** Más que esto no es un perfil de lote: son cientos de teselas y el navegador se traba. */
const LARGO_MAX_M = 25_000;

const FONDO = "#102b37";
const BORDE = "#335968";
const TINTA = "#eef6fa";
const SUAVE = "#9fb9c6";
const VERDE = "#24d5a7";
const NARANJA = "#ffb45d";
const GRILLA = "#2a4a59";

function nf(v: number, d = 0): string {
  return v.toLocaleString("es-AR", { minimumFractionDigits: d, maximumFractionDigits: d });
}

function metros(v: number): string {
  if (Math.abs(v) >= 1000) return `${nf(v / 1000, 1)} km`;
  return `${nf(v)} m`;
}

function bboxFor(a: LatLon, b: LatLon): Bbox {
  const padLat = Math.max(0.003, Math.abs(a[0] - b[0]) * 0.12);
  const padLon = Math.max(0.003, Math.abs(a[1] - b[1]) * 0.12);
  return {
    s: Math.max(-90, Math.min(a[0], b[0]) - padLat),
    n: Math.min(90, Math.max(a[0], b[0]) + padLat),
    w: Math.max(-180, Math.min(a[1], b[1]) - padLon),
    e: Math.min(180, Math.max(a[1], b[1]) + padLon),
  };
}

/** Paso de grilla (segundos de arco) para que el tramo entre en memoria, también en tramos largos. */
function pasoPara(b: Bbox): number {
  for (const seg of [1, 2, 3, 5, 8, 10, 15, 20, 30, 45, 60, 90, 120, 180]) {
    const res = seg / 3600;
    const nx = Math.ceil((b.e - b.w) / res);
    const ny = Math.ceil((b.n - b.s) / res);
    if (nx * ny <= 250_000) return seg;
  }
  return 300;
}

function pasoBonito(span: number): number {
  if (!(span > 0)) return 1;
  const p = 10 ** Math.floor(Math.log10(span));
  const n = span / p;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * p;
}

function Perfil({ p }: { p: TerrainProfile }) {
  const W = 760, H = 260, L = 52, R = 16, T = 16, B = 34;
  const ancho = W - L - R, alto = H - T - B;
  const relleno = Math.max(0.5, p.reliefM * 0.15);
  const yMin = p.minZ - relleno, yMax = p.maxZ + relleno;
  const x = (d: number) => L + (d / p.lengthM) * ancho;
  const y = (z: number) => T + (1 - (z - yMin) / (yMax - yMin)) * alto;

  const tramos: { d: number; z: number }[][] = [];
  let actual: { d: number; z: number }[] = [];
  for (const q of p.points) {
    if (Number.isFinite(q.z)) actual.push(q);
    else if (actual.length) { tramos.push(actual); actual = []; }
  }
  if (actual.length) tramos.push(actual);

  const linea = tramos.map(t => t.map((q, i) => `${i ? "L" : "M"}${x(q.d).toFixed(1)},${y(q.z).toFixed(1)}`).join(" "));
  const area = tramos
    .filter(t => t.length > 1)
    .map(t => `M${x(t[0].d).toFixed(1)},${(T + alto).toFixed(1)} `
      + t.map(q => `L${x(q.d).toFixed(1)},${y(q.z).toFixed(1)}`).join(" ")
      + ` L${x(t[t.length - 1].d).toFixed(1)},${(T + alto).toFixed(1)} Z`);

  const pasoY = pasoBonito((yMax - yMin) / 4);
  const ticksY: number[] = [];
  for (let v = Math.ceil(yMin / pasoY) * pasoY; v <= yMax + 1e-9; v += pasoY) ticksY.push(v);

  const ticksX = [0, 0.25, 0.5, 0.75, 1].map(f => f * p.lengthM);
  const arranque = p.points[0];
  const final = p.points[p.points.length - 1];

  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img"
      aria-label={`Perfil de elevación: ${metros(p.lengthM)} de largo, ${nf(p.reliefM, 1)} metros de desnivel`}
      style={{ width: "100%", height: "auto", display: "block" }}>
      {ticksY.map(v => (
        <g key={`y${v}`}>
          <line x1={L} x2={W - R} y1={y(v)} y2={y(v)} stroke={GRILLA} strokeWidth={1} />
          <text x={L - 8} y={y(v) + 4} textAnchor="end" fontSize={11} fill={SUAVE}>{nf(v, pasoY < 1 ? 1 : 0)}</text>
        </g>
      ))}
      {ticksX.map(d => (
        <g key={`x${d}`}>
          <line x1={x(d)} x2={x(d)} y1={T} y2={T + alto} stroke={GRILLA} strokeWidth={1} strokeDasharray="2 4" />
          <text x={x(d)} y={H - 12} textAnchor={d === 0 ? "start" : d === p.lengthM ? "end" : "middle"}
            fontSize={11} fill={SUAVE}>{metros(d)}</text>
        </g>
      ))}
      {area.map((d, i) => <path key={`a${i}`} d={d} fill={VERDE} fillOpacity={0.16} stroke="none" />)}
      {linea.map((d, i) => (
        <path key={`l${i}`} d={d} fill="none" stroke={VERDE} strokeWidth={2}
          strokeLinejoin="round" strokeLinecap="round" />
      ))}
      <circle cx={x(arranque.d)} cy={y(arranque.z)} r={4} fill={VERDE} stroke={FONDO} strokeWidth={1.5} />
      <circle cx={x(final.d)} cy={y(final.z)} r={4} fill={NARANJA} stroke={FONDO} strokeWidth={1.5} />
      <text x={L - 8} y={T - 4} textAnchor="end" fontSize={10} fill={SUAVE}>m s.n.m.</text>
    </svg>
  );
}

export function TerrainProfile({ start, end }: { start: LatLon; end: LatLon }) {
  const [perfil, setPerfil] = useState<TerrainProfile | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [a0, a1] = start;
  const [b0, b1] = end;

  useEffect(() => {
    const ctrl = new AbortController();
    setCargando(true);
    setError("");
    setPerfil(null);
    const largo = distanceM([a0, a1], [b0, b1]);
    if (largo > LARGO_MAX_M) {
      setError(`El tramo mide ${nf(largo / 1000)} km. Acercate en el mapa y marcá dos puntos a menos de 25 km: el perfil está pensado para un lote o un canal, no para media provincia.`);
      setCargando(false);
      return () => ctrl.abort();
    }
    (async () => {
      try {
        const bbox = bboxFor([a0, a1], [b0, b1]);
        const grid = await loadDem(bbox, ctrl.signal, pasoPara(bbox));
        await new Promise(r => setTimeout(r, 0)); // deja pintar el estado de carga
        if (ctrl.signal.aborted) return;
        const p = profileAlong(grid, [a0, a1], [b0, b1]);
        if (!p) throw new Error("No hay cotas suficientes sobre ese tramo. Probá con puntos sobre tierra firme.");
        setPerfil(p);
      } catch (e) {
        if (ctrl.signal.aborted) return;
        setError(e instanceof Error ? e.message : "No se pudo leer el relieve de ese tramo.");
      } finally {
        if (!ctrl.signal.aborted) setCargando(false);
      }
    })();
    return () => ctrl.abort();
  }, [a0, a1, b0, b1]);

  return (
    <section aria-label="Perfil del terreno del tramo"
      style={{ background: FONDO, border: `1px solid ${BORDE}`, borderRadius: 12, padding: 14, margin: "14px 0", color: TINTA }}>
      <h2 style={{ margin: "0 0 4px" }}>Perfil del terreno</h2>
      <p style={{ margin: "0 0 10px", fontSize: 13, color: SUAVE }}>
        Corte de elevación entre los dos puntos marcados. Sirve para ver desniveles, pendientes y si un bajo tiene salida.
      </p>

      {cargando && <p role="status" style={{ margin: 0 }}>Leyendo el relieve del tramo…</p>}
      {!cargando && error && <p role="alert" style={{ margin: 0 }}>{error}</p>}

      {!cargando && perfil && (
        <>
          <Perfil p={perfil} />
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 10, marginTop: 12 }}>
            <div>
              <div style={{ fontSize: 11, color: SUAVE, textTransform: "uppercase", letterSpacing: ".04em" }}>Largo del tramo</div>
              <div style={{ fontSize: 20, fontWeight: 700 }}>{metros(perfil.lengthM)}</div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: SUAVE, textTransform: "uppercase", letterSpacing: ".04em" }}>Desnivel</div>
              <div style={{ fontSize: 20, fontWeight: 700 }}>{nf(perfil.reliefM, 1)} m</div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: SUAVE, textTransform: "uppercase", letterSpacing: ".04em" }}>Pendiente media</div>
              <div style={{ fontSize: 20, fontWeight: 700 }}>{nf(perfil.slopePct, 1)} %</div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: SUAVE, textTransform: "uppercase", letterSpacing: ".04em" }}>Cota mín. / máx.</div>
              <div style={{ fontSize: 20, fontWeight: 700 }}>{nf(perfil.minZ)} / {nf(perfil.maxZ)} m</div>
            </div>
          </div>
          <p style={{ margin: "10px 0 0", fontSize: 12, color: SUAVE }}>
            El perfil sigue la línea recta entre los puntos, no el cauce. Resolución del DEM: ~{nf(perfil.cellM)} m por celda
            {perfil.validPct < 99.5 ? `; ${nf(perfil.validPct)} % del tramo con dato` : ""}.
            Fuente: Copernicus DEM GLO-30.
          </p>
        </>
      )}
    </section>
  );
}
