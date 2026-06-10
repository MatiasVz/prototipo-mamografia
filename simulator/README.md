# Simulador Julia

Modulo base del simulador mesoscopico del prototipo de analisis mamografico.

Esta version prepara el proyecto Julia y permite leer una entrada `PGM` para obtener dimensiones, valor maximo de gris y matriz de intensidades. Todavia no implementa la conversion a espacio fisico de simulacion ni la dinamica mesoscopica.

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
```

## Alcance actual

- Exponer una CLI minima para integracion futura.
- Leer archivos PGM `P2` y `P5`.
- Obtener ancho, alto, valor maximo de gris y matriz de intensidades.
- Registrar un resumen tecnico de la entrada en `input_summary.txt`.
- Preparar el camino para convertir la matriz de intensidades en espacio de simulacion en issues posteriores.
