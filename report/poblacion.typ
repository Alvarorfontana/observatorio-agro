// DOTS / Campo — Informe de población expuesta (Typst). Datos desde poblacion/report.build vía sys.inputs.data.
#import "identity.typ": name, director, method, cover-id
#let d = json(bytes(sys.inputs.data))
// Identidad institucional compartida de los informes DOTS.
// La especialidad cambia, pero la denominación y la responsabilidad editorial no.

#let ink = rgb("#101828")
#let muted = rgb("#667085")
#let line-c = rgb("#e4e7ec")
#let soft = rgb("#f6f7f9")
#let navy = rgb("#122b3a")
#let blue = rgb("#246fa6")
#let orange = rgb("#b76d27")
#let red = rgb("#bc3647")

#set document(title: d.title, author: name)
#set text(font: "IBM Plex Sans", size: 9.6pt, fill: ink, lang: "es")
#set par(leading: 0.6em)
#set page(paper: "a4", margin: (top: 14mm, bottom: 16mm, x: 15mm),
  footer: context {
    set text(size: 7.2pt, fill: muted)
    line(length: 100%, stroke: 0.5pt + line-c)
    v(-2pt)
    grid(columns: (1fr, auto), [Población residente estimada (modelo). No es un registro de damnificados ni de evacuados.], [#d.url · pág. #counter(page).display()])
  })
#let card(body, fill: soft) = block(fill: fill, radius: 8pt, inset: 10pt, width: 100%, breakable: false, body)
#let sec(t) = block(above: 14pt, below: 6pt, sticky: true, text(size: 12pt, weight: "semibold")[#t])

#cover-id()
#block(width: 100%, fill: navy, radius: 10pt, inset: (x: 16pt, y: 14pt), {
  set text(fill: white)
  grid(columns: (1fr, auto), align: (left + horizon, right + horizon),
    [#text(size: 7.6pt, weight: "bold", tracking: 0.14em)[DOTS · POBLACIÓN Y RIESGO CLIMÁTICO] #linebreak()
     #text(size: 21pt, weight: "bold")[#d.kind · población expuesta] #linebreak()
     #text(size: 8.5pt)[#d.category · fecha de la amenaza #d.event_date]],
    [#text(size: 8pt)[PERSONAS EXPUESTAS] #linebreak() #text(size: 22pt, weight: "bold")[#d.exposed] #linebreak() #text(size: 9pt)[#d.pct de la zona]])
})
#v(3pt)
#text(size: 8pt, fill: muted)[Informe del #d.generated]

#if d.summary.len() > 0 [
  #v(6pt)
  #card[#for l in d.summary [#text(size: 9.6pt)[#l] #parbreak()]]
]
#v(6pt)
#grid(columns: (1fr, 1fr, 1fr, 1fr), column-gutter: 7pt,
  card[#text(size: 7.4pt, fill: muted)[Población en la zona] #linebreak() #text(size: 16pt, weight: "bold")[#d.total]],
  card[#text(size: 7.4pt, fill: muted)[Población expuesta] #linebreak() #text(size: 16pt, weight: "bold", fill: red)[#d.exposed]],
  card[#text(size: 7.4pt, fill: muted)[Superficie superpuesta] #linebreak() #text(size: 16pt, weight: "bold")[#d.inter_km2] #text(size: 8pt)[km²]],
  card[#text(size: 7.4pt, fill: muted)[Densidad de la zona] #linebreak() #text(size: 16pt, weight: "bold")[#d.density] #text(size: 8pt)[hab./km²]])

#sec[Geometrías analizadas]
#let s = d.sketch
#let toPts(r) = r.map(p => (p.at(0) * 1mm, p.at(1) * 1mm))
#block(width: 170mm, height: 95mm, fill: rgb("#f3f6f6"), radius: 6pt, clip: true, {
  for r in s.area { place(polygon(fill: blue.transparentize(85%), stroke: 1.2pt + blue, ..toPts(r))) }
  for r in s.hazard { place(polygon(fill: orange.transparentize(85%), stroke: (paint: orange, thickness: 1.2pt, dash: "dashed"), ..toPts(r))) }
  for r in s.inter { place(polygon(fill: red.transparentize(65%), stroke: 1.4pt + red, ..toPts(r))) }
  place(top + right, dx: -6pt, dy: 6pt, text(size: 8pt, weight: "bold")[N ↑])
  place(bottom + left, dx: 6pt, dy: -6pt, text(size: 7pt, fill: muted)[ancho del recuadro ≈ #s.width_km km])
})
#text(size: 7.6pt, fill: muted)[Azul: zona de estudio · naranja punteado: área de amenaza · rojo: superposición, donde se cuenta la población expuesta. Esquema sin mapa de fondo.]

#sec[Datos del análisis]
#table(columns: (1.2fr, 2fr), stroke: (x, y) => (bottom: 0.5pt + line-c), inset: (x: 5pt, y: 5pt),
  [*Fuente de población*], [#d.provider · #d.year · #d.group],
  [*Superficie de la zona*], [#d.area_km2 km²],
  [*Amenaza*], [#d.kind · #d.category],
  [*Fecha de la amenaza*], [#d.event_date],
  [*Fuente de la amenaza*], [#d.event_source],
  [*Contexto ENSO declarado*], [#d.enso],
  [*Método*], [#d.method],
)

#sec[Cómo leer este informe]
#set text(size: 8.6pt)
- #d.interpretation
#for n in d.notes [- #n]
- El porcentaje expuesto no es la probabilidad de que una persona sufra daño. No se estiman víctimas, costos ni prioridades de evacuación.
- Población: WorldPop (Universidad de Southampton), licencia CC BY 4.0. Ante una emergencia, la información oficial es la de Defensa Civil y los organismos competentes.
