// Revisión de accesibilidad (WCAG 2 A y AA) de las páginas públicas con axe-core. Corre en GitHub Actions.
// Uso: node scripts/accesibilidad.mjs https://observatorio-agro.vercel.app
import { chromium } from 'playwright';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const axe = readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8');
const base = process.argv[2] || 'https://observatorio-agro.vercel.app';
const pages = ['/', '/el-nino', '/cultivos', '/alertas', '/panel', '/poblacion', '/ganaderia', '/libre-deforestacion', '/guia', '/precios', '/contacto', '/conexiones'];
const browser = await chromium.launch();
let total = 0;
for (const path of pages) {
  const p = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  try {
    await p.goto(base + path, { waitUntil: 'networkidle', timeout: 60000 });
  } catch { /* algunas páginas siguen consultando fuentes externas: se revisa lo que cargó */ }
  await p.addScriptTag({ content: axe });
  const v = await p.evaluate(async () => (await axe.run(document, { runOnly: ['wcag2a', 'wcag2aa'] })).violations);
  for (const x of v) {
    total += 1;
    const lvl = x.impact === 'critical' || x.impact === 'serious' ? 'warning' : 'notice';
    console.log(`::${lvl} title=Accesibilidad ${path}::${x.help} (${x.nodes.length} elementos: ${x.nodes.slice(0, 2).map(n => n.target.join(' ')).join(' · ')})`);
  }
  await p.close();
}
await browser.close();
console.log(`${total} problemas de accesibilidad en ${pages.length} páginas.`);
