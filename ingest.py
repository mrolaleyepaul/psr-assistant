"""Step 2: embed every rule and store it in a local Chroma DB.
Safe to re-run: rules already saved are skipped, and rate-limit errors wait and retry.
Use  python ingest.py --rebuild  to delete the old store and embed everything again."""
import json, os, sys, time
import chromadb
from dotenv import load_dotenv
from google import genai
from google.genai import types, errors

load_dotenv(override=True)
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"].strip())
EMBED_MODEL = os.getenv("EMBED_MODEL", "gemini-embedding-001")
BATCH = 20        # rules per request
PAUSE = 15        # seconds between requests (keeps free tier happy)
MAX_WAITS = 6     # how many times to wait on a rate limit before giving up

rules = json.load(open("data/psr_rules.json", encoding="utf-8"))
db = chromadb.PersistentClient(path="data/chroma")
if "--rebuild" in sys.argv:   # start fresh, e.g. after re-running parse_psr.py
    try:
        db.delete_collection("psr"); print("old vector store deleted")
    except Exception:
        pass
col = db.get_or_create_collection("psr", metadata={"hnsw:space": "cosine"})

done = set(col.get(include=[])["ids"])
todo = [r for r in rules if r["rule"] not in done]
print(f"{len(done)} rules already saved, {len(todo)} to go")

def doc_text(r):
    head = f"Public Service Rule {r['rule']} | Chapter {r['chapter']}: {r['chapter_title']}"
    if r.get("section_title"):
        head += f" | Section: {r['section_title']}"
    return f"{head}\n{r['text']}"

def embed(docs):
    for attempt in range(MAX_WAITS):
        try:
            return client.models.embed_content(
                model=EMBED_MODEL, contents=docs,
                config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
            ).embeddings
        except errors.ClientError as e:
            if e.code != 429:
                raise
            wait = 60 * (attempt + 1)
            print(f"  rate limit reached - waiting {wait}s before retrying...")
            time.sleep(wait)
    return None

for i in range(0, len(todo), BATCH):
    batch = todo[i:i + BATCH]
    docs = [doc_text(r) for r in batch]
    embs = embed(docs)
    if embs is None:
        print("\nStill rate-limited, so the daily free quota is probably used up.")
        print(f"Progress is saved ({col.count()}/{len(rules)}). Run 'python ingest.py' again later to continue.")
        break
    col.upsert(
        ids=[r["rule"] for r in batch], documents=docs,
        embeddings=[e.values for e in embs],
        metadatas=[{"rule": r["rule"], "chapter": r["chapter"],
                    "chapter_title": r["chapter_title"], "title": r["title"]} for r in batch],
    )
    print(f"saved {col.count()}/{len(rules)}")
    time.sleep(PAUSE)
else:
    print("done:", col.count(), "rules in the vector store")
