from app.ingestion.chunker import chunk_document


def test_table_becomes_one_chunk_per_row(docs):
    chunks = chunk_document(docs["IT-SPEC-2025-A"], "acme", True)
    rows = [c for c in chunks if c.metadata["chunk_type"] == "table_row"]
    assert [c.metadata["section"] for c in rows] == [
        "Table row: US / Canada", "Table row: EMEA", "Table row: APAC",
    ]


def test_table_row_keeps_column_names_and_values(docs):
    chunks = chunk_document(docs["IT-SPEC-2025-A"], "acme", True)
    emea = next(c for c in chunks if c.metadata["section"] == "Table row: EMEA")
    assert "Laptop Allowance (Max): €1,800 EUR" in emea.text
    assert "Monthly Mobile Stipend: €60 EUR" in emea.text


def test_every_chunk_is_labelled_with_its_source(docs):
    for doc in docs.values():
        for chunk in chunk_document(doc, "acme", True):
            assert chunk.text.startswith(f"[{doc.doc_id}]")


def test_chunk_ids_are_stable_and_tenant_specific(docs):
    doc = docs["POLICY-2025-002"]
    first = [c.chunk_id for c in chunk_document(doc, "acme", True)]
    second = [c.chunk_id for c in chunk_document(doc, "acme", True)]
    other_tenant = [c.chunk_id for c in chunk_document(doc, "globex", True)]
    assert first == second                    # re-ingestion overwrites, never duplicates
    assert set(first).isdisjoint(other_tenant)  # tenants never share IDs


def test_currency_flag_is_stored_on_chunks(docs):
    chunks = chunk_document(docs["POLICY-2024-001"], "acme", False)
    assert chunks and all(c.metadata["is_current"] is False for c in chunks)