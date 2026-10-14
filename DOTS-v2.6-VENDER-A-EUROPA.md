# DOTS v2.6 · Vender a Europa

## Página pública (/libre-deforestacion, menú "Vender a Europa")
Acuerdo UE-Mercosur (provisional desde el 1/5/2026), llave sanitaria (SENASA), llave EUDR (qué demostrar), el trámite en cinco pasos (productor → frigorífico → exportador → importador que declara en TRACES → autoridad que controla), quién certifica, cómo lo resuelven otros países y herramientas gratuitas (DOTS, VISEC, Whisp, GeoRoots, Open Foris Ground, KoboToolbox, INATrace, WHIMO).

## Observatorio
- GeoJSON del lote con el formato oficial de TRACES: un Feature por parcela, `ProductionPlace`, `ProducerCountry: "AR"`, `Area` numérico en ha, 6 decimales, sin puntos repetidos; rechaza contornos que se cruzan. El centroide ya no se exporta como una segunda parcela.
- Informe PDF con la sección "Lista para el comprador": producto, resultado, lo que mide DOTS y lo que declara el productor (marcado como declaración, no verificado).
- Segunda opinión de Whisp (FAO): `POST /api/fuentes/eudr/whisp`. Usa el mapa de bosques 2020 del JRC (referencia de la Comisión) y otros. Necesita la clave gratuita `WHISP_API_KEY` en Vercel; sin ella el panel explica cómo obtenerla.
