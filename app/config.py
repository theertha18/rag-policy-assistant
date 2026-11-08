from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)

    llm_api_key: str = ""
    llm_base_url: str | None = None
    llm_model: str = "gemini-3.8-flash"

    qdrant_url: str = "http://localhost:6333"
    collection: str = "policies"
    data_dir: str = "data"

    dense_model: str = "BAAI/bge-small-en-v1.5"
    sparse_model: str = "Qdrant/bm25"
    rerank_model: str = "Xenova/ms-marco-MiniLM-L-6-v2"

    prefetch_k: int = 20
    top_k: int = 5
    min_rerank_score: float = -10.0 
    default_tenant: str = "acme"


settings = Settings()