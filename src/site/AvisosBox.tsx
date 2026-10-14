/** Suscripción a los avisos de crecidas: correo, Telegram, RSS y widget para otras páginas web. */
import React, { useEffect, useState } from "react";

type Feed = { updated?: string; items: { id: string; place: string; river: string; from: string; to: string; up: boolean; text: string; at: string }[];
  channels: { email: boolean; telegram_url: string | null; ntfy_topic?: string; ntfy_url?: string; feed_rss: string; feed_json: string; widget: string } };

export function AvisosBox() {
  const [feed, setFeed] = useState<Feed | null>(null);
  const [email, setEmail] = useState(""), [trap, setTrap] = useState(""), [msg, setMsg] = useState(""), [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  useEffect(() => { fetch("/api/fuentes/avisos").then(r => r.json()).then(j => setFeed(j.data)).catch(() => {}); }, []);
  const ch = feed?.channels;
  const widget = `<iframe src="https://observatorio-agro.vercel.app/avisos-widget/" title="Avisos de crecidas · DOTS" width="100%" height="420" style="border:0"></iframe>`;
  async function sub(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setMsg("");
    try {
      const r = await fetch("/api/fuentes/avisos/suscribir", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, website: trap }) });
      const j = await r.json(); setMsg(j.message || j.error || "Listo."); if (j.status === "suscripto") setEmail("");
    } catch { setMsg("No se pudo registrar el correo."); } finally { setBusy(false); }
  }
  return <section className="avisos-box" id="avisos">
    <div className="avisos-head"><span className="section-tag">AVISOS AUTOMÁTICOS</span>
      <h2>Enterate cuando una localidad cambia de nivel.</h2>
      <p>Cada dos horas DOTS revisa las alturas oficiales del INA en las 34 localidades. Cuando una pasa de Normal a Atención, Alerta o Evacuación, o vuelve a bajar, se publica el aviso y se envía por los canales de abajo. Texto formal, con la altura, los niveles oficiales y la tendencia.</p></div>
    <div className="avisos-grid">
      <article><b>Por correo</b>
        <form onSubmit={sub}><input type="email" required placeholder="tu@correo.com" value={email} onChange={e => setEmail(e.target.value)} aria-label="Correo electrónico" />
          <input className="trap" tabIndex={-1} autoComplete="off" value={trap} onChange={e => setTrap(e.target.value)} aria-hidden="true" />
          <button disabled={busy}>{busy ? "Registrando…" : "Suscribirme"}</button></form>
        {msg && <p className="small">{msg}</p>}
        {ch && !ch.email && <p className="small">La lista de correo se activa en estos días; mientras tanto usá Telegram o el feed.</p>}
        <p className="small">Cada correo trae un enlace para darse de baja.</p></article>
      <article><b>En el teléfono</b>
        <p className="small">Instalá la app gratuita <b>ntfy</b> (Android o iPhone), tocá <b>+</b> y suscribite al tema <b>{ch?.ntfy_topic || "dots-crecidas-cuenca-plata"}</b>. No pide cuenta ni número de teléfono.</p>
        <a className="avisos-btn" href={ch?.ntfy_url || "https://ntfy.sh/dots-crecidas-cuenca-plata"} target="_blank" rel="noopener">Abrir en ntfy</a>
        {ch?.telegram_url && <p className="small" style={{marginTop:8}}>También en el <a href={ch.telegram_url} target="_blank" rel="noopener">canal de Telegram</a>.</p>}</article>
      <article><b>En otras páginas web</b>
        <p className="small">Municipios, medios y escuelas pueden mostrar los avisos en su sitio, o seguirlos por RSS.</p>
        <button className="avisos-btn ghost" onClick={() => { navigator.clipboard?.writeText(widget).then(() => setCopied(true)).catch(() => {}); }}>{copied ? "Código copiado" : "Copiar código para insertar"}</button>
        <a className="small" href="/api/fuentes/avisos?formato=rss" target="_blank" rel="noopener">Feed RSS</a> · <a className="small" href="/avisos-widget/" target="_blank" rel="noopener">Ver el widget</a></article>
    </div>
    <div className="avisos-last"><b>Últimos avisos</b>
      {!feed ? <p className="small">Cargando…</p> : feed.items.length === 0 ? <p className="small">Todavía no hubo cambios de nivel desde que se activó el sistema.</p> :
        <ul>{feed.items.slice(0, 8).map(i => <li key={i.id + i.at}><span className={"lvl lvl-" + i.to.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()}>{i.to}</span> {i.text} <small>{i.at.replace("T", " ")} UTC</small></li>)}</ul>}
    </div>
  </section>;
}
