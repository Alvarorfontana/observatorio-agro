/** DOTS Campo: contrato común para series geoespaciales temporales.
 * Este módulo NO inventa escenas ni simula física. Solo valida y ordena
 * observaciones obtenidas de fuentes externas.
 */
export type EnvironmentalVariable = string;
export type ObservationKind = 'observed' | 'forecast' | 'scenario';
export type LayerFormat = 'geojson' | 'geotiff' | 'raster-tiles';
export type TemporalFrame = {
  id: string;
  variable: EnvironmentalVariable;
  kind: ObservationKind;
  acquiredAt: string;
  source: string;
  layerUrl: string;
  format: LayerFormat;
  units?: string;
  resolutionMeters?: number;
  qualityNote?: string;
};
export const MODULES: ReadonlyArray<{ id: EnvironmentalVariable; title: string; suggestedSources: readonly string[] }> = [
  { id: 'flood', title: 'Inundaciones y crecidas', suggestedSources: ['Sentinel-1', 'Copernicus GFM', 'INA'] },
  { id: 'vegetation', title: 'Vegetación y cultivos', suggestedSources: ['Sentinel-2', 'Landsat'] },
  { id: 'drought', title: 'Sequía', suggestedSources: ['CHIRPS', 'ERA5-Land', 'SMAP'] },
  { id: 'fire', title: 'Incendios', suggestedSources: ['NASA FIRMS', 'VIIRS', 'MODIS'] },
];
const kinds: readonly ObservationKind[] = ['observed', 'forecast', 'scenario'];
const formats: readonly LayerFormat[] = ['geojson', 'geotiff', 'raster-tiles'];
export function validateFrame(frame: TemporalFrame): string[] {
  const errors: string[] = [];
  if (!frame.id.trim()) errors.push('id vacío');
  if (!/^[a-z][a-z0-9_-]{1,63}$/.test(frame.variable)) errors.push('identificador de variable inválido');
  if (!kinds.includes(frame.kind)) errors.push('tipo desconocido');
  if (!formats.includes(frame.format)) errors.push('formato desconocido');
  if (!frame.source.trim()) errors.push('fuente vacía');
  if (!Number.isFinite(Date.parse(frame.acquiredAt))) errors.push('fecha inválida');
  try {
    const u = new URL(frame.layerUrl);
    if (u.protocol !== 'https:') errors.push('URL de capa debe usar HTTPS');
  } catch { errors.push('URL de capa inválida'); }
  if (frame.resolutionMeters !== undefined && !(frame.resolutionMeters > 0)) errors.push('resolución inválida');
  return errors;
}
export function makeTimeline(frames: readonly TemporalFrame[], variable: EnvironmentalVariable, kind: ObservationKind = 'observed'): TemporalFrame[] {
  const filtered = frames.filter(f => f.variable === variable && f.kind === kind && validateFrame(f).length === 0);
  return filtered.sort((a,b) => Date.parse(a.acquiredAt) - Date.parse(b.acquiredAt));
}
export function nearestFrame(frames: readonly TemporalFrame[], date: string): TemporalFrame | null {
  const target = Date.parse(date);
  if (!Number.isFinite(target)) return null;
  return frames.reduce<TemporalFrame | null>((best, f) => {
    if (validateFrame(f).length) return best;
    return !best || Math.abs(Date.parse(f.acquiredAt)-target) < Math.abs(Date.parse(best.acquiredAt)-target) ? f : best;
  }, null);
}
