/** DOTS OpenFarm-style data adapter. Does not require OpenFarm credentials. */
export type Coordinate = [number, number]; // GeoJSON: [longitude, latitude]
export type Polygon = { type: 'Polygon'; coordinates: Coordinate[][] };
export type MultiPolygon = { type: 'MultiPolygon'; coordinates: Coordinate[][][] };
export type Geometry = Polygon | MultiPolygon;
export function validateGeometry(geometry: Geometry): boolean {
  if (!geometry || !['Polygon', 'MultiPolygon'].includes(geometry.type)) return false;
  const polys = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates;
  return polys.length > 0 && polys.every(rings => rings.length > 0 && rings.every(ring => ring.length >= 4 && ring.every(p => p.length === 2 && p.every(Number.isFinite) && Math.abs(p[0]) <= 180 && Math.abs(p[1]) <= 90) && ring[0][0] === ring[ring.length-1][0] && ring[0][1] === ring[ring.length-1][1]));
}
export async function fetchFieldWeather(lat: number, lon: number) {
  if (!Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180) throw new Error('Coordenadas inválidas');
  const response = await fetch(`/api/openfarm-weather?lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}`);
  if (!response.ok) throw new Error(`Meteorología no disponible (${response.status})`);
  return response.json();
}
export function fieldFeature(id: string, geometry: Geometry, properties: Record<string, unknown> = {}) {
  if (!validateGeometry(geometry)) throw new Error('Polígono GeoJSON inválido');
  return { type: 'Feature' as const, id, properties: { ...properties, dotsSource: 'user-drawn' }, geometry };
}
