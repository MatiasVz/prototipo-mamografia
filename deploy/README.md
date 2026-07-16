# Despliegue distribuido y controlado

La aplicacion se despliega como dos componentes independientes construidos a
partir del mismo repositorio:

- Web Flask: Render mediante `Dockerfile.web`.
- Worker Python/Julia: servidor universitario mediante
  `docker-compose.worker.yml`.
- PostgreSQL: Neon con conexion TLS.
- Cola Redis: Upstash con conexion TLS.
- Archivos privados: Cloudflare R2.
- Correos transaccionales: Brevo mediante HTTPS.

La web no ejecuta simulaciones. Registra la tarea en Redis y el worker del
servidor la procesa con CPU. El worker no publica puertos y no crea servicios
PostgreSQL o Redis locales.

## Controles de seguridad

- Los secretos no se incluyen en imagenes, Compose, Git ni artefactos.
- El contenedor utiliza un usuario sin privilegios, elimina capabilities y
  activa `no-new-privileges`.
- El proyecto Compose remoto siempre se llama `mamografia-<usuario>`.
- Los archivos del despliegue permanecen en el directorio personal del usuario.
- Cada imagen remota se fija por digest `sha256`; no se despliegan etiquetas
  mutables como `latest`.
- Un bloqueo impide ejecutar dos despliegues al mismo tiempo.
- Si el worker nuevo no queda saludable, se restaura la version anterior.
- Ningun script contiene operaciones globales como `docker system prune`,
  `docker stop $(docker ps ...)` o eliminacion de contenedores ajenos.

## Validacion continua

`.github/workflows/ci.yml` se ejecuta en Pull Requests y cambios de `develop` o
`main`. Verifica:

1. Ausencia de secretos versionados.
2. Pruebas y sintaxis Python.
3. Pruebas del simulador Julia.
4. Construccion de las imagenes web y worker sin publicarlas.

Las acciones externas estan fijadas a commits concretos para que el pipeline
sea reproducible.

## Preparacion unica del servidor

El bootstrap solo crea directorios privados. No inicia, detiene ni modifica
contenedores:

```bash
bash deploy/server-bootstrap.sh
```

La estructura resultante es:

```text
~/apps/prototipo-mamografia/
|-- current -> releases/<commit>
|-- previous -> releases/<commit-anterior>
|-- releases/
`-- shared/
    |-- .env.production
    `-- runtime/
```

Crear manualmente
`~/apps/prototipo-mamografia/shared/.env.production` a partir de
`deploy/production.env.example` y protegerlo:

```bash
chmod 600 ~/apps/prototipo-mamografia/shared/.env.production
```

Antes del primer despliegue se valida sin revelar valores:

```bash
python3 deploy/validate_env.py \
  ~/apps/prototipo-mamografia/shared/.env.production
```

## Acceso automatizado por SSH

GitHub Actions utiliza una clave exclusiva para despliegue. La clave publica se
agrega a `~/.ssh/authorized_keys` del usuario universitario. La clave privada no
se copia al servidor ni al repositorio.

En GitHub se crea el Environment `production` con aprobacion manual y estos
secrets:

- `PRODUCTION_SSH_HOST`
- `PRODUCTION_SSH_PORT`
- `PRODUCTION_SSH_USER`
- `PRODUCTION_SSH_PRIVATE_KEY`
- `PRODUCTION_SSH_KNOWN_HOSTS`
- `RENDER_DEPLOY_HOOK_URL`

Tambien se configura la variable `PRODUCTION_WEB_URL` con la URL publica de
Render. Neon, Upstash, R2 y Brevo no se guardan en GitHub: sus valores se
mantienen solamente en Render y en el `.env.production` privado del servidor.

## Aplicacion web en Render

`render.yaml` define un Web Service Docker gratuito sobre `develop` durante la
validacion inicial. El servicio usa `/health/live` como healthcheck y mantiene
el despliegue automatico desactivado. GitHub Actions solicita cada despliegue
mediante un Deploy Hook protegido.

Al crear el Blueprint se completan en el panel de Render las variables marcadas
con `sync: false`. `PUBLIC_BASE_URL` debe coincidir con la URL HTTPS asignada al
servicio. El arranque valida el entorno, crea de forma idempotente las tablas y
despues inicia Gunicorn.

Una vez validada la infraestructura, la rama del servicio puede cambiarse de
`develop` a `main` como promocion estable.

## Despliegue manual aprobado

Mientras `main` conserva el respaldo anterior al despliegue, el workflow se
inicia mediante una etiqueta sobre la punta actual de `develop`:

```bash
git switch develop
git pull origin develop
git tag deploy-develop-YYYYMMDD-HHMM
git push origin deploy-develop-YYYYMMDD-HHMM
```

La ejecucion espera la aprobacion del Environment `production`. Cuando el
workflow exista tambien en la rama predeterminada, puede iniciarse con
`Run workflow`, eligiendo la rama y escribiendo `DESPLEGAR`.

El workflow vuelve a ejecutar las pruebas, publica el worker en GHCR, transfiere
solo los archivos de control, inicia exclusivamente el proyecto Compose del
usuario, espera su healthcheck y valida `/health/live` y `/health/ready` de la
web. Al finalizar conserva un artefacto no sensible llamado
`deployment-evidence`.

## Parametros de produccion

- 200 pasos de simulacion.
- 3 realizaciones.
- 500 particulas etiquetadas para Cv/MDC.
- 30 hilos Julia y limite de 30 CPU autorizado para el contenedor.
- Sin limite artificial de tiempo (`SIMULATION_TIMEOUT_SECONDS=0`).
- Tiempos de salida `0,200`.

## Operacion y recuperacion

Consultar el estado sin modificar el worker:

```bash
bash ~/apps/prototipo-mamografia/current/deploy/remote-worker.sh \
  status _ _
```

Revertir manualmente a la entrega anterior:

```bash
bash ~/apps/prototipo-mamografia/current/deploy/remote-worker.sh \
  rollback _ _
```

El rollback solo reemplaza el servicio `worker` del proyecto Compose del
usuario. La base de datos y los archivos definitivos permanecen en los
proveedores externos.

## Operacion local de contingencia

`deploy/worker.sh` permanece disponible para construir y validar el worker
manualmente desde una copia completa del repositorio:

```bash
bash deploy/worker.sh config
bash deploy/worker.sh build
bash deploy/worker.sh test
bash deploy/worker.sh start
bash deploy/worker.sh status
bash deploy/worker.sh logs
```

En un equipo con menos de 30 CPU se puede reducir el limite solo para la prueba
local:

```bash
SIMULATION_CPU_THREADS=8 WORKER_CPU_LIMIT=8 bash deploy/worker.sh test
```
