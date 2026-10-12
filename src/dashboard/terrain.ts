/**
 * Lectura del DEM Copernicus GLO-30 directo desde el navegador (COG + HTTP Range),
 * a la manera de GeoLibre: sin servidor de procesamiento, sin clave, sin costo.
 *
 * Teselas de 1°×1° en EPSG:4326 publicadas en AWS Open Data (copernicus-dem-30m).
 * Se leen a través del rewrite /dem de Vercel/Vite para evitar CORS.
 */
import { fromUrl } from "geotiff";
import { analyzeTerrain, renderTerrain, type DemGrid, type LatLon, type TerrainAnalysis, type TerrainMode } from "./terrainCore";

export const DEM_ATTRIBUTION =
  "Copernicus DEM GLO-30 © DLR e.V. 2010-2014 y © Airbus Defence and Space GmbH 2014-2018, provisto bajo COPERNICUS por la Unión Europea y la ESA";
export const DEM_SOURCE_URL = "https://registry.opendata.aws/copernicus-dem/";
const PREFIX = "/dem";
const MAX_CELLS = 400_000; // ≈ 360 km² a 30 m: más que esto se vuelve lento en un celular

function tileUrl(latS: number, lonW: number) {
  const ns = latS < 0 ? "S" : "N", ew = lonW < 0 ? "W" : "E";
  const name = `Copernicus_DSM_COG_10_${ns}${String(Math.abs(latS)).padStart(2, "0")}_00_${ew}${String(Math.abs(lonW)).padStart(3, "0")}_00_DEM`;
  return `${PREFIX}/${name}/${name}.tif`;
}

type Bbox = { w: number; s: number; e: number; n: number };

/** Caja del lote con margen: el agua que llega al lote viene de afuera. */
export function analysisBbox(polygon: LatLon[]): Bbox {
  const lats = polygon.map(p => p[0]), lons = polygon.map(p => p[1]);
  let s = Math.min(...lats), n = Math.max(...lats), w = Math.min(...lons), e = Math.max(...lons);
  const kx = 111.32 * Math.cos(((s + n) / 2) * Math.PI / 180), ky = 110.54;
  const spanKm = Math.max((e - w) * kx, (n - s) * ky);
  const bufKm = Math.min(5, Math.max(0.8, spanKm * 0.35));
  s -= bufKm / ky; n += bufKm / ky; w -= bufKm / kx; e += bufKm / kx;
  return { w, s, e, n };
}

export async function loadDem(b: Bbox, signal?: AbortSignal): Promise<DemGrid> {
  const rx = 1 / 3600, ry = 1 / 3600; // grilla destino: 1" (≈ 30 m)
  const nx = Math.ceil((b.e - b.w) / rx), ny = Math.ceil((b.n - b.s) / ry);
  if (nx * ny > MAX_CELLS) throw new Error("El lote es demasiado grande para analizar el relieve en el navegador. Dividilo en lotes más chicos");
  const z = new Float32Array(nx * ny).fill(NaN);
  let read = 0;
  for (let lat = Math.floor(b.s); lat <= Math.floor(b.n); lat++) {
    for (let lon = Math.floor(b.w); lon <= Math.floor(b.e); lon++) {
      let tiff;
      try { tiff = await fromUrl(tileUrl(lat, lon), { allowFullFile: false }, signal); }
      catch { continue; } // tesela inexistente (mar) o sin respuesta: queda sin dato
      const img = await tiff.getImage();
      let [tw, , , tn] = img.getBoundingBox();
      const [trx, tryNeg] = img.getResolution();
      const tr = Math.abs(tryNeg);
      if ((img.getGeoKeys() as any)?.GTRasterTypeGeoKey === 2) { tw -= trx / 2; tn += tr / 2; } // PixelIsPoint
      const W = img.getWidth(), H = img.getHeight();
      const nodata = img.getGDALNoData();
      const px0 = Math.max(0, Math.floor((b.w - tw) / trx)), px1 = Math.min(W, Math.ceil((b.e - tw) / trx) + 1);
      const py0 = Math.max(0, Math.floor((tn - b.n) / tr)), py1 = Math.min(H, Math.ceil((tn - b.s) / tr) + 1);
      if (px1 <= px0 || py1 <= py0) continue;
      const ras = await img.readRasters({ window: [px0, py0, px1, py1], samples: [0], interleave: true, signal }) as unknown as ArrayLike<number>;
      const ww = px1 - px0;
      for (let y = 0; y < ny; y++) {
        const la = b.n - (y + 0.5) * ry;
        if (la < lat || la >= lat + 1) continue;
        const py = Math.floor((tn - la) / tr) - py0;
        if (py < 0 || py >= py1 - py0) continue;
        for (let x = 0; x < nx; x++) {
          const lo = b.w + (x + 0.5) * rx;
          if (lo < lon || lo >= lon + 1) continue;
          const pxx = Math.floor((lo - tw) / trx) - px0;
          if (pxx < 0 || pxx >= ww) continue;
          const v = ras[py * ww + pxx];
          if (v === nodata || v < -1000 || !Number.isFinite(v)) continue;
          z[y * nx + x] = v; read++;
        }
      }
    }
  }
  if (!read) throw new Error("El DEM de Copernicus no respondió para esta zona. Revisá la conexión e intentá de nuevo");
  return { nx, ny, west: b.w, north: b.n, rx, ry, z };
}

export async function terrainForLot(polygon: LatLon[], signal?: AbortSignal): Promise<TerrainAnalysis> {
  const grid = await loadDem(analysisBbox(polygon), signal);
  // cálculo pesado: cedemos un cuadro para que la interfaz no se congele al mostrar "calculando"
  await new Promise(r => setTimeout(r, 0));
  return analyzeTerrain(grid, polygon);
}

/** PNG (data URL) de la capa y sus límites para L.imageOverlay. */
export function terrainImage(a: TerrainAnalysis, mode: TerrainMode): { url: string; bounds: [[number, number], [number, number]] } {
  const { nx, ny, west, north, rx, ry } = a.grid;
  const canvas = document.createElement("canvas");
  canvas.width = nx; canvas.height = ny;
  const ctx = canvas.getContext("2d")!;
  ctx.putImageData(new ImageData(renderTerrain(a, mode), nx, ny), 0, 0);
  return { url: canvas.toDataURL("image/png"), bounds: [[north - ny * ry, west], [north, west + nx * rx]] };
}

export type { TerrainAnalysis, TerrainMode } from "./terrainCore";
