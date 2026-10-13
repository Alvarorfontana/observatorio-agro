// DOTS / Campo — Informe de alerta de crecidas de una localidad (Typst)
// Datos desde cuenca_report.local_data vía sys.inputs.data.
#let d = json(bytes(sys.inputs.data))

#let ink = rgb("#101828")
#let ink2 = rgb("#344054")
#let muted = rgb("#667085")
#let line-c = rgb("#e4e7ec")
#let soft = rgb("#f6f7f9")
#let brand = rgb("#0f9fa6")
#let brand-dark = rgb("#0b2b33")
#let obs-c = rgb("#1f5f99")
#let fc-c = rgb("#7a5af8")
#let ok = rgb("#039855")
#let warn = rgb("#dc6803")
#let alert-c = rgb("#e8590c")
#let risk = rgb("#d92d20")
#let tone(t) = if t == "ok" { ok } else if t == "warn" { warn } else if t == "alert" { alert-c } else if t == "risk" { risk } else { muted }
#let fmt(v, digits: 2) = {
  let r = calc.round(v, digits: digits)
  let s = str(r)
  if not s.contains(".") and digits > 0 { s = s + "." + "0" * digits }
  let parts = s.split(".")
  if parts.len() == 2 and parts.at(1).len() < digits { s = s + "0" * (digits - parts.at(1).len()) }
  s.replace(".", ",")
}

#set document(title: d.title, author: "DOTS / Campo")
#set text(font: "IBM Plex Sans", size: 9.6pt, fill: ink, lang: "es")
#set par(leading: 0.6em)
#set page(paper: "a4", margin: (top: 14mm, bottom: 16mm, x: 15mm),
  footer: context {
    set text(size: 7.3pt, fill: muted)
    line(length: 100%, stroke: 0.5pt + line-c)
    v(-2pt)
    grid(columns: (1fr, auto), [Datos públicos (INA, escalas de Prefectura; ECMWF y GFS; Copernicus). Orientativo: ante una evacuación manda Defensa Civil.], [#d.url · pág. #counter(page).display()])
  })

#let kicker(t, fill: brand) = text(size: 7pt, weight: "semibold", fill: fill, tracking: 0.12em, upper(t))
#let card(body, fill: white, stroke: 0.6pt + line-c, inset: 10pt) = block(fill: fill, stroke: stroke, radius: 8pt, inset: inset, width: 100%, breakable: false, body)
#let pill(t, c) = box(fill: c.transparentize(86%), inset: (x: 6pt, y: 2.5pt), radius: 8pt, text(size: 7.2pt, weight: "semibold", fill: c)[#t])
#let sec(t) = block(above: 13pt, below: 6pt, sticky: true, text(size: 12pt, weight: "semibold")[#t])
#let hd(..xs) = xs.pos().map(t => text(size: 6.8pt, weight: "semibold", fill: muted, upper(t)))
#let note(t) = text(size: 7.2pt, fill: muted)[#t]

// ───────────── banda de nivel ─────────────
#let c = tone(d.tone)
#block(width: 100%, fill: c, radius: 10pt, inset: (x: 16pt, y: 13pt), {
  set text(fill: white)
  grid(columns: (1fr, auto), align: (left + horizon, right + horizon),
    [#text(size: 7.6pt, weight: "bold", tracking: 0.14em)[DOTS · SISTEMA DE ALERTA DE CRECIDAS] #linebreak()
     #text(size: 24pt, weight: "bold")[#d.place] #h(4pt) #text(size: 10pt)[río #d.river]],
    [#text(size: 8pt)[NIVEL HOY] #linebreak() #text(size: 22pt, weight: "bold")[#upper(d.level)]])
})
#v(4pt)
#text(size: 8pt, fill: muted)[Informe del #d.generated #if d.gauge != "" [· #d.gauge]]

#if d.summary.len() > 0 [
  #v(6pt)
  #block(width: 100%, fill: soft, radius: 8pt, inset: (x: 12pt, y: 10pt), breakable: false)[
    #kicker("Resumen de la situación") #v(2pt)
    #set par(leading: 0.62em)
    #for l in d.summary [#text(size: 9.4pt)[#l] #parbreak()]
  ]
]

// ───────────── cifras ─────────────
#if d.has_h [
  #v(6pt)
  #grid(columns: (1fr, 1fr, 1fr, 1fr), column-gutter: 7pt,
    card(fill: soft, stroke: none)[#text(size: 7.6pt, fill: muted)[Altura hoy (#d.date)] #linebreak() #text(size: 19pt, weight: "bold")[#d.h_txt]],
    card(fill: soft, stroke: none)[#text(size: 7.6pt, fill: muted)[Falta para la alerta] #linebreak() #text(size: 19pt, weight: "bold", fill: if d.to_alert == "superado" { risk } else { ink })[#d.to_alert]],
    card(fill: soft, stroke: none)[#text(size: 7.6pt, fill: muted)[Nivel de alerta] #linebreak() #text(size: 19pt, weight: "bold", fill: alert-c)[#d.alert_txt]],
    card(fill: soft, stroke: none)[#text(size: 7.6pt, fill: muted)[Nivel de evacuación] #linebreak() #text(size: 19pt, weight: "bold", fill: risk)[#d.evac_txt]])

  // regla: aguas bajas · hoy · alerta · evacuación
  #if d.alert != none {
    let lo = calc.min(if d.low != none { d.low } else { d.h }, d.h) - 0.5
    let ev = if d.evac != none { d.evac } else { d.alert }
    let hi = calc.max(ev + 1, d.h + 0.5)
    block(width: 100%, height: 30pt, above: 12pt, layout(size => {
      let W = size.width
      let x(v) = (v - lo) / (hi - lo) * W
      let att = if d.river == "Iguazú" or d.river == "Uruguay" { 2 } else { 1 }
      place(dy: 10pt, box(width: W, height: 9pt, radius: 4.5pt, clip: true, fill: rgb("#eef2ef"), stack(dir: ltr,
        rect(width: calc.max(0pt, x(d.alert - att)), height: 9pt, fill: rgb("#bfe9d8")),
        rect(width: calc.max(0pt, x(d.alert) - x(d.alert - att)), height: 9pt, fill: rgb("#ffe1a8")),
        rect(width: calc.max(0pt, x(ev) - x(d.alert)), height: 9pt, fill: rgb("#ffc4a3")),
        rect(width: calc.max(0pt, W - x(ev)), height: 9pt, fill: rgb("#f7a7a0")))))
      place(dx: x(d.h) - 1.5pt, dy: 5pt, rect(width: 3pt, height: 19pt, fill: ink, radius: 1pt))
      place(dx: x(d.h) - 20pt, dy: -4pt, box(width: 40pt, align(center, text(size: 7.5pt, weight: "bold")[#d.h_txt])))
      if d.low != none { place(dx: x(d.low) - 30pt, dy: 22pt, box(width: 60pt, align(center, text(size: 6.5pt, fill: muted)[bajas #fmt(d.low)]))) }
      place(dx: x(d.alert) - 30pt, dy: 22pt, box(width: 60pt, align(center, text(size: 6.5pt, fill: alert-c)[alerta #fmt(d.alert)])))
      if d.evac != none { place(dx: x(d.evac) - 30pt, dy: 22pt, box(width: 60pt, align(center, text(size: 6.5pt, fill: risk)[evacuación #fmt(d.evac)]))) }
    }))
  }

  // gráfico: alturas medidas, pronóstico INA y líneas oficiales
  #if d.series.len() > 1 {
    let H = 58mm
    let obs = d.series
    let fc = d.forecast
    let n = obs.len() + fc.len()
    let vals = obs.map(o => o.v) + fc.map(f => f.lo) + fc.map(f => f.hi) + (d.alert, d.evac).filter(v => v != none)
    let lo = calc.floor(calc.min(..vals) - 0.3)
    let hi = calc.ceil(calc.max(..vals) + 0.3)
    v(8pt)
    block(width: 100%, height: H + 14pt, breakable: false, layout(size => {
      let g = 26pt
      let W = size.width - g
      let x(i) = g + i / calc.max(n - 1, 1) * W
      let y(v) = H - (v - lo) / (hi - lo) * H
      for k in range(5) {
        let vv = lo + k * (hi - lo) / 4
        place(dx: g, dy: y(vv), line(length: W, stroke: 0.4pt + line-c))
        place(dx: 0pt, dy: y(vv) - 4pt, box(width: g - 4pt, align(right, text(size: 6.5pt, fill: muted)[#fmt(vv, digits: 1)])))
      }
      if d.evac != none {
        place(dx: g, dy: y(d.evac), line(length: W, stroke: 1.2pt + risk))
        place(dx: g + W - 80pt, dy: y(d.evac) - 9pt, box(width: 80pt, align(right, text(size: 6.8pt, fill: risk, weight: "semibold")[evacuación #fmt(d.evac) m])))
      }
      if d.alert != none {
        place(dx: g, dy: y(d.alert), line(length: W, stroke: (paint: alert-c, thickness: 1.2pt, dash: "dashed")))
        place(dx: g + W - 80pt, dy: y(d.alert) - 9pt, box(width: 80pt, align(right, text(size: 6.8pt, fill: alert-c, weight: "semibold")[alerta #fmt(d.alert) m])))
      }
      let li = obs.len() - 1
      if fc.len() > 0 {
        let band = (((x(li), y(obs.last().v)),) + fc.enumerate().map(((k, f)) => (x(li + 1 + k), y(f.hi))) + fc.enumerate().rev().map(((k, f)) => (x(li + 1 + k), y(f.lo))))
        place(curve(fill: fc-c.transparentize(85%), stroke: none, curve.move(band.first()), ..band.slice(1).map(p => curve.line(p)), curve.close()))
        let fl = ((x(li), y(obs.last().v)),) + fc.enumerate().map(((k, f)) => (x(li + 1 + k), y(f.c)))
        place(curve(stroke: (paint: fc-c, thickness: 1.4pt, dash: "dashed"), curve.move(fl.first()), ..fl.slice(1).map(p => curve.line(p))))
        for (k, f) in fc.enumerate() { place(dx: x(li + 1 + k) - 2.5pt, dy: y(f.c) - 2.5pt, circle(radius: 2.5pt, fill: fc-c)) }
      }
      let pts = obs.enumerate().map(((k, o)) => (x(k), y(o.v)))
      place(curve(stroke: 2pt + obs-c, curve.move(pts.first()), ..pts.slice(1).map(p => curve.line(p))))
      for p in pts { place(dx: p.at(0) - 1.8pt, dy: p.at(1) - 1.8pt, circle(radius: 1.8pt, fill: obs-c)) }
      let labels = obs.map(o => o.d) + fc.map(f => f.d)
      for (k, lab) in labels.enumerate() {
        if k == 0 or k == li or k > li { place(dx: x(k) - 15pt, dy: H + 3pt, box(width: 30pt, align(center, text(size: 6.5pt, fill: muted)[#lab]))) }
      }
    }))
    text(size: 7.2pt, fill: muted)[#box(width: 12pt, height: 2pt, fill: obs-c) altura medida (INA) #h(8pt) #box(width: 12pt, height: 2pt, fill: fc-c) pronóstico INA #if d.fc_issued != "—" [del #d.fc_issued] y rango #h(8pt) #box(width: 12pt, height: 2pt, fill: alert-c) alerta #h(8pt) #box(width: 12pt, height: 2pt, fill: risk) evacuación]
  }

  #v(6pt)
  #grid(columns: (1fr, 1fr), column-gutter: 10pt,
    card[#kicker("Tendencia", fill: muted) #linebreak() #text(weight: "semibold", size: 11pt)[#d.trend] #linebreak() #text(size: 8.2pt, fill: ink2)[#d.days_alert #d.days_evac]],
    card[#kicker("Pronóstico oficial del INA", fill: muted) #linebreak() #if d.fc_txt != "" [#text(weight: "semibold", size: 11pt)[#d.fc_txt]] else [#text(size: 8.5pt, fill: muted)[El INA no publica pronóstico para este puerto.]]])
  #if d.fc_rows.len() > 1 [
    #v(6pt)
    #table(columns: (auto, auto, 1fr, auto), stroke: (x, y) => (bottom: if y == 0 { 0.6pt + ink2.transparentize(55%) } else { 0.4pt + line-c }), inset: (x: 5pt, y: 4.5pt), align: (left, right, left, left),
      ..hd("Fecha", "Altura central", "Rango", "Nivel"),
      ..d.fc_rows.map(f => (f.d, text(weight: "semibold")[#f.c], text(size: 8pt)[#f.r], if f.lv == "—" [—] else { pill(f.lv, tone(if f.lv == "Normal" { "ok" } else if f.lv == "Atención" { "warn" } else if f.lv == "Alerta" { "alert" } else { "risk" })) })).flatten())
    #note[Pronóstico oficial del INA (Paraná, Corrientes a Rosario) emitido el #d.fc_issued. Variación de la última semana: #d.change7 · altura en % del nivel de alerta: #d.pct_alert.]
  ]
] else [
  #v(8pt)
  #card(fill: soft, stroke: none)[Esta localidad no tiene escala del INA. #if d.discharge != "" [Caudal estimado (GloFAS): *#d.discharge*.]]
]

// ───────────── lo que viene ─────────────
#if d.arrivals.len() > 0 [
  #sec("Crecida en camino por lluvia en las cabeceras")
  #for a in d.arrivals [
    #block(below: 5pt, stroke: (left: 3pt + tone(a.tone), rest: 0.6pt + line-c), radius: 6pt, inset: 8pt, width: 100%, breakable: false)[
      #pill(a.level, tone(a.tone)) #h(4pt) *Lluvia en #a.basin* (#a.mm mm en 15 días): repunte esperado entre el *#a.window*.
      #if a.prediction != "" [#linebreak() #text(size: 8.3pt, fill: ink2)[#a.prediction]]
    ]
  ]
]
// ───────────── qué hacer ─────────────
#v(8pt)
#grid(columns: (1.35fr, 1fr), column-gutter: 10pt,
  block(stroke: (top: 3pt + c, rest: 0.6pt + line-c), radius: 6pt, inset: 10pt, width: 100%, breakable: false)[
    #text(weight: "bold", fill: c)[Qué hacer ahora · #d.level] #v(2pt)
    #set text(size: 9pt)
    #for t in d.actions [• #t #linebreak()]
  ],
  block(fill: risk.transparentize(92%), radius: 6pt, inset: 10pt, width: 100%, breakable: false)[
    #text(weight: "bold")[Teléfonos de emergencia · #d.country] #v(3pt)
    #for p in d.phones [#text(size: 13pt, weight: "bold", fill: risk)[#p.at(0)] #h(3pt) #text(size: 8.5pt)[#p.at(1)] #linebreak()]
  ])

#if d.basins.len() > 0 [
  #sec("De dónde viene el agua: lluvia en las cabeceras")
  #table(columns: (1.5fr, 1.7fr, auto, auto, auto, auto, 1fr), stroke: (x, y) => (bottom: if y == 0 { 0.6pt + ink2.transparentize(55%) } else { 0.4pt + line-c }), inset: (x: 5pt, y: 4.5pt),
    align: (left, left, right, right, right, right, left),
    ..hd("Cuenca", "Dónde llueve", "15 días", "Rango", "vs normal", "≥100 mm", "Llega acá en"),
    ..d.basins.map(b => (
      [#text(weight: "medium")[#b.name] #linebreak() #if b.level != "—" { pill(b.level, tone(b.tone)) }],
      text(size: 7.6pt, fill: ink2)[#b.where #if b.heavy != "" [#linebreak() lluvia fuerte #b.heavy]],
      [#b.mm mm], text(size: 8pt)[#b.range], b.ratio, b.p100,
      text(size: 8pt)[#b.travel #if b.window != "" [#linebreak() #text(fill: ink, weight: "semibold")[#b.window]]])).flatten())
  #note[Pronóstico por conjunto ECMWF (51 corridas) y GFS (31) para los próximos 15 días, promediado sobre puntos de cada cabecera. "vs normal": veces la lluvia normal de esos 15 días (NASA POWER). Los tiempos suman la respuesta de la cuenca y el desfase medio entre puertos (#d.lags_period).]
]

#if d.dams.len() > 0 [
  #sec("Represas río arriba")
  #table(columns: (1.2fr, auto, auto, auto, auto, auto, 1.6fr), stroke: (x, y) => (bottom: if y == 0 { 0.6pt + ink2.transparentize(55%) } else { 0.4pt + line-c }), inset: (x: 5pt, y: 4.5pt),
    align: (left, right, right, right, right, left, left),
    ..hd("Represa", "Suelta", "Entra", "7 días", "vs normal", "Nivel", "Llega acá"),
    ..d.dams.map(x => ([#text(weight: "medium")[#x.name] #linebreak() #text(size: 7pt, fill: muted)[río #x.river · #x.date]],
      [#x.out], [#x.in], x.change, x.ratio, text(size: 8pt)[#x.level], text(size: 7.6pt, fill: ink2)[#x.days #linebreak() #x.note])).flatten())
  #note[Caudales medidos por el ONS (Brasil), en m³/s. Lo que una represa suelta de más suele anticipar la subida río abajo.]
]

#if d.upstream.len() > 0 [
  #sec("Río arriba")
  #table(columns: (1.6fr, auto, auto, auto, 1.2fr, auto, auto), stroke: (x, y) => (bottom: if y == 0 { 0.6pt + ink2.transparentize(55%) } else { 0.4pt + line-c }), inset: (x: 5pt, y: 4.5pt),
    align: (left, right, right, left, left, right, right),
    ..hd("Localidad", "Altura", "% alerta", "Nivel", "Tendencia", "Caudal", "Llega acá"),
    ..d.upstream.map(u => ([#text(weight: "medium")[#u.place] #text(size: 7pt, fill: muted)[#u.river]], u.h, text(size: 8pt)[#u.pct],
      if u.level == "—" [—] else { pill(u.level, tone(u.tone)) }, text(size: 8pt)[#u.trend], text(size: 8pt)[#u.q], text(size: 8pt)[#u.days])).flatten())
  #note[Lo que pasa río arriba llega acá en esos días (desfase medio #d.lags_period; orientativo). "Caudal": veces lo normal para la fecha (GloFAS).]
]

#if d.downstream.len() > 0 [
  #sec("Río abajo: a quién le llega después")
  #table(columns: (1.6fr, auto, auto, auto, 1.2fr, auto), stroke: (x, y) => (bottom: if y == 0 { 0.6pt + ink2.transparentize(55%) } else { 0.4pt + line-c }), inset: (x: 5pt, y: 4.5pt),
    align: (left, right, right, left, left, right),
    ..hd("Localidad", "Altura", "% alerta", "Nivel", "Tendencia", "Desde acá"),
    ..d.downstream.map(u => ([#text(weight: "medium")[#u.place] #text(size: 7pt, fill: muted)[#u.river]], u.h, text(size: 8pt)[#u.pct],
      if u.level == "—" [—] else { pill(u.level, tone(u.tone)) }, text(size: 8pt)[#u.trend], text(size: 8pt)[#u.days])).flatten())
]

#if d.flow != none [
  #sec("Caudal contra la historia")
  #grid(columns: (1fr, 1fr, 1fr, 1fr), column-gutter: 7pt,
    card(fill: soft, stroke: none)[#text(size: 7.4pt, fill: muted)[Caudal hoy (m³/s)] #linebreak() #text(size: 15pt, weight: "bold")[#d.flow.now] #linebreak() #text(size: 7.4pt, fill: ink2)[7 días: #d.flow.change]],
    card(fill: soft, stroke: none)[#text(size: 7.4pt, fill: muted)[Normal para la fecha] #linebreak() #text(size: 15pt, weight: "bold")[#d.flow.normal] #linebreak() #text(size: 7.4pt, fill: ink2)[hoy: #d.flow.ratio]],
    card(fill: soft, stroke: none)[#text(size: 7.4pt, fill: muted)[Posición histórica] #linebreak() #text(size: 15pt, weight: "bold")[#d.flow.level] #linebreak() #text(size: 7.4pt, fill: ink2)[#d.flow.pct (2001-2020)]],
    card(fill: soft, stroke: none)[#text(size: 7.4pt, fill: muted)[Pico en 30 días] #linebreak() #text(size: 10.5pt, weight: "bold")[#d.flow.peak]])
  #v(4pt)
  #note[Crecidas de referencia (Gumbel, 20 años): cada 2 años #d.flow.q2 m³/s · cada 5 años #d.flow.q5 · cada 20 años #d.flow.q20. Máximo de la serie: #d.flow.max. Caudal simulado por Copernicus GloFAS (grilla ~5 km): sirve para comparar contra su propia historia, no reemplaza la altura oficial.]
]

#if d.nino != none [
  #sec("Contexto climático: El Niño")
  #grid(columns: (1fr, 2.2fr), column-gutter: 12pt,
    card(fill: soft, stroke: none)[#text(size: 7.4pt, fill: muted)[Semana del #d.nino.week] #linebreak() #text(size: 13pt, weight: "bold")[#d.nino.phase] #linebreak() #text(size: 7.6pt, fill: ink2)[Niño 3.4: #d.nino.n34 °C · costero: #d.nino.n12 °C]],
    align(horizon, text(size: 8.8pt)[#d.nino.effect #linebreak() #note[Anomalía semanal NOAA CPC (OISST) contra 1991-2020. El estado oficial se declara con el ONI trimestral.]]))
]

#if d.picture != none [
  #sec("Imagen satelital de la zona · " + d.picture.date)
  #block(width: 100%, radius: 6pt, clip: true, breakable: false, image(bytes(d.picture.image), width: 100%))
  #note[#d.picture.caption]
]

#if d.record != "" or d.discharge != "" [
  #v(6pt)
  #text(size: 7.6pt, fill: muted)[#if d.record != "" [Récord de altura de los últimos 20 años: #d.record. ] #if d.discharge != "" [Caudal estimado hoy: #d.discharge.] Las alturas se miden sobre el cero de cada escala: no son comparables entre puertos.]
]

#sec("Fuentes y alcances")
#set text(size: 7.8pt, fill: ink2)
#table(columns: (auto, 1fr), stroke: (x, y) => (bottom: 0.4pt + line-c), inset: (x: 5pt, y: 3.5pt),
  [*Altura y niveles*], [INA · Sistema de Alerta (alerta.ina.gob.ar), escalas de Prefectura Naval; niveles de alerta y evacuación oficiales.],
  [*Pronóstico de altura*], [INA · pronóstico tabprono del río Paraná (Corrientes a Rosario).],
  [*Lluvia en cabeceras*], [ECMWF IFS y NOAA GFS por conjunto, vía Open-Meteo; normales de NASA POWER.],
  [*Caudal*], [Copernicus GloFAS vía Open-Meteo; normales y crecidas de retorno calculadas sobre 2001-2020.],
  [*Represas*], [ONS Brasil, datos abiertos (CC-BY 4.0).],
  [*El Niño e imagen*], [NOAA CPC (OISST semanal) · NASA GIBS (VIIRS, MODIS).],
  [*Oficiales para consultar*], [Argentina: INA, Prefectura, Defensa Civil · Brasil: ANA, SGB · Paraguay: DMH · Bolivia: SENAMHI · Uruguay: INUMET, CTM Salto Grande · Regional: CIC Plata.])
#v(4pt)
#text(size: 7.4pt, fill: muted)[DOTS combina datos públicos con reglas declaradas; no es un organismo oficial. Los tiempos de llegada y las subidas estimadas son orientativos. Ante una evacuación, siguen mandando Defensa Civil y Prefectura.]
