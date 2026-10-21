# Laboratorio ENSO histórico — integración controlada

Se incorporó al observatorio un visor de anomalías SST ERSST v5, cuatro regiones Niño, Hovmöller ecuatorial y mapas anuales. El visor lee `/data/enso-ersst.json` generado con `tools/build_enso_ersst.py`.

## Generar datos reales (fuera de Vercel)
1. Obtener el archivo oficial NOAA ERSST v5 `sst.mnmean.nc` desde https://psl.noaa.gov/data/gridded/data.noaa.ersst.v5.html .
2. Instalar `numpy xarray netCDF4` en un runner o equipo con recursos suficientes.
3. Ejecutar `python tools/build_enso_ersst.py --input sst.mnmean.nc --output public/data/enso-ersst.json`.
4. Revisar período, cobertura, tamaño y resultados antes de incorporar el JSON al sitio.

**Estado:** código de transformación y visualización incorporado. La descarga del NetCDF, la generación del JSON real y su comprobación visual aún requieren ejecutarse. Si el archivo no existe, el panel lo informa; jamás reemplaza datos reales por números sintéticos.

Los índices Niño derivados de anomalías ERSST NO son ONI CPC. El ONI oficial sigue obteniéndose del endpoint independiente NOAA CPC. La climatología para anomalías ERSST se fija en 1991–2020. Los mapas son cortes de enero de cada año disponible, no mapas de todos los meses.

## Próximas fuentes del material original
OLR HIRS, vientos NCEP 850/200 hPa, presión Darwin–Tahiti, humedad de suelo CPC y fuentes NASA/Copernicus necesitan pipelines separados y comprobación de sus unidades, cobertura, métodos y credenciales. No se incorporan como observaciones valores simulados de clorofila, altura del mar, SPI o precipitación.

**Seguridad:** no almacenar tokens NASA Earthdata ni Copernicus en GitHub; usar secretos del runner. Rotar cualquier credencial expuesta en conversaciones o scripts anteriores.
