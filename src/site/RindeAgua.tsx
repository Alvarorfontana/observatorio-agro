/**
 * DOTS · Rinde por agua (AquaCrop, FAO) para maíz y soja en localidades agrícolas.
 * Lee /api/fuentes/rinde-agua (lo calcula una tarea semanal en GitHub; ver scripts/rinde_agua.py). Sin datos simulados:
 * si la tarea todavía no corrió, lo dice.
 */
import { useEffect, useState } from "react";

type Outlook = { p10: number; p50: number; p90: number; below: number; near: number; above: number; members: number; vs_normal_pct: number | null };
type Crop = { normal: { p33: number; p50: number; p67: number }; last_season: { season: string; ratio: number | null } | null; outlook: Outlook | null };
type Place = { name: string; country: string; obs_until: string; forecast_until: string | null; maiz?: Crop; soja?: Crop };
type Data = { season: string; updated: string; soil: string; crops: Record<string, string>; normal_period: string; method: string; places: Record<string, Place> };

const pc = (v: number | null | undefined) => v == null ? "—" : `${Math.round(v * 100)} %`;
const sg = (v: number | null | undefined) => v == null ? "—" : `${v > 0 ? "+" : ""}${v} %`;
const ddmm = (iso?: string | null) => iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}` : "—";

function reading(o: Outlook | null) {
  if (!o) return ["sin dato", "none"];
  if (o.below >= 0.5) return ["más probable debajo de lo normal", "rev"];
  if (o.above >= 0.5) return ["más probable encima de lo normal", "yes"];
  return ["sin una señal clara", "wait"];
}

function Range({ c }: { c: Crop }) {
  const o = c.outlook, x = (v: number) => `${Math.max(0, Math.min(100, v * 100))}%`;
  return <div className="ra-range" aria-hidden="true">
    <span className="ra-normal" style={{ left: x(c.normal.p33), width: `calc(${x(c.normal.p67)} - ${x(c.normal.p33)})` }} />
    {o && <span className="ra-band" style={{ left: x(o.p10), width: `calc(${x(o.p90)} - ${x(o.p10)})` }} />}
    {o && <span className="ra-mid" style={{ left: x(o.p50) }} />}
  </div>;
}

export function RindeAgua() {
  const [res, setRes] = useState<{ data?: Data; error?: string } | null>(null);
  const [crop, setCrop] = useState<"maiz" | "soja">("maiz");
  useEffect(() => {
    let live = true;
    fetch("/api/fuentes/rinde-agua").then(r => r.json()).then(j => live && setRes(j.status === "recibido" ? { data: j.data } : { error: j.error }))
      .catch(() => live && setRes({ error: "No se pudo consultar la simulación de rinde por agua." }));
    return () => { live = false };
  }, []);
  const head = <div className="nn-head">
    <div>
      <span className="section-tag">AQUACROP · FAO</span>
      <h3>¿Cuánto rinde permite el agua de esta campaña?</h3>
      <p>Simulamos maíz y soja con el modelo AquaCrop de la FAO, en secano y con riego completo. El índice es la parte del rinde posible que deja el agua: 100 % es sin falta de agua. Para la campaña en curso usamos lo que ya llovió y el pronóstico de 16 días, y completamos el resto con el clima de cada campaña 1991-2020: el resultado es un rango, no un número.</p>
    </div>
  </div>;
  if (!res) return <section className="nino-now-sa ra-box">{head}<p className="small">Consultando…</p></section>;
  if (!res.data) return <section className="nino-now-sa ra-box">{head}<p className="nn-warn">{res.error || "Sin dato."}</p></section>;
  const d = res.data;
  const rows = Object.entries(d.places).filter(([, p]) => p[crop]).sort((a, b) => (a[1][crop]!.outlook?.p50 ?? 9) - (b[1][crop]!.outlook?.p50 ?? 9));
  const anyPlace = rows[0]?.[1];
  return <section className="nino-now-sa ra-box">
    {head}
    <div className="nn-metrics" role="tablist" aria-label="Cultivo">
      {(["maiz", "soja"] as const).map(k => <button key={k} role="tab" aria-selected={crop === k} className={crop === k ? "on" : ""} onClick={() => setCrop(k)}>{k === "maiz" ? "Maíz" : "Soja"}</button>)}
    </div>
    <p className="small">{d.crops[crop]} · suelo {d.soil.toLowerCase()} · campaña {d.season} · clima observado hasta el {ddmm(anyPlace?.obs_until)} y pronóstico hasta el {ddmm(anyPlace?.forecast_until)}.</p>
    <div className="nn-legend ra-legend"><span><i className="ra-k-normal" />rango normal {d.normal_period} (tercio central)</span><span><i className="ra-k-band" />escenarios de esta campaña (10 a 90 %)</span><span><i className="ra-k-mid" />escenario mediano</span></div>
    <div className="nn-table ra-table" role="table" aria-label={`Rinde por agua de ${crop === "maiz" ? "maíz" : "soja"}`}>
      <div className="nn-tr nn-th" role="row"><span role="columnheader">Localidad</span><span role="columnheader">Campaña pasada</span><span role="columnheader">Esta campaña (0 a 100 %)</span><span role="columnheader">Mediana vs normal</span><span role="columnheader">Debajo · normal · encima</span><span role="columnheader">Lectura</span></div>
      {rows.map(([id, p]) => {
        const c = p[crop]!, o = c.outlook, [txt, cls] = reading(o);
        return <div className="nn-tr" role="row" key={id}>
          <span role="cell"><b>{p.name}</b><small>{p.country}</small></span>
          <span role="cell">{pc(c.last_season?.ratio)}<small>{c.last_season?.season}</small></span>
          <span role="cell"><Range c={c} /><small>{o ? `${pc(o.p10)} a ${pc(o.p90)} · mediana ${pc(o.p50)}` : "sin escenarios"}</small></span>
          <span role="cell">{sg(o?.vs_normal_pct)}<small>normal {pc(c.normal.p50)}</small></span>
          <span role="cell">{o ? `${pc(o.below)} · ${pc(o.near)} · ${pc(o.above)}` : "—"}</span>
          <span role="cell" className={"nn-sig " + cls}>{txt}</span>
        </div>;
      })}
    </div>
    <p className="footnote">{d.method} Fuente: AquaCrop-OSPy (FAO), Copernicus ERA5 y pronóstico vía Open-Meteo. Actualizado el {ddmm(d.updated)}. Es un índice para comparar campañas y lugares; para un lote concreto cuentan el suelo, la napa, la fecha de siembra y el manejo.</p>
  </section>;
}
