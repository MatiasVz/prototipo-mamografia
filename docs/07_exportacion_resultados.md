# Exportacion de reporte academico y paquete de resultados

## Objetivo

La exportacion permite conservar evidencia legible, visual y trazable de un caso procesado.

El usuario puede descargar:

- un reporte academico en formato PDF;
- un paquete ZIP con reporte, imagenes, archivos de entrada, mapas, metricas y logs.

El contenido es academico y de investigacion. No contiene diagnostico clinico.

## Como generar el reporte

1. Levantar la aplicacion web.
2. Iniciar sesion.
3. Abrir el listado de casos propios.
4. Entrar al detalle de un caso procesado.
5. Usar el bloque **Reporte y evidencia**.
6. Descargar:
   - **Descargar reporte PDF** para obtener `caso_<id>_reporte_academico.pdf`;
   - **Descargar paquete ZIP** para obtener `caso_<id>_paquete_resultados.zip`.

## Que contiene el reporte PDF

El reporte esta escrito para que una persona no tecnica pueda entender el caso.

Incluye:

- resumen del caso;
- nota de alcance academico y no diagnostico;
- imagen original o ROI, cuando este disponible;
- region usada por la simulacion;
- explicacion breve de ROI, PGM, caja plana, obstaculos, Cv, MDC y MDC*;
- metricas principales disponibles;
- mapas de concentracion o densidad;
- visualizacion pseudo-3D de la caja de simulacion, si existe;
- explicacion de parametros principales;
- observaciones sobre resultados no disponibles;
- fecha de generacion del reporte.

El reporte no debe mostrar rutas internas innecesarias al usuario final. La trazabilidad tecnica puede quedar dentro del paquete ZIP o en secciones de administracion.

## Que contiene el paquete ZIP

El ZIP organiza los archivos en carpetas:

```text
README.txt
caso_<id>/
  caso_<id>_reporte_academico.pdf
  manifest_trazabilidad.json
  01_imagen_original/
  02_roi/
  03_entrada_simulacion/
  04_resultados/
  visualizaciones/
  logs/
```

La carpeta `visualizaciones/` contiene copias PNG de archivos PGM cuando aplica. Esto facilita abrir mapas y entradas de simulacion sin depender de herramientas especializadas.

## Como validar la exportacion

Para validar que la exportacion funciona:

1. Procesar un caso hasta obtener resultados.
2. Descargar el reporte PDF.
3. Verificar que el PDF incluya ID, estado, modalidad, metricas, imagenes principales y nota academica.
4. Verificar que el PDF sea entendible para un usuario no tecnico.
5. Descargar el paquete ZIP.
6. Abrir el ZIP y confirmar que contiene `README.txt`, el reporte y `manifest_trazabilidad.json`.
7. Revisar que `04_resultados/` incluya archivos como `metrics.json`, `diffusion_metrics.json`, mapas PGM y logs cuando existan.
8. Revisar que `visualizaciones/` incluya versiones PNG de mapas PGM.

## Nota de alcance

La exportacion documenta el flujo funcional del prototipo. No interpreta resultados desde una perspectiva medica y no clasifica lesiones. Su uso esperado es evidencia academica, trazabilidad y reproducibilidad del desarrollo.
