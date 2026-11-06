/**
 * Perfil de elevación sobre una línea recta del DEM.
 *
 * Complementa a terrainCore (que analiza un polígono) y a demHydrology (que traza el
 * flujo D8): acá solo se muestrea la grilla entre dos puntos y se devuelven las cotas
 * con su distancia acumulada. Sirve para cortes transversales de un canal o un camino
 * y para medir el desnivel entre dos puntos del lote.
 *
 * No interpola nada que no exista: si falta el dato devuelve NaN, y quien dibuja corta
 * la línea en ese tramo.
 */
import type { DemGrid, LatLon } from "../dashboard/terrainCore";

export type ProfilePoint = { d: number; lat: number; lon: number; z: number };

export type TerrainProfile = {
  points: ProfilePoint[];
  lengthM: number;
  minZ: number;
  maxZ: number;
  reliefM: number;
  climbM: number; // suma de los ascensos
  dropM: number; // suma de los descensos, en positivo
  slopePct: number; // desnivel neto sobre longitud
  validPct: number; // porcentaje de muestras con dato
  cellM: number; // lado aproximado de celda del DEM usado
};

const RADIO_M = 6371008.8;

/** Distancia entre dos puntos en metros (haversine). */
export function distanceM(a: LatLon, b: LatLon): number {
  const rad = Math.PI / 180;
  const dLat = (b[0] - a[0]) * rad;
  const dLon = (b[1] - a[1]) * rad;
  const h = Math.sin(dLat / 2) ** 2
    + Math.cos(a[0] * rad) * Math.cos(b[0] * rad) * Math.sin(dLon / 2) ** 2;
  return 2 * RADIO_M * Math.asin(Math.min(1, Math.sqrt(h)));
}

/** Cota interpolada en un punto, promediando solo las celdas con dato. */
export function sampleGrid(grid: DemGrid, lat: number, lon: number): number {
  const x = (lon - grid.west) / grid.rx - 0.5;
  const y = (grid.north - lat) / grid.ry - 0.5;
  const x0 = Math.floor(x), y0 = Math.floor(y);
  if (x0 < -1 || y0 < -1 || x0 > grid.nx - 1 || y0 > grid.ny - 1) return NaN;
  let suma = 0, peso = 0;
  for (let dy = 0; dy <= 1; dy++) {
    for (let dx = 0; dx <= 1; dx++) {
      const ix = x0 + dx, iy = y0 + dy;
      if (ix < 0 || iy < 0 || ix >= grid.nx || iy >= grid.ny) continue;
      const v = grid.z[iy * grid.nx + ix];
      if (!Number.isFinite(v)) continue;
      const w = (dx ? x - x0 : 1 - (x - x0)) * (dy ? y - y0 : 1 - (y - y0));
      suma += v * w;
      peso += w;
    }
  }
  return peso > 0 ? suma / peso : NaN;
}

/**
 * Muestrea el DEM a lo largo del segmento a-b.
 * Devuelve null si los extremos coinciden o si no hay ninguna cota válida.
 */
export function profileAlong(grid: DemGrid, a: LatLon, b: LatLon, samples?: number): TerrainProfile | null {
  const lengthM = distanceM(a, b);
  if (!(lengthM >= 1)) return null;

  const cellM = Math.max(1, Math.abs(grid.rx) * 111_320 * Math.cos(((a[0] + b[0]) / 2) * Math.PI / 180));
  const n = samples ?? Math.max(160, Math.min(900, Math.ceil(lengthM / 20)));

  const points: ProfilePoint[] = [];
  let d = 0;
  let prev: LatLon = a;
  for (let i = 0; i < n; i++) {
    const t = i / (n - 1);
    const lat = a[0] + (b[0] - a[0]) * t;
    const lon = a[1] + (b[1] - a[1]) * t;
    if (i > 0) d += distanceM(prev, [lat, lon]);
    prev = [lat, lon];
    points.push({ d, lat, lon, z: sampleGrid(grid, lat, lon) });
  }

  const validos = points.filter(p => Number.isFinite(p.z));
  if (!validos.length) return null;

  let minZ = Infinity, maxZ = -Infinity, climb = 0, drop = 0;
  for (const p of validos) {
    if (p.z < minZ) minZ = p.z;
    if (p.z > maxZ) maxZ = p.z;
  }
  for (let i = 1; i < points.length; i++) {
    const dz = points[i].z - points[i - 1].z;
    if (!Number.isFinite(dz)) continue;
    if (dz > 0) climb += dz; else drop -= dz;
  }

  const neto = points[points.length - 1].z - points[0].z;
  return {
    points,
    lengthM: d,
    minZ,
    maxZ,
    reliefM: maxZ - minZ,
    climbM: climb,
    dropM: drop,
    slopePct: Number.isFinite(neto) ? Math.abs(neto) / d * 100 : NaN,
    validPct: validos.length / points.length * 100,
    cellM,
  };
}
