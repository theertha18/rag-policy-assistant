import pytest

from app.retrieval.query_enrichment import enrich_query


@pytest.mark.parametrize("query, expected", [
    ("Laptop budget in Germany?", {"germany": "EMEA"}),
    ("laptop budget in germany?", {"germany": "EMEA"}),
    ("What is the US laptop cap?", {"US": "US / Canada"}),
    ("Office in Singapore", {"singapore": "APAC"}),
])
def test_countries_map_to_regions(query, expected):
    enriched, found = enrich_query(query)
    assert found == expected
    assert "(Region:" in enriched


@pytest.mark.parametrize("query", ["Can you tell us more?", "Parental leave?", "Is Germanyx a word?"])
def test_no_false_matches(query):
    enriched, found = enrich_query(query)
    assert found == {}
    assert enriched == query