/**
 * DOTS · Caso de estudio Bella Vista (Corrientes): un área rural de ~1.600 ha analizada con todos los módulos,
 * consultando los datos en vivo. No es un establecimiento en particular. Si una fuente no responde, se dice.
 */
import { useEffect, useState } from "react";

type D = Record<string, any>;
const POLY: [number, number][] = [[-28.47, -58.95], [-28.47, -58.90], [-28.50, -58.90], [-28.50, -58.95]];
const LAT = -28.485, LON = -58.925;
const P = encodeURIComponent(JSON.stringify(POLY)) + `&lat=${-28.485}&lon=${-58.925}`;   // las rutas de lote piden también lat y lon
const nf = (v: unknown, d = 0) => v == null || !Number.isFinite(Number(v)) ? "—" : Number(v).toLocaleString("es-AR", { minimumFractionDigits: d, maximumFractionDigits: d });
const sg = (v: unknown, d = 0) => v == null ? "—" : `${Number(v) > 0 ? "+" : ""}${nf(v, d)}`;

function useApi(url: string) {
  const [s, setS] = useState<{ d?: D; err?: string } | null>(null);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setS(null);
    const timer = setTimeout(() => controller.abort(), 45000);
    fetch(url, { signal: controller.signal, headers: { Accept: "application/json" } })
      .then(async r => {
        if (!r.ok) throw new Error(`API DOTS: HTTP ${r.status}`);
        const j = await r.json();
        if (j.status !== "recibido" || !j.data)
          throw new Error(j.error || `Fuente sin información (estado: ${j.status || "desconocido"})`);
        return j.data as D;
      })
      .then(data => { if (!controller.signal.aborted) setS({ d: data }); })
      .catch(e => {
        if (controller.signal.aborted && e?.name !== "AbortError") return;
        setS({ err: e?.name === "AbortError" ? "Tiempo de espera agotado (45 segundos)." : (e?.message || "No se pudo consultar la fuente.") });
      })
      .finally(() => clearTimeout(timer));
    return () => { clearTimeout(timer); controller.abort(); };
  }, [url, retry]);
  return { ...s, retry: () => setRetry(n => n + 1) };
}

function Block({ tag, title, s, children, src }: { tag: string; title: string; s: { d?: D; err?: string; retry?: () => void }; children: (d: D) => React.ReactNode; src: string }) {
  return <section className="bv-block">
    <span className="section-tag">{tag}</span>
    <h3>{title}</h3>
    {!s ? <p className="small">Consultando…</p> : s.d ? children(s.d) : <p className="nn-warn">Sin dato: {s.err} {s.retry && <button type="button" onClick={s.retry}>Reintentar conexión</button>}</p>}
    <p className="bv-src">{src}</p>
  </section>;
}

function Spark({ xs, ys }: { xs: string[]; ys: (number | null)[] }) {
  const pts = ys.map((y, i) => [i, y] as const).filter(([, y]) => y != null) as [number, number][];
  if (pts.length < 2) return null;
  const lo = Math.min(...pts.map(p => p[1])), hi = Math.max(...pts.map(p => p[1])), W = 560, H = 120;
  const x = (i: number) => 8 + (i / (ys.length - 1)) * (W - 16), y = (v: number) => H - 14 - ((v - lo) / ((hi - lo) || 1)) * (H - 28);
  return <svg className="bv-spark" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`NDVI entre ${nf(lo, 2)} y ${nf(hi, 2)}`}>
    <polyline fill="none" stroke="#35978f" strokeWidth="2.2" points={pts.map(([i, v]) => `${x(i)},${y(v)}`).join(" ")} />
    <text x="8" y={H - 2} fontSize="11" fill="#5f6e73">{xs[0]?.slice(0, 7)}</text>
    <text x={W - 8} y={H - 2} fontSize="11" fill="#5f6e73" textAnchor="end">{xs[xs.length - 1]?.slice(0, 7)}</text>
    <text x="8" y="12" fontSize="11" fill="#5f6e73">máx {nf(hi, 2)} · mín {nf(lo, 2)}</text>
  </svg>;
}

export function CasoBellaVista() {
  const agua = useApi(`/api/fuentes/balance-agua?lat=${LAT}&lon=${LON}`);
  const nino = useApi(`/api/fuentes/enso-tablero?lat=${LAT}&lon=${LON}`);
  const ndvi = useApi(`/api/fuentes/ndvi-modis?polygon=${P}&days=760`);
  const anom = useApi(`/api/fuentes/ndvi-anomalia?polygon=${P}`);
  const rh = useApi(`/api/fuentes/riesgo-hidrico?polygon=${P}`);
  const etr = useApi(`/api/fuentes/etr-lote?polygon=${P}`);
  const frost = useApi(`/api/fuentes/heladas-satelite?polygon=${P}`);
  const mb = useApi(`/api/fuentes/mapbiomas?polygon=${P}`);
  const dw = useApi(`/api/fuentes/cobertura-reciente?polygon=${P}`);
  const emb = useApi(`/api/fuentes/cambios-lote?polygon=${P}`);
  const rio = useApi(`/api/fuentes/rio-bellavista`);
  return <div className="bv">
    <section className="bv-intro">
      <p>Un área rural de unas 1.600 hectáreas al este de Bella Vista, Corrientes, donde conviven citrus, forestación, ganadería y pastizal, a pocos kilómetros del río Paraná. No corresponde a un establecimiento en particular: es una muestra para ver qué arma DOTS sobre cualquier campo. Cada número se consulta en vivo y lleva su fuente; si una fuente no responde, aparece "sin dato".</p>
      <div className="bv-actions">
        <a className="nn-btn" href={`/api/fuentes/enso-informe?lat=${LAT}&lon=${LON}&nombre=${encodeURIComponent("Bella Vista (Corrientes)")}`} download>Informe El Niño (PDF)</a>
        <a className="nn-btn ghost" href="/api/fuentes/localidad-informe?id=parana-bellavista" download>Informe del río en Bella Vista (PDF)</a>
        <a className="nn-btn ghost" href="/poblacion?localidad=parana-bellavista#crecidas">Población expuesta a crecidas</a>
      </div>
    </section>
    <div className="bv-grid">
      <Block tag="AGUA" title="Sequía o exceso: índice SPEI" s={agua} src="Copernicus ERA5 vía Open-Meteo · SPEI log-logístico, referencia 1991-2020">{d => <>
        <div className="bv-tiles">{["1", "3", "6", "12"].map(k => { const v = d.spei?.[k]; return <div key={k}><b>{sg(v?.index, 1)}</b><span>{k} {k === "1" ? "mes" : "meses"}</span><small>{v?.class || "sin dato"}</small></div>; })}</div>
        <p>{d.reading}</p><p className="small">Último mes completo: {d.last_month}.</p>
        {d.profile?.to_2_5m && <><div className="bv-tiles" style={{ marginTop: 10 }}>{[d.profile.to_1m, d.profile.to_2_5m].map((l: D) => <div key={l.label}><b>{sg(l.diff_mm)} mm</b><span>agua {l.label}</span><small>{l.class} · percentil {l.percentile ?? "—"}</small></div>)}
          {d.profile.available && <div><b>{d.profile.available.pct} %</b><span>agua útil hasta 2 m</span><small>{d.profile.available.mm != null ? `${d.profile.available.mm} de ${d.profile.available.capacity_mm} mm` : d.profile.available.class}</small></div>}</div>
          <p className="small">{d.profile.reading} Modelo ERA5-Land, no medición en el lote; referencia oficial: INTA y Oficina de Riesgo Agropecuario.</p></>}
      </>}</Block>
      <Block tag="EL NIÑO" title="Qué trae El Niño a este lugar" s={nino} src="NOAA CPC y PSL · historia desde 1991 con ERA5">{d => <>
        <div className="bv-tiles">
          <div><b>{d.phase || "—"}</b><span>fase actual</span><small>ONI {sg(d.oni, 1)}</small></div>
          <div><b>{sg(d.expected_pct)} %</b><span>lluvia en Niño fuerte</span><small>vs años neutros{d.expected_n ? ` · ${d.expected_n} casos` : ""}</small></div>
          <div><b>{sg(d.now?.now90_pct)} %</b><span>últimos 90 días</span><small>contra lo normal</small></div>
        </div>
        {d.impact?.reading && <p>{d.impact.reading}</p>}
        {Array.isArray(d.advice) && d.advice.length > 0 && <ul className="bv-list">{d.advice.slice(0, 3).map((a: any, i: number) => <li key={i}>{typeof a === "string" ? a : a.text || a.title}</li>)}</ul>}
      </>}</Block>
      <Block tag="RÍO" title="El Paraná en Bella Vista" s={rio} src="Copernicus GloFAS vía Open-Meteo · INA · normales 2005-2024">{d => <>
        <div className="bv-tiles">
          <div><b>{nf(d.discharge)}</b><span>m³/s</span><small>caudal del {d.date ? `${d.date.slice(8, 10)}/${d.date.slice(5, 7)}` : "—"}</small></div>
          <div><b>{d.ratio != null ? `${nf(d.ratio * 100)} %` : "—"}</b><span>de lo normal</span><small>para la fecha</small></div>
          <div><b>{d.level || "—"}</b><span>nivel</span><small>7 días: {sg(d.change_7d_pct)} %</small></div>
        </div>
      </>}</Block>
      <Block tag="VEGETACIÓN" title="NDVI de los últimos dos años" s={ndvi} src="NASA MODIS MOD13Q1 (250 m, cada 16 días) · ORNL DAAC">{d => { const rows = (d.series || []).filter((r: D) => r.status === "válida"); return <>
        <Spark xs={rows.map((r: D) => r.datetime)} ys={rows.map((r: D) => r.ndvi_mean)} />
        <p className="small">Último compuesto: NDVI {nf(d.latest?.ndvi_mean, 2)} ({d.latest?.datetime?.slice(0, 10)}). {d.interpretation_scope}</p>
      </>; }}</Block>
      <Block tag="VEGETACIÓN" title="¿Está más verde o más seco que otros años?" s={anom} src="NASA MODIS MOD13Q1 desde 2001 vía Earth Engine · misma época de cada año">{d => <>
        <div className="nn-table bv-table bv-anom" role="table"><div className="nn-tr nn-th" role="row">{["Fecha", "NDVI", "Normal", "Diferencia", "VCI"].map(h => <span role="columnheader" key={h}>{h}</span>)}</div>
          {d.series.slice(-6).map((r: D) => <div className="nn-tr" role="row" key={r.date}><span role="cell">{r.date.slice(8, 10)}/{r.date.slice(5, 7)}/{r.date.slice(2, 4)}</span><span role="cell">{nf(r.ndvi, 2)}</span><span role="cell">{nf(r.normal, 2)}</span><span role="cell">{sg(r.diff, 2)}</span><span role="cell">{r.vci ?? "—"}</span></div>)}</div>
        <p>{d.reading}</p>
      </>}</Block>
      <Block tag="CONSUMO DE AGUA" title="Evapotranspiración real" s={etr} src="NASA MODIS MOD16A2 (500 m, 8 días) vía Earth Engine · misma época desde 2001">{d => <>
        <div className="bv-tiles"><div><b>{nf(d.latest.mm_day, 1)} mm/día</b><span>últimos 8 días</span><small>{d.latest.diff_pct != null ? `${sg(d.latest.diff_pct)} % vs normal` : "sin normal"}</small></div>
          <div><b>{d.latest.percentile ?? "—"}</b><span>percentil</span><small>contra la misma época</small></div></div>
        <p>{d.reading}</p>
      </>}</Block>
      <Block tag="HELADAS" title="Heladas en la superficie, por satélite" s={frost} src="NASA MODIS Aqua MYD11A1 (1 km, noches despejadas) vía Earth Engine">{d => <>
        <div className="bv-tiles"><div><b>{d.frost_nights_30d}</b><span>noches con helada</span><small>últimos 30 días</small></div>
          <div><b>{nf(d.coldest.lst_c, 1)} °C</b><span>noche más fría</span><small>{d.coldest.date.slice(8, 10)}/{d.coldest.date.slice(5, 7)}</small></div></div>
        <p>{d.reading}</p>
      </>}</Block>
      <Block tag="RIESGO HÍDRICO" title="Lomas, planos y bajos del campo" s={rh} src="Copernicus GLO-30 (relieve) · JRC Global Surface Water 1984-2021 · MERIT Hydro, vía Earth Engine">{d => <>
        <div className="bv-bars">{d.zones.filter((z: D) => z.pct >= 0.5).map((z: D) => <div key={z.key}><span>{z.name}</span><i style={{ width: `${z.pct}%`, background: z.color }} /><b>{nf(z.pct)} %</b><small>{nf(z.ha)} ha</small></div>)}</div>
        <p>{d.reading}</p><p className="small">Desde el Observatorio, el "Informe de campo" trae este mapa con un código QR para llevarlo al celular y usarlo sin señal.</p>
      </>}</Block>
      <Block tag="HISTORIA" title={`El área desde ${mb?.d?.first_year ?? 1985}`} s={mb} src="MapBiomas Argentina (Landsat 30 m, CC BY 4.0) vía Earth Engine">{d => { const by: Record<number, D> = {}; (d.years || []).forEach((r: D) => { by[r.year] = r }); const ys = [d.first_year, 2000, 2010, 2020, d.last_year].filter((y, i, a) => by[y] && a.indexOf(y) === i); return <>
        <div className="nn-table bv-table" role="table"><div className="nn-tr nn-th" role="row">{["Año","Bosque","Otra natural","Plantación","Agro","Agua"].map(h=><span role="columnheader" key={h}>{h}</span>)}</div>
          {ys.map(y => <div className="nn-tr" role="row" key={y}><span role="cell"><b>{y}</b></span>{(["bosque","natural","plantacion","uso","agua"] as const).map(k=><span role="cell" key={k}>{nf(by[y].groups_ha[k])} ha</span>)}</div>)}</div>
        <p>{d.reading}</p>{d.eudr && <p className="small">Unión Europea (EUDR): {d.eudr.verdict}.</p>}
      </>; }}</Block>
      <Block tag="AHORA" title="Cobertura de los últimos 90 días" s={dw} src="Dynamic World (Google y WRI, Sentinel-2 10 m, CC BY 4.0)">{d => <>
        <div className="bv-bars">{d.classes.filter((r: D) => r.pct >= 1).map((r: D) => <div key={r.key}><span>{r.name}</span><i style={{ width: `${r.pct}%`, background: r.color }} /><b>{nf(r.pct)} %</b><small>{r.prev_pct != null ? `hace un año ${nf(r.prev_pct)} %` : ""}</small></div>)}</div>
        <p>{d.reading}</p>
      </>}</Block>
      <Block tag="CAMBIOS" title="¿Cambió el área año a año?" s={emb} src="Google DeepMind AlphaEarth · Satellite Embedding anual (10 m, CC BY 4.0)">{d => <>
        <div className="emb-bars bv-emb">{d.years.map((r: D) => <div key={r.year} className={"emb-bar" + (r.year === d.strongest_year ? " hit" : "")} title={r.similarity != null ? `${r.year - 1}→${r.year}: similitud ${nf(r.similarity, 2)}` : `${r.year}: sin dato`}><span style={{ height: r.similarity != null ? `${Math.max(4, Math.round(r.similarity * 100))}%` : "0" }} /><small>{r.year}</small></div>)}</div>
        <p>{d.reading}</p><p className="small">Barra alta: el área se parece al año anterior. Barra baja: cambió. Indica que hubo un cambio, no cuál: para eso está la historia de MapBiomas.</p>
      </>}</Block>
    </div>
    <section className="bv-close">
      <h3>Lo mismo, para tu campo</h3>
      <p>En el Observatorio dibujás el perímetro y DOTS arma este análisis para ese lote, con los informes en PDF. Para cooperativas, municipios e instituciones preparamos casos de estudio a medida.</p>
      <div className="bv-actions"><a className="nn-btn" href="/observatorio">Abrir el Observatorio</a><a className="nn-btn ghost" href="/contacto">Pedir un caso de estudio</a></div>
    </section>
  </div>;
}
