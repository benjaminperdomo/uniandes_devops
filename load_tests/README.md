# Pruebas de carga — entrega 4

Preparadas el 27 de noviembre de 2026. **No ejecutadas contra la API.**
Se revisó el checkout local c7cd1bc y los endpoints de `main` en
https://github.com/benjaminperdomo/uniandes_devops. La copia local es anterior
a la integración de New Relic; no se hizo pull ni se reemplazó código de la aplicación.

## Escenarios propuestos

| Escenario | Duración | Usuarios concurrentes por etapa |
|---|---:|---|
| normal | 8 min | 2 (1 min), 5 (6 min), 2 (1 min) |
| stress | 15 min | 5 (1 min), 10 (2 min), 25 (2 min), 50 (2 min), 100 (6 min), 5 (2 min) |
| errors | 9 min | 5 (1 min normal), 10 (6 min errores), 5 (2 min recuperación) |

Son valores iniciales para el laboratorio, no una capacidad garantizada ni una
prueba ya calibrada. Entre tareas hay una pausa aleatoria de 1–3 segundos; usuarios
concurrentes no equivale a solicitudes por segundo. Las respuestas lentas reducen
el ritmo efectivo. No se sube de 100 usuarios automáticamente.

Normal y estrés: 90% de tareas consulta `GET /blacklists/<email>` (BD) y 10%
consulta `/health`. Cada usuario crea al iniciar una fila sintética mediante
`POST /blacklists`, y comprueba luego su contenido. Las escrituras de preparación
quedan identificadas como `SETUP` en las estadísticas; se deben excluir al analizar
el tramo estable. En una ejecución completa se crean aproximadamente 5, 100 y 10
filas respectivamente. No hay endpoint DELETE: los datos permanecen en la BD y
se identifican por `blocked_reason = Synthetic Locust entrega4 <run_id>` y
correos `load-<uuid>@example.com`. No se borran datos automáticamente.

Errores: durante los seis minutos centrales, 30% de tareas envía JSON inválido
(400), 20% omite el token (401), 40% consulta BD correctamente y 10% consulta salud.
No se modifica la aplicación, no se apaga RDS y no se provocan excepciones 500.
Los errores esperados siguen apareciendo como fallos de Locust con prefijo
`INTENTIONAL_HTTP_`; `run.json` separa fallos esperados e inesperados.

**Límite importante de New Relic:** la alerta configurada usa
`percentage(count(*), WHERE error IS true)`. Un 400/401 esperado no necesariamente
se registra como error APM. Esta corrida verifica respuestas fallidas y su
observabilidad, pero NO garantiza incidentes/correos. Para demostrar esa alerta
hay que confirmar primero qué errores registra el agente o acordar un mecanismo
controlado de fallo de servidor en un ambiente de pruebas. No se debe cambiar la
consulta ni atribuir errores 500 a estas solicitudes sin evidencia.

## Instalación (Python 3.11 o superior)

Desde esta carpeta:

```sh
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

El token debe ser un JWT válido firmado con la clave del ambiente objetivo.
La API no expone un login HTTP. No guardar JWT ni claves en Git, capturas o CSV.

## Revisar el plan sin enviar tráfico

```sh
python run.py normal --host http://blacklist-alb-252943503.us-east-2.elb.amazonaws.com
python run.py stress --host http://blacklist-alb-252943503.us-east-2.elb.amazonaws.com
python run.py errors --host http://blacklist-alb-252943503.us-east-2.elb.amazonaws.com
```

Este host proviene del monitor de New Relic revisado; confirmar que siga siendo
el ambiente acordado antes de la ejecución. No está fijado en el script.

## Ejecución futura, cuando el grupo confirme disponibilidad

En zsh, introducir el JWT sin mostrarlo ni guardarlo en el historial:

```sh
read -rs 'BLACKLIST_TOKEN?JWT del ambiente: '
export BLACKLIST_TOKEN
printf '\n'
python run.py normal --host http://blacklist-alb-252943503.us-east-2.elb.amazonaws.com --execute
```

Abrir http://127.0.0.1:8089 y pulsar **Start**. El perfil controla usuarios,
Si no se configuró BLACKLIST_TOKEN, introducir el JWT en el campo protegido
**Blacklist token** de la interfaz antes de Start. No introducirlo como argumento CLI.
ritmo de ingreso y final automático. `--execute` abre la interfaz pero NO inicia
la carga por sí solo. No usar autostart, headless ni workers distribuidos.
Una corrida por lanzamiento. Al terminar, guardar capturas y pulsar Ctrl+C para
cerrar Locust y generar el HTML. Repetir con `stress` y `errors`, dejando entre
corridas al menos 5 minutos y esperando recuperación de las métricas/alertas.
Al finalizar todas: `unset BLACKLIST_TOKEN`.

Ante degradación que afecte a compañeros, detener con **Stop**; Ctrl+C termina
el proceso. No continuar a estrés si normal falla en autenticación o setup.
El script detiene la corrida si un request normal devuelve 401/422 o falla la
creación de su dato de prueba; es un problema de preparación, no capacidad.

## Evidencia y análisis

Resultados: `results/<fechaUTC>-<escenario>/`: CSV de estadísticas, historial,
fallos, excepciones, `report.html` al cerrar y `run.json` con inicio/fin UTC,
host, etapas, run_id y contadores. No contiene el JWT ni cuerpos de respuesta.

Para cada corrida:
1. Antes de Start: captura del escenario y host, sin token visible.
2. En el tramo estable/máxima carga: capturas **Statistics**, **Charts** y
   **Failures** de Locust mostrando usuarios, RPS, p95/p99 y tasa de fallos.
3. Al finalizar: estadísticas y archivos exportados antes de cerrar.
4. En New Relic, seleccionar exactamente el inicio/fin UTC de `run.json`:
   resumen APM, Transactions, Databases, Apdex, Errors y dashboard.
5. Si aparece un incidente, capturar condición, umbral, hora de apertura/cierre
   y correo recibido. Si no aparece, reportarlo; no asumir que se generó.

Las marcas C09–C30 deben ajustarse al borrador del documento cuando esté disponible.
El correo d.jojoas@uniandes.edu.co estaba pendiente de verificación en la revisión.

## Validación offline (no hace llamadas HTTP)

```sh
python -m unittest -v test_offline.py
python -m locust -f locustfile.py --list
```

Prueba límites y finalización de etapas, host, bloqueo de arranque accidental,
validación de respuestas y separación de errores intencionales.

Referencia oficial: https://docs.locust.io/en/stable/configuration.html
API: https://docs.locust.io/en/stable/api.html
