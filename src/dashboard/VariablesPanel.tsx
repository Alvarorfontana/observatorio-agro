/**
 * Panel de variables del lote (estilo Carbon / IBM: mosaicos planos, IBM Plex, color sólo con significado).
 * Toma la respuesta de Open-Meteo tal como llega y la ordena por lo que el productor necesita saber.
 * No inventa valores: si falta un dato, el mosaico lo dice.
 */
import React from "react";

type Data = Record<string, any>;
type Tone = "ok" | "warn" | "risk" | "idle";

const fmt = (v: unknown, d = 1) =>
  v !== null && v !== undefined && Number.isFinite(Number(v))
    ? Number(v).toLocaleString("es-AR", { minimumFractionDigits: d, maximumFractionDigits: d })
    : "—";

// Nombres en castellano de las variables horarias de Open-Meteo
const NAMES: Record<string, string> = {
  temperature_2m: "Temperatura del aire", relative_humidity_2m: "Humedad relativa", dew_point_2m: "Punto de rocío",
  apparent_temperature: "Sensación térmica", precipitation_probability: "Probabilidad de lluvia", precipitation: "Precipitación",
  rain: "Lluvia", showers: "Chaparrones", snowfall: "Nieve", snow_depth: "Espesor de nieve", weather_code: "Código de tiempo",
  cloud_cover: "Nubosidad total", cloud_cover_low: "Nubes bajas", cloud_cover_mid: "Nubes medias", cloud_cover_high: "Nubes altas",
  pressure_msl: "Presión a nivel del mar", surface_pressure: "Presión en superficie", visibility: "Visibilidad",
  wind_speed_10m: "Viento a 10 m", wind_speed_80m: "Viento a 80 m", wind_speed_120m: "Viento a 120 m", wind_speed_180m: "Viento a 180 m",
  wind_direction_10m: "Dirección del viento", wind_direction_80m: "Dirección del viento a 80 m", wind_gusts_10m: "Ráfagas",
  shortwave_radiation: "Radiación solar", direct_radiation: "Radiación directa", diffuse_radiation: "Radiación difusa",
  direct_normal_irradiance: "Irradiancia directa normal", terrestrial_radiation: "Radiación extraterrestre",
  sunshine_duration: "Duración del sol", uv_index: "Índice UV", uv_index_clear_sky: "Índice UV cielo despejado", is_day: "Día (1) o noche (0)",
  et0_fao_evapotranspiration: "Evapotranspiración de referencia (ET₀)", evapotranspiration: "Evapotranspiración real",
  vapour_pressure_deficit: "Déficit de presión de vapor", cape: "Energía convectiva (CAPE)", lifted_index: "Índice de levantamiento",
  freezing_level_height: "Altura de la isoterma de 0 °C", boundary_layer_height: "Altura de la capa límite",
};
export function varName(key: string) {
  if (NAMES[key]) return NAMES[key];
  let m = key.match(/^soil_temperature_(\d+)cm$/);
  if (m) return `Temperatura del suelo a ${m[1]} cm`;
  m = key.match(/^soil_moisture_(\d+)_to_(\d+)cm$/);
  if (m) return `Humedad del suelo ${m[1]}–${m[2]} cm`;
  m = key.match(/^temperature_(\d+)m$/);
  if (m) return `Temperatura a ${m[1]} m`;
  return key.replaceAll("_", " ").replace(/^\w/, c => c.toUpperCase());
}
function groupOf(key: string) {
  if (key.startsWith("soil_")) return "Suelo";
  if (key.includes("wind")) return "Viento";
  if (/radiation|irradiance|uv_index|sunshine|is_day/.test(key)) return "Sol y radiación";
  if (/precip|rain|shower|snow|evapotrans|vapour|humidity|dew/.test(key)) return "Agua y humedad";
  return "Atmósfera";
}
const GROUP_ORDER = ["Atmósfera", "Agua y humedad", "Viento", "Sol y radiación", "Suelo"];

// Lectura de cada variable: umbrales declarados, con la palabra que se muestra
const tTemp = (v: number): [Tone, string] => v >= 35 ? ["risk", "Calor extremo"] : v >= 32 ? ["warn", "Calor"] : v <= 0 ? ["risk", "Helada"] : v <= 3 ? ["warn", "Riesgo de helada"] : ["ok", "Normal"];
const tWind = (v: number): [Tone, string] => v >= 50 ? ["risk", "Muy fuerte"] : v >= 35 ? ["warn", "Fuerte"] : ["ok", "Normal"];
const tGust = (v: number): [Tone, string] => v >= 70 ? ["risk", "Muy fuertes"] : v >= 50 ? ["warn", "Fuertes"] : ["ok", "Normales"];
const tVpd = (v: number): [Tone, string] => v >= 2.5 ? ["risk", "Aire muy seco"] : v >= 1.5 ? ["warn", "Aire seco"] : ["ok", "Normal"];
const tUv = (v: number): [Tone, string] => v >= 11 ? ["risk", "Extremo"] : v >= 8 ? ["warn", "Muy alto"] : ["ok", "Moderado"];
const tThi = (v: number): [Tone, string] => v >= 79 ? ["risk", "Peligro"] : v >= 72 ? ["warn", "Alerta"] : ["ok", "Sin estrés"];
const tSoil = (v: number): [Tone, string] => v < 0.12 ? ["warn", "Suelo seco"] : ["ok", "Normal"];

type Tile = { label: string; value: unknown; unit: string; digits?: number; rule?: (v: number) => [Tone, string]; series?: (number | null)[]; hint?: string };

function Spark({ values, tone }: { values: (number | null)[]; tone: Tone }) {
  const vs = values.map(v => (v == null || !Number.isFinite(v) ? null : Number(v)));
  const ok = vs.filter((v): v is number => v != null);
  if (ok.length < 3) return null;
  const mn = Math.min(...ok), mx = Math.max(...ok), span = mx - mn || 1;
  const pts = vs.map((v, i) => (v == null ? null : `${(i / (vs.length - 1)) * 100},${22 - ((v - mn) / span) * 20}`)).filter(Boolean).join(" ");
  return (
    <svg className={`cv-spark tone-${tone}`} viewBox="0 0 100 24" preserveAspectRatio="none" aria-hidden="true">
      <polyline points={pts} fill="none" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

function TileView({ t }: { t: Tile }) {
  const n = Number(t.value);
  const has = t.value != null && Number.isFinite(n);
  const [tone, word] = has && t.rule ? t.rule(n) : (["idle", ""] as [Tone, string]);
  return (
    <div className={`cv-tile tone-${has ? tone : "idle"}`}>
      <span className="cv-label">{t.label}</span>
      <div className="cv-value">
        {has ? fmt(n, t.digits ?? 1) : <span className="cv-missing">Sin dato</span>}
        {has && t.unit && <small>{t.unit}</small>}
      </div>
      {word && tone !== "ok" && <span className={`cv-tag tone-${tone}`}>{word}</span>}
      {t.series && <Spark values={t.series} tone={has ? tone : "idle"} />}
      {t.hint && <span className="cv-hint">{t.hint}</span>}
    </div>
  );
}

export function VariablesPanel({ weather }: { weather: Data | null | undefined }) {
  if (!weather?.hourly) return null;
  const cur = weather.current || {}, h = weather.hourly || {}, dd = weather.daily || {}, units = weather.hourly_units || {};
  const times: string[] = h.time || [];
  const i0 = Math.max(0, times.findIndex(t => t >= String(cur.time || "").slice(0, 13) + ":00"));
  const next = (k: string) => (h[k] || []).slice(i0, i0 + 24) as (number | null)[];
  const at = (k: string) => h[k]?.[i0];
  const T = cur.temperature_2m, RH = cur.relative_humidity_2m;
  const thi = Number.isFinite(T) && Number.isFinite(RH) ? 1.8 * T + 32 - (0.55 - 0.0055 * RH) * (1.8 * T - 26) : null;
  const thiSeries = next("temperature_2m").map((t, k) => {
    const rh = next("relative_humidity_2m")[k];
    return t == null || rh == null ? null : 1.8 * t + 32 - (0.55 - 0.0055 * rh) * (1.8 * t - 26);
  });

  const groups: { title: string; note?: string; tiles: Tile[] }[] = [
    { title: "Ahora en el lote", tiles: [
      { label: "Temperatura", value: T, unit: "°C", rule: tTemp, series: next("temperature_2m") },
      { label: "Sensación térmica", value: cur.apparent_temperature ?? at("apparent_temperature"), unit: "°C", rule: tTemp, series: next("apparent_temperature") },
      { label: "Humedad", value: RH, unit: "%", digits: 0, series: next("relative_humidity_2m") },
      { label: "Viento", value: cur.wind_speed_10m, unit: "km/h", digits: 0, rule: tWind, series: next("wind_speed_10m") },
      { label: "Ráfagas", value: cur.wind_gusts_10m, unit: "km/h", digits: 0, rule: tGust, series: next("wind_gusts_10m") },
      { label: "Nubosidad", value: cur.cloud_cover, unit: "%", digits: 0, series: next("cloud_cover") },
    ] },
    { title: "Rodeo", note: "Índice de temperatura y humedad (THI): 72 alerta · 79 peligro", tiles: [
      { label: "THI ahora", value: thi, unit: "", rule: tThi, series: thiSeries },
      { label: "Máxima de hoy", value: dd.temperature_2m_max?.[0], unit: "°C", rule: tTemp },
      { label: "Mínima de hoy", value: dd.temperature_2m_min?.[0], unit: "°C", rule: tTemp },
    ] },
    { title: "Agua", tiles: [
      { label: "Lluvia de hoy", value: dd.precipitation_sum?.[0], unit: "mm", series: next("precipitation") },
      { label: "Probabilidad de lluvia", value: dd.precipitation_probability_max?.[0], unit: "%", digits: 0, series: next("precipitation_probability") },
      { label: "Evapotranspiración hoy", value: dd.et0_fao_evapotranspiration?.[0], unit: "mm", hint: "Agua que pide la atmósfera" },
      { label: "Déficit de presión de vapor", value: at("vapour_pressure_deficit"), unit: "kPa", digits: 2, rule: tVpd, series: next("vapour_pressure_deficit") },
    ] },
    { title: "Sol", tiles: [
      { label: "Radiación de hoy", value: dd.shortwave_radiation_sum?.[0], unit: "MJ/m²", series: next("shortwave_radiation") },
      { label: "Horas de sol", value: dd.sunshine_duration?.[0] != null ? dd.sunshine_duration[0] / 3600 : null, unit: "h" },
      { label: "Índice UV máximo", value: dd.uv_index_max?.[0], unit: "", rule: tUv },
    ] },
  ];
  const soilM = Object.keys(h).filter(k => k.startsWith("soil_moisture_")).sort((a, b) => parseInt(a.split("_")[2]) - parseInt(b.split("_")[2]));
  const soilT = Object.keys(h).filter(k => k.startsWith("soil_temperature_")).sort((a, b) => parseInt(a.split("_")[2]) - parseInt(b.split("_")[2]));
  const allKeys = Object.keys(h).filter(k => k !== "time");

  return (
    <div className="cv-panel">
      {groups.map(g => (
        <section className="cv-group" key={g.title}>
          <div className="cv-head"><h3>{g.title}</h3>{g.note && <span>{g.note}</span>}</div>
          <div className="cv-grid">{g.tiles.map(t => <TileView key={t.label} t={t} />)}</div>
        </section>
      ))}
      {(soilM.length > 0 || soilT.length > 0) && (
        <section className="cv-group">
          <div className="cv-head"><h3>Suelo</h3><span>Humedad volumétrica por profundidad · m³/m³</span></div>
          <div className="cv-soil">
            {soilM.map(k => {
              const v = h[k]?.[i0];
              const [tone] = v != null ? tSoil(v) : ["idle"];
              return (
                <div className="cv-soil-row" key={k}>
                  <span>{varName(k).replace("Humedad del suelo ", "")}</span>
                  <i><b className={`tone-${tone}`} style={{ width: `${Math.min(100, ((v || 0) / 0.5) * 100)}%` }} /></i>
                  <strong>{fmt(v, 2)}</strong>
                </div>
              );
            })}
          </div>
          {soilT.length > 0 && (
            <div className="cv-grid cv-grid-tight">
              {soilT.map(k => <TileView key={k} t={{ label: varName(k).replace("Temperatura del suelo", "Suelo"), value: h[k]?.[i0], unit: "°C", series: next(k) }} />)}
            </div>
          )}
        </section>
      )}
      <details className="cv-all">
        <summary>Todas las variables horarias · {allKeys.length}</summary>
        {GROUP_ORDER.map(gr => {
          const ks = allKeys.filter(k => groupOf(k) === gr);
          if (!ks.length) return null;
          return (
            <div className="cv-all-group" key={gr}>
              <h4>{gr}</h4>
              {ks.map(k => (
                <div className="cv-all-row" key={k}>
                  <span>{varName(k)}</span>
                  <Spark values={next(k)} tone="idle" />
                  <strong>{fmt(h[k]?.[i0], Math.abs(Number(h[k]?.[i0])) < 1 ? 2 : 1)} <small>{units[k] || ""}</small></strong>
                </div>
              ))}
            </div>
          );
        })}
        <p className="cv-foot">Valores de la hora {String(times[i0] || "").replace("T", " ")} · curva: próximas 24 horas · unidades de la fuente.</p>
      </details>
      <p className="cv-foot">
        Open-Meteo · modelos en la grilla del lote ({fmt(weather.latitude, 3)}, {fmt(weather.longitude, 3)}) · {weather.timezone || "sin zona"}. Condiciones modeladas, no medidas en el campo.
      </p>
    </div>
  );
}
