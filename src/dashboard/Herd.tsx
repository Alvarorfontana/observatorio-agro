/**
 * Módulo Ganado del tablero: rodeo del lote por categoría, resultado (carga, pasto, agua, calor, valor)
 * y registro de movimientos de hacienda (para trazabilidad e informe EUDR). Se guarda en el navegador.
 */
import React, { useState } from "react";

export type HerdRow = { cat: string; heads: string; weight: string };
export type Movement = { date: string; kind: string; cat: string; heads: string; note: string };

export const HERD_CATS: [string, string, number][] = [
  ["vaca", "Vacas", 420], ["vaquillona", "Vaquillonas", 320], ["novillo", "Novillos", 440],
  ["novillito", "Novillitos", 330], ["ternero", "Terneros y terneras", 180], ["toro", "Toros", 700],
];
const KINDS = ["Ingreso", "Egreso", "Nacimientos", "Muertes", "Vacunación", "Otro"];
const n = (v: unknown, d = 0) => v == null || !Number.isFinite(Number(v)) ? "—" : Number(v).toLocaleString("es-AR", { maximumFractionDigits: d, minimumFractionDigits: d });
const money = (v: unknown) => v == null ? "—" : "$ " + (Number(v) >= 1e6 ? n(Number(v) / 1e6, 1) + " M" : n(v));

export function HerdPanel({ rows, setRows, movements, setMovements, onRun, busy, data, error, hasLot }: {
  rows: HerdRow[]; setRows: (r: HerdRow[]) => void; movements: Movement[]; setMovements: (m: Movement[]) => void;
  onRun: () => void; busy: boolean; data: any; error?: string; hasLot: boolean;
}) {
  const [mv, setMv] = useState<Movement>({ date: new Date().toISOString().slice(0, 10), kind: "Ingreso", cat: "Vacas", heads: "", note: "" });
  const get = (cat: string) => rows.find(r => r.cat === cat) || { cat, heads: "", weight: "" };
  const put = (cat: string, k: "heads" | "weight", v: string) => {
    const others = rows.filter(r => r.cat !== cat);
    setRows([...others, { ...get(cat), [k]: v }].filter(r => r.heads !== "" || r.weight !== ""));
  };
  const f = data?.forage, h = data?.heat, val = data?.value;
  return <div className="herd">
    {!hasLot && <p className="error">Dibujá o elegí un lote: el rodeo se guarda por lote.</p>}
    <div className="lot-vars-title">Rodeo del lote</div>
    <div className="herd-form">
      <div className="herd-head"><span>Categoría</span><span>Cabezas</span><span>Peso prom. (kg)</span></div>
      {HERD_CATS.map(([k, label, w]) => <div className="herd-row" key={k}>
        <span>{label}</span>
        <input type="number" min={0} inputMode="numeric" value={get(k).heads} placeholder="0" onChange={e => put(k, "heads", e.target.value)} aria-label={`Cabezas de ${label}`} />
        <input type="number" min={30} inputMode="numeric" value={get(k).weight} placeholder={String(w)} onChange={e => put(k, "weight", e.target.value)} aria-label={`Peso de ${label}`} />
      </div>)}
    </div>
    <button className="primary" style={{ width: "100%", marginTop: 8 }} disabled={busy || !hasLot} onClick={onRun}>{busy ? "Calculando pasto, agua y calor…" : "Calcular"}</button>
    {error && <p className="error">{error}</p>}
    {data && <>
      <div className="wx-grid" style={{ marginTop: 10 }}>
        <div><span>Cabezas</span><b>{n(data.heads)}</b></div>
        <div><span>Equivalentes vaca</span><b>{n(data.ev_total, 1)}<small> EV</small></b></div>
        <div><span>Carga</span><b>{n(data.ev_ha, 2)}<small> EV/ha</small></b></div>
        <div><span>Kilos en pie</span><b>{n(data.kg_total)}<small> kg</small></b></div>
      </div>
      {f && <div className={"verdict " + (f.ratio > 1.1 ? "warn" : "ok")}><span>Pasto · últimos 30 días · {f.kind || "pastizal"}</span><b>{f.reading}</b>
        <small>Crece {n(f.supply_kg_ms_day)} kg MS/día en el lote · el rodeo come {n(data.demand_kg_ms_day)} · sostiene {n(f.capacity_ev, 1)} EV</small></div>}
      {!f && data.errors?.pasto && <p className="footnote">{data.errors.pasto}</p>}
      {h && <div className={"verdict " + (h.days_danger ? "warn" : "ok")}><span>Calor · próximos 7 días</span>
        <b>{h.days_danger ? `${h.days_danger} día(s) de peligro` : h.days_alert ? `${h.days_alert} día(s) de alerta` : "sin estrés por calor"}</b>
        <small>ITH máximo {n(h.worst_thi, 0)} ({h.worst_class}) · 72 alerta · 79 peligro · 84 emergencia</small></div>}
      {data.water_max_l_day != null && <div className="verdict ok"><span>Agua de bebida</span><b>{n(data.water_max_l_day)} litros el día de más calor</b>
        <small>{n(data.water_week_l)} litros en la semana · según peso vivo y temperatura máxima</small></div>}
      {val && <div className="verdict ok"><span>Valor de referencia · Cañuelas {val.date || ""}</span><b>{money(val.min)} a {money(val.max)}</b>
        <small>Kilos × precio mínimo y máximo del día por categoría{val.missing?.length ? ` · sin precio de referencia: ${val.missing.join(", ")}` : ""}</small></div>}
      {data.advice?.length > 0 && <><div className="lot-vars-title" style={{ marginTop: 10 }}>Qué conviene revisar</div>
        <ul className="small" style={{ paddingLeft: 18, margin: 0 }}>{data.advice.map((a: string) => <li key={a} style={{ marginBottom: 4 }}>{a}</li>)}</ul></>}
    </>}
    <div className="lot-vars-title" style={{ marginTop: 14 }}>Movimientos de hacienda</div>
    <div className="herd-mv">
      <input type="date" value={mv.date} onChange={e => setMv({ ...mv, date: e.target.value })} aria-label="Fecha" />
      <select value={mv.kind} onChange={e => setMv({ ...mv, kind: e.target.value })} aria-label="Movimiento">{KINDS.map(k => <option key={k}>{k}</option>)}</select>
      <select value={mv.cat} onChange={e => setMv({ ...mv, cat: e.target.value })} aria-label="Categoría">{HERD_CATS.map(([, l]) => <option key={l}>{l}</option>)}</select>
      <input type="number" min={0} placeholder="Cabezas" value={mv.heads} onChange={e => setMv({ ...mv, heads: e.target.value })} aria-label="Cabezas" />
      <input placeholder="Detalle (origen, destino, DTe, caravanas…)" value={mv.note} onChange={e => setMv({ ...mv, note: e.target.value })} aria-label="Detalle" />
      <button disabled={!hasLot || !mv.date} onClick={() => { setMovements([...movements, mv].sort((a, b) => a.date.localeCompare(b.date))); setMv({ ...mv, heads: "", note: "" }); }}>Agregar</button>
    </div>
    {movements.length > 0 && <div className="herd-mvlist">{movements.slice().reverse().map((m, i) => <div key={i}>
      <span>{m.date.split("-").reverse().join("/")}</span><b>{m.kind}</b><span>{m.cat}{m.heads ? ` · ${m.heads}` : ""}</span><small>{m.note}</small>
      <button aria-label="Borrar" onClick={() => setMovements(movements.filter(x => x !== m))}>×</button></div>)}</div>}
    <p className="footnote">El rodeo y los movimientos quedan guardados en este navegador, por lote. Los movimientos se suman al informe de la Unión Europea (EUDR) como registro declarado de la hacienda que pasó por el lote.</p>
    {data?.method && <details className="footnote"><summary>Cómo se calcula</summary><p style={{ whiteSpace: "pre-line" }}>{data.method}</p></details>}
  </div>;
}
