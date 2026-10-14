// Capturas del sitio publicado con un lote de control en Corrientes (uso: node scripts/capturas.mjs <base> <carpeta>)
import { chromium } from 'playwright';
const base = process.argv[2] || 'https://observatorio-agro.vercel.app';
const out = process.argv[3] || 'capturas';
const V = [[-28.56,-58.71],[-28.56,-58.69],[-28.54,-58.69],[-28.54,-58.71]];
const lot = { id: 'control', name: 'Lote control', vertices: V, center: [-28.55,-58.70], areaHa: 432, perimeterKm: 8.3 };
const views = [['Índices satelitales','indices'],['Agua por radar','radar'],['Balance de agua','balance'],['Vegetación · NDVI','ndvi']];
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1600, height: 1000 } });
await p.goto(base + '/observatorio');
await p.evaluate(l => { localStorage.setItem('dots-lotes', JSON.stringify([l])); localStorage.setItem('dots-vista', 'mapa'); }, lot);
await p.goto(base + '/observatorio'); await p.waitForTimeout(4000);
// seleccionar el lote: clic en su nombre o en el polígono
const name = p.locator('.lot-list button', { hasText: 'Lote control' }).first();
if (await name.count()) { await name.click().catch(()=>{}); console.log('lote elegido'); }
else { const poly = p.locator('path.leaflet-interactive').first(); if (await poly.count()) await poly.click({ force: true }).catch(()=>{}); }
await p.waitForTimeout(2500);
for (const [label, file] of views) {
  const btn = p.getByRole('button', { name: label }).first();
  if (!(await btn.count())) { console.log('sin botón', label); continue; }
  await btn.click().catch(e => console.log('click', label, e.message));
  await p.waitForTimeout(label.startsWith('Balance') ? 25000 : 15000);
  await p.screenshot({ path: `${out}/${file}.png` });
  console.log('ok', file);
}
const tab = p.getByRole('tab', { name: 'Tablero' }).first();
if (await tab.count()) { await tab.click().catch(()=>{}); await p.waitForTimeout(12000); await p.screenshot({ path: `${out}/tablero.png` }); console.log('ok tablero'); }
await p.goto(base + '/capas'); await p.waitForTimeout(2000);
await p.screenshot({ path: `${out}/pagina-capas.png` });
await p.goto(base + '/el-nino'); await p.waitForTimeout(20000);
await p.screenshot({ path: `${out}/el-nino.png`, fullPage: true });
await b.close();
