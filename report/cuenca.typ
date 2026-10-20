// DOTS / Campo — Informe de la Cuenca del Plata (Typst)
// Datos ya formateados desde cuenca_report.py vía sys.inputs.data (JSON).
// Estructura fija: portada y resumen · El Niño · alertas · imágenes · lluvia por subcuenca · represas y ríos · traslado · fuentes.
#import "identity.typ": name, director, method, cover-id
#let d = json(bytes(sys.inputs.data))
// Identidad institucional compartida de los informes DOTS.
// La especialidad cambia, pero la denominación y la responsabilidad editorial no.


#let ink = rgb("#101828")
#let ink2 = rgb("#344054")
#let muted = rgb("#667085")
#let line-c = rgb("#e4e7ec")
#let soft = rgb("#f6f7f9")
#let brand = rgb("#0f9fa6")
#let brand-dark = rgb("#0b2b33")
#let brand-soft = rgb("#e6f6f7")
#let brand-light = rgb("#57dce0")
#let ok = rgb("#039855")
#let warn = rgb("#dc6803")
#let alert-c = rgb("#e8590c")
#let risk = rgb("#d92d20")
#let sea = rgb("#1f7ab8")
#let tone(t) = if t == "ok" { ok } else if t == "warn" { warn } else if t == "alert" { alert-c } else if t == "risk" { risk } else { muted }

#set document(title: d.title, author: name)
#set text(font: "IBM Plex Sans", size: 9.2pt, fill: ink, lang: "es")
#set par(leading: 0.6em, justify: false)
#set page(
  paper: "a4",
  margin: (top: 19mm, bottom: 17mm, x: 15mm),
  header: context {
    if counter(page).get().first() > 1 {
      set text(size: 7.5pt, fill: muted)
      grid(columns: (1fr, auto), [*DOTS* #text(fill: brand)[\/ CAMPO] · Cuenca del Plata], [#d.generated])
      v(-2pt)
      line(length: 100%, stroke: 0.5pt + line-c)
    }
  },
  footer: context {
    set text(size: 7.5pt, fill: muted)
    line(length: 100%, stroke: 0.5pt + line-c)
    v(-2pt)
    grid(columns: (1fr, auto),
      [Orientativo, con datos públicos. No reemplaza las alertas del INA, la Prefectura ni Defensa Civil.],
      [Página #counter(page).display() de #counter(page).final().first()])
  },
)

#let sec = counter("cuenca-section")
#let section(t, sub: none) = {
  sec.step()
  block(sticky: true, above: 15pt, below: 7pt, {
    grid(columns: (auto, 1fr), column-gutter: 8pt, align: horizon,
      box(fill: brand-soft, inset: (x: 6pt, y: 3pt), radius: 4pt, text(size: 8pt, weight: "bold", fill: brand, context { let n = sec.get().first(); if n < 10 { "0" + str(n) } else { str(n) } })),
      text(size: 13pt, weight: "semibold")[#t])
    if sub != none { v(-4pt); pad(left: 30pt, text(size: 7.5pt, fill: muted)[#sub]) }
  })
}
#let kicker(t, fill: brand) = text(size: 7pt, weight: "semibold", fill: fill, tracking: 0.12em, upper(t))
#let card(body, fill: white, stroke: 0.6pt + line-c, inset: 10pt) = block(fill: fill, stroke: stroke, radius: 8pt, inset: inset, width: 100%, breakable: false, body)
#let pill(t, c) = box(fill: c.transparentize(86%), inset: (x: 6pt, y: 2.5pt), radius: 8pt, text(size: 7pt, weight: "semibold", fill: c)[#t])
#let note(t) = text(size: 7.3pt, fill: muted)[#t]
#let thead(..cells) = cells.pos().map(c => text(size: 6.8pt, weight: "semibold", fill: muted, upper(c)))
#let table-style = (stroke: (x, y) => (bottom: if y == 0 { 0.6pt + ink2.transparentize(55%) } else { 0.4pt + line-c }), inset: (x: 5pt, y: 4.5pt))

// línea simple para series cortas (anomalías del Niño)
#let spark(vals, c, h: 16mm) = block(width: 100%, height: h, breakable: false, layout(size => {
  let vs = vals.filter(v => v != none)
  if vs.len() < 2 { return }
  let lo = calc.min(0.0, ..vs); let hi = calc.max(0.5, ..vs)
  let W = size.width; let n = vals.len()
  let y(v) = h - 3pt - (v - lo) / (hi - lo) * (h - 6pt)
  place(dx: 0pt, dy: y(0.5), line(length: W, stroke: (paint: muted.transparentize(50%), thickness: 0.4pt, dash: "dashed")))
  let pts = vals.enumerate().filter(p => p.at(1) != none).map(p => (p.at(0) / (n - 1) * W, y(p.at(1))))
  place(curve(stroke: 1.4pt + c, curve.move(pts.first()), ..pts.slice(1).map(p => curve.line(p))))
  let last = pts.last()
  place(dx: last.at(0) - 2pt, dy: last.at(1) - 2pt, circle(radius: 2pt, fill: c))
}))

// ───────────────────────────── 1. portada ─────────────────────────────
#cover-id()
#block(width: 100%, fill: brand-dark, radius: 10pt, inset: 16pt, {
  set text(fill: white)
  grid(columns: (1fr, auto), align: (left + horizon, right + horizon),
    [#text(size: 8pt, weight: "bold", tracking: 0.14em)[DOTS #text(fill: brand-light)[\/ CAMPO]] #h(6pt) #text(size: 7.5pt, fill: rgb("#a5c6cc"))[Inteligencia territorial · Cuenca del Plata]],
    text(size: 7.5pt, fill: rgb("#a5c6cc"))[#d.generated])
  v(8pt)
  text(size: 21pt, weight: "bold")[El Niño y las crecidas de la Cuenca del Plata]
  v(2pt)
  text(size: 9pt, fill: rgb("#cfe3e6"))[Lluvia en las cabeceras de Brasil, Paraguay y Bolivia, caudal de los ríos y cuándo llegaría el agua a cada localidad.]
})
#v(8pt)
#grid(columns: (auto, 1fr), column-gutter: 12pt, align: horizon,
  block(fill: tone(d.worst_tone).transparentize(88%), stroke: 1pt + tone(d.worst_tone), radius: 8pt, inset: (x: 14pt, y: 10pt), {
    kicker("Nivel más alto hoy", fill: tone(d.worst_tone)); linebreak()
    text(size: 20pt, weight: "bold", fill: tone(d.worst_tone))[#d.worst]
    linebreak(); text(size: 7.5pt, fill: ink2)[#d.active_count #if d.active_count == 1 [cuenca con aviso] else [cuencas con aviso]]
  }),
  block({
    kicker("En tres líneas")
    v(2pt)
    for l in d.summary [#text(size: 9.6pt)[#l] #v(1pt)]
  }))

// ───────────────────────────── 2. El Niño ─────────────────────────────
#if d.nino != none [
  #section("El Niño esta semana", sub: [NOAA CPC · semana del #d.nino.week · anomalía de temperatura del mar contra 1991–2020])
  #let sst = d.pictures.filter(p => p.key == "sst")
  #grid(columns: if sst.len() > 0 { (1.25fr, 1fr) } else { (1fr,) }, column-gutter: 10pt,
    ..if sst.len() > 0 { (block({
      let p = sst.first()
      block(radius: 6pt, clip: true, width: 100%, {
        if p.image != none { image(bytes(p.image), width: 100%) }
        if p.overlay != none { place(top + left, image(bytes(p.overlay), width: 100%)) }
      })
      v(2pt)
      grid(columns: (auto, 1fr, auto), column-gutter: 4pt, align: horizon,
        text(size: 6.5pt, fill: sea)[más frío], box(width: 100%, height: 5pt, radius: 2pt, fill: gradient.linear(sea, white, risk)), text(size: 6.5pt, fill: risk)[más cálido])
      note[#p.caption Imagen del #p.date.]
    }),) } else { () },
    block({
      table(columns: (1.4fr, auto, auto, 1fr), ..table-style, align: (left, right, right, left),
        ..thead("Región", "°C", "Anom.", "Fase"),
        ..d.nino.rows.map(r => (text(weight: "medium")[#r.name], r.sst, text(weight: "semibold")[#r.anom], text(size: 7.8pt)[#r.phase #if r.change != "—" [#linebreak()#text(fill: muted, size: 6.8pt)[#r.change en 4 sem.]]])).flatten())
      v(4pt)
      grid(columns: (1fr, 1fr), column-gutter: 8pt,
        [#text(size: 7pt, fill: muted)[Niño 3.4 · 13 semanas] #spark(d.nino.series34, brand)],
        [#text(size: 7pt, fill: muted)[Niño costero 1+2 · 13 semanas] #spark(d.nino.series12, risk)])
      note[Niño 3.4 es la referencia oficial; el costero (frente a Perú y Ecuador) suele anticipar más lluvia en el Litoral. Línea punteada: umbral de +0,5 °C. El estado oficial se declara con el ONI trimestral.]
    }))
]

// ───────────────────────────── 3. alertas ─────────────────────────────
#section("Alertas por lluvia en las cabeceras", sub: [Probabilidad de lluvia de 15 días (ECMWF + GFS), estado del río de salida y represas. Ventanas orientativas.])
#if d.alerts.len() == 0 [
  #card(fill: ok.transparentize(90%), stroke: none)[#text(fill: ok, weight: "semibold")[Sin alertas:] el pronóstico no muestra lluvias fuera de lo común en las cabeceras para los próximos 15 días.]
] else [
  #for a in d.alerts [
    #block(breakable: false, below: 7pt, stroke: (left: 3pt + tone(a.tone), rest: 0.6pt + line-c), radius: 6pt, inset: 10pt, width: 100%, {
      grid(columns: (1fr, auto), align: horizon,
        [#text(size: 11.5pt, weight: "bold")[#a.name] #h(4pt) #text(size: 7.5pt, fill: muted)[#a.where]], pill(a.level, tone(a.tone)))
      v(2pt)
      text(weight: "semibold")[#a.rain]
      if a.prediction != "" {
        v(3pt)
        block(fill: rgb("#f3f8fb"), radius: 5pt, inset: 7pt, width: 100%, {
          kicker("Cálculo lluvia → crecida", fill: sea); linebreak()
          text(weight: "semibold", size: 9pt)[#a.prediction]; linebreak()
          text(size: 7.3pt, fill: muted)[#a.basis]
        })
      }
      v(3pt)
      grid(columns: (1.3fr, 1fr), column-gutter: 14pt,
        [#kicker("Por qué", fill: muted) #v(1pt) #set text(size: 8pt); #for w in a.why [• #w #linebreak()]],
        [#kicker("Cuándo llegaría", fill: muted) #v(1pt)
          #set text(size: 8pt)
          #if a.arrivals.len() == 0 [—] else { table(columns: (1fr, auto), stroke: none, inset: (x: 0pt, y: 2pt), ..a.arrivals.map(x => (x.place, text(weight: "semibold", fill: alert-c)[#x.window])).flatten()) }])
    })
  ]
  #if d.calm.len() > 0 [#note[Sin alerta: #d.calm.join(" · ").]]
]

// ───────────────────────────── 3 bis. temporales, frentes y sudestada ─────────────────────────────
#if d.at("weather", default: none) != none [
  #section("Temporales, frentes y sudestada", sub: [Próximos 5 días en las #d.weather.total localidades · pronóstico horario de Open-Meteo con reglas declaradas])
  #if d.weather.sud != none [
    #block(breakable: false, below: 7pt, stroke: (left: 3pt + tone(d.weather.sud.tone), rest: 0.6pt + line-c), radius: 6pt, inset: 9pt, width: 100%)[
      #pill(d.weather.sud.level, tone(d.weather.sud.tone)) #h(4pt) *Sudestada en el Río de la Plata* #if d.weather.sud.when != "" [· #d.weather.sud.when] #linebreak()
      #text(size: 8.5pt)[#d.weather.sud.text]]
  ]
  #if d.weather.rows.len() == 0 [
    #card(fill: ok.transparentize(90%), stroke: none)[#text(fill: ok, weight: "semibold")[Sin avisos:] no se esperan caídas bruscas de presión, frentes fríos, ráfagas fuertes ni calor extremo en las localidades del sistema.]
  ] else [
    #set text(size: 8pt)
    #table(columns: (1.2fr, auto, 2.6fr, auto), stroke: (x, y) => (bottom: if y == 0 { 0.6pt + ink2.transparentize(55%) } else { 0.4pt + line-c }), inset: (x: 5pt, y: 4pt), align: (left, left, left, right),
      [*Localidad*], [*Nivel*], [*Qué se espera*], [*Presión mín.*],
      ..d.weather.rows.map(r => ([*#r.place* #text(fill: muted, size: 7pt)[río #r.river]], pill(r.level, tone(r.tone)), r.events, [#r.pmin hPa])).flatten())
  ]
  #note[Caída de presión de 3 hPa en 3 h (5, alerta) o de 14 hPa en 24 h (ciclogénesis); frente frío si la máxima baja 8 °C de un día al otro (12, alerta); ráfagas desde 60 km/h (80, alerta); calor extremo con 3 días de máximas de 35 °C y mínimas de 22 °C; sudestada con 12 h seguidas de viento del este al sur de 30 km/h en el centro del Río de la Plata (45, alerta). Orientativo: los avisos oficiales son del SMN y la altura del agua en el estuario la pronostica el Servicio de Hidrografía Naval.]
]

// ───────────────────────────── 4. imágenes ─────────────────────────────
#let others = d.pictures.filter(p => p.key != "sst")
#if others.len() > 0 [
  #section("Imágenes de la zona", sub: [NASA GIBS · imágenes del día anterior; las nubes pueden tapar el suelo])
  #grid(columns: others.map(_ => 1fr), column-gutter: 10pt,
    ..others.map(p => block(breakable: false, {
      text(weight: "semibold", size: 9pt)[#p.title] ; linebreak(); text(size: 7pt, fill: muted)[#p.date]
      v(2pt)
      block(radius: 6pt, clip: true, width: 100%, {
        if p.base != none { image(bytes(p.base), width: 100%) }
        if p.image != none { if p.base != none { place(top + left, image(bytes(p.image), width: 100%)) } else { image(bytes(p.image), width: 100%) } }
        if p.overlay != none { place(top + left, image(bytes(p.overlay), width: 100%)) }
      })
      v(2pt)
      note[#p.caption]
    })))
]

// ───────────────────────────── 5. lluvia por subcuenca ─────────────────────────────
#if d.groups.len() > 0 [
  #section("Lluvia esperada en las subcuencas · 15 días", sub: [#d.models · mediana, rango p10–p90, veces la normal de la época y probabilidad de superar 100 mm])
  #table(columns: (1.5fr, 2fr, auto, auto, auto, auto, auto), ..table-style, align: (left, left, right, right, right, right, left),
    ..thead("Subcuenca", "Dónde", "mm", "Rango", "vs normal", "≥100 mm", "Nivel"),
    ..d.groups.map(g => (table.cell(colspan: 7, fill: soft, text(size: 7.5pt, weight: "bold", fill: brand-dark)[#upper(g.name)]),
      ..g.rows.map(r => (text(weight: "medium")[#r.name], text(size: 7.5pt, fill: ink2)[#r.where], text(weight: "semibold")[#r.mm], r.range, r.normal, r.p100, pill(r.level, tone(r.tone)))).flatten())).flatten())
]

// ───────────────────────────── 6. represas y ríos ─────────────────────────────
#if d.dams.len() > 0 [
  #section("Represas de Brasil · agua medida", sub: [ONS (Operador Nacional do Sistema Elétrico) · m³/s · defluente: lo que la represa suelta río abajo])
  #table(columns: (1.4fr, 1fr, auto, auto, auto, auto, 1fr, auto), ..table-style, align: (left, left, right, right, right, right, left, right),
    ..thead("Represa", "Río", "Suelta", "Entra", "7 días", "vs normal", "Estado", "Dato"),
    ..d.dams.map(x => (text(weight: "medium")[#x.name], x.river, text(weight: "semibold")[#x.out], x.in, x.change, x.ratio, x.level, x.date)).flatten())
]
#if d.rivers.len() > 0 [
  #section("Cifras de referencia por localidad", sub: [Altura del río (INA, escalas de Prefectura) contra los niveles oficiales · pronóstico INA del #d.ina_issued · caudal GloFAS contra lo normal])
  #{
    set text(size: 7.8pt)
    table(columns: (1.5fr, auto, auto, auto, auto, auto, auto, 1.2fr, 1.1fr, auto), ..table-style,
      align: (left, right, right, right, right, right, right, left, right, left),
      ..thead("Localidad", "Hoy", "7 días", "Bajas", "Alerta / evac.", "Falta", "INA prono", "Récord 20 años", "Caudal · normal", "Nivel"),
      ..d.rivers.map(g => (table.cell(colspan: 10, fill: soft, text(size: 7.3pt, weight: "bold", fill: brand-dark)[RÍO #upper(g.name)]),
        ..g.rows.map(r => (text(weight: "medium")[#r.place], [#text(weight: "bold")[#r.h] #if r.h_date != "" [#text(size: 6.2pt, fill: muted)[#r.h_date]]],
          r.d7, r.low, [#r.alert / #r.evac], if r.to_alert == "superado" { text(fill: risk, weight: "bold")[superado] } else { r.to_alert },
          r.fc, text(size: 7pt)[#r.record], r.q, if r.level == "—" [—] else { pill(r.level, tone(r.tone)) })).flatten())).flatten())
  }
  #note[Alturas en metros sobre el cero de cada escala (no son comparables entre puertos); "7 días": cuánto subió o bajó en la semana; "Falta": metros hasta el nivel de alerta y, si el río sube, días estimados para llegar a ese ritmo. Alerta y evacuación son los niveles oficiales que publica el INA para las escalas de la Prefectura. "Atención": a menos de 1 m del nivel de alerta (2 m en el Iguazú y el Uruguay). Donde no hay escala, el nivel sale del caudal (crecidas de 2, 5 y 20 años). Caudal en m³/s y veces lo normal para la fecha.]
]

// ───────────────────────────── 7. traslado y acciones ─────────────────────────────
#if d.travel.len() > 0 [
  #section("¿Cuánto tarda en llegar el agua?", sub: [Desfase estadístico entre estaciones (20 años de GloFAS) y llegada estimada del pico de cabecera pronosticado])
  #grid(columns: d.travel.map(_ => 1fr), column-gutter: 10pt,
    ..d.travel.map(ch => card(inset: 8pt, {
      text(weight: "semibold")[#ch.name]
      v(2pt)
      table(columns: (1fr, auto, auto), stroke: (x, y) => (top: if y > 0 { 0.4pt + line-c } else { none }), inset: (x: 2pt, y: 3.5pt),
        ..ch.rows.map(r => (r.place, text(fill: muted, size: 7.5pt)[#r.days], text(weight: "semibold", fill: alert-c)[#r.arrival])).flatten())
    })))
  #note[La onda se atenúa al bajar y se suma con otros ríos: la fecha es orientativa.]
]
#section("Qué hacer según el nivel", sub: [Orientativo para el campo · los niveles oficiales de alerta y evacuación los fijan Prefectura e INA])
#grid(columns: (1fr, 1fr, 1fr, 1fr), column-gutter: 8pt,
  ..("Normal", "Atención", "Alerta", "Peligro").map(l => {
    let t = if l == "Normal" { "ok" } else if l == "Atención" { "warn" } else if l == "Alerta" { "alert" } else { "risk" }
    block(stroke: (top: 3pt + tone(t), rest: 0.6pt + line-c), radius: 6pt, inset: 8pt, width: 100%, breakable: false, {
      text(weight: "bold", fill: tone(t))[#l]
      if d.worst == l [ #h(3pt) #text(size: 6.5pt, weight: "bold")[HOY] ]
      v(2pt)
      set text(size: 7.8pt)
      for a in d.actions.at(l, default: ()) [• #a #linebreak()]
    })
  }))

// ───────────────────────────── 8. fuentes ─────────────────────────────
#section("Fuentes oficiales por país y alcances")
#table(columns: (auto, 1fr), ..table-style, ..d.official.map(r => (text(weight: "semibold")[#r.at(0)], text(size: 8pt)[#r.at(1)])).flatten())
#v(4pt)
#note[*Datos de este informe:* #d.sources Las ventanas de llegada combinan la respuesta típica de cada cuenca con el desfase estadístico entre estaciones; los caudales GloFAS son simulados y se comparan con su propia serie. Ningún faltante se reemplaza por valores supuestos.#if d.errors.len() > 0 [ Sin respuesta en esta edición: #d.errors.keys().join(", ").]]
