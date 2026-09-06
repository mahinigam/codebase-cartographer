from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore"
    )

    llm_provider: str = "gemini"
    fallback_llm_provider: str = "ollama"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-1.5-flash"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5-coder:7b"

    embedding_provider: str = "gemini"
    fallback_embedding_provider: str = "ollama"
    gemini_embedding_model: str = "text-embedding-004"
    ollama_embedding_model: str = "nomic-embed-text"
    embedding_dimensions: int = 768
    summary_max_files: int = 120
    summary_max_chars: int = 4000
    scan_max_files: int = 10000
    scan_rate_limit_per_minute: int = 6
    api_token: str | None = Field(default=None, repr=False)

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = Field(default="", repr=False)

    allowed_repo_roots_raw: str = Field(default="", alias="ALLOWED_REPO_ROOTS")
    cors_origins_raw: str = Field(default="http://localhost:5173", alias="CORS_ORIGINS")

    @property
    def allowed_repo_roots(self) -> list[str]:
        return [item.strip() for item in self.allowed_repo_roots_raw.split(",") if item.strip()]

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_origins_raw.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
