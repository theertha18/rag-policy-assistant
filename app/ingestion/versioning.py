from app.ingestion.loader import ParsedDoc


def resolve_currency(docs: list[ParsedDoc]) -> dict[str, bool]:
    """Return {doc_id: is_current}. A document is current unless another document supersedes it."""
    superseded = {old_id for doc in docs for old_id in doc.supersedes}
    return {doc.doc_id: doc.doc_id not in superseded for doc in docs}