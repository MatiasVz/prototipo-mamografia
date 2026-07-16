# Despliegue contenedorizado

Esta configuracion usa la misma imagen para la aplicacion Flask y el worker Python/Julia. La imagen inicia la web con Gunicorn por defecto; el Compose del servidor reemplaza el comando para ejecutar solamente el listener de la cola.

## Distribucion prevista

- Web: imagen Docker desplegada en el proveedor web, sin simulaciones locales.
- Worker universitario: `docker-compose.worker.yml`, sin puertos publicados.
- PostgreSQL: Neon mediante `DATABASE_URL` con TLS.
- Cola Redis: Upstash mediante `REDIS_URL` con TLS.
- Archivos privados: Cloudflare R2.
- Correos: API HTTPS de Brevo.

El servidor universitario no crea contenedores PostgreSQL ni Redis. El worker utiliza CPU, tiene un limite de 30 cores autorizado por el responsable del servidor y no solicita acceso a GPU.

## Preparacion del servidor

1. Clonar el repositorio dentro del directorio personal del usuario.
2. Crear `.env.production` a partir de `deploy/production.env.example`.
3. Completar las credenciales directamente en el servidor y proteger el archivo:

```bash
chmod 600 .env.production
```

4. Confirmar que Docker esta disponible para el usuario:

```bash
docker info
docker compose version
```

No se deben copiar secretos dentro del Dockerfile, el Compose, GitHub ni los logs.

## Operacion

Ejecutar los comandos desde la raiz del repositorio:

```bash
bash deploy/worker.sh config
bash deploy/worker.sh build
bash deploy/worker.sh test
bash deploy/worker.sh start
bash deploy/worker.sh status
bash deploy/worker.sh logs
```

Para detener o reiniciar exclusivamente este proyecto:

```bash
bash deploy/worker.sh stop
bash deploy/worker.sh restart
```

Para traer la version mas reciente de `develop`, reconstruir y volver a iniciar:

```bash
bash deploy/worker.sh update
```

El nombre Compose incluye al usuario y evita interferir con contenedores de otros proyectos. Los archivos temporales quedan en `runtime/`, dentro del repositorio del usuario, con permisos privados. Los resultados definitivos se publican en R2 y las copias temporales se limpian al terminar cada caso.

## Parametros del worker

La configuracion de produccion esperada es:

- 200 pasos de simulacion.
- 3 realizaciones.
- 500 particulas etiquetadas para Cv/MDC.
- 30 hilos Julia y limite de 30 CPU para el contenedor.
- Tiempo de simulacion sin limite artificial (`SIMULATION_TIMEOUT_SECONDS=0`).
- Tiempos de salida `0,200`.

Estos valores se definen mediante el archivo de entorno y pueden auditarse en la linea de inicio del worker sin mostrar secretos.

Si la imagen se valida en una computadora con menos de 30 CPU disponibles, se
puede reducir temporalmente el limite solo para esa ejecucion local, sin editar
el perfil de produccion:

```bash
SIMULATION_CPU_THREADS=8 WORKER_CPU_LIMIT=8 bash deploy/worker.sh test
```

## Salud y diagnostico

La imagen web expone:

- `/health/live`: confirma que el proceso web responde.
- `/health/ready`: comprueba PostgreSQL, Redis y la configuracion del almacenamiento.

El worker tiene un healthcheck equivalente. Para revisar su estado y sus ultimos mensajes:

```bash
bash deploy/worker.sh status
LOG_TAIL=500 bash deploy/worker.sh logs
```

Los logs Docker rotan en cinco archivos de 20 MB y no imprimen URLs ni credenciales cloud.

## Recuperacion

Si una actualizacion no inicia correctamente:

1. Revisar `bash deploy/worker.sh logs`.
2. Detener solo este proyecto con `bash deploy/worker.sh stop`.
3. Identificar el commit estable anterior con `git log --oneline`.
4. Cambiar temporalmente a ese commit con `git switch --detach <commit>`.
5. Ejecutar `bash deploy/worker.sh build` y `bash deploy/worker.sh start`.
6. Tras resolver el problema, volver con `git switch develop` y actualizar.

La base de datos y los archivos permanecen en los proveedores externos, por lo que reconstruir el contenedor no elimina los casos almacenados.
