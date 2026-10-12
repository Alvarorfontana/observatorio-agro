/**
 * Importar y exportar lotes (KML de Google Earth y GeoJSON), como hace GeoLibre
 * al abrir datos vectorales: todo en el navegador, el archivo no sale del equipo.
 */
export type LatLon = [number, number];
export type ImportedLot = { name: string; polygon: LatLon[] };
export type ExportLot = { name: string; vertices: LatLon[]; areaHa: number; perimeterKm: number; origin?: string };

const MAX_LOTS = 60;

/** Anillo [lon, lat] → [lat, lon] sin cierre repetido ni vértices consecutivos duplicados. */
function ring(coords: number[][]): LatLon[] {
  const out: LatLon[] = [];
  for (const c of coords) {
    const lon = Number(c[0]), lat = Number(c[1]);
    if (!Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180) continue;
    const p: LatLon = [Math.round(lat * 1e7) / 1e7, Math.round(lon * 1e7) / 1e7];
    const last = out[out.length - 1];
    if (!last || last[0] !== p[0] || last[1] !== p[1]) out.push(p);
  }
  if (out.length > 1 && out[0][0] === out[out.length - 1][0] && out[0][1] === out[out.length - 1][1]) out.pop();
  return out;
}

export function parseGeoJSON(text: string, fallback: string): ImportedLot[] {
  const g = JSON.parse(text);
  const lots: ImportedLot[] = [];
  const add = (geom: any, props: any) => {
    if (!geom) return;
    const base = String(props?.name ?? props?.nombre ?? props?.NOMBRE ?? props?.Name ?? props?.lote ?? "").trim();
    const polys = geom.type === "Polygon" ? [geom.coordinates] : geom.type === "MultiPolygon" ? geom.coordinates : [];
    if (geom.type === "GeometryCollection") (geom.geometries || []).forEach((x: any) => add(x, props));
    polys.forEach((p: number[][][], k: number) => {
      const r = ring(p?.[0] || []);
      if (r.length >= 3) lots.push({ name: (base || fallback) + (polys.length > 1 ? ` (${k + 1})` : ""), polygon: r });
    });
  };
  if (g.type === "FeatureCollection") (g.features || []).forEach((f: any) => add(f.geometry, f.properties));
  else if (g.type === "Feature") add(g.geometry, g.properties);
  else add(g, {});
  return lots.slice(0, MAX_LOTS);
}

export function parseKML(text: string, fallback: string): ImportedLot[] {
  const doc = new DOMParser().parseFromString(text, "application/xml");
  if (doc.getElementsByTagName("parsererror").length) throw new Error("El KML no se pudo leer.");
  const lots: ImportedLot[] = [];
  const polys = Array.from(doc.getElementsByTagNameNS("*", "Polygon"));
  for (const p of polys) {
    const outer = p.getElementsByTagNameNS("*", "outerBoundaryIs")[0] || p;
    const coords = outer.getElementsByTagNameNS("*", "coordinates")[0]?.textContent || "";
    const r = ring(coords.trim().split(/\s+/).map(t => t.split(",").map(Number)));
    if (r.length < 3) continue;
    let el: Element | null = p, name = "";
    while (el && !name) { if (el.localName === "Placemark") name = el.getElementsByTagNameNS("*", "name")[0]?.textContent?.trim() || ""; el = el.parentElement; }
    lots.push({ name: name || `${fallback} ${lots.length + 1}`, polygon: r });
  }
  return lots.slice(0, MAX_LOTS);
}

export async function readLotFile(file: File): Promise<ImportedLot[]> {
  const name = file.name.replace(/\.[^.]+$/, "");
  if (/\.kmz$/i.test(file.name)) throw new Error("Los KMZ vienen comprimidos: en Google Earth usá «Guardar lugar como… KML».");
  const text = await file.text();
  const lots = /\.kml$/i.test(file.name) || text.trimStart().startsWith("<") ? parseKML(text, name) : parseGeoJSON(text, name);
  if (!lots.length) throw new Error("El archivo no tiene polígonos de lotes.");
  return lots;
}

const close = (v: LatLon[]) => [...v, v[0]].map(([la, lo]) => [lo, la]);

export function lotsToGeoJSON(lots: ExportLot[]): string {
  return JSON.stringify({
    type: "FeatureCollection",
    features: lots.map(l => ({
      type: "Feature",
      properties: { name: l.name, area_ha: Math.round(l.areaHa * 100) / 100, perimetro_km: Math.round(l.perimeterKm * 1000) / 1000, origen: l.origin || "DOTS Campo" },
      geometry: { type: "Polygon", coordinates: [close(l.vertices)] },
    })),
  }, null, 1);
}

const esc = (s: string) => s.replace(/[<>&"']/g, c => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;", "'": "&apos;" }[c]!));

export function lotsToKML(lots: ExportLot[], title = "Lotes DOTS Campo"): string {
  const marks = lots.map(l => `  <Placemark><name>${esc(l.name)}</name><description>${l.areaHa.toFixed(2)} ha</description><styleUrl>#lote</styleUrl><Polygon><outerBoundaryIs><LinearRing><coordinates>${close(l.vertices).map(([lo, la]) => `${lo},${la},0`).join(" ")}</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>`).join("\n");
  return `<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>${esc(title)}</name>
  <Style id="lote"><LineStyle><color>ffe0dc57</color><width>2</width></LineStyle><PolyStyle><color>33e0dc57</color></PolyStyle></Style>
${marks}
</Document></kml>
`;
}
