"""Step 3: retrieval + answer generation."""
import json, math, os, re, time
import httpx
import chromadb
from dotenv import load_dotenv
from google import genai
from google.genai import types, errors

load_dotenv(override=True)
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
CHAT_MODEL = os.getenv("CHAT_MODEL", "gemini-2.5-flash")
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "gemini-2.5-flash-lite")  # used when the main model is overloaded
EMBED_MODEL = os.getenv("EMBED_MODEL", "gemini-embedding-001")
col = chromadb.PersistentClient(path="data/chroma").get_collection("psr")

SYSTEM = """You are the PSR Assistant. You explain the Nigerian Public Service Rules (PSR), 2021 Edition,
to government workers so they clearly understand what a rule means and how it affects them.

GROUNDING
- Use ONLY the PSR extracts provided. Never invent rules, rule numbers, days, amounts or procedures.
- Every step in "What you should do" must come from an extract. If a practical step is sensible but
  NOT stated in the extracts (e.g. who to apply to), say so: "(not stated in the rules I found - confirm with your HR)".
- Check who each rule applies to before using it. Each extract shows its chapter and section: a rule from
  a contract template, a specific cadre, or special group (e.g. "Schedule For Non Pensionable Appointment")
  must not be presented as a rule for all officers. Mention who it applies to.
- Keep conditions, limits and safeguards from the rule (time limits, grade levels, "during working hours",
  steps that must be considered first, rights of the officer). Leaving out a protection the officer has is an error.
- Do not interpret or combine rules beyond what they say (e.g. applying one rule's condition to another
  situation). If a link seems likely but isn't stated, don't present it as a rule.
- Before saying something isn't covered, check EVERY extract, including long ones and later ones in the list.
- NEVER say "the PSR does not say/specify" something. You only see some extracts, so say
  "I couldn't find this in the rules I retrieved - please confirm with your HR/Establishment department."
- If the extracts don't answer the question at all, say so plainly. Do not guess.
- The extracts came from a scanned document and may contain OCR typos; read past them sensibly and
  quote the words cleanly.

CITING
- Cite numbered rules as "Rule 120203" (add the sub-part if useful, e.g. "Rule 100404(ii)").
- Some extracts have no rule number and are labelled e.g. "Chapter 18 - Nigerian Foreign Service Regulations".
  Cite those by that label. Never show internal labels such as "18-part14" or "APPX2-part07".

EXAMPLES
- Use made-up Nigerian names (Mr. Ade, Mrs. Okafor). Never name real companies, agencies or people.
- Examples illustrate the rule only: no new facts, deadlines, amounts, or conversions such as
  "about 5 months" that are not in the rule.

ANSWER STRUCTURE (use these headings, skip any that don't apply)
**In simple terms** - one or two sentences a new recruit would understand.
**Example** - a short, realistic Nigerian civil-service scenario showing the rule in action.
**What you should do** - at most 5 practical steps that come from the rules.
**The rule says** - the rule number(s) and the key sentence quoted from the extract.
**Related rules** - other rules from the extracts that the officer should also know (only if present).

STYLE
- Answer the question asked. Leave out rules that don't help answer it, even if they were retrieved.
- Length: about 150 words for simple, 250 for standard, 400 for detailed audiences.
- Short sentences, everyday words. Explain any official term (e.g. "interdiction") the first time.
- Reply in the language the user writes in (English, Nigerian Pidgin, Yoruba, Hausa or Igbo).
- Audience level: {audience}.
- End with: "This is a guide based on the PSR 2021. Extant circulars may have updated this rule."

EXAMPLE
Question: How many days of annual leave do I get on GL 08?
Answer:
**In simple terms** - As an officer on GL 08, you are entitled to 30 working days of annual leave each year.
**Example** - Amaka is a GL 08 officer. She can take 30 working days of annual leave; because leave is counted
in working days, the weekends and public holidays within her leave period are not deducted.
**What you should do** - Get your leave authorised by your superior officer before you go (Rule 120202).
**The rule says** - Rule 120203: "(a) GL 07 and above - 30 working days". Rule 120202 defines annual leave as
absence from duty for the period in Rule 120203 "as may be authorized by a superior Officer."
This is a guide based on the PSR 2021. Extant circulars may have updated this rule."""

AUDIENCE = {
    "simple": "new or junior officer; keep it very simple and practical",
    "standard": "general officer; clear and practical",
    "detailed": "senior officer or HR staff; include precise wording and conditions",
}

RULES = {x["rule"]: x for x in json.load(open("data/psr_rules.json", encoding="utf-8"))}
STOP = set("""a an the of to in on for and or is are be by with as at from that this it its i my me we our you your
he his she her they their shall will may can what how when who which do does did if not no any all have has
""".split())

def _tokens(text):
    # crude stemming: first 6 letters, so "suspension"/"suspended" and "interdict"/"interdiction" match
    return [w[:6] for w in re.findall(r"[a-z]+", text.lower()) if w not in STOP and len(w) > 2]

# simple BM25 keyword index over the cleaned rules (finds exact terms like "suspended", "maternity").
# Long rules are split into their sub-parts ((i), (ii), (a), (b)...) so one relevant clause inside a
# very long rule (e.g. Rule 100307(x) on salary after being cleared) can still be found.
def _parts(text, max_words=120):
    if len(text.split()) <= max_words:
        return [text]
    pieces = re.split(r"(?=\((?:[ivx]{1,4}|[a-z])\)\s)", text)
    return [p for p in pieces if len(p.split()) >= 5] or [text]

_DOCS = []   # (rule id, tokens)
for rid, x in RULES.items():
    for part in _parts(x.get("clean", x["text"])):
        _DOCS.append((rid, _tokens(part + " " + x.get("section_title", ""))))
_AVG = sum(len(d) for _, d in _DOCS) / len(_DOCS)
_DF = {}
for _, d in _DOCS:
    for w in set(d):
        _DF[w] = _DF.get(w, 0) + 1

def keyword_search(question, k=3):
    q = set(_tokens(question))
    best = {}
    for rid, d in _DOCS:
        s = 0.0
        for w in q:
            tf = d.count(w)
            if tf:
                idf = math.log(1 + (len(_DOCS) - _DF[w] + 0.5) / (_DF[w] + 0.5))
                s += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * len(d) / _AVG))
        if s > best.get(rid, 0):
            best[rid] = s
    return sorted(best, key=best.get, reverse=True)[:k]

def cross_references(rule_ids, limit=3):
    """Rules mentioned inside the retrieved rules, e.g. 'in accordance with Rule 100406'."""
    named, ranged = [], []
    for rid in rule_ids:
        text = RULES.get(rid, {}).get("clean", "")
        named += re.findall(r"Rules?\s+(\d{6})(?!\s*[-–]\s*\d)", text)   # "in accordance with Rule 100406"
        for a, b in re.findall(r"(\d{6})\s*[-–]\s*(\d{6})", text):      # ranges like 100302-100306
            if a[:4] == b[:4] and 0 < int(b) - int(a) <= 6:
                ranged += [str(n).zfill(6) for n in range(int(a), int(b) + 1)]
    found = named + ranged
    out = []
    for f in found:
        if f in RULES and f not in rule_ids and f not in out:
            out.append(f)
    return out[:limit]

def label(rid):
    x = RULES[rid]
    if rid[:6].isdigit() and len(rid) == 6:
        head = f"Rule {rid} | Chapter {x['chapter']}: {x['chapter_title']}"
        if x.get("section_title"):
            head += f" | Section: {x['section_title']}"
        return head
    if rid.startswith("18") or rid.startswith("19"):
        return f"Chapter {rid[:2]} - {x['chapter_title']} (extract, no rule number)"
    return "Appendix to the PSR (extract, no rule number)"

def embed_query(question: str, tries: int = 5):
    """Embed the question, retrying when the connection drops, Google is busy, or the rate limit hits."""
    last = None
    for attempt in range(tries):
        try:
            return client.models.embed_content(
                model=EMBED_MODEL, contents=question,
                config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
            ).embeddings[0].values
        except errors.ClientError as e:
            if e.code != 429:
                raise
            last = e
        except (errors.ServerError, httpx.HTTPError, ConnectionError) as e:
            last = e
        wait = 15 * (attempt + 1)
        print(f"  search: connection problem or limit ({type(last).__name__}) - retrying in {wait}s...")
        time.sleep(wait)
    raise last

def _score(qtok, d):
    s = 0.0
    for w in qtok:
        tf = d.count(w)
        if tf and w in _DF:
            idf = math.log(1 + (len(_DOCS) - _DF[w] + 0.5) / (_DF[w] + 0.5))
            s += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * len(d) / _AVG))
    return s

def rule_text(rid, question, long_words=350, keep=3):
    """Full text for normal rules. For very long rules, only the parts most relevant to the question,
    so an important clause isn't buried in hundreds of words (e.g. Rule 100307(x))."""
    text = RULES[rid].get("clean", RULES[rid]["text"])
    if len(text.split()) <= long_words:
        return text
    parts = _parts(text)
    q = set(_tokens(question))
    ranked = sorted(range(len(parts)), key=lambda i: _score(q, _tokens(parts[i])), reverse=True)[:keep]
    chosen = [parts[i].strip() for i in sorted(ranked)]
    return "[Excerpt - only the parts of this long rule that match the question]\n... " + " ... ".join(chosen) + " ..."

def retrieve(question: str, k: int = 6, max_total: int = 10):
    ids = [n for n in re.findall(r"\b\d{6}\b", question) if n in RULES]   # rule numbers typed by the user
    q = embed_query(question)
    res = col.query(query_embeddings=[q], n_results=k, include=[])
    for rid in res["ids"][0] + keyword_search(question):
        if rid not in ids:
            ids.append(rid)
    ids += cross_references(ids)
    ids = [i for i in ids if i in RULES][:max_total]
    return [{"id": i, "doc": f"{label(i)}\n{rule_text(i, question)}"} for i in ids]

def generate(contents, config, tries: int = 4):
    """Call Gemini, retrying when Google is busy (503), rate-limited (429) or the connection drops.
    After two failures on the main model, switch to the lighter fallback model."""
    last = None
    for attempt in range(tries):
        model = CHAT_MODEL if attempt < 2 else FALLBACK_MODEL
        try:
            return client.models.generate_content(model=model, contents=contents, config=config)
        except errors.ServerError as e:            # 500/503: Google overloaded
            last = e
        except errors.ClientError as e:            # only 429 (rate limit) is worth retrying
            if e.code != 429:
                if model == FALLBACK_MODEL and last is not None:
                    print(f"  fallback model {model} not usable ({e.code}) - keeping the original error")
                    raise last
                raise
            last = e
        except (httpx.HTTPError, ConnectionError) as e:
            last = e
        wait = 10 * (attempt + 1)
        code = getattr(last, "code", "")
        why = "daily/minute quota reached" if code == 429 else "Google busy" if code in (500, 503) else "connection problem"
        print(f"  {model}: {why} ({code or type(last).__name__}) - retrying in {wait}s...")
        time.sleep(wait)
    raise last

def answer(question: str, history: list[dict] | None = None, audience: str = "standard"):
    hits = retrieve(question)
    context = "\n\n---\n\n".join(h["doc"] for h in hits)
    contents = []
    for turn in (history or [])[-6:]:  # short memory of the conversation
        contents.append(types.Content(role=turn["role"], parts=[types.Part(text=turn["text"])]))
    contents.append(types.Content(role="user", parts=[types.Part(
        text=f"PSR extracts:\n{context}\n\nQuestion: {question}")]))
    config = types.GenerateContentConfig(
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        system_instruction=SYSTEM.format(audience=AUDIENCE.get(audience, AUDIENCE["standard"])),
        temperature=0.2)
    resp = generate(contents, config)
    return {"answer": resp.text, "sources": [h["id"] for h in hits]}

if __name__ == "__main__":
    print(answer("How many days of annual leave am I entitled to on GL 08?")["answer"])