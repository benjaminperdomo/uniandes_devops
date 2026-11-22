# Microservicio de lista negra global de emails

API REST para gestionar la lista negra global de emails de la organización. Permite que los sistemas internos agreguen emails a la lista negra y consulten si un email se encuentra en ella.

Está construida con Python, Flask, Flask-SQLAlchemy, Flask-RESTful, Flask-Marshmallow, Flask-JWT-Extended, Werkzeug y PostgreSQL, y se despliega como contenedor en AWS Fargate (Amazon ECS), detrás de un Application Load Balancer, con una base de datos en Amazon RDS.

## Estructura del proyecto

```
.
├── application.py          # Punto de entrada WSGI (objeto `application` que ejecuta gunicorn)
├── app/
│   ├── __init__.py         # Application factory y comando para generar el token
│   ├── config.py           # Configuración a partir de variables de entorno
│   ├── extensions.py       # Instancias de SQLAlchemy, Marshmallow y JWT
│   ├── models.py           # Modelos de base de datos
│   └── resources/          # Recursos de Flask-RESTful (endpoints)
├── tests/                  # Pruebas con pytest
├── Dockerfile              # Imagen de la aplicación (etapas base, test y runtime)
├── buildspec.yml           # Build de AWS CodeBuild (pruebas en la imagen y publicación en ECR)
├── taskdef.json            # Definición de la tarea de Amazon ECS (AWS Fargate)
├── appspec.json            # Despliegue Blue/Green de AWS CodeDeploy
├── docker-compose.yml      # Ambiente local: PostgreSQL y la aplicación con el agente de New Relic
├── requirements.txt        # Dependencias de la aplicación
└── requirements-dev.txt    # Dependencias de desarrollo y pruebas
```

## Requisitos

- Python 3.12 o superior (la imagen del contenedor usa Python 3.14)
- Docker y Docker Compose (para el ambiente local con contenedores)

## Instalación

```bash
python -m venv .venv
# Linux / macOS
source .venv/bin/activate
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

pip install -r requirements-dev.txt
cp .env.example .env
```

## Variables de entorno

| Variable | Obligatoria | Descripción |
|---|---|---|
| `JWT_SECRET_KEY` | Sí | Clave con la que se firma y valida el token JWT. Debe tener al menos 32 caracteres. |
| `DATABASE_URL` | Sí, si no se usan las variables `RDS_*` | URL de conexión a PostgreSQL, por ejemplo `postgresql://usuario:clave@host:5432/base`. |
| `RDS_HOSTNAME`, `RDS_PORT`, `RDS_DB_NAME`, `RDS_USERNAME`, `RDS_PASSWORD` | Sí, si no se usa `DATABASE_URL` | Datos de conexión a Amazon RDS. En AWS Fargate los define [taskdef.json](taskdef.json); `RDS_PASSWORD` se lee de Parameter Store. Se usan solo si `DATABASE_URL` no está definida. La conexión espera como máximo 5 segundos. |
| `APP_VERSION` | No | Versión que reporta `GET /health`. Si no se define, se lee del archivo `VERSION` incluido en la imagen. En AWS Fargate no se define, para que la versión desplegada sea la de la imagen. |
| `PROXY_FIX_X_FOR` | No (por defecto `1`) | Número de proxies delante de la aplicación usados para obtener la IP real del cliente desde `X-Forwarded-For`. En AWS Fargate hay un solo proxy: el balanceador de carga. En local, sin proxy, usar `0`. |
| `NEW_RELIC_LICENSE_KEY` | No | License key de New Relic (tipo *INGEST - LICENSE*). Sin ella el agente queda inactivo y la aplicación funciona normalmente. En local se toma del archivo `.env`; nunca se versiona. |
| `NEW_RELIC_APP_NAME` | No | Nombre de la aplicación en New Relic. En local lo define [docker-compose.yml](docker-compose.yml): `blacklist-api-dev`. |

Las tablas se crean automáticamente al iniciar la aplicación.

## Ejecución local

### Con contenedores (recomendada)

Levanta PostgreSQL y la aplicación con la misma imagen que se despliega en AWS Fargate (etapa `runtime` del [Dockerfile](Dockerfile): gunicorn con el agente de New Relic) y los mismos recursos de la tarea: 0,25 vCPU y 512 MB.

1. Crear el archivo `.env` a partir de [.env.example](.env.example) y definir `JWT_SECRET_KEY` y, para enviar datos a New Relic, `NEW_RELIC_LICENSE_KEY`.

2. Construir y levantar los servicios:

   ```bash
   docker compose up -d --build
   ```

3. Verificar el estado del servicio:

   ```bash
   curl http://localhost:8000/health
   ```

   ```json
   {"status": "ok", "version": "1.2.0"}
   ```

4. Generar el token dentro del contenedor (usa la `JWT_SECRET_KEY` del `.env`):

   ```bash
   docker compose exec app flask --app application generate-token
   ```

Para ver los logs de la aplicación y del agente se usa `docker compose logs -f app`, y para detener el ambiente, `docker compose down`.

### Sin contenedor para la aplicación

1. Levantar solo PostgreSQL:

   ```bash
   docker compose up -d db
   ```

2. Ejecutar la aplicación con el servidor de desarrollo de Flask (lee las variables del archivo `.env`):

   ```bash
   flask --app application run
   ```

3. Verificar el estado del servicio:

   ```bash
   curl http://localhost:5000/health
   ```

En este modo el agente de New Relic no está activo.

## Generación del token

Los endpoints de la lista negra requieren un token estático de tipo Bearer. Es un JWT sin expiración firmado con `JWT_SECRET_KEY`, por lo que el token debe generarse con la misma clave configurada en el ambiente donde se va a usar:

```bash
flask --app application generate-token
```

Opcionalmente se puede indicar el sujeto del token con `--identity`. El token se envía en el encabezado `Authorization: Bearer <token>`.

## Uso de la API

En los ejemplos se asume la aplicación en `http://localhost:5000` y el token en la variable `TOKEN`:

```bash
TOKEN=$(flask --app application generate-token)
```

### POST `/blacklists`

Agrega un email a la lista negra global.

| Campo | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `email` | String | Sí | Email a bloquear. Debe tener un formato válido. |
| `app_uuid` | String | Sí | Identificador (UUID) de la aplicación cliente. |
| `blocked_reason` | String | No | Motivo del bloqueo, máximo 255 caracteres. |

```bash
curl -X POST http://localhost:5000/blacklists \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"email": "cliente@example.com", "app_uuid": "6f1c2a3e-8b4d-4f5a-9c7e-1d2b3c4d5e6f", "blocked_reason": "Solicitud del cliente"}'
```

Respuesta `201 Created`:

```json
{"message": "Email added to the blacklist", "email": "cliente@example.com"}
```

| Código | Caso |
|---|---|
| `201` | El email se agregó a la lista negra. |
| `400` | La validación falló; el campo `errors` trae el detalle por campo. |
| `401` | El token no se envió o es inválido. |
| `409` | El email ya está en la lista negra. |
| `413` | El cuerpo de la petición supera 16 KB. |

Ejemplo de respuesta `400 Bad Request`:

```json
{"message": "Validation error", "errors": {"app_uuid": ["Not a valid UUID."]}}
```

### GET `/blacklists/<email>`

Consulta si un email está en la lista negra global y el motivo por el que fue agregado.

```bash
curl http://localhost:5000/blacklists/cliente@example.com \
  -H "Authorization: Bearer $TOKEN"
```

Respuesta `200 OK` si el email está en la lista:

```json
{"is_blacklisted": true, "blocked_reason": "Solicitud del cliente"}
```

Respuesta `200 OK` si no está:

```json
{"is_blacklisted": false, "blocked_reason": null}
```

Responde `401 Unauthorized` si el token no se envió o es inválido.

Los emails se almacenan y consultan sin distinguir mayúsculas de minúsculas.

Si ocurre un error inesperado (por ejemplo, la base de datos no responde), cualquier endpoint responde `500` con `{"message": "Internal server error"}` y el detalle queda en el log del contenedor (Amazon CloudWatch Logs, grupo `/ecs/blacklist-task`).

## Pruebas

Las pruebas usan una base de datos SQLite en memoria, por lo que no requieren PostgreSQL:

```bash
pytest
```

## Integración continua (AWS CodeBuild y contenedores)

Cada commit en `main` dispara un pipeline de AWS CodePipeline que ejecuta AWS CodeBuild con el archivo [buildspec.yml](buildspec.yml):

1. Construye la etapa `test` del [Dockerfile](Dockerfile) y ejecuta las pruebas dentro del contenedor, publicando el informe `reports/junit.xml` (JUnit).
2. Si las pruebas pasan, construye la etapa `runtime` (Python 3.14, gunicorn en el puerto 8000, usuario sin privilegios) y publica la imagen en Amazon ECR con la etiqueta del commit y `latest`.
3. Genera los artefactos de despliegue: `imageDetail.json` (URI de la imagen publicada), `taskdef.json` y `appspec.json`. El pipeline `blacklist-cd-pipeline` los usa para desplegar automáticamente en Amazon ECS (Blue/Green) sobre AWS Fargate; ver [Entrega continua en AWS Fargate](#entrega-continua-en-aws-fargate-codedeploy-bluegreen).

Si alguna prueba falla, el build falla y la imagen no se publica. El proyecto de CodeBuild necesita el modo privilegiado y la variable de entorno `ECR_REPOSITORY_URI`.

Para reproducir localmente el paso de pruebas del build (requiere Docker):

```bash
docker build --target test -t blacklist-service:test .
docker run --rm -v "$PWD/reports:/app/reports" blacklist-service:test
```

## Pruebas con Postman

La carpeta [postman/](postman) contiene la colección (12 escenarios de prueba con su documentación y pruebas automáticas) y el environment para probar la API desplegada. Se importan en Postman, se configura `base_url` con el dominio del ambiente y `token` con el token generado para ese ambiente, y se ejecutan en orden o con el Collection Runner.

## Entrega continua en AWS Fargate (CodeDeploy Blue/Green)

El pipeline `blacklist-cd-pipeline` de AWS CodePipeline tiene tres etapas: **Source** (GitHub, rama `main`), **Build** (AWS CodeBuild) y **Deploy** (AWS CodeDeploy, Amazon ECS Blue/Green sobre AWS Fargate). La etapa Deploy solo se ejecuta si el Build termina bien, es decir, si las pruebas pasan.

Archivos que usa el despliegue:

| Archivo | Para qué sirve |
|---|---|
| [buildspec.yml](buildspec.yml) | Ejecuta las pruebas, construye y publica la imagen en Amazon ECR y genera `imageDetail.json` como artefacto de salida. |
| [taskdef.json](taskdef.json) | Definición de la tarea de ECS (Fargate): contenedor `blacklist-api`, puerto 8000, variables de entorno y secretos desde AWS Systems Manager Parameter Store. La imagen es el marcador `<IMAGE1_NAME>`, que CodePipeline reemplaza con la URI del `imageDetail.json`. |
| [appspec.json](appspec.json) | Indica a CodeDeploy qué contenedor y puerto recibe el tráfico del balanceador. El marcador `<TASK_DEFINITION>` lo reemplaza CodePipeline. |

Los secretos (`JWT_SECRET_KEY` y `RDS_PASSWORD`) no están en el repositorio: la tarea los lee de Parameter Store (`/blacklist/JWT_SECRET_KEY` y `/blacklist/RDS_PASSWORD`). Detrás del balanceador de carga hay un solo proxy, por eso `PROXY_FIX_X_FOR` vale `1`. El balanceador usa `/health` como ruta del health check.

Las entregas 1 y 2 se desplegaron en AWS Elastic Beanstalk; ese ambiente ya no existe.

## Monitoreo con New Relic

La aplicación se instrumenta con el agente de New Relic para Python (`newrelic` en [requirements.txt](requirements.txt)). La imagen de ejecución arranca gunicorn con `newrelic-admin run-program`, que instrumenta Flask, las peticiones HTTP y las consultas a PostgreSQL sin cambios en el código.

El agente se configura solo con variables de entorno:

| Variable | Dónde se define | Valor |
|---|---|---|
| `NEW_RELIC_LICENSE_KEY` | `.env` (local); Parameter Store `/blacklist/NEW_RELIC_LICENSE_KEY` (AWS Fargate, vía [taskdef.json](taskdef.json)) | License key de la cuenta (secreto, no se versiona) |
| `NEW_RELIC_APP_NAME` | [docker-compose.yml](docker-compose.yml) (local); [taskdef.json](taskdef.json) (AWS Fargate) | `blacklist-api-dev` en local, `blacklist-api-prod` en AWS Fargate |
| `NEW_RELIC_LOG`, `NEW_RELIC_LOG_LEVEL` | [Dockerfile](Dockerfile) | `stdout`, `info`: el log del agente sale con el de la aplicación |
| `NEW_RELIC_DISTRIBUTED_TRACING_ENABLED` | [Dockerfile](Dockerfile) | `true` |

Al levantar el ambiente local, el log del agente muestra la conexión con New Relic y, uno o dos minutos después de recibir peticiones, la aplicación `blacklist-api-dev` aparece en **APM & Services**. También se puede verificar con NRQL:

```sql
SELECT count(*) FROM Transaction WHERE appName = 'blacklist-api-dev' FACET name SINCE 30 minutes ago
```

En AWS Fargate el pipeline `blacklist-cd-pipeline` despliega la misma imagen; la tarea lee la license key de Parameter Store (el rol `blacklist-ecs-task-execution-role` tiene permiso `ssm:GetParameters` sobre ese parámetro) y reporta como `blacklist-api-prod`.
