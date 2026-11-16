/**
 * DOTS · Anegamientos por radar Sentinel-1 en Corrientes.
 * Lee /api/fuentes/anegamientos (tarea semanal en GitHub Actions, cruzada con el INA). Mapa de manchas de agua nueva,
 * tabla por zona con el contraste del río, serie de % de agua, rangos de lectura y límites. Sin datos simulados.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";

type Mancha = { id: number; superficie_ha: number; z_medio: number; z_pico: number; intensidad: string; centroide?: [number, number] };
type Zona = {
  zona: string; estado: string; detalle?: string; centro?: [number, number]; bbox?: number[]; orbita?: string;
  fecha_actual?: string; cobertura?: number; umbral_db?: number; umbral_metodo?: string;
  resumen?: { agua_hoy_ha: number; agua_habitual_ha: number; agua_nueva_ha: number; manchas: number };
  manchas?: Mancha[]; manchas_total?: number; serie?: { fecha: string; agua_pct: number; rara: boolean }[];
  ina?: { place: string; river: string; to: string; height: number; alert?: number; evac?: number; date: string } | null;
  coincide?: boolean | null; contraste?: string;
};

const COLOR: Record<string, string> = { fuerte: "#1d4ed8", moderada: "#3b82f6", leve: "#93c5fd" };
const nf = (v: number | undefined | null, d = 0) => v == null ? "—" : v.toLocaleString("es-AR", { maximumFractionDigits: d, minimumFractionDigits: d });
const fecha = (s?: string) => s ? s.slice(0, 10).split("-").reverse().join("/") : "—";

function Serie({ s }: { s: NonNullable<Zona["serie"]> }) {
  if (s.length < 2) return null;
  const W = 520, H = 120, P = 28, max = Math.max(...s.map(x => x.agua_pct), 1);
  const x = (i: number) => P + i * (W - 2 * P) / (s.length - 1), y = (v: number) => H - P + 6 - v / max * (H - P - 10);
  return <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Porcentaje del recuadro con agua en cada pasada" style={{ width: "100%", maxWidth: W }}>
    <line x1={P} x2={W - P} y1={y(0)} y2={y(0)} stroke="#c7cdd1" />
    <text x={4} y={y(max)} fontSize="10" fill="#5b6770">{nf(max, 1)} %</text><text x={4} y={y(0)} fontSize="10" fill="#5b6770">0 %</text>
    <polyline fill="none" stroke="#1d4ed8" strokeWidth="1.6" points={s.map((p, i) => `${x(i)},${y(p.agua_pct)}`).join(" ")} />
    {s.map((p, i) => <circle key={i} cx={x(i)} cy={y(p.agua_pct)} r={p.rara ? 4.5 : 2.5} fill={p.rara ? "#d9480f" : "#1d4ed8"}><title>{fecha(p.fecha)}: {nf(p.agua_pct, 2)} % con agua{p.rara ? " · fecha rara (Hampel)" : ""}</title></circle>)}
    <text x={P} y={H - 2} fontSize="10" fill="#5b6770">{fecha(s[0].fecha)}</text><text x={W - P} y={H - 2} fontSize="10" fill="#5b6770" textAnchor="end">{fecha(s[s.length - 1].fecha)}</text>
  </svg>;
}

function Barras({ z }: { z: Zona }) {
  const r = z.resumen; if (!r) return null;
  const max = Math.max(r.agua_hoy_ha, r.agua_habitual_ha, 1);
  const fila = (t: string, v: number, c: string) => <div style={{ display: "grid", gridTemplateColumns: "120px 1fr 80px", gap: 8, alignItems: "center", fontSize: 13 }}>
    <span>{t}</span><span style={{ background: "#eef1f3", height: 10 }}><span style={{ display: "block", width: `${v / max * 100}%`, height: 10, background: c }} /></span><b style={{ textAlign: "right" }}>{nf(v)} ha</b></div>;
  return <div style={{ display: "grid", gap: 6, margin: "8px 0" }}>{fila("Agua habitual", r.agua_habitual_ha, "#94a3b8")}{fila("Agua hoy", r.agua_hoy_ha, "#3b82f6")}{fila("Agua nueva", r.agua_nueva_ha, "#1d4ed8")}</div>;
}

export function Anegamientos() {
  const [res, setRes] = useState<{ data?: { generado: string; fuente: string; tipo: string; metodo: string; resolucion_m: number; limites: string[]; zonas: Zona[] }; geojson?: any; err?: string } | null>(null);
  const [sel, setSel] = useState<string | null>(null);
  const mapEl = useRef<HTMLDivElement>(null), map = useRef<L.Map | null>(null), capa = useRef<L.LayerGroup | null>(null);

  useEffect(() => {
    let live = true;
    fetch("/api/fuentes/anegamientos").then(async r => ({ ok: r.ok, j: await r.json().catch(() => ({})) }))
      .then(({ ok, j }) => live && setRes(ok && j.status === "recibido" ? { data: j.data, geojson: j.geojson } : { err: j.error || "No respondió." }))
      .catch(() => live && setRes({ err: "No respondió." }));
    return () => { live = false; };
  }, []);

  const zonas = res?.data?.zonas || [];
  const actual = useMemo(() => zonas.find(z => z.zona === sel) || zonas.find(z => z.estado === "ok"), [zonas, sel]);

  useEffect(() => {
    if (!res?.data || !mapEl.current || map.current) return;
    const m = L.map(mapEl.current, { center: [-28.8, -58.2], zoom: 7, scrollWheelZoom: false });
    L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", { maxZoom: 17, attribution: "Esri, Maxar, Earthstar Geographics" }).addTo(m);
    capa.current = L.layerGroup().addTo(m); map.current = m;
    return () => { m.remove(); map.current = null; };
  }, [res?.data ? 1 : 0]);

  useEffect(() => {
    const g = capa.current, m = map.current; if (!g || !m || !res?.data) return; g.clearLayers();
    zonas.forEach(z => {
      if (!z.bbox) return;
      const [x0, y0, x1, y1] = z.bbox;
      L.rectangle([[y0, x0], [y1, x1]], { color: z.zona === actual?.zona ? "#f59f00" : "#ffffff", weight: z.zona === actual?.zona ? 2.5 : 1, fill: false, dashArray: z.estado === "ok" ? undefined : "4 4" })
        .bindTooltip(`${z.zona}${z.estado === "ok" ? ` · ${nf(z.resumen?.agua_nueva_ha)} ha de agua nueva` : ` · ${z.estado}`}`).on("click", () => setSel(z.zona)).addTo(g);
    });
    if (res.geojson?.features?.length) L.geoJSON(res.geojson, {
      style: f => ({ color: COLOR[f?.properties?.intensidad] || "#3b82f6", weight: 1, fillOpacity: .6, fillColor: COLOR[f?.properties?.intensidad] || "#3b82f6" }),
      onEachFeature: (f, l) => l.bindPopup(`<b>${f.properties.zona}</b><br>${nf(f.properties.superficie_ha, 1)} ha · ${f.properties.intensidad}<br>Desvío medio z ${nf(f.properties.z_medio, 1)} · pasada del ${fecha(f.properties.fecha)}`),
    }).addTo(g);
  }, [res, actual?.zona]);

  useEffect(() => {
    const m = map.current, z = actual; if (!m || !z?.bbox || !sel) return;
    const [x0, y0, x1, y1] = z.bbox; m.fitBounds([[y0, x0], [y1, x1]]);
  }, [sel]);

  if (!res) return <section className="cp-local-card"><p>Cargando la última corrida del radar…</p></section>;
  if (res.err) return <section className="cp-local-card"><p>{res.err}</p></section>;
  const d = res.data!;

  return <section className="regional-panel" aria-label="Anegamientos por radar" style={{ maxWidth: 1180, margin: "0 auto", padding: "24px 16px" }}>
    <p className="small">Última corrida: {fecha(d.generado)} · {d.fuente} · píxel de {d.resolucion_m} m · <b>orientativo</b>: {d.tipo}.</p>
    <div ref={mapEl} style={{ height: "min(460px, 70vh)", border: "1px solid #d0d5d9" }} />
    <p className="small">Recuadros: zonas analizadas (punteado = sin datos esta semana). Manchas: agua nueva, más oscuro = más intensa. Tocá un recuadro para ver su detalle.</p>

    <h3>Zonas</h3>
    <div style={{ overflowX: "auto" }}><table className="cp-table"><thead><tr><th>Zona</th><th>Pasada</th><th>Agua nueva</th><th>Manchas</th><th>Río según INA</th><th>¿Coincide?</th></tr></thead><tbody>
      {zonas.map(z => <tr key={z.zona} onClick={() => setSel(z.zona)} style={{ cursor: "pointer", background: z.zona === actual?.zona ? "#fff6e5" : undefined }}>
        <td><b>{z.zona}</b></td>
        <td>{z.estado === "ok" ? fecha(z.fecha_actual) : z.estado}</td>
        <td>{z.estado === "ok" ? `${nf(z.resumen?.agua_nueva_ha)} ha` : "—"}</td>
        <td>{z.estado === "ok" ? z.resumen?.manchas : "—"}</td>
        <td>{z.ina ? `${z.ina.river}: ${z.ina.to.toLowerCase()}, ${nf(z.ina.height, 2)} m (${fecha(z.ina.date)})` : "Sin escala en el recuadro"}</td>
        <td>{z.coincide === true ? "Sí" : z.coincide === false ? <b style={{ color: "#b42318" }}>No, en revisión</b> : "No se puede contrastar"}</td>
      </tr>)}
    </tbody></table></div>

    {actual && <div className="cp-local-card" style={{ marginTop: 16 }}>
      <h3>{actual.zona}</h3>
      {actual.estado !== "ok" ? <p>{actual.detalle}</p> : <>
        <p className="small">Pasada del {fecha(actual.fecha_actual)} · órbita {actual.orbita} · cubre el {nf((actual.cobertura || 0) * 100)} % del recuadro · umbral de agua {nf(actual.umbral_db, 1)} dB ({actual.umbral_metodo}).</p>
        <Barras z={actual} />
        <p>{actual.contraste}</p>
        <h4>Porcentaje del recuadro con agua en cada pasada</h4>
        {actual.serie && <Serie s={actual.serie} />}
        <p className="small">Los puntos naranjas son fechas raras según el filtro Hampel: no se parecen a las de alrededor. Pueden ser un error del sensor o un evento real que hay que mirar.</p>
        {!!actual.manchas?.length && <>
          <h4>Manchas más grandes</h4>
          <div style={{ overflowX: "auto" }}><table className="cp-table"><thead><tr><th>Superficie</th><th>Intensidad</th><th>Desvío medio z</th><th>Ubicación</th></tr></thead><tbody>
            {actual.manchas.slice(0, 8).map(m => <tr key={m.id}><td>{nf(m.superficie_ha, 1)} ha</td><td>{m.intensidad}</td><td>{nf(m.z_medio, 1)}</td>
              <td>{m.centroide ? <a href={`https://www.google.com/maps?q=${m.centroide[1]},${m.centroide[0]}`} target="_blank" rel="noreferrer">{nf(m.centroide[1], 4)}, {nf(m.centroide[0], 4)}</a> : "—"}</td></tr>)}
          </tbody></table></div></>}
      </>}
    </div>}

    <div className="cp-local-card" style={{ marginTop: 16 }}>
      <h3>Cómo se lee</h3>
      <p>Cada píxel se compara con su propio «fondo»: la mediana de sus pasadas del último año, sin las raras. Es el mismo método que usa la astronomía para separar una galaxia del fondo del cielo. Una mancha es agua nueva cuando hoy hay agua donde normalmente no la hay y el radar se oscureció al menos 3 desvíos.</p>
      <div style={{ display: "grid", gap: 6, maxWidth: 520 }}>
        {[["Fuerte", "desvío medio z de −5 o menos", "fuerte"], ["Moderada", "entre −5 y −4", "moderada"], ["Leve", "entre −4 y −3", "leve"]].map(([t, r, k]) =>
          <div key={k} style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 14 }}><span style={{ width: 26, height: 12, background: COLOR[k] }} /><b>{t}</b><span>{r}</span></div>)}
      </div>
      <p className="small">Piso: manchas de 1 ha. Techo: no hay; el recuadro mide unos 20 × 20 km. Método: {d.metodo}.</p>
      <h4>Qué no puede ver</h4>
      <ul>{d.limites.map(l => <li key={l}>{l}</li>)}</ul>
      <p className="small">No reemplaza los avisos del INA ni de Defensa Civil.</p>
    </div>
  </section>;
}
