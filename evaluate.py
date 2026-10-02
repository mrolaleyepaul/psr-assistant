"""Phase 3: measure how well the assistant finds the right rules.

  python evaluate.py            -> retrieval test only (cheap: 1 embedding call per question)
  python evaluate.py --answers  -> also generates full answers into results/answers.md for you to review
                                   (safe to re-run: answers already received are reused, not re-requested)
"""
import json, os, sys, time
from rag import retrieve, answer, col

if col.count() < 500:
    raise SystemExit(f"The vector store only has {col.count()} of 502 rules. "
                     "Finish 'python ingest.py' first, then run this again.")

tests = json.load(open("data/test_questions.json", encoding="utf-8"))
with_answers = "--answers" in sys.argv
os.makedirs("results", exist_ok=True)
SAVED = "results/answers_cache.json"   # answers are saved as they arrive, so a crash never wastes quota
saved = json.load(open(SAVED, encoding="utf-8")) if os.path.exists(SAVED) else {}

hits, report = 0, []
for i, t in enumerate(tests, 1):
    for attempt in range(5):
        try:
            found = [h["id"] for h in retrieve(t["q"])]
            break
        except Exception as e:
            if "429" not in str(e): raise
            print("  rate limit - waiting 60s"); time.sleep(60)
    ok = any(e in found for e in t["expect"])
    hits += ok
    rank = next((found.index(e) + 1 for e in found if e in t["expect"]), None)
    print(f"{'PASS' if ok else 'MISS'}  {i:>2}. {t['q'][:60]:<60} expected {t['expect'][0]}" +
          (f" (rank {rank})" if ok else f" | got {', '.join(found[:3])}"))
    entry = {"question": t["q"], "expected": t["expect"], "found": found, "pass": ok, "fact": t["fact"]}
    if with_answers:
        if t["q"] in saved:                      # answered in an earlier run - reuse it
            entry["answer"] = saved[t["q"]]
        else:
            try:
                entry["answer"] = answer(t["q"])["answer"]
            except Exception as ex:
                print(f"  could not get an answer ({type(ex).__name__}) - run again later to fill it in")
                entry["answer"] = None
            if entry["answer"]:
                saved[t["q"]] = entry["answer"]
                json.dump(saved, open(SAVED, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
            time.sleep(8)
    report.append(entry)
    time.sleep(2)

print(f"\nRetrieval score: {hits}/{len(tests)} ({100 * hits // len(tests)}%) found the right rule in the top 6")
json.dump(report, open("results/retrieval.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
if with_answers:
    with open("results/answers.md", "w", encoding="utf-8") as f:
        for e in report:
            f.write(f"## {e['question']}\n\nExpected rule(s): {', '.join(e['expected'])} - key fact: {e['fact']}\n"
                    f"Retrieved: {', '.join(e['found'])} - {'PASS' if e['pass'] else 'MISS'}\n\n{e['answer'] or '(no answer yet - run again)'}\n\n---\n\n")
    missing = sum(1 for x in report if not x.get("answer"))
    print("Full answers saved to results/answers.md" + (f" ({missing} still missing - run again to fill them in)" if missing else ""))