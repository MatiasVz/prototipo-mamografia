# Simulador Julia

Modulo base del simulador mesoscopico del prototipo de analisis mamografico.

Esta primera version corresponde a la estructura inicial del proyecto Julia. Todavia no implementa la lectura real del PGM ni la dinamica de simulacion; solo prepara una ejecucion controlada desde terminal para validar entrada, salida y trazabilidad basica.

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
```

## Alcance actual

- Crear estructura base del simulador en Julia.
- Exponer una CLI minima para integracion futura.
- Registrar configuracion inicial de ejecucion.
- Preparar el camino para leer PGM y construir la matriz de intensidades en issues posteriores.
