// DOTS · mapa del campo para el celular. Lee el campo desde el enlace (#d=...), lo guarda en el teléfono y usa el GPS.
const CLASS = { L: ['Loma', '#c9a227'], P: ['Plano', '#9ccc65'], B: ['Bajo', '#4fa3d1'], A: ['Bajo anegable', '#1f5fa8'], W: ['Laguna o bañado', '#0b2f6b'] };
const TILE = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';
const $ = id => document.getElementById(id);

async function decode(tok) {
  const b = atob(tok.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - tok.length % 4) % 4));
  const bytes = Uint8Array.from(b, ch => ch.charCodeAt(0));
  const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('deflate-raw'));
  return JSON.parse(await new Response(stream).text());
}
function inPoly(lat, lon, p) {
  let ins = false;
  for (let i = 0, j = p.length - 1; i < p.length; j = i++) {
    const [yi, xi] = p[i], [yj, xj] = p[j];
    if ((yi > lat) !== (yj > lat) && lon < (xj - xi) * (lat - yi) / ((yj - yi) || 1e-12) + xi) ins = !ins;
  }
  return ins;
}
function classAt(d, lat, lon) {
  const z = d.z; if (!z) return null;
  const i = Math.round((lat - z.o[0]) / z.d[0]), j = Math.round((lon - z.o[1]) / z.d[1]);
  if (i < 0 || j < 0 || i >= z.r || j >= z.c) return null;
  const ch = z.g[i * z.c + j]; return ch && ch !== '.' ? ch : null;
}
function tilesFor(bounds, zmin, zmax, cap) {
  const out = [];
  const t = (lat, lon, z) => { const n = 2 ** z, x = Math.floor((lon + 180) / 360 * n), r = lat * Math.PI / 180; return [x, Math.floor((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2 * n)]; };
  for (let z = zmin; z <= zmax; z++) {
    const [x0, y0] = t(bounds.getNorth(), bounds.getWest(), z), [x1, y1] = t(bounds.getSouth(), bounds.getEast(), z);
    for (let x = x0; x <= x1; x++) for (let y = y0; y <= y1; y++) { out.push(TILE.replace('{z}', z).replace('{y}', y).replace('{x}', x)); if (out.length >= cap) return out; }
  }
  return out;
}
function netState() { const on = navigator.onLine; $('net').textContent = on ? 'con señal' : 'sin señal'; $('net').className = 'net' + (on ? '' : ' off'); }

async function main() {
  netState(); addEventListener('online', netState); addEventListener('offline', netState);
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('/campo-sw.js', { scope: '/campo' }).catch(() => {});
  let tok = (location.hash.match(/d=([A-Za-z0-9_-]+)/) || [])[1];
  try { if (tok) localStorage.setItem('dots-campo-last', tok); else tok = localStorage.getItem('dots-campo-last'); } catch {}
  if (!tok) { $('here').innerHTML = '<b>Falta el campo</b><small>Abrí esta página desde el código QR del informe de campo de DOTS.</small>'; return; }
  let d;
  try { d = await decode(tok); } catch (e) { $('here').innerHTML = '<b>El enlace está incompleto</b><small>Volvé a escanear el código QR del informe.</small>'; return; }
  $('name').textContent = d.n || 'Mapa del campo'; document.title = `${d.n || 'Campo'} · DOTS`;
  $('meta').textContent = `Informe del ${d.f.split('-').reverse().join('/')}`;
  const legend = $('legend'); legend.replaceChildren();
  for (const [k, [n, c]] of Object.entries(CLASS)) {
    if (!(d.z && d.z.g.includes(k))) continue;
    const span = document.createElement('span'), icon = document.createElement('i');
    icon.style.background = c;
    span.append(icon, document.createTextNode(n));
    legend.append(span);
  }
  const summary = $('summary'); summary.replaceChildren();
  for (const [a, b] of (d.s || [])) {
    const s1 = document.createElement('span'), s2 = document.createElement('span');
    s1.textContent = a; s2.textContent = b;
    summary.append(s1, s2);
  }

  const map = L.map('map', { zoomControl: true, attributionControl: true });
  L.tileLayer(TILE, { maxZoom: 18, maxNativeZoom: 17, attribution: 'Esri World Imagery' }).addTo(map);
  map.fitBounds(L.latLngBounds(d.p), { padding: [12, 12] });
  if (d.z) {
    const z = d.z, g = L.layerGroup().addTo(map);
    for (let i = 0; i < z.r; i++) for (let j = 0; j < z.c; j++) {
      const ch = z.g[i * z.c + j]; if (ch === '.' || !CLASS[ch]) continue;
      const la = z.o[0] + i * z.d[0], lo = z.o[1] + j * z.d[1];
      L.rectangle([[la - z.d[0] / 2, lo - z.d[1] / 2], [la + z.d[0] / 2, lo + z.d[1] / 2]], { weight: 0, fillColor: CLASS[ch][1], fillOpacity: .45, interactive: false }).addTo(g);
    }
  }
  const outline = L.polygon(d.p, { color: '#fff', weight: 2.5, fill: false }).addTo(map);

  $('save').onclick = async () => {
    if (!navigator.onLine) { $('saveinfo').textContent = 'Necesitás señal para guardar el mapa.'; return; }
    $('save').disabled = true;
    const urls = tilesFor(outline.getBounds().pad(0.15), 12, 17, 700);
    const cache = await caches.open('campo-tiles-v1'); let ok = 0;
    for (let k = 0; k < urls.length; k += 8) {
      await Promise.all(urls.slice(k, k + 8).map(u => fetch(u, { mode: 'no-cors' }).then(r => { if (r.ok || r.type === 'opaque') { ok++; return cache.put(u, r); } }).catch(() => {})));
      $('saveinfo').textContent = `Guardando imágenes del campo: ${ok} de ${urls.length}…`;
    }
    try { localStorage.setItem('dots-campo-saved-' + tok.slice(0, 24), String(Date.now())); } catch {}
    $('saveinfo').textContent = `Listo: el mapa y ${ok} imágenes quedaron guardados en este teléfono. Ya funciona sin señal.`;
    $('save').textContent = 'Guardado ✓';
  };

  let me = null, ring = null;
  if (!navigator.geolocation) { $('here').innerHTML = '<b>Este teléfono no da la ubicación</b>'; return; }
  navigator.geolocation.watchPosition(pos => {
    const { latitude: la, longitude: lo, accuracy } = pos.coords;
    if (!me) { me = L.marker([la, lo], { icon: L.divIcon({ className: '', html: '<div class="me"></div>', iconSize: [16, 16] }) }).addTo(map); ring = L.circle([la, lo], { radius: accuracy, weight: 1, color: '#1d4ed8', fillOpacity: .08 }).addTo(map); }
    else { me.setLatLng([la, lo]); ring.setLatLng([la, lo]).setRadius(accuracy); }
    const inside = inPoly(la, lo, d.p), ch = inside ? classAt(d, la, lo) : null;
    const acc = `precisión ±${Math.round(accuracy)} m`;
    if (!inside) $('here').innerHTML = `<b>Estás fuera del campo</b><small>${acc}</small>`;
    else if (ch) $('here').innerHTML = `<b><span class="chip" style="background:${CLASS[ch][1]}"></span>Estás en: ${CLASS[ch][0]}</b><small>${acc}</small>`;
    else $('here').innerHTML = `<b>Estás dentro del campo</b><small>Sin dato de zona en este punto · ${acc}</small>`;
  }, err => { $('here').innerHTML = `<b>No se pudo obtener la ubicación</b><small>${err.code === 1 ? 'Permití el acceso a la ubicación en el navegador.' : 'Probá al aire libre, con el GPS activado.'}</small>`; },
  { enableHighAccuracy: true, maximumAge: 5000, timeout: 20000 });
}
addEventListener('DOMContentLoaded', main);
