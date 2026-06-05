"""Application settings loaded from environment / .env."""
from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # OpenAI
    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    openai_chat_model: str = Field("gpt-4o-mini", alias="OPENAI_CHAT_MODEL")
    openai_embedding_model: str = Field(
        "text-embedding-3-small", alias="OPENAI_EMBEDDING_MODEL"
    )
    openai_embedding_dim: int = Field(1536, alias="OPENAI_EMBEDDING_DIM")

    azure_openai_tenant_id: str = Field(1536, alias="AZURE_OPENAI_TENANT_ID")
    azure_openai_client_id: str = Field(..., alias="AZURE_OPENAI_CLIENT_ID")
    azure_openai_client_secret: str = Field(..., alias="AZURE_OPENAI_CLIENT_SECRET")
    azure_openai_api_version: str = Field("2024-02-15-preview", alias="AZURE_OPENAI_API_VERSION")
    azure_openai_deployment_name: str = Field("gpt-4", alias="AZURE_OPENAI_DEPLOYMENT_NAME")
    azure_openai_endpoint: str = Field(..., alias="AZURE_OPENAI_ENDPOINT")
    azure_openai_deployment_url: str = Field(..., alias="AZURE_OPENAI_DEPLOYMENT_URL")
    azure_openai_embedding_deployment_name: str = Field(
        "text-embedding-3-small", alias="AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME"
    )

    # OpenSearch
    opensearch_url: str = Field("http://localhost:9200", alias="OPENSEARCH_URL")
    opensearch_user: str = Field("", alias="OPENSEARCH_USER")
    opensearch_password: str = Field("", alias="OPENSEARCH_PASSWORD")
    opensearch_index: str = Field("chatbot-docs", alias="OPENSEARCH_INDEX")
    opensearch_use_ssl: bool = Field(False, alias="OPENSEARCH_USE_SSL")
    opensearch_verify_certs: bool = Field(False, alias="OPENSEARCH_VERIFY_CERTS")

    # Redis
    redis_url: str = Field("redis://localhost:6379/0", alias="REDIS_URL")

    # MCP
    mcp_servers_config: str = Field("", alias="MCP_SERVERS_CONFIG")

    # App
    app_env: str = Field("dev", alias="APP_ENV")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    cors_origins: str = Field("http://localhost:5173", alias="CORS_ORIGINS")

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
