/* DOTS · modo vitrina. Si el sitio está en vitrina y el visitante no tiene acceso, muestra una franja
   fija abajo con el aviso y un campo para la clave de invitación. Sin modo vitrina no hace nada. */
(() => {
  if (window.__dotsVitrina) return;
  window.__dotsVitrina = true;

  const css = `
  .dv-bar{position:fixed;left:0;right:0;bottom:0;z-index:2147483000;background:#0d1f2d;color:#dbe9ee;border-top:1px solid #36515e;
    font:14px/1.45 "IBM Plex Sans",system-ui,Arial,sans-serif;padding:12px 16px}
  .dv-in{max-width:1120px;margin:0 auto;display:flex;flex-wrap:wrap;align-items:center;gap:10px 16px}
  .dv-txt{flex:1 1 320px;margin:0}
  .dv-txt b{color:#fff;font-weight:600}
  .dv-form{display:flex;gap:8px;flex-wrap:wrap}
  .dv-bar input{min-width:0;width:190px;padding:9px 10px;border-radius:6px;border:1px solid #57a5b0;background:#091724;color:#fff;font:inherit}
  .dv-bar button{padding:9px 13px;border-radius:6px;border:1px solid #57a5b0;background:#1c4454;color:#fff;font:600 13px system-ui,sans-serif;cursor:pointer}
  .dv-bar button:focus-visible,.dv-bar input:focus-visible{outline:2px solid #65d9df;outline-offset:1px}
  .dv-msg{flex-basis:100%;margin:0;color:#f3c58b;font-size:13px}
  .dv-msg:empty{display:none}
  @media print{.dv-bar{display:none!important}}`;

  function mount(info) {
    const st = document.createElement('style');
    st.textContent = css;
    document.head.appendChild(st);
    const bar = document.createElement('aside');
    bar.className = 'dv-bar';
    bar.setAttribute('role', 'region');
    bar.setAttribute('aria-label', 'Modo vitrina');
    const zona = (info.zona_ejemplo && info.zona_ejemplo.nombre) || 'Bella Vista, Corrientes';
    bar.innerHTML = `<div class="dv-in">
      <p class="dv-txt"><b>DOTS en modo vitrina.</b> Podés recorrer todo el sitio. Las consultas sobre tu campo o tu localidad son por invitación; la zona de ejemplo de <span class="dv-zona"></span> funciona completa.</p>
      <form class="dv-form" autocomplete="on">
        <input type="password" name="clave" placeholder="Clave de acceso" aria-label="Clave de acceso" autocomplete="current-password" required>
        <button type="submit">Entrar</button>
        <button type="button" class="dv-contacto">Pedir acceso</button>
      </form>
      <p class="dv-msg" role="status" aria-live="polite"></p></div>`;
    bar.querySelector('.dv-zona').textContent = zona;
    const msg = bar.querySelector('.dv-msg');
    bar.querySelector('.dv-contacto').onclick = () => { location.href = '/contacto'; };
    bar.querySelector('form').onsubmit = async (e) => {
      e.preventDefault();
      const clave = e.target.clave.value.trim();
      if (!clave) return;
      msg.textContent = 'Verificando…';
      try {
        const r = await fetch('/api/acceso', { method: 'POST', credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ clave }) });
        const j = await r.json().catch(() => ({}));
        if (r.ok && j.acceso) { msg.textContent = 'Acceso habilitado.'; location.reload(); return; }
        msg.textContent = r.status === 429 ? 'Demasiados intentos. Probá de nuevo en unos minutos.' : (j.error || 'La clave no es válida.');
      } catch { msg.textContent = 'No se pudo verificar la clave. Probá de nuevo.'; }
    };
    document.body.appendChild(bar);
    const pad = () => { document.body.style.paddingBottom = bar.offsetHeight + 'px'; };
    pad();
    window.addEventListener('resize', pad);
  }

  async function start() {
    try {
      const r = await fetch('/api/acceso', { credentials: 'same-origin', headers: { Accept: 'application/json' } });
      if (!r.ok) return;
      const info = await r.json();
      if (info.vitrina && !info.acceso) mount(info);
    } catch { /* sin API no hay vitrina que mostrar */ }
  }
  if (window.self !== window.top) return;   // no aparece en el widget embebido de avisos
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
