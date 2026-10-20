// Identidad institucional única para todos los informes Typst de DOTS.
// Módulos temáticos conservan sus gráficos, análisis y advertencias científicas.
#let name = "DOTS · Sistema de Inteligencia Territorial, Ambiental y Climática"
#let director = "Dirección: Álvaro Fontana"
#let method = "Observación satelital · Telemetría · Análisis geoespacial"
#let color = rgb("#0f9fa6")
#let dark = rgb("#0b2b33")
#let muted = rgb("#667085")
#let cover-id() = block(width: 100%, inset: (bottom: 5pt), {
  text(size: 8pt, weight: "bold", fill: dark)[#name]
  v(2pt)
  text(size: 7.2pt, fill: muted)[#method · #director]
})
#let footer-id(page: none) = {
  text(size: 7pt, fill: muted)[#name · #director]
}
