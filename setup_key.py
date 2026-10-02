"""Save your Gemini API key into .env and check that Google accepts it.
Run: python setup_key.py   (the key is hidden while you paste it)"""
import getpass, os
import requests

key = getpass.getpass("Paste your Gemini API key (it will stay hidden), then press Enter: ").strip().strip('"').strip("'")
if key.startswith("GEMINI_API_KEY="):
    key = key.split("=", 1)[1].strip()
if not key:
    raise SystemExit("No key entered. Run the script again.")

with open(".env", "w", encoding="utf-8") as f:
    f.write(f"GEMINI_API_KEY={key}\nCHAT_MODEL=gemini-2.5-flash\nEMBED_MODEL=gemini-embedding-001\n")
print(f"Saved to .env: {key[:8]}... (length {len(key)})")

if os.environ.get("GEMINI_API_KEY") and os.environ["GEMINI_API_KEY"] != key:
    print("Note: Windows also has an old GEMINI_API_KEY saved. The project will ignore it and use .env.")

print("Checking the key with Google...")
r = requests.post(
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent",
    headers={"x-goog-api-key": key, "Content-Type": "application/json"},
    json={"content": {"parts": [{"text": "annual leave"}]}}, timeout=60)
if r.ok:
    print("SUCCESS: Google accepted the key. Now run:  python ingest.py --rebuild")
elif r.status_code == 429:
    print("The key is VALID, but you've hit the rate limit. Wait a few minutes, then run: python ingest.py --rebuild")
else:
    msg = r.json().get("error", {}).get("message", r.text[:200])
    print(f"Google REJECTED this key ({r.status_code}): {msg}")
    print("Open aistudio.google.com > API keys, check this key is listed (not deleted),")
    print("or create a new one, wait 2 minutes, and run this script again.")