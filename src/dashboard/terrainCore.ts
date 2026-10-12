/**
 * Relieve y anegamiento del lote — núcleo de cálculo (sin dependencias, corre en el navegador).
 *
 * Inspirado en el enfoque de GeoLibre / Whitebox (opengeos/GeoLibre, MIT): el análisis
 * hidrológico se hace del lado del cliente, sin servidor y sin clave.
 *
 * Métodos declarados:
 *  - Relleno de depresiones: priority-flood (Barnes, Lehman & Mulla 2014).
 *  - Dirección de flujo: D8 sobre el DEM rellenado con épsilon (drena llanos).
 *  - Acumulación de flujo: orden descendente de cota.
 *  - Pendiente: Horn (1981), en %.
 *  - Índice topográfico de humedad (TWI): ln(a / tan β) (Beven & Kirkby 1979).
 *
 * Todo se calcula sobre una grilla lat/lon regular, fila 0 = norte.
 */

export type LatLon = [number, number];

export type DemGrid = {
  nx: number;
  ny: number;
  west: number;
  north: number;
  rx: number; // grados por celda (lon)
  ry: number; // grados por celda (lat), positivo
  z: Float32Array; // cota en m; NaN = sin dato
};

export type TerrainClassStats = { bajo: number; medio: number; alto: number };

export type TerrainSummary = {
  cells: number;
  cellM: number; // lado medio de celda en metros
  areaHa: number;
  elevMin: number;
  elevMean: number;
  elevMax: number;
  elevP5: number;
  elevP95: number;
  relief: number; // p95 - p5 dentro del lote
  slopeMeanPct: number;
  flatPct: number; // % del lote con pendiente < 0,5 %
  depressionPct: number; // % del lote con depresión >= 10 cm
  depressionHa: number;
  maxDepthM: number;
  storageM3: number; // volumen de los bajos cerrados (>= 10 cm) dentro del lote
  twiP50: number;
  twiP90: number;
  riskPct: TerrainClassStats;
  drainageHa: number; // superficie del lote atravesada por vías de escurrimiento
  position: number; // 0 = lo más bajo del entorno, 100 = lo más alto
  positionLabel: "bajo" | "media loma" | "loma";
  envMean: number;
  histogram: { from: number; to: number; pct: number }[];
};

export type TerrainAnalysis = {
  grid: DemGrid;
  mask: Uint8Array;
  slopePct: Float32Array;
  depth: Float32Array;
  acc: Float32Array; // celdas aguas arriba (incluida)
  twi: Float32Array;
  risk: Uint8Array; // 0 fuera/sin dato, 1 bajo, 2 medio, 3 alto
  drainage: Uint8Array; // 1 = vía de escurrimiento
  thresholds: { twiMed: number; twiHigh: number; drainageCells: number };
  summary: TerrainSummary;
};

const M_LAT = 110540;
const M_LON = 111320;
const DEPTH_MIN = 0.1; // m: menos que esto es ruido del DEM
const DRAINAGE_HA = 10; // ha aguas arriba para considerar vía de escurrimiento
const D8: [number, number][] = [[-1, -1], [0, -1], [1, -1], [-1, 0], [1, 0], [-1, 1], [0, 1], [1, 1]];

/** Montículo binario mínimo de índices, ordenado por prioridad (Float64). */
class MinHeap {
  private idx: Int32Array;
  private pri: Float64Array;
  size = 0;
  constructor(cap: number) {
    this.idx = new Int32Array(Math.max(16, cap));
    this.pri = new Float64Array(Math.max(16, cap));
  }
  push(i: number, p: number) {
    if (this.size === this.idx.length) {
      const ni = new Int32Array(this.size * 2), np = new Float64Array(this.size * 2);
      ni.set(this.idx); np.set(this.pri); this.idx = ni; this.pri = np;
    }
    let k = this.size++;
    while (k > 0) {
      const parent = (k - 1) >> 1;
      if (this.pri[parent] <= p) break;
      this.idx[k] = this.idx[parent]; this.pri[k] = this.pri[parent]; k = parent;
    }
    this.idx[k] = i; this.pri[k] = p;
  }
  pop(): number {
    const top = this.idx[0];
    const li = this.idx[--this.size], lp = this.pri[this.size];
    let k = 0;
    for (;;) {
      let c = 2 * k + 1;
      if (c >= this.size) break;
      if (c + 1 < this.size && this.pri[c + 1] < this.pri[c]) c++;
      if (this.pri[c] >= lp) break;
      this.idx[k] = this.idx[c]; this.pri[k] = this.pri[c]; k = c;
    }
    this.idx[k] = li; this.pri[k] = lp;
    return top;
  }
}

/**
 * Priority-flood. Con eps = 0 rellena depresiones (agua estancada);
 * con eps > 0 además da una pendiente mínima a los llanos para poder trazar el flujo.
 * Bordes de la grilla y celdas sin dato actúan como salidas.
 */
export function priorityFlood(z: Float32Array, nx: number, ny: number, eps = 0): Float64Array {
  const n = nx * ny;
  const out = new Float64Array(n);
  const closed = new Uint8Array(n);
  const heap = new MinHeap(2 * (nx + ny));
  for (let i = 0; i < n; i++) out[i] = z[i];
  for (let y = 0; y < ny; y++) {
    for (let x = 0; x < nx; x++) {
      const i = y * nx + x;
      if (Number.isNaN(z[i])) { closed[i] = 1; continue; }
      let edge = x === 0 || y === 0 || x === nx - 1 || y === ny - 1;
      if (!edge) for (const [dx, dy] of D8) if (Number.isNaN(z[(y + dy) * nx + x + dx])) { edge = true; break; }
      if (edge) { closed[i] = 1; heap.push(i, out[i]); }
    }
  }
  while (heap.size) {
    const c = heap.pop();
    const cx = c % nx, cy = (c - cx) / nx;
    for (const [dx, dy] of D8) {
      const x = cx + dx, y = cy + dy;
      if (x < 0 || y < 0 || x >= nx || y >= ny) continue;
      const k = y * nx + x;
      if (closed[k]) continue;
      closed[k] = 1;
      const floor = out[c] + eps;
      if (out[k] < floor) out[k] = floor;
      heap.push(k, out[k]);
    }
  }
  return out;
}

/** Dirección D8 (índice de la celda receptora, -1 = salida) y acumulación en celdas. */
export function flowAccumulation(filled: Float64Array, nx: number, ny: number, dxM: number, dyM: number): Float32Array {
  const n = nx * ny;
  const recv = new Int32Array(n).fill(-1);
  const diag = Math.hypot(dxM, dyM);
  for (let y = 0; y < ny; y++) {
    for (let x = 0; x < nx; x++) {
      const i = y * nx + x;
      const zi = filled[i];
      if (Number.isNaN(zi)) continue;
      let best = 0, to = -1;
      for (const [dx, dy] of D8) {
        const xx = x + dx, yy = y + dy;
        if (xx < 0 || yy < 0 || xx >= nx || yy >= ny) continue;
        const k = yy * nx + xx, zk = filled[k];
        if (Number.isNaN(zk)) continue;
        const dist = dx && dy ? diag : dx ? dxM : dyM;
        const s = (zi - zk) / dist;
        if (s > best) { best = s; to = k; }
      }
      recv[i] = to;
    }
  }
  const order: number[] = [];
  for (let i = 0; i < n; i++) if (!Number.isNaN(filled[i])) order.push(i);
  order.sort((a, b) => filled[b] - filled[a]);
  const acc = new Float32Array(n);
  for (const i of order) acc[i] = 1;
  for (const i of order) { const r = recv[i]; if (r >= 0) acc[r] += acc[i]; }
  return acc;
}

/** Pendiente de Horn en % (NaN de vecinos se reemplaza por la celda central). */
export function slopePercent(z: Float32Array, nx: number, ny: number, dxM: number, dyM: number): Float32Array {
  const out = new Float32Array(nx * ny).fill(NaN);
  const at = (x: number, y: number, c: number) => {
    x = Math.min(nx - 1, Math.max(0, x)); y = Math.min(ny - 1, Math.max(0, y));
    const v = z[y * nx + x];
    return Number.isNaN(v) ? c : v;
  };
  for (let y = 0; y < ny; y++) {
    for (let x = 0; x < nx; x++) {
      const c = z[y * nx + x];
      if (Number.isNaN(c)) continue;
      const a = at(x - 1, y - 1, c), b = at(x, y - 1, c), cc = at(x + 1, y - 1, c);
      const d = at(x - 1, y, c), f = at(x + 1, y, c);
      const g = at(x - 1, y + 1, c), h = at(x, y + 1, c), i = at(x + 1, y + 1, c);
      const dzdx = ((cc + 2 * f + i) - (a + 2 * d + g)) / (8 * dxM);
      const dzdy = ((g + 2 * h + i) - (a + 2 * b + cc)) / (8 * dyM);
      out[y * nx + x] = Math.hypot(dzdx, dzdy) * 100;
    }
  }
  return out;
}

/** Celdas cuyo centro cae dentro del polígono [[lat, lon], ...] (regla par-impar). */
export function polygonMask(grid: DemGrid, polygon: LatLon[]): Uint8Array {
  const { nx, ny, west, north, rx, ry } = grid;
  const mask = new Uint8Array(nx * ny);
  const lat = polygon.map(p => p[0]), lon = polygon.map(p => p[1]);
  for (let y = 0; y < ny; y++) {
    const py = north - (y + 0.5) * ry;
    // intersecciones de la fila con los lados
    const xs: number[] = [];
    for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
      if ((lat[i] > py) !== (lat[j] > py)) xs.push(lon[i] + (py - lat[i]) / (lat[j] - lat[i]) * (lon[j] - lon[i]));
    }
    xs.sort((a, b) => a - b);
    for (let k = 0; k + 1 < xs.length; k += 2) {
      const x0 = Math.max(0, Math.ceil((xs[k] - west) / rx - 0.5));
      const x1 = Math.min(nx - 1, Math.floor((xs[k + 1] - west) / rx - 0.5));
      for (let x = x0; x <= x1; x++) mask[y * nx + x] = 1;
    }
  }
  return mask;
}

function quantile(sorted: number[], q: number) {
  if (!sorted.length) return NaN;
  const pos = (sorted.length - 1) * q, lo = Math.floor(pos), hi = Math.ceil(pos);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
}

const r = (v: number, d = 1) => Math.round(v * 10 ** d) / 10 ** d;

export function analyzeTerrain(grid: DemGrid, polygon: LatLon[]): TerrainAnalysis {
  const { nx, ny, z, rx, ry, north } = grid;
  const n = nx * ny;
  const latC = north - (ny * ry) / 2;
  const dxM = rx * M_LON * Math.cos(latC * Math.PI / 180);
  const dyM = ry * M_LAT;
  const cellHa = dxM * dyM / 10000;

  const mask = polygonMask(grid, polygon);
  for (let i = 0; i < n; i++) if (Number.isNaN(z[i])) mask[i] = 0;
  let cells = 0;
  for (let i = 0; i < n; i++) cells += mask[i];
  if (cells < 4) throw new Error("El lote es muy chico para el DEM de 30 m (menos de 4 celdas)");

  const filled = priorityFlood(z, nx, ny, 0);
  const routed = priorityFlood(z, nx, ny, 1e-5);
  const acc = flowAccumulation(routed, nx, ny, dxM, dyM);
  const slopePct = slopePercent(z, nx, ny, dxM, dyM);
  const width = (dxM + dyM) / 2;

  const depth = new Float32Array(n).fill(NaN);
  const twi = new Float32Array(n).fill(NaN);
  const envTwi: number[] = [], envZ: number[] = [];
  for (let i = 0; i < n; i++) {
    if (Number.isNaN(z[i])) continue;
    depth[i] = Math.max(0, filled[i] - z[i]);
    const tan = Math.max(slopePct[i] / 100, 0.001);
    twi[i] = Math.log((acc[i] * dxM * dyM / width) / tan);
    envTwi.push(twi[i]); envZ.push(z[i]);
  }
  envTwi.sort((a, b) => a - b); envZ.sort((a, b) => a - b);
  // Umbrales relativos al entorno analizado: el TWI absoluto depende de la resolución.
  const twiMed = quantile(envTwi, 0.75), twiHigh = quantile(envTwi, 0.9);
  const drainageCells = Math.max(3, Math.round(DRAINAGE_HA / cellHa));

  const risk = new Uint8Array(n);
  const drainage = new Uint8Array(n);
  const zs: number[] = [], tw: number[] = [];
  let slopeSum = 0, flat = 0, dep = 0, maxDepth = 0, storage = 0, drainN = 0;
  const cls = { bajo: 0, medio: 0, alto: 0 };
  for (let i = 0; i < n; i++) {
    if (Number.isNaN(z[i])) continue;
    if (acc[i] >= drainageCells) drainage[i] = 1;
    const d = depth[i];
    const level = d >= 0.2 || twi[i] >= twiHigh ? 3 : d >= 0.05 || twi[i] >= twiMed ? 2 : 1;
    risk[i] = level;
    if (!mask[i]) continue;
    zs.push(z[i]); tw.push(twi[i]);
    slopeSum += slopePct[i];
    if (slopePct[i] < 0.5) flat++;
    if (d >= DEPTH_MIN) { dep++; storage += d * cellHa * 10000; }
    if (d > maxDepth) maxDepth = d;
    if (drainage[i]) drainN++;
    cls[level === 3 ? "alto" : level === 2 ? "medio" : "bajo"]++;
  }
  zs.sort((a, b) => a - b); tw.sort((a, b) => a - b);
  const mean = zs.reduce((a, b) => a + b, 0) / zs.length;
  const envLo = quantile(envZ, 0.1), envHi = quantile(envZ, 0.9);
  const position = envHi - envLo > 0.01 ? Math.min(100, Math.max(0, (mean - envLo) / (envHi - envLo) * 100)) : 50;
  const p5 = quantile(zs, 0.05), p95 = quantile(zs, 0.95);

  // Histograma de cotas del lote en 8 clases entre p5 y p95
  const bins = 8, lo = Math.floor(p5 * 10) / 10, hi = Math.max(lo + 0.1, Math.ceil(p95 * 10) / 10);
  const step = (hi - lo) / bins;
  const counts = new Array(bins).fill(0);
  for (const v of zs) counts[Math.min(bins - 1, Math.max(0, Math.floor((v - lo) / step)))]++;

  const pct = (k: number) => r(k / cells * 100, 1);
  return {
    grid, mask, slopePct, depth, acc, twi, risk, drainage,
    thresholds: { twiMed, twiHigh, drainageCells },
    summary: {
      cells, cellM: r(Math.sqrt(dxM * dyM), 0), areaHa: r(cells * cellHa, 1),
      elevMin: r(zs[0]), elevMean: r(mean), elevMax: r(zs[zs.length - 1]),
      elevP5: r(p5), elevP95: r(p95), relief: r(p95 - p5),
      slopeMeanPct: r(slopeSum / cells, 2), flatPct: pct(flat),
      depressionPct: pct(dep), depressionHa: r(dep * cellHa, 1), maxDepthM: r(maxDepth, 2),
      storageM3: Math.round(storage / 100) * 100,
      twiP50: r(quantile(tw, 0.5)), twiP90: r(quantile(tw, 0.9)),
      riskPct: { bajo: pct(cls.bajo), medio: pct(cls.medio), alto: pct(cls.alto) },
      drainageHa: r(drainN * cellHa, 1),
      position: Math.round(position), positionLabel: position < 33 ? "bajo" : position < 66 ? "media loma" : "loma",
      envMean: r(envZ.reduce((a, b) => a + b, 0) / envZ.length),
      histogram: counts.map((c, k) => ({ from: r(lo + k * step, 1), to: r(lo + (k + 1) * step, 1), pct: pct(c) })),
    },
  };
}

export type TerrainMode = "anegamiento" | "relieve" | "pendiente" | "twi";

const lerp = (a: number[], b: number[], t: number) => a.map((v, k) => v + (b[k] - v) * t);
function ramp(stops: number[][], t: number) {
  t = Math.min(1, Math.max(0, t));
  const s = t * (stops.length - 1), k = Math.min(stops.length - 2, Math.floor(s));
  return lerp(stops[k], stops[k + 1], s - k);
}
const ELEV = [[33, 102, 172], [103, 169, 207], [209, 229, 240], [253, 219, 199], [239, 138, 98], [178, 24, 43]];
const SLOPE = [[255, 255, 204], [161, 218, 180], [65, 182, 196], [44, 127, 184], [37, 52, 148]];
const TWI = [[254, 235, 226], [158, 202, 225], [66, 146, 198], [8, 69, 148]];
export const RISK_COLORS: Record<number, [number, number, number]> = { 1: [50, 180, 110], 2: [245, 190, 60], 3: [225, 70, 60] };
export const DRAIN_COLOR: [number, number, number] = [30, 120, 255];

/** Imagen RGBA (nx × ny) sólo dentro del lote, lista para un canvas. */
export function renderTerrain(a: TerrainAnalysis, mode: TerrainMode): Uint8ClampedArray<ArrayBuffer> {
  const { nx, ny, z } = a.grid;
  const s = a.summary;
  const px = new Uint8ClampedArray(nx * ny * 4);
  // sombreado para "relieve" con exageración vertical (la llanura es casi plana)
  const latC = a.grid.north - (ny * a.grid.ry) / 2;
  const dxM = a.grid.rx * M_LON * Math.cos(latC * Math.PI / 180), dyM = a.grid.ry * M_LAT;
  const zf = 15, az = 315 * Math.PI / 180, alt = 45 * Math.PI / 180;
  for (let y = 0; y < ny; y++) {
    for (let x = 0; x < nx; x++) {
      const i = y * nx + x;
      if (!a.mask[i]) continue;
      let c: number[];
      if (mode === "anegamiento") {
        c = a.drainage[i] ? DRAIN_COLOR : RISK_COLORS[a.risk[i]] || [0, 0, 0];
      } else if (mode === "pendiente") {
        c = ramp(SLOPE, a.slopePct[i] / 3); // 0–3 %
      } else if (mode === "twi") {
        c = ramp(TWI, (a.twi[i] - s.twiP50 + 3) / 8);
      } else {
        const t = s.elevP95 - s.elevP5 > 0.05 ? (z[i] - s.elevP5) / (s.elevP95 - s.elevP5) : 0.5;
        const g = (dx: number, dy: number) => { const v = z[Math.min(ny - 1, Math.max(0, y + dy)) * nx + Math.min(nx - 1, Math.max(0, x + dx))]; return Number.isNaN(v) ? z[i] : v; };
        const dzdx = (g(1, 0) - g(-1, 0)) / (2 * dxM) * zf, dzdy = (g(0, 1) - g(0, -1)) / (2 * dyM) * zf;
        const slope = Math.atan(Math.hypot(dzdx, dzdy)), aspect = Math.atan2(dzdy, -dzdx);
        const shade = Math.max(0, Math.cos(alt) * Math.cos(slope) + Math.sin(alt) * Math.sin(slope) * Math.cos(az - aspect));
        c = ramp(ELEV, t).map(v => v * (0.55 + 0.45 * shade));
      }
      px[i * 4] = c[0]; px[i * 4 + 1] = c[1]; px[i * 4 + 2] = c[2]; px[i * 4 + 3] = 215;
    }
  }
  return px;
}
