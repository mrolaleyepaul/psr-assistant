# Step 1: turns the extracted PSR text into one JSON record per rule.
# Usage: extract the .docx to data/psr.md first (e.g. pandoc PSR.docx -t markdown -o data/psr.md), then: python parse_psr.py
import re, json
text = open("data/psr.md", encoding="utf-8").read()
lines = text.split("\n")
start = next(i for i,l in enumerate(lines) if "010101.—" in l or "010101.-" in l)
ch18 = next(i for i,l in enumerate(lines) if i>start and "CHAPTER 18 NIGERIAN FOREIGN" in l)
index_part, body = "\n".join(lines[:start]), "\n".join(lines[start:ch18])
tail = [l for l in lines[ch18:] if l.strip()]

# titles from the index: "Investments ; a6 Re i - i 100424" -> "Investments"
def clean_title(t):
    t = re.sub(r"\*+", "", t)
    t = re.split(r"\.{2,}|\s[.;:,‘’'“»«|_=~-]\s|\s[.;:,‘’'“»«|_=~]|…", t)[0]
    words = []
    for w in t.split():
        if re.fullmatch(r"[A-Za-z][A-Za-z’'()/-]*[.,]?|of|and|to|in|on|for|the|a", w) and not (len(w) <= 2 and w[0].isupper() and words):
            words.append(w.rstrip(".,"))
        else:
            break
    return " ".join(words)

titles = {}
idx_lines = [l.strip() for l in index_part.split("\n")]
for i, l in enumerate(idx_lines):
    m = re.search(r"\b(\d{6})\s*$", l)
    if not m: continue
    t = clean_title(l[:m.start()])
    if not t:  # title on an earlier line
        for j in range(i - 1, max(i - 3, -1), -1):
            if idx_lines[j] and not re.search(r"\d{6}\s*$", idx_lines[j]):
                t = clean_title(idx_lines[j]); break
    if len(t) > 2: titles[m.group(1)] = t

CH = {"01":"Introduction","02":"Appointments and Leaving the Service","03":"Prescribed Examination for Confirmation",
"04":"Emoluments and Increments","05":"Performance Management System","06":"Reward and Recognition for Outstanding Work",
"07":"Training and Staff Development","08":"Free Transport Facilities on Official Assignments","09":"Virtual Meetings and Engagements",
"10":"Discipline","11":"Petitions and Appeals","12":"Leave","13":"Medical and Dental Procedures","14":"Allowances",
"15":"Innovations and Inventions","16":"Compensation and Insurance","17":"Application of PSR to Federal Government Parastatals",
"18":"Nigerian Foreign Service Regulations","19":"Procedures for Amending the Public Service Rules"}

body = re.sub(r"\*+", "", body)
body = re.sub(r"\s+", " ", body)
parts = re.split(r"(?<!Rule )(?<!Rules )(?<!and )(?<!to )(?<![-–—] )\b(\d{6})\s*(?:[.,]\s*[—–~-]+|\s:)\s*", body)
rules, prev = [], None
HEAD = re.compile(r"SECTION\s*(\d+)\s*[.,]?\s*[—–-]+\s*((?:[A-Z][A-Z,/()&'’]*\s*){1,14})", re.I)
section_titles = {}
pending = []
for num, txt in zip(parts[1::2], parts[2::2]):
    ch = num[:2]
    if ch not in CH: continue
    for sec, title in pending:           # headings seen just before this rule
        section_titles[(ch, int(sec))] = title
    pending = []
    for m in HEAD.finditer(txt):         # headings at the end of this rule's text
        title = re.sub(r"\s+", " ", m.group(2)).strip(" ,").title()
        pending.append((m.group(1), title))
    txt = HEAD.sub("", txt)
    txt = re.sub(r"\s*(Chapter \d+ )?CHAPTER \d+ [A-Z ,/-]+$", "", txt).strip()
    rules.append({"rule": num, "chapter": int(ch), "chapter_title": CH[ch], "section": int(num[2:4]),
                  "section_title": "", "title": titles.get(num, ""), "text": txt})
for r in rules:
    r["section_title"] = section_titles.get((f"{r['chapter']:02d}", r["section"]), "")
# Chapter 18/19 + appendices: not rule-numbered, chunk by ~350 words
buf, part, cur_ch, appx = [], 0, "18", 0
def flush():
    global buf, part
    if buf:
        part += 1
        rules.append({"rule": f"{cur_ch}-part{part:02d}", "chapter": int(cur_ch[:2]) if cur_ch[:2].isdigit() else 99,
            "chapter_title": CH.get(cur_ch, "Appendix"), "section": 0, "section_title": "", "title": "", "text": re.sub(r"\*+","", " ".join(buf))})
        buf = []
for l in tail:
    if "CHAPTER 19" in l: flush(); cur_ch, part = "19", 0
    elif l.startswith("**APPENDIX"): flush(); appx += 1; cur_ch, part = f"APPX{appx}", 0
    buf.append(l.strip())
    if sum(len(x.split()) for x in buf) > 350: flush()
flush()
json.dump(rules, open("data/psr_rules.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(rules), "rules;", sum(1 for r in rules if r["section_title"]), "with section titles")
from collections import Counter; print(sorted(Counter(r["chapter"] for r in rules).items()))
dups=[k for k,v in Counter(r["rule"] for r in rules).items() if v>1]; print("dup ids:",len(dups),dups[:10])
