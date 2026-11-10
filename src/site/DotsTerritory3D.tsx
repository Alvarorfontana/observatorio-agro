import React, { useEffect, useMemo, useRef, useState } from "react";

type WdiPoint = { year: string; value: number };
type Lot3D = { name: string; vertices: [number, number][]; areaHa?: number | null; center?: [number, number] };
type TerrainSummary3D = { elevMin?: number; elevMean?: number; elevMax?: number; relief?: number; slopeMeanPct?: number; flatPct?: number; depressionPct?: number; depressionHa?: number; maxDepthM?: number; storageM3?: number; drainageHa?: number; positionLabel?: string; riskPct?: { bajo?: number; medio?: number; alto?: number } };
type SoilLayer = { name: string; unit: string; depths: { depth: string; value: number | null }[] };

function lotGeoJson(lot: Lot3D | null): any {
  if (!lot || !Array.isArray(lot.vertices) || lot.vertices.length < 3) return { type: "FeatureCollection", features: [] };
  const ring = lot.vertices.map(([lat, lon]) => [lon, lat]);
  ring.push(ring[0]);
  return { type: "FeatureCollection", features: [{ type: "Feature", properties: { name: lot.name }, geometry: { type: "Polygon", coordinates: [ring] } }] };
}

function fitLot(map: any, vertices: [number, number][]) {
  const lons = vertices.map(p => p[1]), lats = vertices.map(p => p[0]);
  map.fitBounds([[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]], { padding: 55, maxZoom: 15, pitch: 58, duration: 900 });
}

const WDI = "AG.PRD.CROP.XD";
const SOIL_PROPS = ["phh2o", "soc", "clay", "sand", "nitrogen"];

export function DotsTerritory3D({ lot = null, terrainSummary = null, onTerrain, terrainBusy = false }: { lot?: Lot3D | null; terrainSummary?: TerrainSummary3D | null; onTerrain?: () => void; terrainBusy?: boolean }) {
  const mapNode = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const [terrainOn, setTerrainOn] = useState(true);
  const [imageryOn, setImageryOn] = useState(false);
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
    let disposed = false;
    const startMap = () => {
    if (disposed || !mapNode.current || mapRef.current) return;
    const maplibregl = (window as any).maplibregl;
    if (!maplibregl) return;
    const map = new maplibregl.Map({
      container: mapNode.current,
      center: lot?.center ? [lot.center[1], lot.center[0]] : lot?.vertices?.length ? [lot.vertices.reduce((a,p)=>a+p[1],0)/lot.vertices.length, lot.vertices.reduce((a,p)=>a+p[0],0)/lot.vertices.length] : [-60.65, -32.95],
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
          },
          modis: {
            type: "raster",
            tiles: [`https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/MODIS_Terra_CorrectedReflectance_TrueColor/default/${new Date().toISOString().slice(0,10)}/GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpg`],
            tileSize: 256,
            maxzoom: 9,
            attribution: "NASA GIBS / NASA Earthdata"
          }
        },
        layers: [
          { id: "base", type: "raster", source: "osm", paint: { "raster-opacity": 0.88 } },
          { id: "modis-imagery", type: "raster", source: "modis", layout: { visibility: "none" }, paint: { "raster-opacity": 0.82 } }
        ]
      }
    });
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
    map.on("load", () => {
      map.setTerrain({ source: "dem", exaggeration: 1.35 });
      map.addSource("selected-lot", { type: "geojson", data: lotGeoJson(lot) });
      map.addLayer({ id: "selected-lot-fill", type: "fill", source: "selected-lot", paint: { "fill-color": "#39d5b0", "fill-opacity": 0.20 } });
      map.addLayer({ id: "selected-lot-line", type: "line", source: "selected-lot", paint: { "line-color": "#ffe08a", "line-width": 3, "line-dasharray": [2, 1] } });
      if (lot && lot.vertices.length >= 3) fitLot(map, lot.vertices);
    });
    mapRef.current = map;
    };
    const cssId = "dots-maplibre-css";
    if (!document.getElementById(cssId)) {
      const link = document.createElement("link");
      link.id = cssId; link.rel = "stylesheet";
      link.href = "https://unpkg.com/maplibre-gl@5.6.1/dist/maplibre-gl.css";
      document.head.appendChild(link);
    }
    if ((window as any).maplibregl) startMap();
    else {
      const script = document.createElement("script");
      script.src = "https://unpkg.com/maplibre-gl@5.6.1/dist/maplibre-gl.js";
      script.async = true;
      script.onload = startMap;
      script.onerror = () => setError("No se pudo cargar MapLibre GL desde el CDN.");
      document.head.appendChild(script);
    }
    return () => { disposed = true; mapRef.current?.remove(); mapRef.current = null; };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const syncLot = () => {
      const source = map.getSource("selected-lot");
      if (source) (source as any).setData(lotGeoJson(lot));
      if (lot && lot.vertices.length >= 3) {
        const centerLat = lot.vertices.reduce((a,p)=>a+p[0],0)/lot.vertices.length;
        const centerLon = lot.vertices.reduce((a,p)=>a+p[1],0)/lot.vertices.length;
        setLat(centerLat.toFixed(5)); setLon(centerLon.toFixed(5));
        fitLot(map, lot.vertices);
      }
    };
    if (map.isStyleLoaded() && map.getSource("selected-lot")) syncLot();
    else map.once("load", syncLot);
    return () => { map.off("load", syncLot); };
  }, [lot?.name, lot?.areaHa, lot?.vertices]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    map.setTerrain(terrainOn ? { source: "dem", exaggeration } : null);
  }, [terrainOn, exaggeration]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    map.setLayoutProperty("modis-imagery", "visibility", imageryOn ? "visible" : "none");
  }, [imageryOn]);

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
      const centerLat = Number(lat), centerLon = Number(lon);
      if (!Number.isFinite(centerLat) || !Number.isFinite(centerLon) || centerLat < -90 || centerLat > 90 || centerLon < -180 || centerLon > 180) {
        throw new Error("Coordenadas inválidas para la transecta.");
      }
      // Si hay lote, la transecta une sus dos vértices más distantes; sin lote usa 20 km de contexto.
      let start: [number, number], end: [number, number];
      if (lot && lot.vertices.length >= 3) {
        let maxDistance = -1;
        start = lot.vertices[0]; end = lot.vertices[1];
        for (let i = 0; i < lot.vertices.length; i++) for (let j = i + 1; j < lot.vertices.length; j++) {
          const p = lot.vertices[i], q = lot.vertices[j], rad = Math.PI / 180;
          const dx = (q[1] - p[1]) * rad * Math.cos(centerLat * rad), dy = (q[0] - p[0]) * rad;
          const distance = Math.hypot(dx, dy);
          if (distance > maxDistance) { maxDistance = distance; start = p; end = q; }
        }
      } else {
        const halfLon = 0.1 / Math.max(0.2, Math.cos(centerLat * Math.PI / 180));
        start = [centerLat, centerLon - halfLon]; end = [centerLat, centerLon + halfLon];
      }
      const points = Array.from({ length: 25 }, (_, i) => ({
        latitude: start[0] + (end[0] - start[0]) * i / 24,
        longitude: start[1] + (end[1] - start[1]) * i / 24
      }));
      const params = new URLSearchParams();
      params.set("latitude", points.map(p => p.latitude.toFixed(5)).join(","));
      params.set("longitude", points.map(p => p.longitude.toFixed(5)).join(","));
      const response = await fetch("https://api.open-meteo.com/v1/elevation?" + params.toString());
      if (!response.ok) throw new Error("Servicio de elevación respondió HTTP " + response.status);
      const json = await response.json();
      if (!Array.isArray(json.elevation) || json.elevation.length !== points.length) throw new Error("El servicio no devolvió el perfil de elevación completo");
      const distanceKm = (a: typeof points[number], b: typeof points[number]) => {
        const rad = Math.PI / 180, dx = (b.longitude - a.longitude) * rad * Math.cos(centerLat * rad);
        const dy = (b.latitude - a.latitude) * rad;
        return 6371 * Math.hypot(dx, dy);
      };
      let cumulative = 0;
      const profilePoints = json.elevation.map((e: number, i: number) => {
        if (i) cumulative += distanceKm(points[i - 1], points[i]);
        return { distance: cumulative, elevation: e };
      });
      setProfile(profilePoints);
    } catch (e) { setError((e as Error).message); setProfile([]); }
    finally { setProfileBusy(false); }
  }

  function exportCsv() {
    const rows = [["anio", "indicador", "valor"], ...series.map(p => [p.year, "AG.PRD.CROP.XD", String(p.value)])];
    const csv = "\ufeff" + rows.map(r => r.map(v => '"' + v.replaceAll('"', '""') + '"').join(";")).join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const a = document.createElement("a"); a.href = url; a.download = "DOTS-serie-agricola-world-bank.csv"; a.click(); URL.revokeObjectURL(url);
  }


  function exportSoilCsv() {
    const rows: string[][] = [
      ["propiedad", "unidad", "profundidad", "valor"],
      ...soil.flatMap(layer => layer.depths.map(d => [layer.name, layer.unit, d.depth, String(d.value ?? "")]))
    ];
    const csv = "\\ufeff" + rows.map(r => r.map(v => '"' + v.replaceAll('"', '""') + '"').join(";")).join("\\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const a = document.createElement("a"); a.href = url; a.download = "DOTS-observatorio-suelos.csv"; a.click(); URL.revokeObjectURL(url);
  }

  function exportTerrainCsv() {
    if (!terrainSummary) return;
    const rows = [["variable", "valor", "unidad"], ["elevacion_minima", String(terrainSummary.elevMin ?? ""), "m"],
      ["elevacion_media", String(terrainSummary.elevMean ?? ""), "m"], ["elevacion_maxima", String(terrainSummary.elevMax ?? ""), "m"],
      ["relieve_p95_p5", String(terrainSummary.relief ?? ""), "m"], ["pendiente_media", String(terrainSummary.slopeMeanPct ?? ""), "%"],
      ["superficie_plana", String(terrainSummary.flatPct ?? ""), "%"], ["depresiones", String(terrainSummary.depressionHa ?? ""), "ha"],
      ["depresiones_porcentaje", String(terrainSummary.depressionPct ?? ""), "%"], ["profundidad_maxima_depresion", String(terrainSummary.maxDepthM ?? ""), "m"],
      ["almacenamiento_topografico_estimado", String(terrainSummary.storageM3 ?? ""), "m3"], ["drenaje_en_lote", String(terrainSummary.drainageHa ?? ""), "ha"]];
    const csv = "\\ufeff" + rows.map(r => r.map(v => '"' + v.replaceAll('"', '""') + '"').join(";")).join("\\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const a = document.createElement("a"); a.href = url; a.download = "DOTS-relieve-hidrologia-lote.csv"; a.click(); URL.revokeObjectURL(url);
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
    <header className="dt-head"><div><div className="dt-kicker">DOTS / OBSERVATORIO AGRO</div><h1>Territorio 3D · Modelo del establecimiento</h1><p>Relieve digital, polígono del lote seleccionado, perfil topográfico, suelos y contexto satelital.</p></div><button className="dt-btn" onClick={() => window.print()}>Generar informe PDF</button></header>
    <div className="dt-cards">
      <div className="dt-stat"><small>Lote activo</small><b>{lot?.name || "Sin lote seleccionado"}</b><span>{lot?.areaHa != null ? lot.areaHa.toLocaleString("es-AR",{maximumFractionDigits:2})+" ha · polígono real" : "Seleccioná un lote en el mapa principal"}</span></div>
      <div className="dt-stat"><small>Serie agrícola · último dato disponible</small><b>{latest ? latest.value.toLocaleString("es-AR", { maximumFractionDigits: 2 }) : "—"}</b><span>{latest ? latest.year + " · Banco Mundial" : busy ? "Consultando fuente…" : "Sin observación"}</span></div>
      <div className="dt-stat"><small>Observaciones históricas</small><b>{series.length || "—"}</b><span>Argentina · 1995–2024 · WDI</span></div>
      <div className="dt-stat"><small>Perfil topográfico</small><b>{profile.length ? profile.length + " puntos" : "No consultado"}</b><span>Elevación modelada · Open-Meteo</span></div>
    </div>
    <div className="dt-layout">
      <section className="dt-panel"><div className="dt-head"><h3>Modelo digital del terreno</h3><button className="dt-btn" onClick={onTerrain} disabled={!lot || !onTerrain || terrainBusy}>{terrainBusy ? "Calculando relieve…" : terrainSummary ? "Actualizar relieve e hidrología" : "Calcular relieve e hidrología del lote"}</button></div><div className="dt-map-tools"><label><input type="checkbox" checked={terrainOn} onChange={e => setTerrainOn(e.target.checked)} /> Relieve 3D</label><label><input type="checkbox" checked={imageryOn} onChange={e => setImageryOn(e.target.checked)} /> Imagen satelital NASA MODIS</label><label>Exageración <input type="range" min="0.5" max="2.5" step="0.05" value={exaggeration} onChange={e => setExaggeration(Number(e.target.value))} /></label><span className="dt-muted">{lot?.name ? "Lote delimitado sobre el terreno" : "Cuenca del Paraná · navegación libre"}</span></div><div ref={mapNode} className="dt-map" aria-label="Mapa tridimensional de relieve" /><p className="dt-source">Cartografía base: OpenStreetMap. Elevación: AWS Terrain Tiles (Terrarium). Imagen opcional: NASA GIBS MODIS Terra True Color, 250 m. Es contexto regional y no sustituye Sentinel-2 de 10 m para decisiones parcelarias. El polígono amarillo corresponde al lote activo.</p></section>
      <aside className="dt-panel dt-side"><h3>Series históricas agrícolas</h3><label className="dt-muted">País </label><select value={country} onChange={e => setCountry(e.target.value)}><option value="ARG">Argentina</option><option value="BRA">Brasil</option><option value="URY">Uruguay</option><option value="PRY">Paraguay</option></select><p className="dt-muted">Índice de producción agrícola (2014–16 = 100)</p>{series.length ? <><svg className="dt-chart" viewBox="0 0 640 160" role="img" aria-label="Serie histórica del índice de producción agrícola"><line x1="20" y1="140" x2="620" y2="140" stroke="#60727d"/><polyline points={chart} fill="none" stroke="#5bc3a5" strokeWidth="4" strokeLinejoin="round" strokeLinecap="round"/></svg><div className="dt-legend"><span>{series[0].year}</span><span>{series[series.length-1].year}</span></div><button className="dt-btn" onClick={exportCsv}>Descargar serie CSV</button></> : <p className="dt-muted">{busy ? "Consultando Banco Mundial…" : "No hay observaciones para mostrar."}</p>}<p className="dt-source">Fuente: World Bank API · WDI {WDI}. Consulta: {sourceStamp || "pendiente"}. Los años faltantes no se interpolan.</p></aside>
    </div>
    {terrainSummary && <section className="dt-panel" style={{ marginTop: 14 }}>
      <div className="dt-head"><div><h3>Relieve e hidrología del lote</h3><p className="dt-muted">Análisis del DEM Copernicus GLO-30 y acumulación de flujo en el entorno del polígono. Indicadores topográficos modelados; no equivalen a un estudio hidráulico ni a una delimitación oficial de cuenca.</p></div><button className="dt-btn" onClick={exportTerrainCsv}>Descargar relieve e hidrología CSV</button></div>
      <div className="dt-cards">
        <div className="dt-stat"><small>Elevación media</small><b>{terrainSummary.elevMean?.toFixed(1) ?? "—"} m</b><span>mín. {terrainSummary.elevMin?.toFixed(1) ?? "—"} · máx. {terrainSummary.elevMax?.toFixed(1) ?? "—"} m</span></div>
        <div className="dt-stat"><small>Relieve interno P95–P5</small><b>{terrainSummary.relief?.toFixed(2) ?? "—"} m</b><span>Pendiente media {terrainSummary.slopeMeanPct?.toFixed(2) ?? "—"} %</span></div>
        <div className="dt-stat"><small>Superficie casi plana</small><b>{terrainSummary.flatPct?.toFixed(1) ?? "—"} %</b><span>Pendiente menor a 0,5 %</span></div>
        <div className="dt-stat"><small>Depresiones modeladas</small><b>{terrainSummary.depressionHa?.toFixed(2) ?? "—"} ha</b><span>{terrainSummary.depressionPct?.toFixed(1) ?? "—"} % del lote · profundidad máx. {terrainSummary.maxDepthM?.toFixed(2) ?? "—"} m</span></div>
        <div className="dt-stat"><small>Almacenamiento topográfico potencial</small><b>{terrainSummary.storageM3?.toLocaleString("es-AR",{maximumFractionDigits:0}) ?? "—"} m³</b><span>Estimación geomorfológica, no volumen de agua medido</span></div>
        <div className="dt-stat"><small>Vías de escurrimiento</small><b>{terrainSummary.drainageHa?.toFixed(2) ?? "—"} ha</b><span>Dentro del polígono · posición {terrainSummary.positionLabel || "—"}</span></div>
      </div>
      <p className="dt-source">Fuente: Copernicus DEM GLO-30. El flujo y las depresiones son derivados de elevación y algoritmo D8; requieren verificación de campo y no reemplazan curvas de nivel ni modelación hidráulica calibrada. La hidrografía de fondo procede de OpenStreetMap; no se dibuja una cuenca oficial si no hay delimitación disponible.</p>
    </section>}
    <div className="dt-layout">
      <section className="dt-panel"><h3>Perfil topográfico</h3><p className="dt-muted">{lot && lot.vertices.length >= 3 ? "Transecta sobre el lote: une los dos vértices más distantes del polígono." : "Transecta de contexto de aproximadamente 20 km centrada en las coordenadas ingresadas."}</p><button className="dt-btn" onClick={() => void loadProfile()} disabled={profileBusy}>{profileBusy ? "Consultando elevación…" : "Consultar perfil de elevación"}</button>{profile.length > 0 && <><svg className="dt-chart" viewBox="0 0 640 170" role="img" aria-label="Perfil de elevación consultado"><polyline points={profile.map((p,i)=>`${20+i*600/Math.max(1,profile.length-1)},${145-(p.elevation-Math.min(...profile.map(x=>x.elevation)))/(Math.max(...profile.map(x=>x.elevation))-Math.min(...profile.map(x=>x.elevation))||1)*115}`).join(" ")} fill="none" stroke="#e1b45b" strokeWidth="3"/></svg><div className="dt-muted">Mínimo: {Math.min(...profile.map(p=>p.elevation)).toFixed(1)} m · Máximo: {Math.max(...profile.map(p=>p.elevation)).toFixed(1)} m · Distancia: {profile[profile.length-1].distance.toFixed(2)} km · {profile.length} puntos</div></>}</section>
      <section className="dt-panel"><h3>Composición del suelo · SoilGrids</h3><div className="dt-map-tools"><label>Latitud <input value={lat} onChange={e=>setLat(e.target.value)} size={9}/></label><label>Longitud <input value={lon} onChange={e=>setLon(e.target.value)} size={9}/></label><button className="dt-btn" onClick={() => void loadSoil()} disabled={busy}>{busy ? "Consultando…" : "Consultar punto"}</button></div>{soil.length > 0 ? <><button className="dt-btn" onClick={exportSoilCsv}>Descargar suelo CSV</button><table className="dt-soil"><thead><tr><th>Variable</th><th>Profundidad</th><th>Valor</th><th>Unidad</th></tr></thead><tbody>{soil.flatMap(layer=>layer.depths.map(d=><tr key={layer.name+d.depth}><td>{layer.name}</td><td>{d.depth}</td><td>{d.value ?? "Sin dato"}</td><td>{layer.unit}</td></tr>))}</tbody></table></> : <p className="dt-muted">Ingresá coordenadas y consultá el producto modelado de SoilGrids. No se presentan valores hasta recibir respuesta de la fuente.</p>}<p className="dt-source">Fuente: ISRIC SoilGrids · resolución espacial aproximada 250 m. Producto modelado; no equivale a análisis de laboratorio ni medición de compactación.</p></section>
    </div>
    {error && <div className="dt-alert" role="alert">{error}</div>}
    <p className="dt-source">Los gráficos y tablas se completan únicamente con respuestas de las fuentes consultadas. No se generan valores de relleno. Esta vista 3D usa elevación real de un modelo digital; no representa por sí misma una simulación hidrológica.</p>
  </main>;
}
