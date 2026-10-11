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
| `APP_VERSION` | No (por defecto `1.0.0`) | Versión que reporta `GET /health`. Sirve para verificar qué versión está desplegada. |
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

## Pruebas

Las pruebas usan una base de datos SQLite en memoria, por lo que no requieren PostgreSQL:

```bash
pytest
```

## Despliegue en Elastic Beanstalk

- Elastic Beanstalk ejecuta el objeto `application` del archivo `application.py` con gunicorn.
- Configurar `JWT_SECRET_KEY` y `APP_VERSION` como propiedades de entorno del ambiente.
- Si la base de datos RDS está asociada al ambiente, Elastic Beanstalk inyecta las variables `RDS_*`; si es externa, definir `DATABASE_URL`.
- Usar `/health` como ruta del health check.
