export type Lot = { id: string; name: string; vertices: [number, number][]; center: [number, number]; areaHa: number; perimeterKm: number };
export type SheetSource = { status: string; payload?: Record<string, any>; error?: string; scopeKey?: string };
export type Reading = { label: string; value: number | null; unit: string; date: string; support: string };
export type Section = { title: string; state: string; source: string; url?: string; consulted: string; note?: string; readings: Reading[] };
export type Sheet = { geometry: string; sections: Record<string, Section> };
export const SHEET_SOURCES = ['variables', 'ndvi', 'suelo', 'sustentabilidad'] as const;
export const sheetScope = (lot: Lot) => JSON.stringify([lot.center, lot.vertices]);
const numeric = (x: unknown): number | null => typeof x === 'number' && Number.isFinite(x) ? x : null;
export function sheetSection(key: string, s: SheetSource): Section {
  const p = s.payload || {}, d = p.data || {};
  const titles: Record<string, string> = { variables: 'Clima', ndvi: 'Vegetación', suelo: 'Suelo', sustentabilidad: 'Cobertura' };
  const out: Section = { title: titles[key], state: s.status === 'consultando' ? 'consultando' : s.status === 'sin dato' || p.status === 'sin dato' ? 'sin dato' : 'recibido', source: p.organism || ({ variables: 'Open-Meteo', ndvi: 'Sentinel-2', suelo: 'ISRIC SoilGrids', sustentabilidad: 'ESA WorldCover · Planetary Computer' }[key] || key), url: p.source_url?.startsWith('https://') ? p.source_url : undefined, consulted: p.consulted_at || new Date().toISOString(), note: s.error || p.error, readings: [] };
  const add = (label: string, value: unknown, unit: string, date: string, support: string) => out.readings.push({ label, value: numeric(value), unit, date, support });
  if (key === 'variables') {
    add('Temperatura', d.current?.temperature_2m, '°C', d.current?.time || '', 'Modelo en grilla · punto');
    const rain = d.daily?.precipitation_sum;
    add('Lluvia pronosticada', Array.isArray(rain) && rain.length && rain.every((v: unknown) => numeric(v) !== null) ? rain.reduce((a: number, b: number) => a + b, 0) : null, 'mm', d.daily?.time?.length ? `${d.daily.time[0]} a ${d.daily.time.at(-1)}` : '', 'Acumulado del período · punto');
  } else if (key === 'ndvi') {
    add('NDVI medio', d.latest?.ndvi_mean, 'índice', d.latest?.datetime?.slice(0, 10) || '', 'Media del polígono · Sentinel-2');
  } else if (key === 'suelo') {
    for (const k of ['phh2o', 'soc', 'nitrogen', 'clay', 'sand']) {
      const r = d.dots_summary?.rows?.find((x: any) => x.key === k);
      add(r?.label || ({ phh2o: 'pH', soc: 'Carbono orgánico', nitrogen: 'Nitrógeno total', clay: 'Arcilla', sand: 'Arena' }[k]!), r?.by_depth?.['0-5cm'], r?.unit || '', 'Modelo SoilGrids · 0–5 cm', 'Punto · resolución 250 m');
    }
    add('Agua útil 0–60 cm', d.dots_summary?.available_water_mm_0_60, 'mm', 'Modelo SoilGrids', 'Derivada del perfil puntual');
    out.note = out.note || 'Estimación modelada; no sustituye muestreo de suelo ni representa el promedio del campo.';
    if (p.point_used?.note) out.note += ` Se usó ${p.point_used.note} (${p.point_used.lat}, ${p.point_used.lon}).`;
  } else if (key === 'sustentabilidad') {
    const wc = d.deforestation?.worldcover?.find((x: any) => x.year === 2021);
    for (const [k, label] of [['trees', 'Árboles'], ['grass', 'Pastizal'], ['crops', 'Cultivos']]) {
      const fraction = numeric(wc?.[k]);
      add(label, fraction === null ? null : fraction * 100, '%', 'WorldCover 2021', 'Proporción del polígono · 10 m');
    }
    out.note = 'Referencia histórica 2021. Estas tres clases no agotan la cobertura del terreno.';
    const errors = Object.entries(d.deforestation?.errors || {}).filter(([k]) => k.startsWith('wc-'));
    if (errors.length) out.note += ' Consulta WorldCover incompleta: ' + errors.map(([k, v]) => `${k}: ${v}`).join('; ');
    if (s.error || p.error) out.note += ` ${s.error || p.error}`;
  }
  if (out.state === 'recibido' && !out.readings.some(r => r.value !== null)) out.state = 'sin dato';
  return out;
}
export const readingText = (r: Reading) => r.value === null ? 'Sin dato' : `${r.value.toLocaleString('es-AR', { maximumFractionDigits: r.unit === 'índice' ? 3 : 2 })} ${r.unit}`.trim();
