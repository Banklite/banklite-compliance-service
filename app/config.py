from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "compliance-service"
    api_port: int = 8008

    database_url: str = (
        "postgresql+psycopg2://banklite:banklite@compliance-db:5432/compliance_db"
    )

    # Screening AML/PEP: OpenSanctions (2.000 creditos gratis) o OFAC SDN sin credenciales.
    # La variable de entorno se llama OPEN_SANCTIONS_API_KEY (con guion bajo), por eso
    # lleva validation_alias: sin el alias pydantic buscaria OPENSANCTIONS_API_KEY y
    # la clave nunca se cargaria (quedaria en el respaldo OFAC sin avisar).
    opensanctions_api_key: str | None = Field(
        default=None, validation_alias="OPEN_SANCTIONS_API_KEY"
    )

    # Resolucion del titular de una cuenta (REST sincrono hacia account-service)
    account_service_url: str = "http://account-service:8002"

    # Regla AML: toda transferencia igual o superior a este monto se marca para revision
    aml_umbral_monto: float = 10_000_000.0

    # Bus de eventos (RabbitMQ). Apagado por defecto: se activa con ENABLE_CONSUMER=true.
    rabbitmq_url: str = "amqp://banklite:banklite@rabbitmq:5672/"
    events_exchange: str = "banklite.events"
    events_queue: str = "compliance.events"
    enable_consumer: bool = False

settings = Settings()
