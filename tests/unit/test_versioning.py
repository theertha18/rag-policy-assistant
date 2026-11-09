from app.ingestion.versioning import resolve_currency


def test_superseded_policy_is_not_current(docs):
    currency = resolve_currency(list(docs.values()))
    assert currency == {"POLICY-2024-001": False, "POLICY-2025-002": True, "IT-SPEC-2025-A": True}