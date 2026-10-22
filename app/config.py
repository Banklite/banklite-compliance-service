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

settings = Settings()
