import time

from openai import OpenAI

from app.config import settings as s

client = OpenAI(api_key=s.llm_api_key, base_url=s.llm_base_url, timeout=60, max_retries=0)

for model in ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-2.5-flash-lite"]:
    start = time.perf_counter()
    try:
        r = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": 'Reply with exactly this JSON: {"ok": true}'}],
        )
        print(f"{model:24} {time.perf_counter() - start:6.1f}s  {r.choices[0].message.content[:40]!r}")
    except Exception as e:
        print(f"{model:24} {time.perf_counter() - start:6.1f}s  ERROR {type(e).__name__}: {str(e)[:100]}")