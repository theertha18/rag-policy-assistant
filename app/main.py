import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from tenacity import retry, stop_after_attempt, wait_fixed

from app.api.routes_health import router as health_router
from app.api.routes_query import router as query_router
from app.config import settings
from app.generation.llm_client import OpenAICompatibleClient
from app.ingestion.pipeline import ingest_directory
from app.retrieval.embeddings import Embedder
from app.retrieval.reranker import Reranker
from app.retrieval.vector_store import VectorStore
from app.services.rag_service import LLMUnavailable, RAGService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)  # hide noisy per-request HTTP logs
log = logging.getLogger("app")


@retry(stop=stop_after_attempt(30), wait=wait_fixed(1), reraise=True)
def wait_for_qdrant(store: VectorStore) -> None:
    """Qdrant may still be starting (especially in Docker), so retry for up to 30 seconds."""
    store.client.get_collections()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail fast with a clear message instead of a confusing error at the first question
    if not settings.llm_api_key:
        raise RuntimeError("LLM_API_KEY is not set. Copy .env.example to .env and add your key.")

    embedder = Embedder(settings.dense_model, settings.sparse_model)
    store = VectorStore(settings.qdrant_url, settings.collection)
    wait_for_qdrant(store)
    store.ensure_collection()
    if store.count() == 0:
        n = ingest_directory(settings.data_dir, settings.default_tenant, embedder, store)
        log.info("Ingested %d chunks", n)

    app.state.store = store
    app.state.rag_service = RAGService(
        embedder=embedder,
        store=store,
        reranker=Reranker(settings.rerank_model),
        llm=OpenAICompatibleClient(settings.llm_api_key, settings.llm_model, settings.llm_base_url),
        settings=settings,
    )
    log.info("Ready: %d chunks indexed, model=%s", store.count(), settings.llm_model)
    yield


app = FastAPI(
    title="Policy RAG API",
    version="1.0.0",
    description="Grounded answers over company policy documents, with citations and deterministic refusal.",
    lifespan=lifespan,
)
app.include_router(health_router)
app.include_router(query_router)


@app.exception_handler(LLMUnavailable)
async def llm_unavailable_handler(request: Request, exc: LLMUnavailable) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": "The language model is temporarily unavailable. Please retry."})