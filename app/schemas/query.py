from enum import Enum

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """What the client sends."""
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=10)
    include_superseded: bool = False
    debug: bool = False


class AnswerStatus(str, Enum):
    ANSWERED = "answered"
    REFUSED = "refused"
    BLOCKED = "blocked"


class Citation(BaseModel):
    """One source backing the answer."""
    document_id: str
    title: str
    section: str
    relevance_score: float = Field(ge=0, le=1)
    snippet: str


class RetrievedChunk(BaseModel):
    """Retrieval details, returned only when debug=true."""
    document_id: str
    section: str
    relevance_score: float


class QueryResponse(BaseModel):
    """What the API returns."""
    status: AnswerStatus
    answer: str
    citations: list[Citation] = []
    refusal_reason: str | None = None
    trace_id: str
    latency_ms: int
    debug: list[RetrievedChunk] | None = None