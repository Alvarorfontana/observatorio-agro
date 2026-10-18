# DOTS Campo: datos satelitales abiertos para decidir en el campo y frente a la crecida

**Un observatorio abierto que junta, en una sola pantalla, el clima, el satélite, el río y el suelo —
con la procedencia y la escala de cada dato a la vista.**

---

## Bajada

DOTS Campo es un observatorio operativo que reúne información pública de satélites, reanálisis climáticos
y organismos oficiales (NASA, Copernicus, NOAA, INTA, INA, SoilGrids, WorldPop, entre otros) y la traduce
en respuestas concretas: ¿pulverizo hoy?, ¿está subiendo el río?, ¿cómo viene la humedad del suelo?,
¿qué cultivo se ve mejor en mi lote? Cada número viaja con su fuente y con su escala explícita de mínimo
y máximo, para que se pueda leer sin ser especialista.

Sitio: https://observatorio-agro.vercel.app
Código abierto: https://github.com/Alvarorfontana/observatorio-agro

## Cómo nace

DOTS nace de una pregunta simple y muy concreta: ¿por qué hay que ser especialista en teledetección para
saber si conviene fumigar mañana o si el río va a desbordar? La información existe, es pública y es
gratuita: satélites de la NASA y de la Unión Europea la publican todos los días. El problema no es la
falta de datos, sino que están dispersos, en formatos técnicos y sin contexto.

DOTS Campo toma esos datos, los limpia, los pone en la misma unidad y los devuelve con una frase que se
entiende, sin esconder de dónde salió ni cuánto vale. Cuando una fuente no responde, no inventa: dice
"sin dato" y explica por qué.

## Qué es

- **Panel público** con el estado del clima, la vegetación, la humedad del suelo, el estado de los ríos y
  el fenómeno de El Niño.
- **Informes y newsletters** por tema y por audiencia (gobierno, municipio, empresa), generados con los
  mismos datos que muestra la web.
- **Alertas** operativas (heladas, viento, riesgo de enfermedad, crecidas) pensadas para el trabajo diario.

## Quién lo hace

Álvaro Fontana. El proyecto es de desarrollo propio y de código abierto: cualquiera puede auditar de dónde
sale cada dato, cómo se calcula y con qué escala se interpreta.

## Qué es gratis y qué no

- **La consulta pública es gratuita**: el panel, los informes por tema y las alertas pueden verse sin costo.
- **La consultoría y los servicios a medida son pagos**: informes específicos, integración en los sistemas
  de un organismo o una empresa, análisis a medida y acompañamiento técnico.

## Capacidades (se suman a medida que el dato existe)

- Clima actual y pronóstico a 7 días, y clima de los últimos 30 años.
- Vegetación (NDVI, NDMI) y cobertura del lote (Dynamic World, MapBiomas).
- Humedad del suelo por satélite (SMAP de la NASA) y comparada con lo normal (NASA POWER/MERRA-2).
- Ventana de pulverización y riesgo de enfermedad por clima.
- Estado de los ríos (Copernicus GloFAS, alturas del INA) y amenaza de crecida por período de retorno.
- El Niño (ONI, RONI), inundaciones satelitales (GFM) y población expuesta.

## Trazabilidad y límites

- **Todo dato lleva su escala**: rango mínimo y máximo, bandas y en qué banda cae el valor.
- **Toda respuesta lleva su fuente**: organismo, método y URL de origen.
- **Nada se inventa**: si una fuente falla, el dato queda en "sin dato" con el motivo.
- **Son modelos, no mapas oficiales**: la información de amenaza y de exposición es estimada; las cuentas
  oficiales de evacuados y damnificados las publican los organismos de emergencia, no DOTS.

## Cifras clave

- Más de 20 fuentes públicas integradas.
- Informes por tema, audiencia y a medida.
- Cobertura inicial centrada en la cuenca del río Paraná y la región.

## Citas

> "La información es pública y gratuita; lo que faltaba era traducirla. DOTS Campo hace ese trabajo y no
> esconde de dónde sale cada número."
> — Álvaro Fontana, creador de DOTS Campo.

## Contacto de prensa

- Nombre: Álvaro Fontana
- Correo: alvarofontana@gmail.com
- Teléfono: [COMPLETAR]
- Sitio: https://observatorio-agro.vercel.app
- Repositorio: https://github.com/Alvarorfontana/observatorio-agro

---

### Notas para la redacción (datos a completar antes de publicar)

- Teléfono de contacto.
- Correo de prensa dedicado (si se prefiere distinto del personal).
- Fecha de inicio del proyecto y del primer lanzamiento público.
- Logotipo y material gráfico (`public/dots-logo.svg`, `public/dots-portada.png`).
- Confirmar la lista de fuentes citadas a la fecha de publicación.
