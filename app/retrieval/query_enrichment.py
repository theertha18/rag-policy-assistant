import re

# Full country names: matched case-insensitively ("germany", "Germany")
COUNTRY_TO_REGION = {
    "germany": "EMEA", "france": "EMEA", "united kingdom": "EMEA", "spain": "EMEA",
    "netherlands": "EMEA", "india": "APAC", "japan": "APAC", "singapore": "APAC",
    "australia": "APAC", "united states": "US / Canada", "canada": "US / Canada",
}

# Short codes: matched only in capitals, so "tell us" does not mean "US"
CODES = {"US": "US / Canada", "USA": "US / Canada", "UK": "EMEA"}


def enrich_query(query: str) -> tuple[str, dict[str, str]]:
    """Return (search_query, {country: region}). The search query gets the region appended."""
    found = {c: r for c, r in COUNTRY_TO_REGION.items() if re.search(rf"\b{c}\b", query, re.I)}
    found |= {c: r for c, r in CODES.items() if re.search(rf"\b{c}\b", query)}
    if not found:
        return query, {}
    regions = ", ".join(sorted(set(found.values())))
    return f"{query} (Region: {regions})", found