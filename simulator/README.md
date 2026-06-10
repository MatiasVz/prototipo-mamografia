# Simulador Julia

Modulo base del simulador mesoscopico del prototipo de analisis mamografico.

Esta version prepara el proyecto Julia, permite leer una entrada `PGM` para obtener dimensiones, valor maximo de gris y matriz de intensidades, y convierte esa matriz en una grilla interna con obstaculos derivados de la imagen. Todavia no implementa la dinamica mesoscopica.

## Ejecucion inicial

Desde la raiz del repositorio:

```powershell
julia --project=simulator simulator/scripts/run_case.jl `
  --input storage/uploads/case_1/simulation_input.pgm `
  --output storage/uploads/case_1/results `
  --seed 1234 `
  --steps 0
```

La ejecucion crea la carpeta de salida y genera:

```text
simulation.log
simulation_config.txt
input_summary.txt
space_summary.txt
obstacles.tsv
```

## Alcance actual

- Exponer una CLI minima para integracion futura.
- Leer archivos PGM `P2` y `P5`.
- Obtener ancho, alto, valor maximo de gris y matriz de intensidades.
- Registrar un resumen tecnico de la entrada en `input_summary.txt`.
- Convertir la matriz de intensidades en una grilla de simulacion.
- Generar obstaculos a partir de intensidades mayores que cero.
- Registrar un resumen del espacio en `space_summary.txt`.
- Exportar una tabla inspeccionable de obstaculos en `obstacles.tsv`.
