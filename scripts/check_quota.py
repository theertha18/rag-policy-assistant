from openai import OpenAI

from app.config import settings as s

client = OpenAI(api_key=s.llm_api_key, base_url=s.llm_base_url, max_retries=0)

for model in [s.llm_model, "gemini-3.5-flash-lite"]:
    try:
        client.chat.completions.create(model=model, messages=[{"role": "user", "content": "hi"}])
        print(f"{model}: OK, quota available")
    except Exception as e:
        print(f"{model}: {e}")
    print()