// "El Niño y crecidas": amenaza de crecida por período de retorno (JRC), exposición (WorldPop) e historia (GFD).
// Consume /api/fuentes/amenaza y /api/fuentes/cuenca (localidades ribereñas), y deja bajar el informe/newsletter.
import { useEffect, useState } from "react";

type Data = Record<string, any>;

const nf = (v: unknown, d = 0) => v == null || !Number.isFinite(Number(v)) ? "—" : Number(v).toLocaleString("es-AR", { minimumFractionDigits: d, maximumFractionDigits: d });
const toneDepth = (v: unknown) => v == null ? "idle" : Number(v) < 0.05 ? "ok" : Number(v) < 0.5 ? "warn" : "risk";
const toneRp = (rp: unknown) => rp == null ? "ok" : Number(rp) <= 20 ? "risk" : Number(rp) <= 100 ? "warn" : "idle";
const WET = 0.1;

export function NinoCrecidas() {
  const [stations, setStations] = useState<Data[]>([]);
  const [place, setPlace] = useState<string>("");
  const [env, setEnv] = useState<Data | null>(null);
  const [scales, setScales] = useState<Record<string, Data>>({});
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [pdfBusy, setPdfBusy] = useState(false);

  useEffect(() => {
    let live = true;
    fetch("/api/fuentes/cuenca").then(r => r.json()).then(j => {
      if (!live) return;
      const st: Data[] = (j?.data?.rivers?.stations || []).filter((s: Data) => s.lat != null && s.lon != null);
      setStations(st);
      if (st[0]) setPlace(st[0].id);
    }).catch(() => { if (live) setErr("No se pudo consultar la lista de localidades."); });
    return () => { live = false; };
  }, []);

  useEffect(() => {
    fetch("/api/fuentes/escalas").then(r => r.json()).then(j => {
      const m: Record<string, Data> = {};
      for (const s of j?.scales || []) m[s.scale] = s;
      setScales(m);
    }).catch(() => { /* la escala es informativa: si no llega, no se muestra */ });
  }, []);

  const selected = stations.find(s => s.id === place);

  useEffect(() => {
    const s = stations.find(x => x.id === place);
    if (!s) return;
    let live = true;
    setBusy(true); setErr(""); setEnv(null);
    fetch(`/api/fuentes/amenaza?lat=${s.lat}&lon=${s.lon}`, { signal: AbortSignal.timeout(45000) })
      .then(r => r.json())
      .then(j => { if (!live) return; if (j.status === "recibido" || j.status === "sin dato") setEnv(j); else setErr(j.error || "Sin datos de amenaza."); })
      .catch(() => { if (live) setErr("No se pudo consultar la amenaza de crecida."); })
      .finally(() => { if (live) setBusy(false); });
    return () => { live = false; };
  }, [place, stations]);

  const d: Data | undefined = env?.data;
  const rps: Data[] = d?.return_periods || [];
  const maxDepth = Math.max(0.5, ...rps.map((r: Data) => Number(r.depth_m) || 0));
  const schRp = scales["flood_rp_years"], schDepth = scales["flood_depth_m"];

  const downloadPdf = async () => {
    if (!selected) return;
    setPdfBusy(true);
    try {
      const r = await fetch("/api/fuentes/informe-temas", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ temas: ["amenaza", "crecidas", "inundaciones", "evacuados"], lat: selected.lat, lon: selected.lon, nombre: `El Niño y crecidas · ${selected.place}` }),
        signal: AbortSignal.timeout(60000),
      });
      if (!r.ok) throw new Error("sin respuesta");
      const blob = await r.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `DOTS-crecidas-${selected.place}.pdf`;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch { setErr("No se pudo generar el informe PDF."); }
    finally { setPdfBusy(false); }
  };

  return <section className="cp-block ncr" aria-label="Amenaza de crecida por período de retorno">
    <h3>Amenaza de crecida por período de retorno <small>JRC Global River Flood Hazard Maps v2.1 (Copernicus EMS) · LISFLOOD-FP · 90 m</small></h3>
    <p className="cp-note">Hasta dónde llega el agua del río según el modelo del JRC, para crecidas que ocurren cada 10, 20, 50, 75, 100, 200 y 500 años. Se cruza con la población que vive en 10 km a la redonda (WorldPop 2020) y con las crecidas observadas por satélite entre 2000 y 2018 (Global Flood Database).</p>

    <div className="ncr-pick">
      <label>Localidad ribereña
        <select value={place} onChange={e => setPlace(e.target.value)}>
          {stations.length === 0 && <option value="">—</option>}
          {stations.map(s => <option key={s.id} value={s.id}>{s.place} · río {s.river}</option>)}
        </select>
      </label>
      {selected && <span className="ncr-coord">{Number(selected.lat).toFixed(3)}, {Number(selected.lon).toFixed(3)}</span>}
      <button onClick={downloadPdf} disabled={pdfBusy || !selected}>{pdfBusy ? "Generando…" : "Informe PDF (amenaza + crecidas) ↓"}</button>
      {selected && <a href={`/api/fuentes/newsletter-temas?temas=amenaza,crecidas,poblaciones&nombre=El%20Ni%C3%B1o%20y%20crecidas%20%C2%B7%20${encodeURIComponent(selected.place)}&lat=${selected.lat}&lon=${selected.lon}`} target="_blank" rel="noreferrer">Ver newsletter ↗</a>}
    </div>

    {busy && <p className="cp-loading">Consultando el modelo de amenaza del JRC…</p>}
    {err && !busy && <p className="rp-error">{err} No se muestran valores supuestos.</p>}

    {d && !busy && <>
      <p className="ncr-reading">{d.reading}</p>

      <div className="ncr-head">
        <div className={`ncr-badge ${toneRp(d.first_rp_years)}`}>
          <span>Primera crecida que anega</span>
          <b>{d.first_rp_years != null ? `cada ~${d.first_rp_years} años` : "no anega (≥500 años)"}</b>
        </div>
        {schRp && <div className="ncr-scale"><span>Escala · {schRp.name} ({nf(schRp.min)}–{nf(schRp.max)} {schRp.unit})</span>
          <div className="ncr-scale-bar"><i style={{ width: `${Math.min(100, (Number(d.first_rp_years || 500) / (schRp.max || 500)) * 100)}%` }} /></div>
          <div className="ncr-legend">{schRp.bands.map((b: Data) => <span key={b.range} className={`cp-chip ${b.tone}`}>{b.range}</span>)}</div>
        </div>}
      </div>

      <div className="ncr-profile">
        <table className="cp-table">
          <thead><tr><th>Período de retorno</th><th>Profundidad (m)</th><th>Personas expuestas (10 km)</th><th>Escala</th></tr></thead>
          <tbody>{rps.map((r: Data) => {
            const e = (d.exposed || []).find((x: Data) => x.rp_years === r.rp_years);
            return <tr key={r.rp_years}>
              <td><b>{r.rp_years} años</b></td>
              <td>{r.depth_m != null ? <><b>{nf(r.depth_m, 2)}</b> m<span className="ncr-bar"><i className={`t-${toneDepth(r.depth_m)}`} style={{ width: `${Math.min(100, (r.depth_m / maxDepth) * 100)}%` }} /></span></> : <span className="cp-note">sin dato</span>}</td>
              <td>{e?.people != null ? `~${nf(e.people)}` : "—"}</td>
              <td><span className={`cp-chip ${toneDepth(r.depth_m)}`}>{r.depth_m == null ? "sin anegamiento" : r.depth_m < WET ? "< 0,10 m" : r.depth_m < 1.5 ? "anegamiento" : "profundo"}</span></td>
            </tr>;
          })}</tbody>
        </table>
      </div>

      <div className="ncr-foot">
        <div className="ncr-hist">
          <span>Historia observada 2000–2018 (Global Flood Database)</span>
          <b>{d.history?.events != null ? `${d.history.events} eventos de crecida en la zona` : "sin dato"}</b>
          <small>{d.history?.ever ? "El satélite vio agua de crecida al menos una vez." : "No se registró agua de crecida en el período."}</small>
        </div>
        {schDepth && <div className="ncr-scale"><span>Escala · {schDepth.name} ({nf(schDepth.min)}–{nf(schDepth.max)} {schDepth.unit})</span>
          <div className="ncr-legend">{schDepth.bands.map((b: Data) => <span key={b.range} className={`cp-chip ${b.tone}`}>{b.range}</span>)}</div>
        </div>}
      </div>

      <p className="cp-note">{d.caveat} Fuentes: {(d.sources || []).join(" · ")}. Ante una emergencia mandan el INA, la Prefectura Naval y Defensa Civil.</p>
    </>}

    {env?.status === "sin dato" && !err && <p className="cp-note">{env.error || "El punto no tiene amenaza del JRC (puede estar fuera del modelo, cuenca < 500 km²)."}</p>}
  </section>;
}
