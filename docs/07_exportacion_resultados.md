# Exportacion de reporte academico y paquete de resultados

## Objetivo

La exportacion permite conservar evidencia legible y trazable de un caso procesado.
El usuario puede descargar:

- un reporte academico en formato Markdown;
- un paquete ZIP con el reporte, archivos de entrada, mapas, metricas y logs.

El contenido es academico y de investigacion. No contiene diagnostico clinico.

## Como generar el reporte

1. Levantar la aplicacion web.
2. Abrir el listado de casos o el detalle de un caso.
3. Entrar al detalle del caso.
4. Usar el bloque **Reporte y evidencia**.
5. Descargar:
   - **Descargar reporte** para obtener `caso_<id>_reporte_academico.md`;
   - **Descargar paquete ZIP** para obtener `caso_<id>_paquete_resultados.zip`.

## Que contiene el reporte

El reporte esta escrito para que una persona no tecnica pueda entender el caso.
Incluye:

- resumen del caso;
- explicacion breve de ROI, PGM, caja plana, obstaculos, MDC y MDC*;
- datos principales del archivo cargado;
- metricas principales disponibles;
- parametros de simulacion;
- listado de archivos incluidos;
- elementos no disponibles, si existen;
- trazabilidad de rutas registradas;
- nota academica/no diagnostica.

## Que contiene el paquete ZIP

El ZIP organiza los archivos en carpetas:

```text
README.txt
caso_<id>/
  caso_<id>_reporte_academico.md
  manifest_trazabilidad.json
  01_imagen_original/
  02_roi/
  03_entrada_simulacion/
  04_resultados/
  visualizaciones/
```

La carpeta `visualizaciones/` contiene copias PNG de archivos PGM cuando aplica.
Esto facilita abrir mapas y entradas de simulacion sin depender de herramientas
especializadas.

## Como validar la exportacion

Para validar que la exportacion funciona:

1. Procesar un caso hasta obtener resultados.
2. Descargar el reporte Markdown.
3. Verificar que el reporte incluya ID, estado, modalidad, metricas y nota academica.
4. Descargar el paquete ZIP.
5. Abrir el ZIP y confirmar que contiene `README.txt`, el reporte y
   `manifest_trazabilidad.json`.
6. Revisar que `04_resultados/` incluya archivos como `metrics.json`,
   `diffusion_metrics.json`, mapas PGM y logs cuando existan.
7. Revisar que `visualizaciones/` incluya versiones PNG de mapas PGM.

## Nota de alcance

La exportacion documenta el flujo funcional del prototipo. No interpreta resultados
desde una perspectiva medica y no clasifica lesiones. Su uso esperado es evidencia
academica, trazabilidad y reproducibilidad del desarrollo.
