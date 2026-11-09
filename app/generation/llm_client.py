import json
import re
from typing import Protocol


class LLMClient(Protocol):
    """Anything with this method can be used as the LLM."""
    def complete_json(self, system: str, user: str) -> dict: ...


def _parse_json(text: str) -> dict:
    """Parse the model's reply, tolerating ```json fences some models add."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    return json.loads(cleaned)


class OpenAICompatibleClient:
    """Works with OpenAI, Azure OpenAI and Gemini (via its OpenAI-compatible endpoint)."""

    def __init__(self, api_key: str, model: str, base_url: str | None = None, timeout: float = 30.0):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=2)
        self.model = model

    def complete_json(self, system: str, user: str) -> dict:
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return _parse_json(response.choices[0].message.content or "")


class FakeLLM:
    """Stand-in for unit tests: returns a fixed answer and counts how often it was called."""

    def __init__(self, response: dict):
        self.response = response
        self.calls = 0

    def complete_json(self, system: str, user: str) -> dict:
        self.calls += 1
        return self.response