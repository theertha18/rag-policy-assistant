import time

from openai import OpenAI

from app.config import settings as s

client = OpenAI(api_key=s.llm_api_key, base_url=s.llm_base_url, timeout=120, max_retries=0)


def timed(label: str, **extra):
    start = time.perf_counter()
    try:
        r = client.chat.completions.create(
            model=s.llm_model,
            messages=[{"role": "user", "content": 'Reply with exactly this JSON: {"ok": true}'}],
            **extra,
        )
        print(f"{label:24} {time.perf_counter() - start:6.1f}s  {r.choices[0].message.content[:60]!r}")
    except Exception as e:
        print(f"{label:24} {time.perf_counter() - start:6.1f}s  ERROR {type(e).__name__}: {str(e)[:150]}")


timed("plain")
timed("json format", response_format={"type": "json_object"})
timed("json + low reasoning", response_format={"type": "json_object"}, reasoning_effort="low")