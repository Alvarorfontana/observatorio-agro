import React, { useEffect, useMemo, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

type WdiPoint = { year: string; value: number };
type SoilLayer = { name: string; unit: string; depths: { depth: string; value: number | null }[] };

const YEARS = ["1995", "2000", "2005", "2010", "2015", "2020", "2024"];
const WDI = "AG.PRD.CROP.XD";
const SOIL_PROPS = ["phh2o", "soc", "clay", "sand", "nitrogen"];

export function DotsTerritory3D() {
  const mapNode = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [terrainOn, setTerrainOn] = useState(true);
  const [exaggeration, setExaggeration] = useState(1.35);
  const [country, setCountry] = useState("ARG");
  const [series, setSeries] = useState<WdiPoint[]>([]);
  const [soil, setSoil] = useState<SoilLayer[]>([]);
  const [lat, setLat] = useState("-32.95");
  const [lon, setLon] = useState("-60.65");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sourceStamp, setSourceStamp] = useState("");
  const [profile, setProfile] = useState<{ distance: number; elevation: number }[]>([]);
  const [profileBusy, setProfileBusy] = useState(false);

  useEffect(() => {
    if (!mapNode.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: mapNode.current,
      center: [-60.65, -32.95],
      zoom: 6.2,
      pitch: 58,
      bearing: -18,
      antialias: true,
      style: {
        version: 8,
        sources: {
          osm: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: "© OpenStreetMap contributors"
          },
          dem: {
            type: "raster-dem",
            tiles: ["https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"],
            tileSize: 256,
            encoding: "terrarium",
            maxzoom: 15,
            attribution: "Terrain RGB: AWS Terrain Tiles"
          }
        },
        layers: [{ id: "base", type: "raster", source: "osm", paint: { "raster-opacity": 0.88 } }]
      }
    });
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
    map.on("load", () => {
      map.setTerrain({ source: "dem", exaggeration: 1.35 });
      map.addSource("relief-hillshade", { type: "raster-dem", url: "https://demotiles.maplibre.org/terrain-tiles/tiles.json", tileSize: 256 });
      map.addLayer({ id: "relief-hillshade", type: "hillshade", source: "relief-hillshade", paint: { "hillshade-shadow-color": "#152d36", "hillshade-highlight-color": "#e4e8d9", "hillshade-exaggeration": 0.28 } });
    });
    mapRef.current = map;
    return () => { map.remove(); mapRef.current = null; };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    map.setTerrain(terrainOn ? { source: "dem", exaggeration } : null);
  }, [terrainOn, exaggeration]);

  useEffect(() => {
    let cancelled = false;
    async function loadHistory() {
      setBusy(true); setError("");
      try {
        const response = await fetch(`https://api.worldbank.org/v2/country/${country}/indicator/${WDI}?format=json&per_page=100&date=1995:2024`);
        if (!response.ok) throw new Error("Banco Mundial respondió HTTP " + response.status);
        const json = await response.json();
        if (!Array.isArray(json) || !Array.isArray(json[1])) throw new Error("Respuesta estadística no reconocida");
        const values = json[1].filter((x: any) => x.value !== null && Number.isFinite(Number(x.value))).map((x: any) => ({ year: String(x.date), value: Number(x.value) })).sort((a: WdiPoint, b: WdiPoint) => Number(a.year) - Number(b.year));
        if (!cancelled) { setSeries(values); setSourceStamp(new Date().toISOString()); }
      } catch (e) { if (!cancelled) setError((e as Error).message); }
      finally { if (!cancelled) setBusy(false); }
    }
    void loadHistory();
    return () => { cancelled = true; };
  }, [country]);

  const latest = series[series.length - 1];
  const chart = useMemo(() => {
    if (!series.length) return "";
    const min = Math.min(...series.map(p => p.value)), max = Math.max(...series.map(p => p.value));
    const span = max - min || 1;
    return series.map((p, i) => `${i * 600 / Math.max(1, series.length - 1)},${130 - ((p.value - min) / span) * 110}`).join(" ");
  }, [series]);

  async function loadSoil() {
    const a = Number(lat), o = Number(lon);
    if (!Number.isFinite(a) || !Number.isFinite(o) || a < -90 || a > 90 || o < -180 || o > 180) { setError("Coordenadas inválidas."); return; }
    setBusy(true); setError("");
    try {
      const params = new URLSearchParams({ lon: String(o), lat: String(a), value: "mean" });
      SOIL_PROPS.forEach(p => params.append("property", p));
      ["0-5cm", "5-15cm", "15-30cm"].forEach(d => params.append("depth", d));
      const response = await fetch("https://rest.isric.org/soilgrids/v2.0/properties/query?" + params.toString());
      if (!response.ok) throw new Error("SoilGrids respondió HTTP " + response.status);
      const json = await response.json();
      const layers = (json?.properties?.layers || []).map((layer: any) => ({
        name: layer.name,
        unit: layer.unit_measure?.mapped_units || layer.unit_measure?.target_units || "",
        depths: (layer.depths || []).map((d: any) => ({ depth: d.label, value: d.values?.mean ?? null }))
      }));
      setSoil(layers); setSourceStamp(new Date().toISOString());
    } catch (e) { setError((e as Error).message); setSoil([]); }
    finally { setBusy(false); }
  }

  async function loadProfile() {
    setProfileBusy(true); setError("");
    try {
      const points = Array.from({ length: 25 }, (_, i) => ({ latitude: -32.72 + i * (-33.18 + 32.72) / 24, longitude: -60.95 + i * (-60.35 + 60.95) / 24 }));
      const params = new URLSearchParams();
      params.set("latitude", points.map(p => p.latitude.toFixed(5)).join(","));
      params.set("longitude", points.map(p => p.longitude.toFixed(5)).join(","));
      const response = await fetch("https://api.open-meteo.com/v1/elevation?" + params.toString());
      if (!response.ok) throw new Error("Servicio de elevación respondió HTTP " + response.status);
      const json = await response.json();
      if (!Array.isArray(json.elevation)) throw new Error("El servicio no devolvió un perfil de elevación");
      setProfile(json.elevation.map((e: number, i: number) => ({ distance: i * 2.7, elevation: e })));
    } catch (e) { setError((e as Error).message); setProfile([]); }
    finally { setProfileBusy(false); }
  }

  function exportCsv() {
    const rows = [["anio", "indicador", "valor"], ...series.map(p => [p.year, "AG.PRD.CROP.XD", String(p.value)])];
    const csv = "\ufeff" + rows.map(r => r.map(v => '"' + v.replaceAll('"', '""') + '"').join(";")).join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const a = document.createElement("a"); a.href = url; a.download = "DOTS-serie-agricola-world-bank.csv"; a.click(); URL.revokeObjectURL(url);
  }

  return <main className="dots-territory">
    <style>{`
      .dots-territory{color:#e7edf2;background:#101a22;padding:22px;border-radius:16px;margin:14px 0;font-family:inherit}
      .dt-head{display:flex;justify-content:space-between;align-items:flex-start;gap:14px;flex-wrap:wrap}.dt-kicker{font-size:11px;letter-spacing:.14em;color:#7fc9b6;font-weight:700}.dt-head h1{font-size:25px;margin:7px 0}.dt-head p,.dt-muted{color:#a8b6c1;font-size:13px}
      .dt-btn{border:1px solid #40515d;background:#1b2a35;color:#edf5f6;padding:9px 12px;border-radius:8px;cursor:pointer}.dt-btn:disabled{opacity:.45;cursor:wait}
      .dt-layout{display:grid;grid-template-columns:minmax(0,1.8fr) minmax(260px,.8fr);gap:14px;margin-top:16px}.dt-panel{background:#172630;border:1px solid #2a3b46;border-radius:12px;padding:14px;min-width:0}.dt-map{height:430px;border-radius:9px;overflow:hidden;background:#22343e}.dt-map-tools{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:10px}.dt-map-tools label{font-size:12px;color:#b7c5ce}.dt-map-tools input{accent-color:#55b69b}
      .dt-cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:14px 0}.dt-stat{background:#1a2b35;border:1px solid #2b3d48;padding:12px;border-radius:10px}.dt-stat small{display:block;color:#9fb0ba;font-size:11px}.dt-stat b{display:block;font-size:19px;margin:7px 0}.dt-stat span{font-size:11px;color:#91a5b0}
      .dt-side h3,.dt-panel h3{font-size:14px;margin:0 0 10px}.dt-panel select,.dt-panel input{background:#0f1c24;color:#edf5f6;border:1px solid #40515d;border-radius:7px;padding:8px;max-width:100%}.dt-chart{width:100%;height:auto;display:block}.dt-legend{display:flex;justify-content:space-between;font-size:11px;color:#a8b6c1}.dt-soil{width:100%;border-collapse:collapse;font-size:12px}.dt-soil td,.dt-soil th{padding:8px 5px;border-bottom:1px solid #2b3d48;text-align:left}.dt-source{font-size:11px;color:#9dafb9;line-height:1.5;margin-top:10px}.dt-alert{background:#352d1d;border:1px solid #66532c;color:#f4d99b;padding:10px;border-radius:8px;font-size:12px;margin-top:12px}
      @media(max-width:850px){.dt-layout{grid-template-columns:1fr}.dt-map{height:330px}.dt-cards{grid-template-columns:1fr 1fr}.dots-territory{padding:14px}}@media(max-width:480px){.dt-cards{grid-template-columns:1fr}}
      @media print{.dt-btn,.dt-map-tools{display:none!important}.dots-territory{background:white;color:#111}.dt-panel,.dt-stat{background:white;color:#111;border-color:#ccc;break-inside:avoid}.dt-muted,.dt-source,.dt-stat small,.dt-stat span{color:#444}}
    `}</style>
    <header className="dt-head"><div><div className="dt-kicker">DOTS / OBSERVATORIO AGRO</div><h1>Territorio 3D · Relieve y análisis geoespacial</h1><p>Relieve, cuencas, series históricas y variables de suelo con procedencia visible.</p></div><button className="dt-btn" onClick={() => window.print()}>Generar informe PDF</button></header>
    <div className="dt-cards">
      <div className="dt-stat"><small>Serie agrícola · último dato disponible</small><b>{latest ? latest.value.toLocaleString("es-AR", { maximumFractionDigits: 2 }) : "—"}</b><span>{latest ? latest.year + " · Banco Mundial" : busy ? "Consultando fuente…" : "Sin observación"}</span></div>
      <div className="dt-stat"><small>Observaciones históricas</small><b>{series.length || "—"}</b><span>Argentina · 1995–2024 · WDI</span></div>
      <div className="dt-stat"><small>Perfil topográfico</small><b>{profile.length ? profile.length + " puntos" : "No consultado"}</b><span>Elevación modelada · Open-Meteo</span></div>
    </div>
    <div className="dt-layout">
      <section className="dt-panel"><h3>Modelo digital del terreno</h3><div className="dt-map-tools"><label><input type="checkbox" checked={terrainOn} onChange={e => setTerrainOn(e.target.checked)} /> Relieve 3D</label><label>Exageración <input type="range" min="0.5" max="2.5" step="0.05" value={exaggeration} onChange={e => setExaggeration(Number(e.target.value))} /></label><span className="dt-muted">Cuenca del Paraná · navegación libre</span></div><div ref={mapNode} className="dt-map" aria-label="Mapa tridimensional de relieve" /><p className="dt-source">Cartografía base: OpenStreetMap. Elevación: AWS Terrain Tiles (Terrarium). La exageración vertical es un ajuste visual; no modifica las alturas de origen.</p></section>
      <aside className="dt-panel dt-side"><h3>Series históricas agrícolas</h3><label className="dt-muted">País </label><select value={country} onChange={e => setCountry(e.target.value)}><option value="ARG">Argentina</option><option value="BRA">Brasil</option><option value="URY">Uruguay</option><option value="PRY">Paraguay</option></select><p className="dt-muted">Índice de producción agrícola (2014–16 = 100)</p>{series.length ? <><svg className="dt-chart" viewBox="0 0 640 160" role="img" aria-label="Serie histórica del índice de producción agrícola"><line x1="20" y1="140" x2="620" y2="140" stroke="#60727d"/><polyline points={chart} fill="none" stroke="#5bc3a5" strokeWidth="4" strokeLinejoin="round" strokeLinecap="round"/></svg><div className="dt-legend"><span>{series[0].year}</span><span>{series[series.length-1].year}</span></div><button className="dt-btn" onClick={exportCsv}>Descargar serie CSV</button></> : <p className="dt-muted">{busy ? "Consultando Banco Mundial…" : "No hay observaciones para mostrar."}</p>}<p className="dt-source">Fuente: World Bank API · WDI {WDI}. Consulta: {sourceStamp || "pendiente"}. Los años faltantes no se interpolan.</p></aside>
    </div>
    <div className="dt-layout">
      <section className="dt-panel"><h3>Perfil topográfico</h3><p className="dt-muted">Transecta regional de referencia entre latitudes −32,72 y −33,18; longitud −60,95 a −60,35.</p><button className="dt-btn" onClick={() => void loadProfile()} disabled={profileBusy}>{profileBusy ? "Consultando elevación…" : "Consultar perfil de elevación"}</button>{profile.length > 0 && <><svg className="dt-chart" viewBox="0 0 640 170" role="img" aria-label="Perfil de elevación consultado"><polyline points={profile.map((p,i)=>`${20+i*600/Math.max(1,profile.length-1)},${145-(p.elevation-Math.min(...profile.map(x=>x.elevation)))/(Math.max(...profile.map(x=>x.elevation))-Math.min(...profile.map(x=>x.elevation))||1)*115}`).join(" ")} fill="none" stroke="#e1b45b" strokeWidth="3"/></svg><div className="dt-muted">Mínimo: {Math.min(...profile.map(p=>p.elevation)).toFixed(1)} m · Máximo: {Math.max(...profile.map(p=>p.elevation)).toFixed(1)} m · {profile.length} puntos</div></>}</section>
      <section className="dt-panel"><h3>Composición del suelo · SoilGrids</h3><div className="dt-map-tools"><label>Latitud <input value={lat} onChange={e=>setLat(e.target.value)} size={9}/></label><label>Longitud <input value={lon} onChange={e=>setLon(e.target.value)} size={9}/></label><button className="dt-btn" onClick={() => void loadSoil()} disabled={busy}>{busy ? "Consultando…" : "Consultar punto"}</button></div>{soil.length > 0 ? <table className="dt-soil"><thead><tr><th>Variable</th><th>Profundidad</th><th>Valor</th><th>Unidad</th></tr></thead><tbody>{soil.flatMap(layer=>layer.depths.map(d=><tr key={layer.name+d.depth}><td>{layer.name}</td><td>{d.depth}</td><td>{d.value ?? "Sin dato"}</td><td>{layer.unit}</td></tr>))}</tbody></table> : <p className="dt-muted">Ingresá coordenadas y consultá el producto modelado de SoilGrids. No se presentan valores hasta recibir respuesta de la fuente.</p>}<p className="dt-source">Fuente: ISRIC SoilGrids · resolución espacial aproximada 250 m. Producto modelado; no equivale a análisis de laboratorio ni medición de compactación.</p></section>
    </div>
    {error && <div className="dt-alert" role="alert">{error}</div>}
    <p className="dt-source">Los gráficos y tablas se completan únicamente con respuestas de las fuentes consultadas. No se generan valores de relleno. Esta vista 3D usa elevación real de un modelo digital; no representa por sí misma una simulación hidrológica.</p>
  </main>;
}
