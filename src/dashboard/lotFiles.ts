/**
 * Importar y exportar lotes (KML de Google Earth, GeoJSON y DXF), como hace GeoLibre
 * al abrir datos vectorales: todo en el navegador, el archivo no sale del equipo.
 */
export type LatLon = [number, number];
export type ImportedLot = { name: string; polygon: LatLon[] };
export type ExportLot = { name: string; vertices: LatLon[]; areaHa: number; perimeterKm: number; origin?: string };
export type DxfCrs = "EPSG:4326" | "EPSG:3857" | "EPSG:32720" | "EPSG:32721" | "EPSG:32722";
export type DxfUnits = "degrees" | "meters" | "international-feet" | "us-survey-feet";
export type LotImportResult = { lots: ImportedLot[]; warnings: string[] };

const MAX_LOTS = 60;
const MAX_DXF_BYTES = 25 * 1024 * 1024;
const MAX_DXF_ENTITIES = 50000;
const MAX_DXF_VERTICES = 1000;
const MAX_DXF_TOTAL_VERTICES = 20000;

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

type DxfPair = { code: number; value: string };
type DxfPolyline = { layer: string; points: [number, number][] };

function dxfPairs(text: string): DxfPair[] {
  if (text.startsWith("AutoCAD Binary DXF")) throw new Error("El DXF binario no se puede leer en el navegador. Exportalo como DXF ASCII.");
  const lines = text.replace(/^\uFEFF/, "").replace(/\s+$/, "").split(/\r?\n/);
  if (lines.length < 2 || lines.length % 2 !== 0) throw new Error("El DXF no tiene pares de códigos válidos; verificá que sea un DXF ASCII.");
  const pairs: DxfPair[] = [];
  for (let i = 0; i < lines.length; i += 2) {
    const codeText = lines[i].trim(), code = Number(codeText);
    if (!/^\d+$/.test(codeText) || !Number.isInteger(code) || code > 1071) {
      throw new Error(`Código DXF inválido en la línea ${i + 1}.`);
    }
    pairs.push({ code, value: lines[i + 1].trim() });
  }
  return pairs;
}

function entityValue(entity: DxfPair[], code: number): string | undefined {
  return entity.find(pair => pair.code === code)?.value;
}

function entityNumber(entity: DxfPair[], code: number, fallback = 0): number {
  const value = entityValue(entity, code);
  if (value === undefined) return fallback;
  const n = Number(value);
  if (!Number.isFinite(n)) throw new Error("El DXF contiene una coordenada no numérica.");
  return n;
}

function dxfEntities(pairs: DxfPair[]): DxfPair[][] {
  const entities: DxfPair[][] = [];
  let inEntities = false;
  for (let i = 0; i < pairs.length;) {
    const pair = pairs[i];
    if (pair.code === 0 && pair.value === "SECTION" && pairs[i + 1]?.code === 2) {
      inEntities = pairs[i + 1].value === "ENTITIES";
      i += 2;
      continue;
    }
    if (pair.code === 0 && pair.value === "ENDSEC") { inEntities = false; i++; continue; }
    if (!inEntities || pair.code !== 0) { i++; continue; }
    const start = i++;
    while (i < pairs.length && pairs[i].code !== 0) i++;
    entities.push(pairs.slice(start, i));
    if (entities.length > MAX_DXF_ENTITIES) throw new Error(`El DXF supera el límite de ${MAX_DXF_ENTITIES.toLocaleString("es-AR")} entidades. Exportá solo los límites de los lotes.`);
  }
  if (!entities.length) throw new Error("El DXF no contiene entidades en una sección ENTITIES.");
  return entities;
}

function parseDxfPolylines(pairs: DxfPair[]): { polylines: DxfPolyline[]; warnings: string[] } {
  const entities = dxfEntities(pairs), polylines: DxfPolyline[] = [], warnings: string[] = [];
  let ignoredOpen = 0, ignoredCurves = 0, ignoredOther = 0, ignoredInvalid = 0;
  for (let i = 0; i < entities.length; i++) {
    const entity = entities[i], kind = entityValue(entity, 0);
    if (kind === "LWPOLYLINE") {
      try {
        const flags = entityNumber(entity, 70);
        const xs = entity.filter(pair => pair.code === 10).map(pair => Number(pair.value));
        const ys = entity.filter(pair => pair.code === 20).map(pair => Number(pair.value));
        const count = entityNumber(entity, 90, xs.length);
        if (entity.some(pair => pair.code === 42 && Number(pair.value) !== 0)) { ignoredCurves++; continue; }
        if ((flags & 1) === 0) { ignoredOpen++; continue; }
        if (flags & (8 | 16 | 64)) { ignoredOther++; continue; }
        if (entityNumber(entity, 38) !== 0 || entityNumber(entity, 210) !== 0 || entityNumber(entity, 220) !== 0 || entityNumber(entity, 230, 1) !== 1) { ignoredOther++; continue; }
        if (xs.length < 3 || xs.length !== ys.length || xs.length !== count || xs.length > MAX_DXF_VERTICES ||
            xs.some(x => !Number.isFinite(x)) || ys.some(y => !Number.isFinite(y))) { ignoredInvalid++; continue; }
        polylines.push({ layer: entityValue(entity, 8) || "", points: xs.map((x, index) => [x, ys[index]]) });
      } catch { ignoredInvalid++; }
      continue;
    }
    if (kind === "POLYLINE") {
      let flags = 0;
      try { flags = entityNumber(entity, 70); } catch { ignoredInvalid++; continue; }
      const vertices: [number, number][] = [];
      let hasCurve = false, hasInvalid = false;
      while (i + 1 < entities.length && entityValue(entities[i + 1], 0) === "VERTEX") {
        const vertex = entities[++i];
        try {
          const x = entityNumber(vertex, 10, Number.NaN), y = entityNumber(vertex, 20, Number.NaN);
          const z = entityNumber(vertex, 30, 0);
          if (!Number.isFinite(x) || !Number.isFinite(y) || Math.abs(z) > 1e-8) hasInvalid = true;
          vertices.push([x, y]);
          if (vertex.some(pair => pair.code === 42 && Number(pair.value) !== 0)) hasCurve = true;
        } catch { hasInvalid = true; }
      }
      if (i + 1 < entities.length && entityValue(entities[i + 1], 0) === "SEQEND") i++;
      if (hasCurve) { ignoredCurves++; continue; }
      if (flags & (2 | 4 | 8 | 16 | 64)) { ignoredOther++; continue; }
      if ((flags & 1) === 0) { ignoredOpen++; continue; }
      if (hasInvalid || vertices.length < 3 || vertices.length > MAX_DXF_VERTICES) { ignoredInvalid++; continue; }
      polylines.push({ layer: entityValue(entity, 8) || "", points: vertices });
      continue;
    }
    if (kind !== "SEQEND" && kind !== "VERTEX") ignoredOther++;
  }
  if (ignoredOpen) warnings.push(`${ignoredOpen} polilínea${ignoredOpen === 1 ? "" : "s"} abierta${ignoredOpen === 1 ? "" : "s"} ignorada${ignoredOpen === 1 ? "" : "s"}.`);
  if (ignoredCurves) warnings.push(`${ignoredCurves} polilínea${ignoredCurves === 1 ? "" : "s"} con segmentos curvos ignorada${ignoredCurves === 1 ? "" : "s"}; solo se admiten segmentos rectos.`);
  if (ignoredOther) warnings.push(`${ignoredOther} entidad${ignoredOther === 1 ? "" : "es"} no poligonal${ignoredOther === 1 ? "" : "es"} o 3D ignorada${ignoredOther === 1 ? "" : "s"}.`);
  if (ignoredInvalid) warnings.push(`${ignoredInvalid} polígono${ignoredInvalid === 1 ? "" : "s"} inválido${ignoredInvalid === 1 ? "" : "s"} ignorado${ignoredInvalid === 1 ? "" : "s"}.`);
  return { polylines, warnings };
}

function inverseUtmSouth(x: number, y: number, zone: 20 | 21 | 22): LatLon {
  const a = 6378137, f = 1 / 298.257223563, e2 = f * (2 - f), ep2 = e2 / (1 - e2), k0 = 0.9996;
  const m = (y - 10000000) / k0, east = x - 500000;
  const mu = m / (a * (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256));
  const e1 = (1 - Math.sqrt(1 - e2)) / (1 + Math.sqrt(1 - e2));
  const phi1 = mu
    + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * Math.sin(2 * mu)
    + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * Math.sin(4 * mu)
    + (151 * e1 ** 3 / 96) * Math.sin(6 * mu)
    + (1097 * e1 ** 4 / 512) * Math.sin(8 * mu);
  const sin = Math.sin(phi1), cos = Math.cos(phi1), tan = Math.tan(phi1);
  const n1 = a / Math.sqrt(1 - e2 * sin ** 2), r1 = a * (1 - e2) / (1 - e2 * sin ** 2) ** 1.5;
  const t1 = tan ** 2, c1 = ep2 * cos ** 2, d = east / (n1 * k0);
  const lat = phi1 - n1 * tan / r1 * (
    d ** 2 / 2
    - (5 + 3 * t1 + 10 * c1 - 4 * c1 ** 2 - 9 * ep2) * d ** 4 / 24
    + (61 + 90 * t1 + 298 * c1 + 45 * t1 ** 2 - 252 * ep2 - 3 * c1 ** 2) * d ** 6 / 720
  );
  const lon0 = (-183 + 6 * zone) * Math.PI / 180;
  const lon = lon0 + (
    d - (1 + 2 * t1 + c1) * d ** 3 / 6
    + (5 - 2 * c1 + 28 * t1 - 3 * c1 ** 2 + 8 * ep2 + 24 * t1 ** 2) * d ** 5 / 120
  ) / cos;
  return [lat * 180 / Math.PI, lon * 180 / Math.PI];
}

function projectDxfPoint(x: number, y: number, crs: DxfCrs, units: DxfUnits): LatLon {
  if (crs === "EPSG:4326") {
    if (units !== "degrees") throw new Error("EPSG:4326 requiere que las coordenadas estén en grados.");
    return [y, x];
  }
  if (units === "degrees") throw new Error("El CRS proyectado elegido requiere coordenadas en metros o pies.");
  const factor = units === "international-feet" ? 0.3048 : units === "us-survey-feet" ? 1200 / 3937 : 1;
  x *= factor; y *= factor;
  if (crs === "EPSG:3857") {
    const limit = 20037508.342789244;
    if (Math.abs(x) > limit || Math.abs(y) > limit) throw new Error("coordenada fuera del rango de EPSG:3857");
    return [Math.atan(Math.sinh(y / 6378137)) * 180 / Math.PI, x / 6378137 * 180 / Math.PI];
  }
  const zone = crs === "EPSG:32720" ? 20 : crs === "EPSG:32721" ? 21 : 22;
  if (x < 100000 || x > 900000 || y < 0 || y > 10000000) throw new Error(`coordenada fuera del rango habitual de UTM ${zone}S`);
  const point = inverseUtmSouth(x, y, zone);
  if (point[0] > 0 || point[0] < -80 || Math.abs(point[1] - (-183 + 6 * zone)) > 6) throw new Error(`coordenada fuera del área esperada de UTM ${zone}S`);
  return point;
}

function isValidPolygon(points: LatLon[]): boolean {
  const unique = points.filter((p, i) => points.findIndex(q => p[0] === q[0] && p[1] === q[1]) === i);
  if (unique.length < 3) return false;
  const orient = (a: LatLon, b: LatLon, c: LatLon) => (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
  const on = (a: LatLon, b: LatLon, p: LatLon) => p[0] >= Math.min(a[0], b[0]) && p[0] <= Math.max(a[0], b[0]) && p[1] >= Math.min(a[1], b[1]) && p[1] <= Math.max(a[1], b[1]);
  let area = 0;
  for (let i = 0; i < unique.length; i++) {
    const a = unique[i], b = unique[(i + 1) % unique.length];
    area += a[0] * b[1] - b[0] * a[1];
    for (let j = i + 1; j < unique.length; j++) {
      if (j === i + 1 || (i === 0 && j === unique.length - 1)) continue;
      const c = unique[j], d = unique[(j + 1) % unique.length];
      const o1 = orient(a, b, c), o2 = orient(a, b, d), o3 = orient(c, d, a), o4 = orient(c, d, b);
      if ((o1 * o2 < 0 && o3 * o4 < 0) || (o1 === 0 && on(a, b, c)) || (o2 === 0 && on(a, b, d)) || (o3 === 0 && on(c, d, a)) || (o4 === 0 && on(c, d, b))) return false;
    }
  }
  return Math.abs(area) > 1e-12;
}

export function parseDXF(text: string, fallback: string, crs?: DxfCrs | "", units?: DxfUnits | ""): LotImportResult {
  if (!crs) throw new Error("Elegí el CRS del DXF antes de importarlo. Un DXF también puede contener coordenadas locales sin georreferenciar.");
  if (!units) throw new Error("Elegí las unidades de las coordenadas del DXF.");
  const parsed = parseDxfPolylines(dxfPairs(text)), lots: ImportedLot[] = [], names = new Map<string, number>();
  let invalid = 0;
  const projectionErrors = new Map<string, number>();
  let totalVertices = 0, truncatedLots = false, truncatedVertices = false;
  for (const line of parsed.polylines) {
    try {
      const raw = line.points.filter((p, i) => i === 0 || p[0] !== line.points[i - 1][0] || p[1] !== line.points[i - 1][1]);
      if (raw.length > 1 && raw[0][0] === raw[raw.length - 1][0] && raw[0][1] === raw[raw.length - 1][1]) raw.pop();
      if (raw.length > MAX_DXF_VERTICES) { invalid++; continue; }
      if (totalVertices + raw.length > MAX_DXF_TOTAL_VERTICES) { truncatedVertices = true; break; }
      const polygon = raw.map(([x, y]) => projectDxfPoint(x, y, crs, units));
      if (polygon.some(([lat, lon]) => !Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180) || !isValidPolygon(polygon)) { invalid++; continue; }
      if (lots.length === MAX_LOTS) { truncatedLots = true; break; }
      const base = line.layer && line.layer !== "0" ? line.layer : fallback;
      const occurrence = (names.get(base) || 0) + 1;
      names.set(base, occurrence);
      lots.push({ name: occurrence === 1 ? base : `${base} (${occurrence})`, polygon });
      totalVertices += raw.length;
    } catch (error) {
      invalid++;
      const message = error instanceof Error ? error.message : "error de coordenadas";
      projectionErrors.set(message, (projectionErrors.get(message) || 0) + 1);
    }
  }
  if (invalid) parsed.warnings.push(`${invalid} polígono${invalid === 1 ? "" : "s"} inválido${invalid === 1 ? "" : "s"} ignorado${invalid === 1 ? "" : "s"}.`);
  for (const [message, count] of [...projectionErrors].slice(0, 3)) {
    parsed.warnings.push(`${count} polígono${count === 1 ? "" : "s"}: ${message}.`);
  }
  if (truncatedLots) parsed.warnings.push(`Se importaron los primeros ${MAX_LOTS} lotes; el límite por archivo es ${MAX_LOTS}.`);
  if (truncatedVertices) parsed.warnings.push(`Se alcanzó el límite de ${MAX_DXF_TOTAL_VERTICES.toLocaleString("es-AR")} vértices; la importación se detuvo.`);
  if (!lots.length) throw new Error(`No se encontró ningún polígono DXF compatible. Se aceptan polilíneas 2D cerradas con al menos 3 vértices rectos. ${parsed.warnings.join(" ")}`.trim());
  return { lots: lots.slice(0, MAX_LOTS), warnings: parsed.warnings };
}

export async function readLotFile(file: File, dxf?: { crs?: DxfCrs | ""; units?: DxfUnits | "" }): Promise<LotImportResult> {
  const name = file.name.replace(/\.[^.]+$/, "");
  if (/\.kmz$/i.test(file.name)) throw new Error("Los KMZ vienen comprimidos: en Google Earth usá «Guardar lugar como… KML».");
  if (/\.dxf$/i.test(file.name)) {
    if (file.size > MAX_DXF_BYTES) throw new Error("El DXF supera 25 MB. Exportá solo los límites de los lotes y volvé a intentarlo.");
    return parseDXF(await file.text(), name, dxf?.crs, dxf?.units);
  }
  const text = await file.text();
  const lots = /\.kml$/i.test(file.name) || text.trimStart().startsWith("<") ? parseKML(text, name) : parseGeoJSON(text, name);
  if (!lots.length) throw new Error("El archivo no tiene polígonos de lotes.");
  return { lots, warnings: [] };
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
