"""Send the five benchmark questions to the running API and print a compact summary."""
import json
import urllib.request
from pathlib import Path

URL = "http://localhost:8000/v1/query"

for case in json.loads(Path("data/benchmark_eval.json").read_text(encoding="utf-8")):
    body = json.dumps({"query": case["query"]}).encode()
    req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        r = json.load(resp)
    sources = ", ".join(sorted({c["document_id"] for c in r["citations"]})) or "none"
    print(f"\n{case['eval_id']} | {r['status']} | reason={r['refusal_reason']} | {r['latency_ms']} ms | sources: {sources}")
    print("  " + r["answer"][:220].replace("\n", " "))