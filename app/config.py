from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "compliance-service"
    api_port: int = 8008

    database_url: str = (
        "postgresql+psycopg2://banklite:banklite@compliance-db:5432/compliance_db"
    )

settings = Settings()
