/**
 * Delimitación gratuita de lotes con Fields of The World (FTW).
 *
 * Fuente: mapa global de límites de lotes 2025 (PRUE / Fields of The World, CC-BY-4.0),
 * publicado como PMTiles en Source Cooperative. Capa `fields`, zoom 9–13, verbatim en z13.
 * Se lee directo desde el navegador con peticiones HTTP Range: sin servidor, sin clave, sin costo.
 *
 * Un lote que cruza el borde de una tesela llega recortado en varias; se reconstruye
 * uniendo las partes que se tocan en las teselas vecinas (polygon-clipping).
 */
import { PMTiles } from "pmtiles";
import { VectorTile } from "@mapbox/vector-tile";
import { PbfReader } from "pbf";
import polygonClipping from "polygon-clipping";

export const FTW_ATTRIBUTION = "Lotes sugeridos: Fields of the World / PRUE (Robinson et al. 2026), CC-BY-4.0";
export const FTW_RELIABLE = 69; // umbral recomendado por FTW (confidence >= 69)
const DIRECT = "https://data.source.coop/ftw/global-field-boundaries/pmtiles/ftw-global-fields-2025.pmtiles";
const PROXIED = "/ftw/ftw-global-fields-2025.pmtiles"; // rewrite de Vercel/Vite: evita CORS
const Z = 13;
const LAYER = "fields";

type Ring = [number, number][]; // [lon, lat]
type Poly = Ring[];
type Multi = Poly[];

export type SuggestedField = {
  polygon: [number, number][]; // [[lat, lon], ...] anillo exterior, listo para DOTS
  rings: Poly;                 // geometría completa (lon, lat) para dibujar
  confidence: number | null;
  areaHa: number | null;
  reliable: boolean;
  parts: number;               // teselas que aportaron partes
  neighborhood: Neighborhood;
};

export type Neighborhood = {
  radiusKm: number;
  count: number;        // lotes FTW con centro dentro del radio
  meanHa: number | null;
  medianHa: number | null;
  coverPct: number;     // % del círculo ocupado por lotes agrícolas detectados
  reliablePct: number | null; // % de esos lotes con confianza >= 69
};

/** Índice de compacidad (Polsby-Popper): 1 = círculo; < 0,4 lote alargado o irregular. */
export function compactness(areaHa: number, perimeterKm: number) {
  if (!areaHa || !perimeterKm) return null;
  return Math.round((4 * Math.PI * areaHa * 10000) / ((perimeterKm * 1000) ** 2) * 100) / 100;
}

/** Estadística del entorno a partir de las partes FTW ya leídas (se deduplican por área+confianza). */
export function neighborhood(all: { geom: Multi; props: Record<string, unknown> }[], lat: number, lon: number, radiusKm = 2): Neighborhood {
  const seen = new Set<string>();
  const areas: number[] = []; let reliable = 0, withConf = 0;
  const kx = 111.32 * Math.cos(lat * Math.PI / 180), ky = 110.54;
  for (const f of all) {
    const a = f.props["metrics:area"];
    const key = `${a}|${f.props.confidence}`;
    if (a == null || seen.has(key)) continue;
    const [x0, y0, x1, y1] = bbox(f.geom);
    const dx = ((x0 + x1) / 2 - lon) * kx, dy = ((y0 + y1) / 2 - lat) * ky;
    if (Math.hypot(dx, dy) > radiusKm) continue;
    seen.add(key); areas.push(Number(a) / 10000);
    if (f.props.confidence != null) { withConf++; if (Number(f.props.confidence) >= FTW_RELIABLE) reliable++; }
  }
  const sorted = areas.slice().sort((p, q) => p - q);
  const sum = areas.reduce((p, q) => p + q, 0);
  const circleHa = Math.PI * radiusKm * radiusKm * 100;
  return {
    radiusKm, count: areas.length,
    meanHa: areas.length ? Math.round(sum / areas.length * 10) / 10 : null,
    medianHa: areas.length ? Math.round(sorted[Math.floor(sorted.length / 2)] * 10) / 10 : null,
    coverPct: Math.min(100, Math.round(sum / circleHa * 1000) / 10),
    reliablePct: withConf ? Math.round(reliable / withConf * 100) : null,
  };
}

let archive: PMTiles | null = null;
let triedProxy = false;

function open(url: string) {
  archive = new PMTiles(url);
  return archive;
}

async function getTile(x: number, y: number, signal?: AbortSignal): Promise<VectorTile | null> {
  if (!archive) open(PROXIED);
  try {
    const r = await archive!.getZxy(Z, x, y, signal);
    return r?.data ? new VectorTile(new PbfReader(new Uint8Array(r.data))) : null;
  } catch (e) {
    if ((e as Error)?.name === "AbortError") throw e;
    if (!triedProxy) { // el rewrite no existe (dev local o host sin proxy): probar directo
      triedProxy = true;
      open(DIRECT);
      const r = await archive!.getZxy(Z, x, y, signal);
      return r?.data ? new VectorTile(new PbfReader(new Uint8Array(r.data))) : null;
    }
    throw e;
  }
}

export function tileOf(lat: number, lon: number, z = Z): [number, number] {
  const n = 2 ** z;
  const x = Math.floor(((lon + 180) / 360) * n);
  const r = (lat * Math.PI) / 180;
  const y = Math.floor(((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2) * n);
  return [x, y];
}

function features(tile: VectorTile | null, x: number, y: number) {
  const layer = tile?.layers[LAYER];
  const out: { geom: Multi; props: Record<string, unknown> }[] = [];
  if (!layer) return out;
  for (let i = 0; i < layer.length; i++) {
    const f = layer.feature(i);
    if (f.type !== 3) continue;
    const g = f.toGeoJSON(x, y, Z).geometry as any;
    const geom: Multi = g.type === "Polygon" ? [g.coordinates] : g.type === "MultiPolygon" ? g.coordinates : [];
    if (geom.length) out.push({ geom, props: f.properties });
  }
  return out;
}

function inRing(lon: number, lat: number, ring: Ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i], [xj, yj] = ring[j];
    if ((yi > lat) !== (yj > lat) && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

function inMulti(lon: number, lat: number, m: Multi) {
  return m.some(p => inRing(lon, lat, p[0]) && !p.slice(1).some(h => inRing(lon, lat, h)));
}

function bbox(m: Multi): [number, number, number, number] {
  let a = Infinity, b = Infinity, c = -Infinity, d = -Infinity;
  for (const p of m) for (const [x, y] of p[0]) { a = Math.min(a, x); b = Math.min(b, y); c = Math.max(c, x); d = Math.max(d, y); }
  return [a, b, c, d];
}

function touches(a: Multi, b: Multi) {
  const [a0, a1, a2, a3] = bbox(a), [b0, b1, b2, b3] = bbox(b);
  const eps = 1e-6;
  if (a2 < b0 - eps || b2 < a0 - eps || a3 < b1 - eps || b3 < a1 - eps) return false;
  try { return polygonClipping.intersection(a as any, b as any).length > 0; }
  catch { return false; }
}

function ringAreaHa(ring: Ring) {
  const lat0 = (ring.reduce((s, p) => s + p[1], 0) / ring.length) * Math.PI / 180;
  let s = 0;
  for (let i = 0; i < ring.length; i++) {
    const [x1, y1] = ring[i], [x2, y2] = ring[(i + 1) % ring.length];
    s += x1 * 111320 * Math.cos(lat0) * y2 * 110540 - x2 * 111320 * Math.cos(lat0) * y1 * 110540;
  }
  return Math.abs(s) / 2 / 10000;
}

/** Simplificación Douglas-Peucker en grados (tolerancia ~2 m) para no superar 500 vértices. */
function simplify(ring: Ring, tol = 0.00002): Ring {
  if (ring.length <= 4) return ring;
  const keep = new Uint8Array(ring.length); keep[0] = keep[ring.length - 1] = 1;
  const stack: [number, number][] = [[0, ring.length - 1]];
  while (stack.length) {
    const [s, e] = stack.pop()!;
    const [x1, y1] = ring[s], [x2, y2] = ring[e];
    let best = -1, dmax = 0;
    for (let i = s + 1; i < e; i++) {
      const [x, y] = ring[i];
      const dx = x2 - x1, dy = y2 - y1;
      const d = dx || dy ? Math.abs(dy * x - dx * y + x2 * y1 - y2 * x1) / Math.hypot(dx, dy) : Math.hypot(x - x1, y - y1);
      if (d > dmax) { dmax = d; best = i; }
    }
    if (dmax > tol && best > 0) { keep[best] = 1; stack.push([s, best], [best, e]); }
  }
  return ring.filter((_, i) => keep[i]);
}

/** Lotes FTW visibles alrededor de un punto (tesela z13 + vecinas), para dibujarlos como sugerencias. */
export async function fieldsAround(lat: number, lon: number, signal?: AbortSignal) {
  const [cx, cy] = tileOf(lat, lon);
  const jobs: Promise<{ geom: Multi; props: Record<string, unknown> }[]>[] = [];
  for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) {
    const x = cx + dx, y = cy + dy;
    jobs.push(getTile(x, y, signal).then(t => features(t, x, y)));
  }
  return (await Promise.all(jobs)).flat();
}

/** Lote FTW que contiene el punto, reconstruido entre teselas. null si FTW no tiene lote ahí. */
export async function fieldAt(lat: number, lon: number, signal?: AbortSignal): Promise<SuggestedField | null> {
  const all = await fieldsAround(lat, lon, signal);
  const hit = all.findIndex(f => inMulti(lon, lat, f.geom));
  if (hit < 0) return null;
  let geom: Multi = all[hit].geom;
  const used = new Set([hit]);
  let parts = 1, grew = true;
  while (grew) { // unir partes recortadas en teselas vecinas que se tocan con lo ya reunido
    grew = false;
    for (let i = 0; i < all.length; i++) {
      if (used.has(i) || !touches(geom, all[i].geom)) continue;
      const a = all[i].props["metrics:area"], b = all[hit].props["metrics:area"];
      if (a != null && b != null && Math.abs(Number(a) - Number(b)) > 1) continue; // otro lote vecino, no una parte
      geom = polygonClipping.union(geom as any, all[i].geom as any) as Multi;
      used.add(i); parts++; grew = true;
    }
  }
  const main = geom.slice().sort((p, q) => ringAreaHa(q[0]) - ringAreaHa(p[0]))[0];
  let outer = main[0];
  if (outer.length > 2 && outer[0][0] === outer[outer.length - 1][0] && outer[0][1] === outer[outer.length - 1][1]) outer = outer.slice(0, -1);
  let tol = 0.00002;
  let simple = simplify([...outer, outer[0]], tol).slice(0, -1);
  while (simple.length > 500) { tol *= 2; simple = simplify([...outer, outer[0]], tol).slice(0, -1); }
  const conf = all[hit].props.confidence;
  const area = all[hit].props["metrics:area"];
  const confidence = conf == null ? null : Number(conf);
  return {
    polygon: simple.map(([x, y]) => [y, x]),
    rings: main,
    confidence,
    areaHa: area != null ? Number(area) / 10000 : ringAreaHa(outer),
    reliable: confidence != null && confidence >= FTW_RELIABLE,
    parts,
    neighborhood: neighborhood(all, lat, lon),
  };
}
