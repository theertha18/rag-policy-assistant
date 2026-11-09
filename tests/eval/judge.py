JUDGE_SYSTEM = """You are a strict fact checker. You receive SOURCES and an ANSWER.
Split the ANSWER into short, atomic factual claims. Ignore polite phrasing and formatting.
For each claim, decide whether it is fully supported by the SOURCES.
Paraphrases of the sources count as supported. Anything not stated in the SOURCES is unsupported.
Respond with JSON only: {"claims": [{"claim": "...", "supported": true}]}"""


class FaithfulnessJudge:
    """LLM-as-a-judge: share of answer claims supported by the cited sources."""

    def __init__(self, llm):
        self.llm = llm

    def score(self, answer: str, contexts: list[str], region_map: dict[str, str]) -> tuple[float, list[str]]:
        """Returns (faithfulness between 0 and 1, list of unsupported claims)."""
        sources = "\n\n".join(f"[{i + 1}] {text}" for i, text in enumerate(contexts))
        if region_map:
            notes = "; ".join(f"{c.title() if c.islower() else c} is in region {r}" for c, r in region_map.items())
            sources += f"\n\n[company configuration] {notes}"
        out = self.llm.complete_json(JUDGE_SYSTEM, f"SOURCES:\n{sources}\n\nANSWER:\n{answer}")
        claims = out.get("claims", [])
        if not claims:
            return 0.0, ["judge returned no claims"]
        unsupported = [c.get("claim", "?") for c in claims if not c.get("supported")]
        return (len(claims) - len(unsupported)) / len(claims), unsupported