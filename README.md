# Observatorio de Datos · Ideas para Gobernar

Extrae y actualiza datos abiertos de datos.gov.co (API Socrata) para los productos del Observatorio.

## Qué hay aquí
- `extractor_datosgov.py`: catálogo, cruce de ids, diccionario de columnas, descargas y consultas agregadas.
- `catalogo_ancla.csv`: los 50 datasets prioritarios por línea de investigación.
- `consultas.json`: consultas agregadas (SoQL) que alimentan cada producto.
- `.github/workflows/catalogo.yml`: catálogo y diccionario, mensual.
- `.github/workflows/actualizar.yml`: productos, diario.
- `datos/`: resultados que generan los flujos (no editar a mano).

## Principio
Se agrega en el servidor de datos.gov.co (SoQL `$group`) y solo se guardan tablas pequeñas.
Los conjuntos de millones de filas no se descargan completos a este repositorio.

## Requisito
Secreto del repositorio `SOCRATA_APP_TOKEN` con el token de aplicación de datos.gov.co.
