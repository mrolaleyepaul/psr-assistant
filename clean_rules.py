"""Phase 4: clean scanning leftovers out of the rule text that Gemini reads.
Adds a "clean" field to data/psr_rules.json. The search database is NOT changed, so no re-embedding needed.
Run: python clean_rules.py"""
import json, re

PATH = "data/psr_rules.json"
rules = json.load(open(PATH, encoding="utf-8"))

WORD_FIXES = {
    "Publie": "Public", "Misconpuct": "Misconduct", "Misconduet": "Misconduct", "ful.": "full",
    " fora ": " for a ", " ino ": " into ", "Ifthe": "If the", "ExtraMinisterial": "Extra-Ministerial",
    "HealthCare": "Healthcare", "Ist ": "1st ",
}
ROMAN_FIXES = {  # OCR misreads of list numbering
    "(/)": "(i)", "(//)": "(ii)", "(/i/)": "(iii)", "(/v)": "(iv)", "(v/)": "(vi)", "(vil)": "(vii)",
    "(vill)": "(viii)", "(x/)": "(xi)", "(x//)": "(xii)", "(vy)": "(y)", "(J)": "(l)", "(0)": "(o)", "(>)": "(b)",
}

def fix_letter_sequence(t: str) -> str:
    """In lettered lists, i/j/l are often misread for each other: "(k) Bribery; (j) Corruption" -> "(l)"."""
    if "(h)" not in t:
        return t
    out, prev, pos = [], None, 0
    for m in re.finditer(r"\(([a-z])\)", t):
        cur = m.group(1)
        if prev and cur != chr(ord(prev) + 1) and cur in "ijl" and chr(ord(prev) + 1) in "ijl":
            cur = chr(ord(prev) + 1)
        out.append(t[pos:m.start()] + f"({cur})")
        pos, prev = m.end(), cur
    return "".join(out) + t[pos:]

def clean(t: str) -> str:
    # page furniture: "100308 Chapter 10", "Chapter 12 120231", "Federal Government Public Service Rules"
    t = re.sub(r"Federal Government Publi[ce] Service Rules( books of reference)?", " ", t)
    t = re.sub(r"\b\d{6} Chapter \d+\b|\bChapter \d+ \d{6}\b|\bChapter \d+\s*(?=/)", " ", t)
    # margin headings between slashes: "/ Gifts from Traditional Rulers. /"
    t = re.sub(r"(?:\s*/\s*(?:[A-Z][\w’'()-]*)(?:\s+[\w’'()/-]+){0,8}[.,](?=\s*/|\s*$))+\s*/?", " ", t)
    # a heading dropped mid-sentence: "absent Leave. without leave", "fora Casual Leave. short period"
    t = re.sub(r"\b(?:[A-Z][a-z]+\s){0,4}[A-Z][a-z]+\.\s+(?=[a-z])", "", t)
    if "(h)" in t:                                   # in a lettered list, "(/)" is a misread "(j)"
        t = t.replace("(/)", "(j)")
    for bad, good in ROMAN_FIXES.items():
        t = t.replace(bad, good)
    t = re.sub(r"^\(7\)", "(i)", t.strip())
    if "(a)" in t:                                   # "(6)" after "(a)" is a misread "(b)"
        t = re.sub(r"\(6\)", "(b)", t)
    t = fix_letter_sequence(t)
    if "(aa)" in t:
        t = t.replace("(ah)", "(ab)")
    for bad, good in WORD_FIXES.items():
        t = t.replace(bad, good)
    t = re.sub(r"\s+/\s+", " ", t)                   # leftover list separators
    # margin headings left dangling after the last sentence: "...corrupt practices. Presents in Recognition of Service."
    t = re.sub(r"(?<=[.;])(?:\s+(?:[A-Z][\w’'-]*|of|in|to|and|the|from|on|for)(?:\s+(?:[A-Z][\w’'-]*|of|in|to|and|the|from|on|for)){0,7}[.,])+\s*$", "", t)
    t = re.sub(r"\s+([,;.])", r"\1", t)
    t = re.sub(r"\s{2,}", " ", t).strip(" /")
    t = re.sub(r",$", ".", t)
    return t

changed = 0
for r in rules:
    r["clean"] = clean(r["text"])
    changed += r["clean"] != r["text"]
json.dump(rules, open(PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"cleaned {changed} of {len(rules)} rules")
