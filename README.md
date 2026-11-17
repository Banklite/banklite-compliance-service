# Compliance & Analytics Service — BankLite

Cumplimiento AML (screening OFAC/OpenSanctions), monitoreo de operaciones sospechosas, reportes regulatorios, auditoria e indicadores para la direccion.

Parte del proyecto **BankLite** (banca digital con microservicios) de *Arquitectura y Modelamiento de Software*, Universidad Cooperativa de Colombia. Cada microservicio tiene su propio repositorio y su propia base de datos (`compliance_db`).

## Responsabilidad en la arquitectura

Cumplimiento AML (screening OFAC/OpenSanctions), monitoreo de operaciones sospechosas, reportes regulatorios, auditoria e indicadores para la direccion. Se comunica con los demas servicios por **REST** (operaciones que necesitan respuesta inmediata) y por **eventos** en RabbitMQ (exchange `banklite.events`, tipo topic).

| Eventos publicados | Eventos consumidos |
|---|---|
| — | `transfer.completed`, `fraud.alert` |

## Tecnologias

FastAPI, SQLAlchemy, PostgreSQL, RabbitMQ (pika). Externo: OpenSanctions / lista OFAC SDN. Python 3.12, Docker.

## Despliegue

- URL publica: <https://banklite-compliance-service.onrender.com>
- Salud: <https://banklite-compliance-service.onrender.com/health>
- Documentacion interactiva (Swagger): <https://banklite-compliance-service.onrender.com/docs>

Desplegado en Render (plan gratuito: tarda hasta ~1 minuto en responder si estuvo inactivo). Las credenciales se configuran como variables de entorno en la plataforma, no en el codigo.

## Endpoints principales

| Metodo | Ruta | Descripcion |
|---|---|---|
| `POST` | `/reportes` | Crea un reporte regulatorio |
| `GET` | `/reportes` | Lista reportes |
| `POST` | `/sospechosas` | Registra una transaccion sospechosa |
| `GET` | `/sospechosas` | Lista sospechosas (filtros por estado y riesgo) |
| `POST` | `/auditorias` | Registra una auditoria |
| `POST` | `/screenings` | Screening AML/PEP de una persona |
| `GET` | `/analytics/indicadores` | KPIs de cumplimiento |
| `GET` | `/analytics/transacciones-por-dia` | Serie diaria de transacciones |
| `GET` | `/health` | Estado del servicio |
| `GET` | `/stats` | Contadores del servicio |

La lista completa esta en `/docs`.

## Variables de entorno

Copia `.env.example` a `.env` y completa los valores.

| Variable | Descripcion |
|---|---|
| `DATABASE_URL` | Conexion PostgreSQL |
| `OPEN_SANCTIONS_API_KEY` | API key de OpenSanctions (si falta, usa OFAC SDN) |
| `ACCOUNT_SERVICE_URL` | URL de account-service (titular de la cuenta) |
| `AML_UMBRAL_MONTO` | Monto desde el cual una transferencia se marca para revision AML |
| `RABBITMQ_URL` | URL del bus de eventos |
| `EVENTS_QUEUE` | Cola propia |
| `ENABLE_CONSUMER` | Consumir eventos |

## Base de datos

Motor: PostgreSQL. Base: `compliance_db`.

- `db/schema.sql`: creacion de tablas, indices y restricciones.
- `db/seed.sql`: datos de ejemplo.

El servicio tambien crea las tablas solo al arrancar (`create_all`). Para restaurar a mano:

```bash
createdb compliance_db
psql -d compliance_db -f db/schema.sql
psql -d compliance_db -f db/seed.sql
```

Respaldo completo (para entregar o restaurar): `pg_dump -Fc compliance_db > compliance_db.dump` y `pg_restore -d compliance_db compliance_db.dump`.

## Instalacion y ejecucion

Con Docker:

```bash
docker build -t banklite-compliance-service .
docker run --env-file .env -p 8008:8008 -e PORT=8008 banklite-compliance-service
```

Sin Docker:

```bash
python -m venv .venv && source .venv/bin/activate   # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8008
```

Prueba: abre <http://localhost:8008/docs>.

## Pruebas automatizadas

```bash
pip install -r requirements-dev.txt
python -m pytest tests -v --cov=app --cov-report=term-missing --cov-report=html
```

No necesitan PostgreSQL, RabbitMQ ni los otros microservicios: la base es SQLite en memoria y las dependencias externas se reemplazan con mocks (`unittest.mock`). El reporte navegable queda en `htmlcov/index.html`.

| Tipo | Archivo | Que verifica |
|---|---|---|
| Unitaria (mocks) | `tests/unit/test_screening.py` | Screening de sanciones/PEP: normalizacion de nombres, coincidencias contra la lista OFAC, cache, respaldo cuando OpenSanctions falla (`httpx` simulado). |
| Integracion | `tests/integration/test_eventos_aml.py` | Evento `transfer.completed` -> regla AML por monto -> tablas `transaccion_monitoreada` y `transaccion_sospechosa`; idempotencia; evento `fraud.alert`. |
| Integracion | `tests/integration/test_compliance_api.py` | Reportes regulatorios, transacciones sospechosas, auditorias, screening e indicadores calculados desde la base. |

Resultado actual: **28 pruebas** (12 unitarias y 16 de integracion), todas aprobadas, con **90 % de cobertura** de `app/`.

En GitHub Actions las pruebas corren en cada `push` y `pull request`. Si una falla, la imagen no se construye y no se despliega. El reporte de cobertura queda en el resumen de la ejecucion y como artefacto descargable `coverage-banklite-compliance-service`.

## Repositorios del proyecto

`banklite-identity-service`, `banklite-account-service`, `banklite-ledger-service`, `banklite-transfer-service`, `banklite-card-service`, `banklite-fraud-service`, `banklite-notification-service`, `banklite-compliance-service`. Panel web: `services/web-panel` en el repositorio `banklite-microservicios`.
