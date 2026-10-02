"""Diagnose Gemini API key problems. Run: python check_key.py  (never prints your full key)"""
import os, json
import requests
from dotenv import load_dotenv
import google.genai

def show(k):
    return f"{k[:8]}... (length {len(k)})" if k else "(not set)"

print("google-genai version:", google.genai.__version__)
print("Windows GEMINI_API_KEY:", show(os.environ.get("GEMINI_API_KEY", "")))
print("Windows GOOGLE_API_KEY:", show(os.environ.get("GOOGLE_API_KEY", "")))

load_dotenv(override=True)
key = os.environ.get("GEMINI_API_KEY", "").strip()
print("Key from .env:        ", show(key))
if key != os.environ.get("GEMINI_API_KEY", ""):
    print("WARNING: the key in .env has extra spaces around it - remove them.")

for i, line in enumerate(open("ingest.py", encoding="utf-8"), 1):
    if "load_dotenv(" in line and "import" not in line:
        print(f"ingest.py line {i}: {line.strip()}")

base = "https://generativelanguage.googleapis.com/v1beta/models/"
tests = {
    "chat (gemini-2.5-flash)": ("gemini-2.5-flash:generateContent",
        {"contents": [{"parts": [{"text": "Say hello"}]}]}),
    "embedding (gemini-embedding-001)": ("gemini-embedding-001:embedContent",
        {"content": {"parts": [{"text": "annual leave"}]}}),
}
print("\nDirect tests with the .env key (no SDK):")
for name, (path, body) in tests.items():
    try:
        r = requests.post(base + path, json=body, timeout=60,
                          headers={"x-goog-api-key": key, "Content-Type": "application/json"})
        if r.ok:
            print(f"  {name}: OK")
        else:
            err = r.json().get("error", {})
            reason = (err.get("details") or [{}])[0].get("reason", "")
            print(f"  {name}: FAILED {r.status_code} {reason} - {err.get('message', '')[:120]}")
    except Exception as e:
        print(f"  {name}: could not connect - {e}")
