"""Chat with the PSR Assistant in the terminal. Run: python ask.py   (type 'exit' to quit)"""
from rag import answer

print("PSR Assistant - ask about the Public Service Rules. Type 'exit' to quit.")
level = input("Audience level? simple / standard / detailed [standard]: ").strip() or "standard"
history = []
while True:
    q = input("\nYour question: ").strip()
    if q.lower() in ("exit", "quit", ""):
        break
    try:
        res = answer(q, history, level)
    except Exception as e:
        print(f"\n[error] {e}\nIf this says 429, wait a minute and ask again.")
        continue
    print("\n" + res["answer"])
    print(f"\n(rules searched: {', '.join(res['sources'])})")
    history += [{"role": "user", "text": q}, {"role": "model", "text": res["answer"]}]
