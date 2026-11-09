"""Rebuild data/polls.js from the Wikipedia page listing 2027 first-round polls.

Usage:
    python3 scripts/update_polls.py            # fetch the live page
    python3 scripts/update_polls.py page.txt   # parse a saved wikitext file

Wikipedia is used only as an index: every poll keeps the link to the pollster's
own publication (or the press article) that Wikipedia cites.
"""
import datetime, json, os, re, sys, urllib.request

PAGE = "Opinion_polling_for_the_2027_French_presidential_election"
RAW = f"https://en.wikipedia.org/w/index.php?title={PAGE}&action=raw"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "data", "polls.js")
SINCE = "2024-07-01"  # after the 2024 dissolution: the current political landscape

# Wikipedia column name -> candidate id used by the site (see data/site.js)
TRACKED = {
    "Marine Le Pen": "lepen",
    "Jean-Luc Mélenchon": "melenchon",
    "Raphaël Glucksmann": "glucksmann",
    "Fabien Roussel": "roussel",
    "Gabriel Attal": "attal",
    "Édouard Philippe": "philippe",
    "Marine Tondelier": "tondelier",
    "David Lisnard": "lisnard",
}

if len(sys.argv) > 1:
    text = open(sys.argv[1], encoding="utf-8").read()
else:
    req = urllib.request.Request(RAW, headers={"User-Agent": "road-to-2027-poll-updater/1.0"})
    text = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
start = text.index("== First round ==")
end = text.index("== Second round ==")
body = text[start:end]

MONTHS = {m: i + 1 for i, m in enumerate(
    "january february march april may june july august september october november december".split())}

def month(s):
    s = s.strip().lower()
    for k, v in MONTHS.items():
        if k.startswith(s[:3]):
            return v
    raise ValueError(s)

def split_attr(cell):
    """Return (attrs, content) splitting on first '|' outside brackets."""
    depth = 0
    i = 0
    while i < len(cell):
        two = cell[i:i + 2]
        if two in ("[[", "{{"):
            depth += 1; i += 2; continue
        if two in ("]]", "}}"):
            depth -= 1; i += 2; continue
        if cell[i] == "[":
            depth += 1
        elif cell[i] == "]":
            depth -= 1
        elif cell[i] == "|" and depth == 0:
            return cell[:i], cell[i + 1:]
        i += 1
    return "", cell

def parse_date(c):
    m = re.search(r"\{\{Opdrts\|([^}]*)\}\}", c)
    if not m:
        return None
    p = m.group(1).split("|")
    d1, d2, mo, yr = p[0], p[1], p[2], p[3]
    # forms: d1|d2|Month|Year  or  d1|Month1|d2|Month2|Year (cross-month)
    if not yr.isdigit():
        # cross-month: d1|M1|d2|M2|Y
        d1, m1, d2, m2, yr = p[0], p[1], p[2], p[3], p[4]
        return f"{int(yr):04d}-{month(m2):02d}-{int(d2):02d}", f"{int(yr):04d}-{month(m1):02d}-{int(d1):02d}"
    end = f"{int(yr):04d}-{month(mo):02d}-{int(d2):02d}"
    if not d1.strip():
        return end, end
    # "{{Opdrts|31|1|Sep|2026}}" = 31 Aug to 1 Sep: a first day larger than the last one
    # means the fieldwork started in the previous month (and year, for January).
    sy, sm = int(yr), month(mo)
    if int(d1) > int(d2):
        sy, sm = (sy - 1, 12) if sm == 1 else (sy, sm - 1)
    return end, f"{sy:04d}-{sm:02d}-{int(d1):02d}"

def parse_firm(c):
    m = re.search(r"\[(https?://\S+)\s+([^\]]+)\]", c)
    if m:
        return re.sub(r"<[^>]+>|'''", "", m.group(2)).strip(), m.group(1)
    m = re.search(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]", c)
    name = m.group(1) if m else re.sub(r"<ref.*", "", c).strip()
    ref = re.search(r"url=(https?://[^ |}]+)", c)
    return name.strip(), ref.group(1) if ref else None

def pct(c):
    c = re.sub(r"<ref.*?(</ref>|/>)", "", c)
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", c)
    return float(m.group(1)) if m else None

polls = []
for tbl in re.findall(r"\{\|.*?\n\|\}", body, re.S):
    cands = [re.sub(r"\|.*", "", n) for n in re.findall(r"vert header\|[^\n]*?\[\[([^\]]+)\]\]", tbl)]
    ncol = 3 + len(cands)
    rows = re.split(r"\n\|-[^\n]*", tbl)
    carry = {}  # col -> [remaining, content]
    last = None
    for r in rows:
        lines = [l for l in r.split("\n") if l.startswith("|") and not l.startswith("|}") and not l.startswith("{|")]
        if not lines:
            continue
        cells = []
        for l in lines:
            cells += l[1:].split("||")
        parsed = []
        for c in cells:
            a, v = split_attr(c)
            m = re.match(r'\s*(rowspan\s*=\s*"?\d+"?)\s*(.*)', v, re.S) if not a else None
            if m:
                a, v = m.group(1), m.group(2)
            parsed.append((a, v.strip()))
        if any("colspan" in a for a, _ in parsed):  # timeline note row, not a poll
            continue
        row = [None] * ncol
        it = iter(parsed)
        for col in range(ncol):
            if col in carry and carry[col][0] > 0:
                row[col] = carry[col][1]
                carry[col][0] -= 1
                continue
            try:
                a, v = next(it)
            except StopIteration:
                break
            row[col] = v
            rs = re.search(r'rowspan\s*=\s*"?(\d+)', a)
            if rs and int(rs.group(1)) > 1:
                carry[col] = [int(rs.group(1)) - 1, v]
        if row[1] is None or parse_date(row[1] or "") is None:
            continue
        end_d, st_d = parse_date(row[1])
        firm, url = parse_firm(row[0] or "")
        vals = {}
        for i, name in enumerate(cands):
            p = pct(row[3 + i] or "")
            if p is not None:
                vals[name] = p
        key = (firm, end_d, row[2])
        if last and last["key"] == key:
            last["scenarios"].append(vals)
        else:
            sample = re.sub(r"[^\d]", "", re.sub(r"<ref.*", "", row[2] or ""))
            last = {"key": key, "firm": firm, "url": url, "date": end_d, "start": st_d,
                    "sample": int(sample) if sample else None, "scenarios": [vals]}
            polls.append(last)

def scenario(vals):
    return {TRACKED[k]: v for k, v in vals.items() if k in TRACKED}

out = []
for p in polls:
    if p["date"] < SINCE:
        continue
    scen = [scenario(v) for v in p["scenarios"]]
    if not any(scen):
        continue
    out.append({"firm": p["firm"], "url": p["url"], "start": p["start"], "date": p["date"],
                "sample": p["sample"], "scenarios": scen})
out.sort(key=lambda p: (p["date"], p["firm"]))

payload = {
    "fetched": datetime.date.today().isoformat(),
    "index": f"https://en.wikipedia.org/wiki/{PAGE}",
    "polls": out,
}
with open(OUT, "w", encoding="utf-8") as f:
    f.write("/* Généré par scripts/update_polls.py : ne pas modifier à la main. */\n")
    f.write("window.POLLS = ")
    json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    f.write(";\n")
print(f"{len(out)} sondages écrits dans data/polls.js (depuis {SINCE})")
missing = [p for p in out if not p["url"]]
if missing:
    print("Sans lien source :", [(p["firm"], p["date"]) for p in missing])
