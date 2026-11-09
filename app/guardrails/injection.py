import re
import unicodedata

PATTERNS = [
    r"ignore (all |any )?(previous|prior|above|earlier) (instructions|prompts|rules)",
    r"disregard (all |any )?(previous|prior|above|your) (instructions|rules|guidelines)",
    r"system (override|prompt)",
    r"(print|reveal|show|repeat|output) .{0,30}(system prompt|your (instructions|rules|prompt)|hidden (instructions|prompt))",
    r"you are now (a|an|in|the|my|no longer)\b",
    r"developer mode",
    r"jailbreak",
    r"return ['\"]?approved",
    r"</?(system|assistant|instructions?)>",
]
_COMPILED = [re.compile(p) for p in PATTERNS]

# Invisible characters attackers insert to break up words, e.g. "Ig\u200bnore"
_ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff"))


def detect_injection(text: str) -> list[str]:
    """Return the patterns that matched. An empty list means the text looks safe."""
    normalized = unicodedata.normalize("NFKC", text).translate(_ZERO_WIDTH).lower()
    return [p.pattern for p in _COMPILED if p.search(normalized)]