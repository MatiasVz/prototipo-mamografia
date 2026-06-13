# Simulador Julia

Modulo de simulacion mesoscopica MPC del prototipo de analisis mamografico.

El simulador recibe una ROI confirmada convertida a PGM, construye un dominio de simulacion a partir de la region mamaria valida, genera obstaculos cilindricos derivados de intensidades, inicializa particulas MPC y produce mapas, metricas y archivos de trazabilidad.

Este modulo es parte de un prototipo academico/de investigacion. Sus resultados son relativos y no constituyen diagnostico clinico.

## Documentacion relacionada

- [EVIDENCE.md](EVIDENCE.md): guia de evidencia tecnica y cientifica para tesis, PR y sustentacion.
- [VALIDATION.md](VALIDATION.md): validacion del simulador Julia frente al programa C del tutor y casos sinteticos.

## Ejecucion desde terminal

Desde la raiz del repositorio:

```powershell
julia --project=simulator simulator/scripts/run_case.jl `
  --input storage/uploads/case_1/simulation_input.pgm `
  --output storage/uploads/case_1/results `
  --seed 1234 `
  --steps 10 `
  --density 0.25 `
  --n0 10 `
  --mass 1 `
  --kbt 1 `
  --tau 1 `
  --rotation-angle 1.5707963267948966 `
  --realizations 1 `
  --labeled-particles 500 `
  --correlation-initial-times 1 `
  --output-times 0,100,500 `
  --grid-shift false
```

## Flujo interno

```text
ROI confirmada en PGM
-> lectura de matriz de intensidades
-> deteccion de region mamaria valida
-> caja plana de simulacion
-> obstaculos cilindricos por intensidad
-> particulas MPC con posicion continua y velocidad
-> traslacion, frontera periodica y rebote
-> colision multiparticula por celda
-> mapas de concentracion
-> autocorrelacion Cv
-> MDC, MDC0 y MDC*
```

## Archivos principales de salida

La ejecucion crea una carpeta `results/` con archivos inspeccionables:

```text
simulation.log
worker_execution.log
simulation_config.txt
input_summary.txt
space_summary.txt
metrics.json
domain_mask.pgm
density_map.pgm
density_matrix.tsv
obstacles.tsv
obstacle_radius_matrix.tsv
obstacle_radius_map.pgm
obstacle_radius_histogram.tsv
mpc_config.json
mpc_initial_particles.tsv
mpc_streamed_particles.tsv
mpc_streaming_summary.txt
mpc_collided_particles.tsv
mpc_collision_summary.txt
mpc_cell_collisions.tsv
mpc_concentration_summary.txt
mpc_concentration_times.tsv
mpc_concentration_initial.pgm
mpc_concentration_final.pgm
mpc_concentration_t_<tiempo>.pgm
mpc_high_concentration_initial.pgm
mpc_high_concentration_final.pgm
velocity_autocorrelation.tsv
velocity_autocorrelation_summary.txt
velocity_autocorrelation_realizations.tsv
diffusion_metrics.json
diffusion_metrics.tsv
diffusion_metrics_summary.txt
```

## Resultados que muestra la app web

Cuando el caso termina en estado `completado`, la app web puede presentar:

- ROI usada como entrada;
- region mamaria valida;
- mapa de radios de obstaculos;
- mapa de densidad;
- mapas de concentracion MPC por tiempos disponibles;
- tabla resumida de autocorrelacion `Cv`;
- metricas `MDC`, `MDC0` y `MDC*`;
- parametros principales de la corrida;
- rutas tecnicas y logs para trazabilidad.

## Parametros relevantes

| Parametro | Descripcion |
| --- | --- |
| `seed` | Semilla reproducible de la corrida. |
| `steps` | Numero de pasos de simulacion. |
| `density` | Densidad preliminar usada por el motor secuencial de apoyo. |
| `n0` | Densidad media MPC de particulas por celda. |
| `mass` | Masa reducida de particula. |
| `kbt` | Energia termica reducida. |
| `tau` | Paso temporal reducido. |
| `rotation-angle` | Angulo de rotacion usado en colision multiparticula. |
| `realizations` | Numero de realizaciones estadisticas. |
| `labeled-particles` | Particulas solicitadas para autocorrelacion; por defecto se piden 500 y, si la ROI tiene menos particulas disponibles, se usan las disponibles sin detener la corrida. |
| `correlation-initial-times` | Cantidad de tiempos iniciales usados para `Cv`. |
| `output-times` | Tiempos donde se capturan mapas de concentracion. |
| `grid-shift` | Desplazamiento de grilla MPC; inicialmente desactivado. |

## Validacion sintetica

Generar casos sinteticos:

```powershell
julia --project=simulator simulator/scripts/generate_validation_cases.jl `
  --output storage/validation/synthetic_cases
```

Ejecutar validacion:

```powershell
julia --project=simulator simulator/scripts/validate_synthetic_cases.jl `
  --output storage/validation/synthetic_report `
  --seed 1234 `
  --steps 5
```

La validacion revisa dominio, obstaculos, conservacion de particulas y generacion de metricas comparables.
