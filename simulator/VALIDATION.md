# Validacion del simulador Julia

Este documento describe la estrategia de validacion del simulador Julia frente al programa C del tutor y frente a casos sinteticos controlados.

El objetivo no es afirmar equivalencia clinica ni diagnostica. El objetivo es demostrar que el prototipo produce resultados trazables, reproducibles y coherentes con la formulacion mesoscopica usada como referencia.

Para una explicacion mas amplia del flujo cientifico, parametros, archivos de evidencia y uso en tesis, revisar [EVIDENCE.md](EVIDENCE.md).

## Programa C del tutor

El programa C revisado se encuentra fuera del repositorio, en el entorno local de trabajo del estudiante. No se copia al repositorio porque es material externo del tutor.

Ruta local usada para revision:

```text
C:\Users\matia\OneDrive\Escritorio\Escritorio\Universidad\Octavo ciclo\Tesis\VARIOS\Programa Tutor\src
```

Componentes relevantes observados:

- `matrix.in`: matriz de entrada con coordenadas `x`, `y` e intensidad.
- `size.in`: dimensiones de la matriz.
- `Dynamic/multPartPartialCol.c`: dinamica de colision multiparticula y traslacion.
- `Obstacles/mamographic.h`: interfaz de obstaculos mamograficos.
- `Measure/density.c`: medicion de densidad.
- `Measure/particleTrace.c`: seguimiento de particulas.
- `CDvacf.f`: calculo relacionado con autocorrelacion de velocidades.

## Correspondencia tecnica

| Programa C del tutor | Simulador Julia |
| --- | --- |
| `matrix.in` | `input.pgm` y exportacion compatible `matrix.in` |
| `size.in` | exportacion compatible `size.in` |
| Obstaculos cilindricos | `SimulationObstacle` con centro, radio y altura |
| `multPartPartialCol` | `collide_mpc_particles` y `stream_mpc_particles` |
| Densidad | mapas y matrices de concentracion MPC |
| Seguimiento de particulas | particulas etiquetadas y autocorrelacion de velocidades |
| Coeficiente de difusion | `MDC`, `MDC0` y `MDC*` |

## Casos sinteticos

El simulador Julia incluye generacion de casos sinteticos no sensibles:

- `free_field`: campo libre sin obstaculos bloqueantes.
- `central_obstacle`: obstaculo oscuro central.
- `intensity_pattern`: patron simple de intensidades.
- `clear_dark_channel`: canal claro rodeado por zonas oscuras.
- `synthetic_roi`: ROI mamaria sintetica sin datos clinicos.

Cada caso genera:

```text
input.pgm
matrix.in
size.in
case_metadata.tsv
```

`matrix.in` y `size.in` permiten comparar la entrada generada por Julia con el formato historico usado por el programa C del tutor.

## Ejecutar generacion de casos

Desde la raiz del repositorio:

```powershell
julia --project=simulator simulator/scripts/generate_validation_cases.jl `
  --output storage/validation/synthetic_cases
```

## Ejecutar validacion sintetica

Desde la raiz del repositorio:

```powershell
julia --project=simulator simulator/scripts/validate_synthetic_cases.jl `
  --output storage/validation/synthetic_report `
  --seed 1234 `
  --steps 5
```

La validacion genera:

```text
validation_summary.tsv
validation_summary.md
cases/<case_name>/input.pgm
cases/<case_name>/matrix.in
cases/<case_name>/size.in
cases/<case_name>/results/
```

## Metricas verificadas

La validacion revisa:

- conteo esperado y real de celdas del dominio;
- conteo esperado y real de obstaculos bloqueantes preliminares;
- conservacion de particulas entre inicializacion y mapas de concentracion;
- generacion de `MDC`, `MDC0` y `MDC*`;
- trazabilidad de archivos de salida por caso.

## Diferencias conocidas frente al C

El programa C del tutor es un motor historico modular, orientado a compilacion por componentes. La version Julia del prototipo busca reproducibilidad, trazabilidad y conexion con el aplicativo web.

Diferencias pendientes o aceptadas:

- El C usa modulos intercambiables por compilacion; Julia usa configuracion y funciones del paquete.
- El C trabaja con estructuras internas propias de celda, particula y obstaculo; Julia exporta archivos inspeccionables TSV/PGM/JSON.
- La validacion automatizada actual compara invariantes y formatos de entrada, no bit a bit la trayectoria de particulas del C.
- La comparacion exacta de trayectorias queda limitada por diferencias de generador aleatorio, orden de listas de particulas y politicas de rotacion.

## Uso en tesis

Esta validacion puede presentarse como evidencia de:

- preparacion de datos de entrada reproducibles;
- correspondencia entre formato historico `matrix.in`/`size.in` y entrada PGM del prototipo;
- conservacion de particulas;
- comportamiento esperado en geometria simple;
- generacion de metricas relativas de difusion;
- limitaciones conocidas y trazables del prototipo.

Evidencias recomendadas para anexos o sustentacion:

- salida de `validation_summary.md`;
- capturas de la pantalla de detalle del caso completado;
- mapas `domain_mask.pgm`, `obstacle_radius_map.pgm` y `mpc_concentration_t_<tiempo>.pgm`;
- tabla `velocity_autocorrelation.tsv`;
- archivo `diffusion_metrics.json`;
- log `worker_execution.log` cuando la corrida se ejecute desde la app web.
