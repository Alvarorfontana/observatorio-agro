import { useEffect, useState } from "react";

// ¿Puedo vender a la Unión Europea? Autoevaluación frente al Reglamento (UE) 2023/1115 (EUDR).
// Junta lo que DOTS mide (geolocalización y cobertura arbórea) con lo que sólo el productor puede declarar.
// Orientativo: no reemplaza la debida diligencia del exportador ni el asesoramiento legal.

type Data = Record<string, any>;

const PRODUCTS: [string, string, boolean][] = [
  ["bovino", "Ganado bovino y carne", true],
  ["soja", "Soja (grano, harina, aceite)", true],
  ["madera", "Madera y carbón vegetal", true],
  ["cuero", "Cuero bovino", false],
  ["otro", "Maíz, trigo, girasol u otro", false],
];

const CHECKS: { id: string; text: string; help: string; only?: string }[] = [
  { id: "otbn", text: "El lote respeta el ordenamiento de bosques (Ley 26.331)", help: "Sin desmontes en zonas roja o amarilla del OTBN provincial, o con autorización si hubo cambio de uso." },
  { id: "titulo", text: "Tengo el título o el contrato de arrendamiento del campo", help: "La UE pide que la producción cumpla la ley del país, incluidos los derechos de uso de la tierra." },
  { id: "renspa", text: "RENSPA de SENASA vigente para el establecimiento", help: "Registro sanitario del campo donde se crían o engordan los animales.", only: "bovino" },
  { id: "trazab", text: "Puedo rastrear cada animal desde que nació", help: "Identificación individual y DT-e de todos los movimientos. La UE pide ubicar todos los campos por donde pasó el animal (cría, recría e invernada).", only: "bovino" },
  { id: "campos", text: "Tengo la ubicación de todos los campos de origen", help: "Coordenadas de cada predio de origen, con polígono si supera 4 ha. Para ganado alcanza la ubicación de cada establecimiento donde estuvo el animal." },
  { id: "laboral", text: "Personal registrado y obligaciones fiscales al día", help: "Derechos laborales, ambientales y tributarios forman parte de la legalidad que se verifica." },
  { id: "indig", text: "Sin reclamos de comunidades indígenas o campesinas sobre el lote", help: "Incluye el consentimiento libre, previo e informado cuando corresponde." },
  { id: "dds", text: "El comprador o exportador va a presentar la declaración de diligencia debida", help: "La presenta quien introduce el producto en la UE. Un pequeño operador primario puede usar la declaración simplificada." },
];

function load(): Record<string, boolean> {
  try { return JSON.parse(localStorage.getItem("dots-eudr-checks") || "{}"); } catch { return {}; }
}

export function EudrReadiness({ d, tof, tofImg, onState, whisp, onWhisp, whispBusy }: { d?: Data; tof?: Data | null; tofImg?: string; onState?: (r: Data) => void; whisp?: Data | null; onWhisp?: (product: string) => void; whispBusy?: boolean }) {
  const [imgFail, setImgFail] = useState(false);
  useEffect(() => setImgFail(false), [tofImg]);
  const ha = (v: any) => v == null ? "—" : Number(v).toLocaleString("es-AR", { maximumFractionDigits: 1 }) + " ha";
  const [product, setProduct] = useState<string>(() => { try { return localStorage.getItem("dots-eudr-product") || "bovino"; } catch { return "bovino"; } });
  const [checks, setChecks] = useState<Record<string, boolean>>(load);
  const p = PRODUCTS.find(x => x[0] === product) || PRODUCTS[0];
  const inScope = p[2];
  const list = CHECKS.filter(c => !c.only || c.only === product);

  const toggle = (id: string) => setChecks(prev => {
    const n = { ...prev, [id]: !prev[id] };
    try { localStorage.setItem("dots-eudr-checks", JSON.stringify(n)); } catch {}
    return n;
  });
  const pick = (v: string) => { setProduct(v); try { localStorage.setItem("dots-eudr-product", v); } catch {} };

  // Lo que mide DOTS
  const geo = d?.area_ha != null;
  const v = String(d?.verdict || "sin dato");
  const forest: "ok" | "warn" | "bad" | "na" = v.startsWith("sin pérdida") ? "ok" : v.startsWith("pérdida menor") ? "warn" : v.startsWith("pérdida de cobertura") ? "bad" : "na";
  const missing = list.filter(c => !checks[c.id]);

  let tone = "", title = "", text = "";
  if (!inScope) {
    tone = "ok"; title = "Este producto no está alcanzado por el EUDR";
    text = product === "cuero" ? "El acto delegado de julio de 2026 sacó los cueros bovinos del alcance. La carne y el ganado siguen alcanzados." : "El reglamento cubre ganado bovino, soja, madera, palma, cacao, café y caucho. Para este producto rigen las reglas comunes de importación.";
  } else if (forest === "bad") {
    tone = "warn"; title = "No apto por ahora";
    text = "DOTS detectó pérdida de árboles después del 31/12/2020 por encima del umbral. Hay que verificarla en campo y documentarla antes de ofrecer el producto a la UE.";
  } else if (!geo || forest === "na") {
    tone = ""; title = "Faltan datos del lote";
    text = "Dibujá el lote y tocá Calcular para que DOTS mida la cobertura arbórea desde 2020.";
  } else if (missing.length || forest === "warn") {
    tone = "warn"; title = `Faltan ${missing.length + (forest === "warn" ? 1 : 0)} pasos`;
    text = forest === "warn" ? "Hay una pérdida menor de árboles para revisar. " : "";
    text += missing.length ? "Completá lo que falta en la lista de abajo." : "";
  } else {
    tone = "ok"; title = "En condiciones de ofrecer el producto";
    text = "El lote cumple lo que DOTS puede medir y declaraste el resto. El exportador igual hace su propia debida diligencia.";
  }

  useEffect(() => {
    onState?.({ product: p[1], in_scope: inScope, result: { title, text, tone }, declared: list.map(c => ({ text: c.text, done: !!checks[c.id] })),
      whisp: whisp?.risk ? { risk: whisp.risk, text: whisp.text } : null });
  }, [product, checks, title, text, tone, whisp?.risk]);

  const mark = (s: "ok" | "warn" | "bad" | "na") => s === "ok" ? "✓" : s === "na" ? "·" : "!";

  return <div className="eudr-ready">
    <div className="lot-vars-title" style={{ marginTop: 10 }}>¿Puedo vender a la Unión Europea?</div>
    <label className="small">Producto
      <select value={product} onChange={e => pick(e.target.value)} style={{ width: "100%", marginTop: 6 }}>
        {PRODUCTS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
      </select>
    </label>

    <div className={"verdict " + tone} style={{ marginTop: 8 }}><span>Resultado</span><b>{title}</b><small>{text}</small></div>

    {inScope && <>
      <div className="eudr-sub">Lo que mide DOTS</div>
      <ul className="eudr-list auto">
        <li className={geo ? "ok" : "na"}><i>{mark(geo ? "ok" : "na")}</i><span>Geolocalización del lote<small>{geo ? `Polígono de ${Number(d?.area_ha).toLocaleString("es-AR", { maximumFractionDigits: 1 })} ha listo para exportar en GeoJSON.` : "Sin polígono todavía."}</small></span></li>
        <li className={forest}><i>{mark(forest)}</i><span>Libre de deforestación desde el 31/12/2020<small>{v}</small></span></li>
        <li className="warn"><i>!</i><span>Riesgo país: estándar<small>Argentina figura como riesgo estándar en la clasificación de la Comisión: debida diligencia completa y controles sobre el 3 % de los operadores.</small></span></li>
        {whisp?.risk && <li className={whisp.risk === "low" ? "ok" : whisp.risk === "high" ? "bad" : "warn"}><i>{whisp.risk === "low" ? "✓" : "!"}</i><span>Segunda opinión · Whisp (FAO)<small>{whisp.text}</small></span></li>}
      </ul>
      {tof && tof.trees_ha != null && <>
        <div className="eudr-sub">Árboles fuera del bosque</div>
        <p className="small" style={{ margin: "4px 0 6px" }}>{tof.reading}</p>
        <ul className="eudr-ranges">
          <li><b><i className="dw-dot" style={{ background: "#1b5e20" }} /> Bosque 2020 (JRC)</b> {ha(tof.forest_2020_ha)} · cualquier pérdida posterior cuenta para la UE</li>
          <li><b><i className="dw-dot" style={{ background: "#f2a900" }} /> Cortinas y árboles sueltos</b> {ha(tof.small_ha)} · parches de menos de 0,5 ha</li>
          <li><b><i className="dw-dot" style={{ background: "#7cb342" }} /> Montes fuera del bosque</b> {ha(tof.large_ha)} · 0,5 ha o más: revisar altura</li>
        </ul>
        {tofImg && !imgFail && <img src={tofImg} alt="Mapa del lote con bosque 2020, cortinas y montes" loading="lazy" onError={() => setImgFail(true)}
          style={{ width: "100%", borderRadius: 8, marginTop: 6, background: "#eef1ec" }} />}
        <p className="footnote">ESA WorldCover 2021 (10 m) cruzado con el mapa de bosques 2020 del JRC, referencia de la Comisión Europea. Una cortina angosta puede quedar subestimada.</p>
      </>}
      {onWhisp && <button disabled={whispBusy || !geo} onClick={() => onWhisp(product)}>{whispBusy ? "Consultando a Whisp… puede tardar un minuto" : whisp?.risk ? "Volver a consultar Whisp" : "Pedir segunda opinión a Whisp (FAO)"}</button>}
      {whisp?.status === "requiere credencial" && <p className="footnote">Whisp es gratis pero pide una clave: crear cuenta en whisp.openforis.org, generarla y cargarla en Vercel como WHISP_API_KEY.</p>}
      {whisp?.error && <p className="footnote">{whisp.error}</p>}
      <p className="footnote">Whisp cruza decenas de mapas públicos, incluido el mapa de bosques 2020 que la Comisión Europea usa como referencia (JRC).</p>

      <div className="eudr-sub">Lo que declarás vos</div>
      <ul className="eudr-list">
        {list.map(c => <li key={c.id} className={checks[c.id] ? "ok" : ""}>
          <label><input type="checkbox" checked={!!checks[c.id]} onChange={() => toggle(c.id)} /><span>{c.text}<small>{c.help}</small></span></label>
        </li>)}
      </ul>
    </>}

    <div className="eudr-sub">Rangos de la verificación de árboles</div>
    <ul className="eudr-ranges">
      <li><b>Sin pérdida</b> menos de 0,5 ha o menos de 1 punto de cobertura perdido</li>
      <li><b>Pérdida menor</b> menos de 5 ha, o dentro del ruido del mapa, o no sostenida: revisar</li>
      <li><b>Requiere verificación</b> más de 5 ha, el doble del ruido del mapa y sostenida dos años</li>
    </ul>

    <div className="eudr-sub">Fechas</div>
    <ul className="eudr-ranges">
      <li><b>30/12/2026</b> empieza a regir para empresas grandes y medianas</li>
      <li><b>30/06/2027</b> para micro y pequeñas empresas</li>
      <li><b>31/12/2020</b> fecha de corte: no puede haber deforestación posterior</li>
    </ul>
    <p className="footnote">Autoevaluación orientativa según el Reglamento (UE) 2023/1115, modificado por el 2025/2650, y el acto delegado de alcance de julio de 2026. Las respuestas quedan sólo en este navegador. No reemplaza la debida diligencia del exportador ni el asesoramiento legal.</p>
  </div>;
}
