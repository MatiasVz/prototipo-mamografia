# Evidencia tecnica y cientifica del simulador MPC

Este documento consolida la evidencia tecnica y cientifica del simulador MPC implementado en Julia para el prototipo web de analisis mamografico. Esta escrito para apoyar el informe de tesis, la sustentacion y la trazabilidad del desarrollo de software.

El sistema es un prototipo academico/de investigacion. No realiza diagnostico clinico, no clasifica lesiones y no reemplaza evaluacion medica.

## 1. Relacion con requerimientos

| Requerimiento | Evidencia cubierta |
| --- | --- |
| RF-08: Ejecucion de simulacion | El worker ejecuta el simulador Julia sobre una ROI confirmada convertida a PGM. |
| RF-09: Calculo de metricas relativas de difusion | El simulador genera `MDC`, `MDC0` y `MDC*`. |
| RF-10: Generacion de mapas de densidad | Se generan mapas PGM de densidad y concentracion MPC. |
| RF-11: Presentacion y entrega de resultados | La app web muestra mapas, metricas y parametros principales en el detalle del caso. |
| RNF-03: Trazabilidad | Cada caso conserva rutas de entrada, resultados, configuracion y logs. |
| RNF-04: Reproducibilidad | Se usan semillas, parametros versionados y casos sinteticos repetibles. |

## 2. Flujo cientifico implementado

El flujo cientifico del prototipo se puede explicar asi:

```text
ROI mamografica confirmada
-> conversion a PGM en escala de grises
-> deteccion de region mamaria valida
-> construccion de caja plana de simulacion
-> generacion de obstaculos cilindricos desde intensidades
-> inicializacion de particulas MPC
-> traslacion libre, bordes periodicos y rebote contra obstaculos
-> colision multiparticula por celdas
-> mapas de concentracion por tiempo
-> autocorrelacion de velocidades Cv
-> metricas MDC, MDC0 y MDC*
```

La salida no es una nueva mamografia. Es una representacion computacional derivada de la ROI para observar distribucion de particulas, concentracion y metricas relativas de difusion.

## 3. Explicacion simple de cada etapa

### ROI y PGM

La ROI es la region de interes que sera procesada. Puede venir de una imagen ya recortada o de una mamografia completa recortada dentro de la app.

El archivo PGM se usa porque representa la imagen como una matriz de intensidades en escala de grises. Cada pixel tiene un valor numerico:

- valores cercanos a `0`: zonas oscuras;
- valores intermedios: tejido con intensidad media;
- valores cercanos a `255`: zonas claras.

Esto permite que el simulador no trabaje con una imagen visual, sino con una matriz numerica reproducible.

### Caja plana de simulacion

La ROI se transforma en una caja bidimensional. La caja representa el dominio donde se moveran las particulas. El fondo externo de la mamografia se excluye para evitar simular zonas que no pertenecen a la region mamaria.

Evidencia generada:

```text
domain_mask.pgm
space_summary.txt
```

### Obstaculos cilindricos

Cada pixel valido de la ROI se interpreta como una celda del dominio. La intensidad del pixel se transforma en un radio de obstaculo cilindrico.

Formula registrada por el simulador:

```text
radius = 0.5 * cell_length * (1 - intensity / (max_gray + 1))
```

Interpretacion:

- intensidad alta -> radio menor;
- intensidad baja -> radio mayor;
- fondo externo -> no se considera dominio valido.

Esta representacion permite aproximar heterogeneidad del tejido dentro de una geometria mesoscopica.

Evidencia generada:

```text
obstacles.tsv
obstacle_radius_matrix.tsv
obstacle_radius_map.pgm
obstacle_radius_histogram.tsv
```

### Particulas MPC

El simulador genera particulas con posicion continua `(x, y, z)` y velocidad `(vx, vy, vz)`. Estas particulas se mueven dentro de la caja plana y se usan para observar comportamiento de transporte/difusion.

Evidencia generada:

```text
mpc_initial_particles.tsv
mpc_streamed_particles.tsv
mpc_collided_particles.tsv
```

### Traslacion, rebote y colision

Durante la traslacion, las particulas avanzan segun su velocidad y paso temporal. Si alcanzan un borde, se aplica frontera periodica. Si chocan con un obstaculo cilindrico, se registra el rebote.

Luego se aplica colision multiparticula por celdas. Esta etapa agrupa particulas por celda, calcula la velocidad media local y rota velocidades relativas segun el angulo configurado.

Evidencia generada:

```text
mpc_streaming_summary.txt
mpc_collision_summary.txt
mpc_cell_collisions.tsv
```

### Mapas de concentracion

Los mapas de concentracion muestran cuantas particulas caen en cada celda en distintos tiempos. Sirven para observar como se distribuye la poblacion de particulas dentro del dominio.

Evidencia generada:

```text
mpc_concentration_initial.pgm
mpc_concentration_final.pgm
mpc_concentration_t_<tiempo>.pgm
mpc_high_concentration_initial.pgm
mpc_high_concentration_final.pgm
mpc_concentration_times.tsv
mpc_concentration_summary.txt
```

### Autocorrelacion Cv

La autocorrelacion de velocidades `Cv` mide que tanto se conserva la direccion/velocidad de particulas etiquetadas a lo largo del tiempo.

En palabras simples: si las particulas cambian mucho su movimiento, la correlacion baja; si mantienen comportamiento parecido, la correlacion se conserva mas tiempo.

Evidencia generada:

```text
velocity_autocorrelation.tsv
velocity_autocorrelation_summary.txt
velocity_autocorrelation_realizations.tsv
```

### MDC, MDC0 y MDC*

`MDC` es la metrica calculada a partir de la autocorrelacion de velocidades.

`MDC0` es una referencia teorica sin obstaculos.

`MDC*` es la metrica normalizada:

```text
MDC* = MDC / MDC0
```

Esta normalizacion permite comparar corridas de forma relativa. No representa un diagnostico medico.

Evidencia generada:

```text
diffusion_metrics.json
diffusion_metrics.tsv
diffusion_metrics_summary.txt
```

## 4. Parametros principales

| Parametro | Significado simple | Donde queda registrado |
| --- | --- | --- |
| `seed` | Semilla para repetir resultados similares. | `simulation_config.txt`, `mpc_config.json` |
| `steps` | Numero de pasos/iteraciones de simulacion. | `simulation_config.txt`, `mpc_config.json` |
| `n0` | Densidad media de particulas por celda. | `mpc_config.json` |
| `mass` | Masa reducida de cada particula. | `mpc_config.json` |
| `kBT` | Energia termica reducida usada en velocidades. | `mpc_config.json` |
| `tau` | Paso temporal de movimiento. | `mpc_config.json` |
| `rotation_angle` | Angulo usado en colision multiparticula. | `mpc_config.json` |
| `realizations` | Numero de corridas usadas para promediar. | `mpc_config.json` |
| `labeled_particles` | Particulas solicitadas para calcular `Cv`; por defecto son 500 y el simulador registra tambien cuantas se usaron efectivamente. | `mpc_config.json`, `velocity_autocorrelation_summary.txt` |
| `output_times` | Tiempos donde se capturan mapas. | `mpc_config.json`, `mpc_concentration_summary.txt` |
| `grid_shift` | Desplazamiento de grilla; inicialmente desactivado. | `mpc_config.json` |

## 5. Archivos de evidencia por caso

Para un caso procesado, la evidencia queda organizada asi:

```text
storage/uploads/case_<id>/
├── original.<ext>
├── roi/...
├── simulation_input.pgm
└── results/
    ├── metrics.json
    ├── domain_mask.pgm
    ├── density_map.pgm
    ├── obstacle_radius_map.pgm
    ├── obstacle_radius_matrix.tsv
    ├── obstacle_radius_histogram.tsv
    ├── mpc_config.json
    ├── mpc_initial_particles.tsv
    ├── mpc_streamed_particles.tsv
    ├── mpc_collided_particles.tsv
    ├── mpc_cell_collisions.tsv
    ├── mpc_concentration_t_<tiempo>.pgm
    ├── mpc_concentration_times.tsv
    ├── velocity_autocorrelation.tsv
    ├── diffusion_metrics.json
    ├── simulation.log
    └── worker_execution.log
```

Estos archivos no deben versionarse si provienen de mamografias reales o de pruebas locales. Sirven como evidencia generada durante ejecuciones reproducibles.

## 6. Evidencia visible en la app web

La pantalla de detalle del caso muestra:

- ROI asociada al caso;
- estado del flujo: registro, ROI, PGM y resultados;
- mapas de dominio, obstaculos y concentracion;
- metricas `MDC`, `MDC0`, `MDC*`;
- parametros principales usados por el simulador;
- tabla resumida de `Cv`;
- rutas tecnicas en una seccion desplegable.

Capturas recomendadas para tesis o sustentacion:

1. Pantalla de carga de mamografia o ROI.
2. Pantalla de recorte/confirmacion de ROI.
3. Detalle del caso en estado `procesando`.
4. Detalle del caso en estado `completado`.
5. Bloque de mapas MPC avanzados.
6. Bloque de metricas `MDC`, `MDC0`, `MDC*`.
7. Seccion desplegable con trazabilidad de archivos.

## 7. Validacion sintetica reproducible

La validacion sintetica usa casos no sensibles para comprobar invariantes basicos:

- `free_field`: dominio libre;
- `central_obstacle`: obstaculo central;
- `intensity_pattern`: patron de intensidades;
- `clear_dark_channel`: canal claro rodeado de zonas oscuras;
- `synthetic_roi`: ROI sintetica sin datos clinicos.

Generar casos:

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

Evidencia esperada:

```text
validation_summary.tsv
validation_summary.md
cases/<case_name>/input.pgm
cases/<case_name>/matrix.in
cases/<case_name>/size.in
cases/<case_name>/results/
```

## 8. Comparacion con el programa C del tutor

El programa C del tutor usa archivos historicos como:

```text
matrix.in
size.in
```

El simulador Julia acepta `input.pgm` como entrada principal, pero tambien puede generar `matrix.in` y `size.in` en los casos sinteticos para comparar el formato de entrada.

Correspondencia principal:

| Programa C del tutor | Prototipo Julia |
| --- | --- |
| `matrix.in` | `input.pgm` y exportacion compatible `matrix.in` |
| `size.in` | exportacion compatible `size.in` |
| obstaculos mamograficos | `SimulationObstacle` con radio derivado de intensidad |
| colision multiparticula | `collide_mpc_particles` |
| traslacion y rebote | `stream_mpc_particles` |
| densidad | mapas de concentracion MPC |
| autocorrelacion | `velocity_autocorrelation.tsv` |
| coeficiente de difusion | `MDC`, `MDC0`, `MDC*` |

Diferencias documentadas:

- El programa C es modular por compilacion; Julia usa funciones y configuracion.
- El C no se incluye en este repositorio porque es material externo del tutor.
- La validacion automatizada actual revisa invariantes y reproducibilidad, no igualdad bit a bit.
- Las trayectorias exactas pueden diferir por generador aleatorio, orden de particulas y decisiones internas de implementacion.

## 9. Limitaciones

- El prototipo no esta validado clinicamente.
- Los resultados son relativos y academicos.
- `MDC*` ayuda a comparar corridas, pero no clasifica lesiones.
- La simulacion actual prioriza trazabilidad y explicabilidad antes que rendimiento.
- La comparacion contra el C del tutor no es todavia una equivalencia numerica completa.
- Las mamografias usadas en pruebas deben evitar datos sensibles o identificables.
- La salida depende de la ROI seleccionada y de los parametros configurados.

## 10. Como repetir el flujo completo

Levantar servicios principales:

```powershell
docker-compose up -d
```

Levantar web local:

```powershell
cd web
.\.venv\Scripts\Activate.ps1
python -m flask --app run.py db-check
python -m flask --app run.py db-init
python run.py
```

Levantar worker en otra terminal:

```powershell
cd web
.\.venv\Scripts\Activate.ps1
python ..\worker\worker.py
```

Flujo de usuario:

1. Abrir `http://127.0.0.1:5000/mamografias/cargar`.
2. Cargar mamografia completa o ROI recortada.
3. Si es mamografia completa, recortar ROI.
4. Confirmar ROI.
5. Esperar que el worker procese el caso.
6. Revisar el detalle del caso completado.
7. Guardar capturas de mapas, metricas y trazabilidad.

## 11. Frase corta para defensa

El prototipo toma una ROI mamografica confirmada, la convierte a una matriz PGM, construye una caja plana de simulacion con obstaculos cilindricos derivados de las intensidades, ejecuta un modelo MPC en Julia y presenta mapas de concentracion junto con metricas relativas de difusion. Todo el proceso queda asociado a un caso, con archivos, parametros, estados y logs para garantizar trazabilidad y reproducibilidad.
