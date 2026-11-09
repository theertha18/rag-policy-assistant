import re

NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
LABEL_RE = re.compile(r"\bS\d+\b")                    # source labels like S1, S12
LIST_MARKER_RE = re.compile(r"(?m)^\s*\d+[.)]\s")      # "1. " or "2) " at the start of a line


def _numbers(text: str) -> set[str]:
    """All numbers in a text, with thousands separators removed ("1,800" -> "1800")."""
    return {n.replace(",", "") for n in NUM_RE.findall(text)}


def _factual_text(answer: str) -> str:
    """The answer without source labels and list numbering, which are not facts."""
    return LIST_MARKER_RE.sub(" ", LABEL_RE.sub(" ", answer))


def validate_output(answer: str, cited: list[str], sources: dict[str, str], leak_marker: str) -> list[str]:
    """Return a list of problems. An empty list means the answer passed every check."""
    errors = []
    if not cited:
        errors.append("no_citations")
    if leak_marker in answer:
        errors.append("prompt_leak")
    cited_text = " ".join(sources[c] for c in cited if c in sources)
    ungrounded = _numbers(_factual_text(answer)) - _numbers(cited_text)
    if ungrounded:
        errors.append(f"ungrounded_numbers:{sorted(ungrounded)}")
    return errors