import { useEffect, useRef, useState } from 'react';
import { SHEET_SOURCES, sheetScope, sheetSection, readingText, type Lot, type SheetSource, type Sheet } from './terrainSheetModel';
import './terrainSheet.css';
const STORAGE = 'dots-terrain-sheets-v1';
const stamp = (s: string) => new Date(s).toLocaleString('es-AR');
export function TerrainSheet({ lots, selectedId, sources, onSelect, onLayer, onPdf, onResult }: {
  lots: Lot[]; selectedId: string | null; sources: Record<string, SheetSource>;
  onResult: (geometry: string, key: string, result: SheetSource) => void;
  onSelect: (id: string) => void; onLayer: (key: string) => void; onPdf: () => void;
}) {
  const [sheets, setSheets] = useState<Record<string, Sheet>>(() => {
    try {
      const x = JSON.parse(localStorage.getItem(STORAGE) || '{}');
      if (x.version !== 1 || !x.sheets || typeof x.sheets !== 'object') return {};
      const restored: Record<string, Sheet> = {};
      for (const [id, raw] of Object.entries(x.sheets) as [string, Sheet][]) {
        if (!raw || typeof raw.geometry !== 'string' || !raw.sections) continue;
        const sections = Object.fromEntries(Object.entries(raw.sections).filter(([key, s]) => SHEET_SOURCES.includes(key as typeof SHEET_SOURCES[number]) && s && Array.isArray(s.readings)).map(([key, s]) => [key, s.state === 'consultando' ? { ...s, state: 'sin dato', note: 'Consulta interrumpida. Actualizá la ficha para reintentar.' } : s]));
        restored[id] = { geometry: raw.geometry, sections };
      }
      return restored;
    } catch { return {}; }
  });
  const [chosen, setChosen] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const alive = useRef(true);
  const running = useRef(false);
  const controllers = useRef(new Set<AbortController>());
  const lot = lots.find(x => x.id === selectedId);
  const geometry = lot ? sheetScope(lot) : '';
  const current = lot && sheets[lot.id]?.geometry === geometry ? sheets[lot.id] : undefined;
  useEffect(() => { alive.current = true; const pending = controllers.current; return () => { alive.current = false; pending.forEach(c => c.abort()); }; }, []);
  useEffect(() => {
    try { localStorage.setItem(STORAGE, JSON.stringify({ version: 1, sheets })); } catch {
      // Report an external storage failure without interrupting the current render cycle.
      queueMicrotask(() => { if (alive.current) setMessage('No se pudieron guardar las fichas en este navegador. Descargalas en JSON.'); });
    }
  }, [sheets]);
  // Only accept results tagged with the exact point and polygon of this lot.
  useEffect(() => {
    if (!selectedId || !geometry) return;
    const id = selectedId;
    const matches = SHEET_SOURCES.filter(k => sources[k]?.scopeKey === geometry && sources[k].status !== 'consultando');
    if (!matches.length) return;
    // Snapshot matching external API results; never derive a lot identity from the visible label.
    queueMicrotask(() => {
      if (!alive.current) return;
      setSheets(prev => {
        const old = prev[id]?.geometry === geometry ? prev[id].sections : {};
        const sections = { ...old, ...Object.fromEntries(matches.map(k => [k, sheetSection(k, sources[k])])) };
        return JSON.stringify(old) === JSON.stringify(sections) ? prev : { ...prev, [id]: { geometry, sections } };
      });
    });
  }, [sources, geometry, selectedId]);
  const put = (l: Lot, key: string, result: SheetSource) => {
    if (!alive.current) return;
    setSheets(prev => ({ ...prev, [l.id]: { geometry: sheetScope(l), sections: { ...(prev[l.id]?.geometry === sheetScope(l) ? prev[l.id].sections : {}), [key]: sheetSection(key, result) } } }));
  };
  async function complete(targets: Lot[]) {
    if (running.current) return;
    running.current = true; setBusy(true); setMessage('');
    try {
      // Bound pressure on providers: one lot at a time, independent sources in parallel.
      for (const l of targets) {
        if (!alive.current) break;
        await Promise.allSettled(SHEET_SOURCES.map(async key => {
          put(l, key, { status: 'consultando' });
          const ctl = new AbortController(); controllers.current.add(ctl);
          const timer = setTimeout(() => ctl.abort(), 60000);
          try {
            const q = new URLSearchParams({ lat: String(l.center[0]), lon: String(l.center[1]), polygon: JSON.stringify(l.vertices) });
            const r = await fetch(`/api/fuentes/${key}?${q}`, { signal: ctl.signal });
            const j = await r.json();
            if (!r.ok) throw Error(j.error || `Fuente no disponible (${r.status})`);
            const result = { status: j.status === 'sin dato' ? 'sin dato' : 'recibido', payload: j };
            put(l, key, result);
            if (alive.current) onResult(sheetScope(l), key, result);
          } catch (e) { put(l, key, { status: 'sin dato', error: e instanceof Error && e.name !== 'AbortError' ? e.message : 'La consulta excedió el tiempo disponible. Podés reintentar.' }); }
          finally { clearTimeout(timer); controllers.current.delete(ctl); }
        }));
      }
    } finally { running.current = false; if (alive.current) setBusy(false); }
  }
  const compared = lots.filter(l => chosen.includes(l.id));
  const exportSheets = () => {
    const rows = (compared.length ? compared : lot ? [lot] : []).map(l => ({ lot: l, analysis: sheets[l.id]?.geometry === sheetScope(l) ? sheets[l.id] : null }));
    const url = URL.createObjectURL(new Blob([JSON.stringify({ version: 1, exported_at: new Date().toISOString(), lots: rows }, null, 2)], { type: 'application/json' }));
    const a = document.createElement('a'); a.href = url; a.download = 'DOTS-fichas-terrenos.json'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  return <section className="terrain-sheet panel" aria-label="Ficha única y comparación de terrenos">
    <div className="ts-heading"><div><span className="small">TERRENOS Y LOTES</span><h2>Ficha única y comparación</h2><p>Suelo, vegetación, clima y cobertura con su fecha y fuente.</p></div>
      <div className="ts-actions"><button disabled={!lot || busy} onClick={() => lot && void complete([lot])}>{busy ? 'Consultando fuentes…' : 'Completar / actualizar ficha'}</button><button disabled={!lot} onClick={exportSheets}>Descargar JSON</button><button disabled={!lot} onClick={onPdf}>Informe PDF</button></div></div>
    {!lot ? <p>Dibujá, importá o seleccioná un lote para reunir sus resultados.</p> : <>
      <div className="ts-identity"><strong>{lot.name}</strong><span>{lot.areaHa.toLocaleString('es-AR', { maximumFractionDigits: 2 })} ha · {lot.perimeterKm.toFixed(2)} km de perímetro</span><span>Centro: {lot.center.map(n => n.toFixed(5)).join(', ')} · WGS84</span></div>
      <div className="ts-grid">{SHEET_SOURCES.map(k => {
        const s = current?.sections[k];
        return <article key={k}><div className="ts-section-title"><h3>{s?.title || ({ variables: 'Clima', ndvi: 'Vegetación', suelo: 'Suelo', sustentabilidad: 'Cobertura' }[k])}</h3><span role="status">{s?.state || 'Sin consultar'}</span></div>
          {s?.readings.map(r => <div className="ts-reading" key={r.label}><span>{r.label}<small>{r.date} · {r.support}</small></span><b>{readingText(r)}</b></div>)}
          {s && <p className="ts-provenance">{s.source} · consulta: {stamp(s.consulted)}{s.url && <> · <a href={s.url} target="_blank" rel="noreferrer">Fuente</a></>}</p>}
          {s?.note && <p className="ts-provenance">{s.note}</p>}
          <button onClick={() => onLayer(k)}>{k === 'suelo' ? 'Ver perfil de suelo' : k === 'variables' ? 'Ver clima' : k === 'ndvi' ? 'Ver NDVI en el mapa' : 'Ver WorldCover en el mapa'}</button>
        </article>;
      })}</div>
    </>}
    <details className="ts-compare"><summary>Comparar terrenos · {compared.length} seleccionados</summary>
      <p>Elegí de 2 a 4 lotes. Las fechas se conservan: imágenes de distintos días no representan una observación simultánea.</p>
      <div className="ts-picks">{lots.map(l => <label key={l.id}><input type="checkbox" checked={chosen.includes(l.id)} disabled={!chosen.includes(l.id) && compared.length >= 4} onChange={e => setChosen(prev => e.target.checked ? [...prev, l.id] : prev.filter(id => id !== l.id))}/>{l.name}</label>)}</div>
      <div className="ts-actions"><button disabled={busy || compared.length < 2} onClick={() => void complete(compared)}>Actualizar fichas seleccionadas</button><button disabled={compared.length < 2} onClick={exportSheets}>Descargar comparación JSON</button></div>
      {compared.length >= 2 && <div className="ts-table-scroll"><table><caption>Comparación descriptiva · sin puntaje de aptitud automático</caption><thead><tr><th scope="col">Variable</th>{compared.map(l => <th scope="col" key={l.id}><button onClick={() => onSelect(l.id)}>{l.name}</button></th>)}</tr></thead><tbody>
        <tr><th scope="row">Superficie</th>{compared.map(l => <td key={l.id}>{l.areaHa.toFixed(2)} ha</td>)}</tr>
        {SHEET_SOURCES.flatMap(key => {
          const sections = compared.map(l => sheets[l.id]?.geometry === sheetScope(l) ? sheets[l.id].sections[key] : undefined);
          const labels = [...new Set(sections.flatMap(s => s?.readings.map(r => r.label) || []))];
          return labels.length ? labels.map(label => <tr key={`${key}-${label}`}><th scope="row">{label}<small>{sections.find(Boolean)?.title}</small></th>{compared.map((l, i) => { const s = sections[i], r = s?.readings.find(r => r.label === label); return <td key={l.id}>{s?.state === 'consultando' ? 'Consultando…' : r ? readingText(r) : 'Sin dato'}{r && <small>{r.date}<br/>{r.support}</small>}{s && <small>{s.source} · consulta {stamp(s.consulted)}</small>}</td>; })}</tr>) : <tr key={key}><th scope="row">{{ variables: 'Clima', ndvi: 'Vegetación', suelo: 'Suelo', sustentabilidad: 'Cobertura' }[key]}</th>{compared.map((l, i) => <td key={l.id}>{sections[i]?.state || 'Sin consultar'}{sections[i]?.note && <small>{sections[i]?.note}</small>}</td>)}</tr>;
        })}
      </tbody></table></div>}
    </details>
    {message && <p role="status">{message}</p>}
  </section>;
}
