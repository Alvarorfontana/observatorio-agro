/**
 * DOTS · Focos de calor y eventos extremos en el sur de Sudamérica.
 * Lee /api/fuentes/focos (NASA FIRMS, cuatro satélites, con provincia, cobertura y área protegida) y muestra el mapa,
 * la tabla filtrable, las descargas y el pronóstico de eventos extremos de 5 días. Sin datos simulados.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";

type Pt = { lat: number; lon: number; date: string; time: string; sat: string; conf: string; frp: number | null; dn: string; country: string; province: string; cover?: string | null; protected?: boolean };
type Prov = { country: string; province: string; count: number; frp: number; protected: number; top_cover: string | null };
type Place = { id: string; name: string; country: string; lat: number; lon: number; events: Record<string, string[]>; tmin: number | null; tmax: number | null; snow_cm: number; rain_mm: number };
type Data = { days: number; count: number; points: Pt[]; by_province: Prov[]; danger: Place[] | null; reading: string; sources: string[]; errors: Record<string, string>; enrichment_note: string | null; enriched: number; method: string };

const SAT_COLOR: Record<string, string> = { "MODIS (Terra/Aqua)": "#d94841", "VIIRS Suomi NPP": "#1a9850", "VIIRS NOAA-20": "#e6a100", "VIIRS NOAA-21": "#7b3fa0" };
const frpColor = (f: number | null) => f == null ? "#98a2b3" : f >= 100 ? "#7f0000" : f >= 30 ? "#d7301f" : f >= 10 ? "#fc8d59" : "#fdcc8a";
const EVENTS: [string, string, string][] = [["incendio", "Peligro de incendio", "#d7301f"], ["helada", "Helada", "#2166ac"], ["nevada", "Nevada", "#6a51a3"], ["calor", "Calor extremo", "#b2182b"], ["lluvia", "Lluvia fuerte", "#1b7837"]];
const dm = (iso: string) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;
const nf = (v: number | null | undefined, d = 0) => v == null ? "—" : v.toLocaleString("es-AR", { maximumFractionDigits: d, minimumFractionDigits: d });

function csvOf(rows: Pt[]) {
  const cols: (keyof Pt)[] = ["lat", "lon", "date", "time", "sat", "conf", "frp", "dn", "country", "province", "cover", "protected"];
  const esc = (v: unknown) => v == null ? "" : /[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : String(v);
  return [cols.join(","), ...rows.map(r => cols.map(c => esc(r[c])).join(","))].join("\n");
}
function download(name: string, text: string) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type: "text/csv;charset=utf-8" })); a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}
const km = (a: [number, number], b: [number, number]) => { const R = 6371, r = Math.PI / 180, dLa = (b[0] - a[0]) * r, dLo = (b[1] - a[1]) * r; const h = Math.sin(dLa / 2) ** 2 + Math.cos(a[0] * r) * Math.cos(b[0] * r) * Math.sin(dLo / 2) ** 2; return 2 * R * Math.asin(Math.sqrt(h)); };

export function Focos() {
  const [days, setDays] = useState(2);
  const [res, setRes] = useState<{ d?: Data; err?: string } | null>(null);
  const [color, setColor] = useState<"sat" | "frp">("sat");
  const [country, setCountry] = useState("Todos"), [prov, setProv] = useState("Todas"), [sat, setSat] = useState("Todos"), [cover, setCover] = useState("Todas");
  const [onlyProt, setOnlyProt] = useState(false), [q, setQ] = useState("");
  const [near, setNear] = useState<{ lat: string; lon: string; km: string }>({ lat: "", lon: "", km: "50" });
  const [page, setPage] = useState(0);
  const mapEl = useRef<HTMLDivElement | null>(null), map = useRef<L.Map | null>(null), layer = useRef<L.LayerGroup | null>(null);

  useEffect(() => {
    let live = true; setRes(null);
    fetch(`/api/fuentes/focos?dias=${days}`).then(r => r.json()).then(j => live && setRes(j.status === "recibido" ? { d: j.data } : { err: j.error || "FIRMS no respondió." }))
      .catch(() => live && setRes({ err: "No se pudo consultar NASA FIRMS." }));
    return () => { live = false };
  }, [days]);

  const d = res?.d;
  const rows = useMemo(() => {
    if (!d) return [];
    const ql = q.trim().toLowerCase();
    const c = near.lat && near.lon ? [parseFloat(near.lat.replace(",", ".")), parseFloat(near.lon.replace(",", "."))] as [number, number] : null;
    const rad = parseFloat(near.km) || 50;
    return d.points.filter(p => (country === "Todos" || p.country === country) && (prov === "Todas" || p.province === prov) && (sat === "Todos" || p.sat === sat)
      && (cover === "Todas" || p.cover === cover) && (!onlyProt || p.protected)
      && (!ql || `${p.date} ${p.sat} ${p.conf} ${p.province} ${p.country} ${p.cover || ""}`.toLowerCase().includes(ql))
      && (!c || Number.isNaN(c[0]) || Number.isNaN(c[1]) || km(c, [p.lat, p.lon]) <= rad));
  }, [d, country, prov, sat, cover, onlyProt, q, near]);
  useEffect(() => setPage(0), [rows]);

  useEffect(() => {
    if (!mapEl.current || map.current) return;
    const m = L.map(mapEl.current, { center: [-30, -60], zoom: 4, preferCanvas: true, scrollWheelZoom: false });
    L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}", { maxZoom: 16, attribution: "Esri, HERE, Garmin, © OpenStreetMap" }).addTo(m);
    layer.current = L.layerGroup().addTo(m); map.current = m;
    return () => { m.remove(); map.current = null; };
  }, [res?.d ? 1 : 0]);
  useEffect(() => {
    const g = layer.current; if (!g) return; g.clearLayers();
    rows.slice(0, 6000).forEach(p => L.circleMarker([p.lat, p.lon], { radius: color === "frp" ? Math.min(9, 3 + Math.sqrt(p.frp || 1) / 2) : 4, weight: 0.6, color: "#222", fillOpacity: .85, fillColor: color === "sat" ? SAT_COLOR[p.sat] || "#667085" : frpColor(p.frp) })
      .bindPopup(`<b>${p.province}, ${p.country}</b><br>${dm(p.date)} ${p.time} UTC · ${p.sat}<br>Intensidad (FRP): ${nf(p.frp, 1)} MW · confianza ${p.conf}<br>${p.cover ? `Cobertura: ${p.cover}<br>` : ""}${p.protected ? "<b>Dentro de un área protegida</b>" : ""}`).addTo(g));
    (d?.danger || []).filter(x => Object.values(x.events).some(v => v.length)).forEach(x => {
      const ev = EVENTS.filter(([k]) => x.events[k]?.length);
      L.marker([x.lat, x.lon], { icon: L.divIcon({ className: "fz-ev", html: `<span style="background:${ev[0][2]}">${ev.length}</span>`, iconSize: [20, 20] }) })
        .bindPopup(`<b>${x.name}</b> · próximos 5 días<br>${ev.map(([k, l]) => `${l}: ${x.events[k].map(dm).join(", ")}`).join("<br>")}`).addTo(g);
    });
  }, [rows, color, d]);

  const countries = d ? ["Todos", ...Array.from(new Set(d.points.map(p => p.country))).sort()] : ["Todos"];
  const provs = d ? ["Todas", ...Array.from(new Set(d.points.filter(p => country === "Todos" || p.country === country).map(p => p.province))).sort()] : ["Todas"];
  const covers = d ? ["Todas", ...Array.from(new Set(d.points.map(p => p.cover).filter(Boolean) as string[])).sort()] : ["Todas"];
  const sats = d ? ["Todos", ...d.sources] : ["Todos"];
  const PER = 100, shown = rows.slice(page * PER, page * PER + PER);
  const evPlaces = (d?.danger || []).filter(x => Object.values(x.events).some(v => v.length));

  return <section className="fz">
    <div className="fz-days" role="tablist" aria-label="Período">{[1, 2, 3, 5].map(n => <button key={n} role="tab" aria-selected={days === n} className={days === n ? "on" : ""} onClick={() => setDays(n)}>{n === 1 ? "Último día" : `Últimos ${n} días`}</button>)}</div>
    {!res && <p className="small">Consultando NASA FIRMS (cuatro satélites)…</p>}
    {res?.err && <p className="nn-warn">Sin dato: {res.err}</p>}
    {d && <>
      <div className="fz-head">
        <p className="fz-read">{d.reading}</p>
        <div className="fz-kpis"><div><b>{nf(d.count)}</b><span>focos</span></div><div><b>{nf(d.by_province.length)}</b><span>provincias o estados</span></div><div><b>{nf(d.points.filter(p => p.protected).length)}</b><span>en áreas protegidas</span></div><div><b>{nf(evPlaces.length)}</b><span>localidades con eventos en 5 días</span></div></div>
      </div>
      {Object.keys(d.errors || {}).length > 0 && <p className="nn-warn">No respondieron: {Object.keys(d.errors).join(", ")}. El resto de los datos está completo.</p>}
      {d.enrichment_note && <p className="small">Cobertura y áreas protegidas: {d.enrichment_note}.</p>}
      <div className="fz-grid">
        <div>
          <div className="fz-tools"><span>Color:</span><button className={color === "sat" ? "on" : ""} onClick={() => setColor("sat")}>por satélite</button><button className={color === "frp" ? "on" : ""} onClick={() => setColor("frp")}>por intensidad</button></div>
          <div ref={mapEl} className="fz-map" role="region" aria-label="Mapa de focos de calor" />
          <div className="nn-legend fz-legend">{color === "sat" ? Object.entries(SAT_COLOR).map(([k, c]) => <span key={k}><i style={{ background: c }} />{k}</span>)
            : [["menos de 10 MW", "#fdcc8a"], ["10 a 30", "#fc8d59"], ["30 a 100", "#d7301f"], ["más de 100", "#7f0000"]].map(([l, c]) => <span key={l}><i style={{ background: c }} />{l}</span>)}
            <span><i className="fz-k-ev" />localidad con eventos extremos (número de tipos)</span></div>
        </div>
        <div className="fz-side">
          <h3>Dónde se concentran</h3>
          <div className="nn-table fz-prov" role="table" tabIndex={0} aria-label="Focos por provincia"><div className="nn-tr nn-th" role="row"><span role="columnheader">Provincia o estado</span><span role="columnheader">Focos</span><span role="columnheader">Más quemado</span></div>
            {d.by_province.slice(0, 15).map(b => <div className="nn-tr" role="row" key={b.country + b.province} onClick={() => { setCountry(b.country); setProv(b.province); }}><span role="cell"><b>{b.province}</b><small>{b.country}{b.protected ? ` · ${b.protected} en áreas protegidas` : ""}</small></span><span role="cell">{nf(b.count)}</span><span role="cell">{b.top_cover || "—"}</span></div>)}</div>
          <h3>Próximos 5 días</h3>
          {d.danger == null ? <p className="small">Pronóstico no disponible.</p> : evPlaces.length === 0 ? <p className="small">Sin eventos extremos pronosticados en las localidades del monitor.</p> :
            <ul className="fz-ev-list">{evPlaces.slice(0, 14).map(x => <li key={x.id}><b>{x.name}</b> <small>{x.country}</small><br />{EVENTS.filter(([k]) => x.events[k]?.length).map(([k, l, c]) => <span key={k} className="fz-tag" style={{ borderColor: c, color: c }}>{l} {x.events[k].map(dm).join(", ")}</span>)}</li>)}</ul>}
        </div>
      </div>
      <h3 className="fz-title">Tabla de focos</h3>
      <div className="fz-filters">
        <label>Buscar<input value={q} onChange={e => setQ(e.target.value)} placeholder="fecha, satélite, provincia, cobertura…" /></label>
        <label>País<select value={country} onChange={e => { setCountry(e.target.value); setProv("Todas"); }}>{countries.map(x => <option key={x}>{x}</option>)}</select></label>
        <label>Provincia<select value={prov} onChange={e => setProv(e.target.value)}>{provs.map(x => <option key={x}>{x}</option>)}</select></label>
        <label>Satélite<select value={sat} onChange={e => setSat(e.target.value)}>{sats.map(x => <option key={x}>{x}</option>)}</select></label>
        <label>Cobertura<select value={cover} onChange={e => setCover(e.target.value)}>{covers.map(x => <option key={x}>{x}</option>)}</select></label>
        <label className="fz-check"><input type="checkbox" checked={onlyProt} onChange={e => setOnlyProt(e.target.checked)} />Sólo áreas protegidas</label>
        <label>Cerca de (lat)<input value={near.lat} onChange={e => setNear({ ...near, lat: e.target.value })} placeholder="-28.5" inputMode="decimal" /></label>
        <label>(lon)<input value={near.lon} onChange={e => setNear({ ...near, lon: e.target.value })} placeholder="-59.0" inputMode="decimal" /></label>
        <label>Radio km<input value={near.km} onChange={e => setNear({ ...near, km: e.target.value })} inputMode="numeric" /></label>
        <button className="nn-btn ghost" onClick={() => navigator.geolocation?.getCurrentPosition(p => setNear({ ...near, lat: p.coords.latitude.toFixed(3), lon: p.coords.longitude.toFixed(3) }))}>Mi ubicación</button>
        <button className="fz-clear" onClick={() => { setCountry("Todos"); setProv("Todas"); setSat("Todos"); setCover("Todas"); setOnlyProt(false); setQ(""); setNear({ lat: "", lon: "", km: "50" }); }}>Limpiar filtros</button>
      </div>
      <div className="fz-dl"><span>{nf(rows.length)} focos con estos filtros</span><button className="nn-btn ghost" onClick={() => download(`DOTS-focos-filtrados.csv`, csvOf(rows))}>Descargar filtrados (CSV)</button><a className="nn-btn ghost" href={`/api/fuentes/focos-csv?dias=${days}`} download>Descargar completa (CSV)</a></div>
      <div className="nn-table fz-table" role="table" tabIndex={0} aria-label="Focos de calor">
        <div className="nn-tr nn-th" role="row">{["Fecha y hora (UTC)", "Lugar", "Satélite", "Intensidad", "Confianza", "Cobertura", "Área protegida", ""].map(h => <span role="columnheader" key={h}>{h}</span>)}</div>
        {shown.map((p, i) => <div className="nn-tr" role="row" key={i}>
          <span role="cell">{dm(p.date)} {p.time}<small>{p.dn}</small></span><span role="cell"><b>{p.province}</b><small>{p.country} · {p.lat}, {p.lon}</small></span>
          <span role="cell"><i style={{ background: SAT_COLOR[p.sat] }} />{p.sat}</span><span role="cell">{nf(p.frp, 1)} MW</span><span role="cell">{p.conf}</span>
          <span role="cell">{p.cover ?? "—"}</span><span role="cell">{p.protected == null ? "—" : p.protected ? "Sí" : "No"}</span>
          <span role="cell"><button className="fz-go" onClick={() => { map.current?.setView([p.lat, p.lon], 11); mapEl.current?.scrollIntoView({ behavior: "smooth", block: "center" }); }}>Ver en el mapa</button></span>
        </div>)}
      </div>
      {rows.length > PER && <div className="fz-pages"><button disabled={page === 0} onClick={() => setPage(page - 1)}>← Anteriores</button><span>{page * PER + 1}-{Math.min(rows.length, page * PER + PER)} de {nf(rows.length)}</span><button disabled={(page + 1) * PER >= rows.length} onClick={() => setPage(page + 1)}>Siguientes →</button></div>}
      <p className="footnote">{d.method} Cobertura y área protegida calculadas para {nf(d.enriched)} focos (los más intensos). Fuentes: NASA FIRMS / LANCE (datos casi en tiempo real, preliminares), ESA WorldCover 2021, WDPA (UNEP-WCMC), Natural Earth, Open-Meteo.</p>
    </>}
  </section>;
}
