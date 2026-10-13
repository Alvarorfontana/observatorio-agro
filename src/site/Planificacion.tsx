/**
 * DOTS · Planificación del cultivo (portado y corregido de AgroClima v3).
 * Margen bruto con valores editables, calendario orientativo de siembra por zona, plagas y enfermedades de la
 * zona, y carbono del suelo con el método de Nivel 1 del IPCC (2019) sobre el stock real de SoilGrids.
 * Nada de esto inventa precios ni datos del lote: lo que depende del productor lo carga el productor.
 */
import { useEffect, useMemo, useState } from "react";
import { CULTIVOS } from "./Cultivos";

type Data = Record<string, any>;
const nf = (v: unknown, d = 0) => v == null || !Number.isFinite(Number(v)) ? "—" : Number(v).toLocaleString("es-AR", { minimumFractionDigits: d, maximumFractionDigits: d });

// ── zonas agroecológicas (aproximación por coordenadas; el usuario puede cambiarla)
export const ZONAS: Record<string, string> = {
  pampa_humeda: "Pampa húmeda", pampa_semiarida: "Pampa semiárida", nea: "NEA", noa: "NOA", cuyo: "Cuyo",
  uruguay: "Uruguay", paraguay: "Paraguay oriental", brasil_sur: "Sur de Brasil",
};
export function zonaDe(lat: number, lon: number, pais?: string) {
  const cc = (pais || "").toLowerCase();
  if (cc === "uy") return "uruguay";
  if (cc === "py") return "paraguay";
  if (cc === "br") return "brasil_sur";
  if (!cc) {                                   // coordenadas sueltas: aproximación por fronteras
    if (lat > -27.4 && lat < -19 && lon > -62.6 && lon < -54.3 && !(lon > -56.1 && lat < -25.5)) return "paraguay";
    if (lat < -30.1 && lon > -58.0 + (lat + 30.1) * 0.15) return "uruguay";
    if (lon > -53.8) return "brasil_sur";
  }
  if (lon < -66.5) return "cuyo";
  if (lat > -30 && lon < -62.5) return "noa";
  if (lat > -30.5) return "nea";
  return lon < -63.5 ? "pampa_semiarida" : "pampa_humeda";
}

// ── margen bruto: referencias de AgroClima (2024), sólo para precargar; el usuario las reemplaza
export const REF: Record<string, { rinde: number; precio: number; costo: number }> = {
  soja: { rinde: 3.0, precio: 320, costo: 570 }, maiz: { rinde: 8.0, precio: 180, costo: 680 }, trigo: { rinde: 3.2, precio: 220, costo: 445 },
  girasol: { rinde: 2.2, precio: 380, costo: 570 }, sorgo: { rinde: 5.5, precio: 170, costo: 435 }, arroz: { rinde: 7.0, precio: 280, costo: 1100 },
};
export function margen(rinde: number, precio: number, costo: number, comPct: number, flete: number, alquiler: number) {
  const bruto = rinde * precio, gastosCom = bruto * comPct / 100 + rinde * flete;
  const neto = bruto - gastosCom, mb = neto - costo, mbAlq = mb - alquiler;
  const precioNetoT = precio * (1 - comPct / 100) - flete;
  return { bruto, gastosCom, neto, mb, mbAlq, indif: precioNetoT > 0 ? (costo + alquiler) / precioNetoT : null, ret: costo + alquiler > 0 ? 100 * mbAlq / (costo + alquiler) : null };
}

// ── calendario de referencia de AgroClima (Pampa húmeda), en días del año. Sin corrimientos inventados por zona.
const VENT: Record<string, [string, number, number, string, string][]> = {
  soja: [["Temprana", 268, 288, "marzo, 1.ª quincena", "grupos I a V (115 a 130 días)"], ["Normal", 288, 324, "marzo y abril", "grupos VI y VII (130 a 140 días)"], ["Tardía", 324, 344, "abril y mayo", "grupo VIII o más (más de 140 días)"]],
  maiz: [["Temprana", 227, 258, "enero y febrero", "híbridos tempranos (110 a 120 días)"], ["Normal", 258, 303, "febrero y marzo", "híbridos medios (120 a 140 días)"], ["Tardía", 305, 344, "marzo y abril", "híbridos tardíos (más de 140 días)"]],
  trigo: [["Temprana", 130, 156, "octubre y noviembre", "ciclo largo"], ["Normal", 156, 201, "noviembre y diciembre", "ciclo intermedio"], ["Tardía", 201, 217, "diciembre y enero", "ciclo corto"]],
  girasol: [["Temprana", 244, 274, "enero y febrero", "híbridos de ciclo corto (120 días)"], ["Normal", 274, 319, "febrero y marzo", "híbridos medios (140 días)"], ["Tardía", 319, 349, "marzo y abril", "híbridos tardíos (160 días)"]],
};
const fecha = (doy: number) => new Date(Date.UTC(2001, 0, doy)).toLocaleDateString("es-AR", { day: "numeric", month: "short", timeZone: "UTC" });

// ── plagas y enfermedades (orientativo; corregido respecto de AgroClima)
const PLAGAS: { n: string; cult: string[]; zonas: string[]; temp: string; dano: string; manejo: string }[] = [
  { n: "Chicharrita del maíz (Dalbulus maidis) · achaparramiento", cult: ["maiz"], zonas: ["noa", "nea", "pampa_humeda", "paraguay", "brasil_sur"], temp: "Octubre a marzo", dano: "Transmite el espiroplasma del achaparramiento; en 2024 causó pérdidas masivas en el norte y centro.", manejo: "Monitoreo con trampas adhesivas, respetar fechas de siembra regionales, eliminar maíces guachos e híbridos de mejor comportamiento." },
  { n: "Oruga cogollera (Spodoptera frugiperda)", cult: ["maiz", "sorgo"], zonas: ["noa", "nea", "pampa_humeda", "paraguay", "brasil_sur", "uruguay"], temp: "Septiembre a marzo", dano: "Destruye el cogollo y el punto de crecimiento; peor en siembras tardías.", manejo: "Monitoreo semanal de plantas con daño, maíces Bt con refugio, control químico o biológico según umbral." },
  { n: "Isoca medidora (Rachiplusia nu)", cult: ["soja", "girasol"], zonas: ["pampa_humeda", "pampa_semiarida", "uruguay", "nea"], temp: "Diciembre a marzo", dano: "Defoliación en vegetativo y llenado de granos.", manejo: "Paño vertical, umbrales por estado del cultivo, preferir productos selectivos." },
  { n: "Oruga bolillera (Helicoverpa gelotopoeon)", cult: ["soja"], zonas: ["noa", "nea", "pampa_humeda"], temp: "Octubre a enero", dano: "Corta plántulas y daña vainas.", manejo: "Monitoreo desde la emergencia, especialmente con rastrojos de leguminosas." },
  { n: "Chinches (Nezara viridula, Piezodorus guildinii)", cult: ["soja"], zonas: ["pampa_humeda", "nea", "noa", "uruguay", "paraguay", "brasil_sur"], temp: "Febrero a abril (R3 a R6)", dano: "Granos chuzos y manchados; caída de rinde y calidad.", manejo: "Paño vertical desde R3; control por umbral." },
  { n: "Roya asiática de la soja (Phakopsora pachyrhizi)", cult: ["soja"], zonas: ["nea", "pampa_humeda", "paraguay", "brasil_sur"], temp: "Enero a abril, años húmedos", dano: "Defoliación prematura y granos chicos.", manejo: "Monitoreo desde R1, fungicidas con mezcla de modos de acción según riesgo." },
  { n: "Arañuela roja (Tetranychus urticae)", cult: ["soja", "maiz"], zonas: ["pampa_humeda", "pampa_semiarida", "noa"], temp: "Veranos secos y calurosos", dano: "Hojas amarillentas y bronceadas; avanza desde los bordes.", manejo: "Monitoreo en el envés de las hojas en sequía; acaricidas específicos sólo por umbral." },
  { n: "Langosta sudamericana (Schistocerca cancellata)", cult: ["soja", "maiz", "girasol", "sorgo", "trigo", "arroz"], zonas: ["noa", "nea", "cuyo", "pampa_semiarida"], temp: "Octubre a marzo", dano: "Mangas que defolian todo a su paso.", manejo: "Denunciar mangas y bandas a SENASA; el control es coordinado." },
  { n: "Pulgón amarillo (Sipha flava)", cult: ["sorgo"], zonas: ["noa", "nea", "paraguay"], temp: "Verano y otoño", dano: "Debilita plantas jóvenes y amarillea hojas.", manejo: "Monitoreo en hojas basales, favorecer enemigos naturales." },
  { n: "Pulgones y roya amarilla del trigo", cult: ["trigo"], zonas: ["pampa_humeda", "pampa_semiarida", "uruguay"], temp: "Julio a octubre", dano: "Debilitamiento y transmisión de virus; la roya amarilla avanza rápido con fresco y humedad.", manejo: "Monitoreo semanal, variedades resistentes, fungicida según umbral de severidad." },
  { n: "Bicho moro y gusano barrenador (arroz)", cult: ["arroz"], zonas: ["nea", "uruguay", "brasil_sur", "paraguay"], temp: "Diciembre a marzo", dano: "Plantas muertas y panojas vacías.", manejo: "Manejo del agua de inundación y monitoreo de bordes." },
];

// ── carbono: IPCC 2019, Nivel 1, tierras de cultivo, clima templado cálido húmedo (cuadro 5.5)
const FMG: Record<string, [string, number]> = { convencional: ["Labranza convencional", 1.0], reducida: ["Labranza reducida", 1.04], directa: ["Siembra directa", 1.10] };
const FI: Record<string, [string, number]> = { bajo: ["Bajo: rastrojo retirado o quemado, monocultivo", 0.92], medio: ["Medio: rastrojo queda en el lote", 1.0], alto: ["Alto: cultivos de servicio, rotación con gramíneas o pasturas", 1.11], estiercol: ["Alto con estiércol", 1.44] };

const TABS = [["margen", "Margen bruto"], ["calendario", "Calendario de siembra"], ["plagas", "Plagas y enfermedades"], ["carbono", "Carbono del suelo"]] as const;

export function Planificacion({ place, cultivo }: { place: Data; cultivo: string }) {
  const [tab, setTab] = useState("margen");
  const [zona, setZona] = useState(() => zonaDe(place.lat, place.lon, place.cc));
  useEffect(() => setZona(zonaDe(place.lat, place.lon, place.cc)), [place.lat, place.lon, place.cc]);
  const c = CULTIVOS[cultivo];
  return <section className="cult-sec cult-plan">
    <h3>Planificación y negocio</h3>
    <div className="cult-tabs no-print">{TABS.map(([id, t]) => <button key={id} className={tab === id ? "on" : ""} onClick={() => setTab(id)}>{t}</button>)}
      <label className="cult-zona">Zona <select value={zona} onChange={e => setZona(e.target.value)}>{Object.entries(ZONAS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label></div>
    {tab === "margen" && <Margen cultivo={cultivo} />}
    {tab === "calendario" && <Calendario cultivo={cultivo} zona={zona} />}
    {tab === "plagas" && <Plagas cultivo={cultivo} zona={zona} nombre={c.nombre} />}
    {tab === "carbono" && <Carbono place={place} />}
  </section>;
}

function Num({ label, v, set, step = 1, suf }: { label: string; v: number; set: (n: number) => void; step?: number; suf?: string }) {
  return <label>{label}<span className="cult-num"><input type="number" step={step} value={Number.isFinite(v) ? v : ""} onChange={e => set(parseFloat(e.target.value))} />{suf && <em>{suf}</em>}</span></label>;
}

function Margen({ cultivo }: { cultivo: string }) {
  const r = REF[cultivo];
  const [rinde, setRinde] = useState(r.rinde), [precio, setPrecio] = useState(r.precio), [costo, setCosto] = useState(r.costo);
  const [com, setCom] = useState(3), [flete, setFlete] = useState(20), [alq, setAlq] = useState(0), [ha, setHa] = useState(100);
  useEffect(() => { setRinde(r.rinde); setPrecio(r.precio); setCosto(r.costo); }, [cultivo]);
  const m = margen(rinde || 0, precio || 0, costo || 0, com || 0, flete || 0, alq || 0);
  const comp = Object.entries(REF).map(([k, x]) => ({ k, ...margen(x.rinde, x.precio, x.costo, com || 0, flete || 0, alq || 0) })).sort((a, b) => b.mbAlq - a.mbAlq);
  return <>
    <div className="cult-grid cult-grid4">
      <Num label="Rinde esperado" v={rinde} set={setRinde} step={0.1} suf="t/ha" /><Num label="Precio de venta" v={precio} set={setPrecio} suf="USD/t" />
      <Num label="Costo directo (insumos y labores)" v={costo} set={setCosto} suf="USD/ha" /><Num label="Alquiler" v={alq} set={setAlq} suf="USD/ha" />
      <Num label="Comercialización" v={com} set={setCom} step={0.5} suf="% del bruto" /><Num label="Flete a puerto o acopio" v={flete} set={setFlete} suf="USD/t" />
      <Num label="Superficie" v={ha} set={setHa} suf="ha" />
    </div>
    <div className="cult-kpis" style={{ marginTop: 12 }}>
      <div><span>Ingreso bruto</span><b>{nf(m.bruto)}</b><em>USD/ha</em></div>
      <div><span>Ingreso neto</span><b>{nf(m.neto)}</b><em>menos {nf(m.gastosCom)} de comercialización y flete</em></div>
      <div><span>Margen bruto</span><b className={m.mbAlq < 0 ? "neg" : ""}>{nf(m.mbAlq)}</b><em>USD/ha{alq ? " con alquiler" : ""} · {nf(m.mbAlq * (ha || 0))} USD en {nf(ha)} ha</em></div>
      <div><span>Rinde de indiferencia</span><b>{m.indif != null ? nf(m.indif, 2) : "—"}</b><em>t/ha para cubrir costos</em></div>
      <div><span>Retorno sobre costos</span><b>{m.ret != null ? `${nf(m.ret)} %` : "—"}</b><em>margen / (costo + alquiler)</em></div>
    </div>
    <h4 style={{ marginTop: 16 }}>Comparación entre cultivos con valores de referencia</h4>
    <div className="cult-table"><table><thead><tr><th>Cultivo</th><th>Rinde t/ha</th><th>Precio USD/t</th><th>Costo USD/ha</th><th>Margen USD/ha</th></tr></thead>
      <tbody>{comp.map(x => <tr key={x.k}><td>{CULTIVOS[x.k].nombre}</td><td>{nf(REF[x.k].rinde, 1)}</td><td>{nf(REF[x.k].precio)}</td><td>{nf(REF[x.k].costo)}</td><td><b className={x.mbAlq < 0 ? "cp-red" : ""}>{nf(x.mbAlq)}</b></td></tr>)}</tbody></table></div>
    <p className="cp-note">Los valores precargados son referencias de 2024 tomadas de AgroClima (presupuestos tipo de BCR y Aapresid): <b>no son precios de hoy</b>. Reemplazalos por tu rinde, tu pizarra y tus costos. No incluye estructura, impuestos ni gastos financieros.</p>
  </>;
}

function Calendario({ cultivo, zona }: { cultivo: string; zona: string }) {
  const v = VENT[cultivo];
  if (!v) return <p className="cp-note">No hay calendario de referencia para {CULTIVOS[cultivo].nombre.toLowerCase()}: consultá la agencia del INTA de tu zona.</p>;
  const hoy = Math.floor((Date.now() - Date.UTC(new Date().getUTCFullYear(), 0, 1)) / 864e5) + 1;
  const en = v.find(([, a, b]) => hoy >= a && hoy <= b), prox = v.find(([, a]) => a > hoy);
  return <>
    <div className="cult-cal">{v.map(([n, a, b, cos, tipo]) => <div key={n} className={en?.[0] === n ? "on" : ""}><span>Siembra {n.toLowerCase()}</span><b>{fecha(a)} al {fecha(b)}</b><em>Cosecha en {cos} · {tipo}</em></div>)}</div>
    <div className={`cult-alert ${en ? "ok" : "warn"}`} style={{ marginTop: 10 }}><b>{en ? `Según la referencia, hoy corresponde la siembra ${en[0].toLowerCase()}.` : prox ? `Fuera de ventana: la próxima (${prox[0].toLowerCase()}) abre el ${fecha(prox[1])}.` : "Fuera de las ventanas de referencia de este año."}</b>
      <p className="reco">Antes de sembrar, mirá la pestaña Siembra en Labores: temperatura y humedad del suelo de esta semana.</p></div>
    <p className="cp-note">Fechas de referencia de la Pampa húmeda (AgroClima).{zona !== "pampa_humeda" ? ` En ${ZONAS[zona]} las ventanas son otras: tomalo como orientación y consultá al INTA.` : ""}</p>
  </>;
}

function Plagas({ cultivo, zona, nombre }: { cultivo: string; zona: string; nombre: string }) {
  const lista = PLAGAS.filter(p => p.cult.includes(cultivo) && p.zonas.includes(zona));
  return <>
    {lista.length ? lista.map(p => <div key={p.n} className="cult-alert warn"><b>{p.n}</b><p>{p.dano} <i>Época: {p.temp}.</i></p><p className="reco">Manejo: {p.manejo}</p></div>)
      : <p>No hay plagas de esta lista asociadas a {nombre.toLowerCase()} en {ZONAS[zona]}. Igual conviene el monitoreo general.</p>}
    <p className="cp-note">Lista orientativa, corregida respecto de AgroClima. El manejo concreto depende del umbral de daño y del estado del cultivo: consultá al INTA, a SENASA y a tu asesor.</p>
  </>;
}

function Carbono({ place }: { place: Data }) {
  const [soc, setSoc] = useState<Data | null>(null), [err, setErr] = useState("");
  const [antes, setAntes] = useState("convencional"), [desp, setDesp] = useState("directa"), [inA, setInA] = useState("medio"), [inD, setInD] = useState("alto");
  const [ha, setHa] = useState(100), [precio, setPrecio] = useState<number>(NaN);
  useEffect(() => {
    setSoc(null); setErr("");
    fetch(`/api/fuentes/carbono-suelo?lat=${place.lat}&lon=${place.lon}`, { signal: AbortSignal.timeout(30000) }).then(r => r.json())
      .then(j => j?.data?.soc_t_ha != null ? setSoc(j.data) : setErr("SoilGrids no tiene dato para este punto.")).catch(() => setErr("SoilGrids no respondió."));
  }, [place.lat, place.lon]);
  const calc = useMemo(() => {
    if (!soc) return null;
    const f0 = FMG[antes][1] * FI[inA][1], f1 = FMG[desp][1] * FI[inD][1];
    const total = soc.soc_t_ha * (f1 / f0 - 1);               // t C/ha al nuevo equilibrio (20 años)
    const anual = total / 20, co2 = anual * 44 / 12;
    return { total, anual, co2, co2Tot: co2 * (ha || 0) };
  }, [soc, antes, desp, inA, inD, ha]);
  return <>
    {err && <p className="cult-err">{err}</p>}
    {!soc && !err && <p className="cp-note">Consultando el carbono del suelo en SoilGrids…</p>}
    {soc && <>
      <div className="cult-kpis"><div><span>Carbono del suelo hoy (0–30 cm)</span><b>{nf(soc.soc_t_ha, 1)} t C/ha</b><em>rango {nf(soc.soc_t_ha_range?.[0], 0)}–{nf(soc.soc_t_ha_range?.[1], 0)} · SoilGrids</em></div>
        <div><span>Equivale a</span><b>{nf(soc.soc_t_ha * 44 / 12)} t CO₂/ha</b><em>stock, no crédito</em></div></div>
      <div className="cult-grid cult-grid4" style={{ marginTop: 12 }}>
        <label>Manejo actual<select value={antes} onChange={e => setAntes(e.target.value)}>{Object.entries(FMG).map(([k, [t]]) => <option key={k} value={k}>{t}</option>)}</select></label>
        <label>Aporte de residuos actual<select value={inA} onChange={e => setInA(e.target.value)}>{Object.entries(FI).map(([k, [t]]) => <option key={k} value={k}>{t}</option>)}</select></label>
        <label>Manejo propuesto<select value={desp} onChange={e => setDesp(e.target.value)}>{Object.entries(FMG).map(([k, [t]]) => <option key={k} value={k}>{t}</option>)}</select></label>
        <label>Aporte de residuos propuesto<select value={inD} onChange={e => setInD(e.target.value)}>{Object.entries(FI).map(([k, [t]]) => <option key={k} value={k}>{t}</option>)}</select></label>
        <Num label="Superficie" v={ha} set={setHa} suf="ha" /><Num label="Precio del crédito (si tenés una oferta)" v={precio} set={setPrecio} suf="USD/t CO₂" />
      </div>
      {calc && <div className="cult-kpis" style={{ marginTop: 12 }}>
        <div><span>Cambio de carbono en 20 años</span><b className={calc.total < 0 ? "neg" : ""}>{calc.total >= 0 ? "+" : ""}{nf(calc.total, 1)} t C/ha</b><em>al nuevo equilibrio</em></div>
        <div><span>Por año</span><b className={calc.co2 < 0 ? "neg" : ""}>{nf(calc.co2, 2)} t CO₂/ha</b><em>{nf(calc.anual, 2)} t C/ha</em></div>
        <div><span>En {nf(ha)} ha, por año</span><b>{nf(calc.co2Tot, 0)} t CO₂</b><em>potencial antes de descuentos</em></div>
        <div><span>Ingreso bruto anual</span><b>{Number.isFinite(precio) ? `${nf(calc.co2Tot * precio)} USD` : "—"}</b><em>{Number.isFinite(precio) ? "antes de costos de certificación" : "cargá un precio para calcularlo"}</em></div>
      </div>}
      <p className="cp-note">Método de Nivel 1 del IPCC (Refinamiento 2019, tierras de cultivo, clima templado cálido húmedo): el carbono cambia en la proporción de los factores de manejo y de aporte de residuos, repartido en 20 años, sobre el stock actual de SoilGrids (modelo global a 250 m). Es una estimación de potencial: para vender créditos hace falta línea de base con muestreo de suelo, plan de monitoreo, verificación independiente y registro en un estándar, con costos que en lotes chicos pueden superar el ingreso. Los precios del mercado voluntario varían mucho: DOTS no supone ninguno.</p>
    </>}
  </>;
}
