from fastapi import APIRouter, Depends, Header, Request

from app.schemas.query import QueryRequest, QueryResponse
from app.services.rag_service import RAGService

router = APIRouter(prefix="/v1", tags=["query"])


def get_service(request: Request) -> RAGService:
    """Hand each request the one shared service created at startup."""
    return request.app.state.rag_service


@router.post("/query", response_model=QueryResponse, summary="Ask a grounded policy question")
def query(
    req: QueryRequest,
    x_tenant_id: str = Header(
        default="acme",
        pattern=r"^[a-z0-9-]{1,64}$",
        description="Tenant (company) ID. Demo only: in production it comes from the verified login token.",
    ),
    service: RAGService = Depends(get_service),
) -> QueryResponse:
    return service.answer(req, x_tenant_id)