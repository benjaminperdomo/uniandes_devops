# Microservicio de lista negra global de emails

API REST para gestionar la lista negra global de emails de la organización. Permite que los sistemas internos agreguen emails a la lista negra y consulten si un email se encuentra en ella.

Está construida con Python, Flask, Flask-SQLAlchemy, Flask-RESTful, Flask-Marshmallow, Flask-JWT-Extended, Werkzeug y PostgreSQL, y está preparada para desplegarse en AWS Elastic Beanstalk con una base de datos en Amazon RDS.

## Estructura del proyecto

```
.
├── application.py          # Punto de entrada WSGI (objeto `application` para Elastic Beanstalk)
├── app/
│   ├── __init__.py         # Application factory y comando para generar el token
│   ├── config.py           # Configuración a partir de variables de entorno
│   ├── extensions.py       # Instancias de SQLAlchemy, Marshmallow y JWT
│   ├── models.py           # Modelos de base de datos
│   └── resources/          # Recursos de Flask-RESTful (endpoints)
├── tests/                  # Pruebas con pytest
├── Dockerfile              # Imagen de la aplicación (etapas base, test y runtime)
├── buildspec.yml           # Build de AWS CodeBuild (pruebas en la imagen y publicación en ECR)
├── docker-compose.yml      # PostgreSQL para desarrollo local
├── requirements.txt        # Dependencias de la aplicación
└── requirements-dev.txt    # Dependencias de desarrollo y pruebas
```

## Requisitos

- Python 3.12 o superior
- Docker y Docker Compose (para la base de datos local)

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
| `RDS_HOSTNAME`, `RDS_PORT`, `RDS_DB_NAME`, `RDS_USERNAME`, `RDS_PASSWORD` | Sí, si no se usa `DATABASE_URL` | Datos de conexión que Elastic Beanstalk inyecta cuando la base de datos RDS está asociada al ambiente. Se usan solo si `DATABASE_URL` no está definida. |
| `APP_VERSION` | No | Versión que reporta `GET /health`. Si no se define, se lee del archivo `VERSION` incluido en el paquete. En Elastic Beanstalk se recomienda no definirla, para que la versión desplegada sea la del paquete. |
| `PROXY_FIX_X_FOR` | No (por defecto `2`) | Número de proxies delante de la aplicación usados para obtener la IP real del cliente desde `X-Forwarded-For`. En Elastic Beanstalk con balanceador son 2 (balanceador + nginx). |

Las tablas se crean automáticamente al iniciar la aplicación.

## Ejecución local

1. Levantar PostgreSQL:

   ```bash
   docker compose up -d
   ```

2. Ejecutar la aplicación (lee las variables del archivo `.env`):

   ```bash
   flask --app application run
   ```

3. Verificar el estado del servicio:

   ```bash
   curl http://localhost:5000/health
   ```

   ```json
   {"status": "ok", "version": "1.0.0"}
   ```

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

## Pruebas

Las pruebas usan una base de datos SQLite en memoria, por lo que no requieren PostgreSQL:

```bash
pytest
```

## Integración continua (AWS CodeBuild y contenedores)

Cada commit en `main` dispara un pipeline de AWS CodePipeline que ejecuta AWS CodeBuild con el archivo [buildspec.yml](buildspec.yml):

1. Construye la etapa `test` del [Dockerfile](Dockerfile) y ejecuta las pruebas dentro del contenedor, publicando el informe `reports/junit.xml` (JUnit).
2. Si las pruebas pasan, construye la etapa `runtime` (Python 3.14, gunicorn en el puerto 8000, usuario sin privilegios) y publica la imagen en Amazon ECR con la etiqueta del commit y `latest`.
3. Genera `Dockerrun.aws.json`, el descriptor para la plataforma Docker de Elastic Beanstalk. No hay despliegue automático.

Si alguna prueba falla, el build falla y la imagen no se publica. El proyecto de CodeBuild necesita el modo privilegiado y la variable de entorno `ECR_REPOSITORY_URI`.

Para reproducir localmente el paso de pruebas del build (requiere Docker):

```bash
docker build --target test -t blacklist-service:test .
docker run --rm -v "$PWD/reports:/app/reports" blacklist-service:test
```

## Pruebas con Postman

La carpeta [postman/](postman) contiene la colección (12 escenarios de prueba con su documentación y pruebas automáticas) y el environment para probar la API desplegada. Se importan en Postman, se configura `base_url` con el dominio del ambiente y `token` con el token generado para ese ambiente, y se ejecutan en orden o con el Collection Runner.

## Despliegue en Elastic Beanstalk

- Elastic Beanstalk ejecuta el objeto `application` del archivo `application.py` con gunicorn.
- Configurar `JWT_SECRET_KEY` como propiedad de entorno del ambiente. La versión que reporta `/health` sale del archivo `VERSION` del paquete.
- Si la base de datos RDS está asociada al ambiente, Elastic Beanstalk inyecta las variables `RDS_*`; si se creó por separado, definir las variables `RDS_*` manualmente o `DATABASE_URL`.
- Usar `/health` como ruta del health check.
