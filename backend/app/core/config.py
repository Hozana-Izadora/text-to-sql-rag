from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM Providers
    gemini_api_key: str = ""
    groq_api_key: str = ""

    # Banco de produção (read-only)
    production_db_host: str = "localhost"
    production_db_port: int = 5432
    production_db_name: str = "production"
    production_db_user: str = "querymind_readonly"
    production_db_password: str = ""

    # Banco de metadados (pgvector)
    metadata_db_host: str = "localhost"
    metadata_db_port: int = 5433
    metadata_db_name: str = "querymind_metadata"
    metadata_db_user: str = "querymind"
    metadata_db_password: str = ""

    # Criptografia de credenciais das conexões cadastradas (Fernet).
    encryption_secret_key: str = ""

    # Embeddings
    embedding_model: str = "intfloat/multilingual-e5-small"
    embedding_dimensions: int = 384

    # Frontend
    frontend_url: str = "http://localhost:3000"

    # App
    log_level: str = "INFO"
    sql_timeout_seconds: int = 30
    sql_max_rows: int = 500
    correction_max_retries: int = 3

    @property
    def production_db_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.production_db_user}:{self.production_db_password}"
            f"@{self.production_db_host}:{self.production_db_port}/{self.production_db_name}"
        )

    @property
    def metadata_db_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.metadata_db_user}:{self.metadata_db_password}"
            f"@{self.metadata_db_host}:{self.metadata_db_port}/{self.metadata_db_name}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
