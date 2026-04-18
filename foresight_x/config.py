"""Runtime configuration from environment."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    tavily_api_key: str = Field(default="", validation_alias="TAVILY_API_KEY")

    chroma_persist_dir: Path = Field(
        default=Path("./data/chroma"),
        validation_alias="CHROMA_PERSIST_DIR",
    )

    foresight_user_id: str = Field(default="demo_user", validation_alias="FORESIGHT_USER_ID")
    foresight_data_dir: Path = Field(default=Path("./data"), validation_alias="FORESIGHT_DATA_DIR")

    # LlamaIndex uses OpenAI-compatible APIs for chat + embeddings (RAG still uses LlamaIndex + Chroma).
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", validation_alias="OPENAI_MODEL")
    openai_embedding_model: str = Field(
        default="text-embedding-3-small",
        validation_alias="OPENAI_EMBEDDING_MODEL",
    )
    openai_api_base: str | None = Field(default=None, validation_alias="OPENAI_API_BASE")

    @property
    def memory_dir(self) -> Path:
        return self.foresight_data_dir / "memory"

    @property
    def world_cache_dir(self) -> Path:
        return self.foresight_data_dir / "world_cache"

    @property
    def traces_dir(self) -> Path:
        return self.foresight_data_dir / "traces"

    @property
    def outcomes_dir(self) -> Path:
        return self.foresight_data_dir / "outcomes"


def load_settings() -> Settings:
    return Settings()
