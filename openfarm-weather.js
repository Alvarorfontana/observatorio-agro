// DOTS OpenFarm adapter — standalone Vercel serverless endpoint.
// GET /api/openfarm-weather?lat=-28.5&lon=-59.0
export default async function handler(req, res) {
  if (req.method !== 'GET') return res.status(405).json({ error: 'Método no permitido' });
  const lat = Number(req.query.lat), lon = Number(req.query.lon);
  if (!Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180 || req.query.lat == null || req.query.lon == null)
    return res.status(400).json({ error: 'Coordenadas inválidas' });
  const params = new URLSearchParams({ latitude: String(lat), longitude: String(lon), timezone: 'auto', forecast_days: '7', daily: 'temperature_2m_max,temperature_2m_min,precipitation_sum,et0_fao_evapotranspiration,wind_speed_10m_max', current: 'temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m' });
  try {
    const upstream = await fetch(`https://api.open-meteo.com/v1/forecast?${params}`, { signal: AbortSignal.timeout(12000) });
    if (!upstream.ok) return res.status(502).json({ error: 'Servicio meteorológico no disponible' });
    const data = await upstream.json();
    res.setHeader('Cache-Control', 's-maxage=900, stale-while-revalidate=1800');
    return res.status(200).json({ source: 'Open-Meteo', retrievedAt: new Date().toISOString(), coordinates: { lat, lon }, current: data.current, daily: data.daily, units: { current: data.current_units, daily: data.daily_units }, timezone: data.timezone });
  } catch { return res.status(502).json({ error: 'No se pudo consultar Open-Meteo' }); }
}
