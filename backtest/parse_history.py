"""Parse first-round poll tables of past French presidential elections (Wikipedia wikitext).

Usage: python3 backtest/parse_history.py backtest/raw/polls_2022.txt backtest/data/polls_2022.json
Output: [{firm, url, date, sample, scenarios: [{"Candidate Name": pct, ...}, ...]}]
Rows sharing firm + date + sample (rowspan) are scenarios of one poll.
"""
import json, re, sys

MONTHS = "january february march april may june july august september october november december".split()

def month(s):
    s = s.strip().lower().rstrip(".")
    for i, m in enumerate(MONTHS):
        if m.startswith(s[:3]):
            return i + 1
    raise ValueError(s)

def split_attr(cell):
    depth, i = 0, 0
    while i < len(cell):
        two = cell[i:i + 2]
        if two in ("[[", "{{"):
            depth += 1; i += 2; continue
        if two in ("]]", "}}"):
            depth -= 1; i += 2; continue
        c = cell[i]
        if c == "[": depth += 1
        elif c == "]": depth -= 1
        elif c == "|" and depth == 0:
            a = cell[:i]
            # only treat as attributes if it looks like html attributes
            if re.search(r'\w+\s*=', a) or not a.strip():
                return a, cell[i + 1:]
            return "", cell
        i += 1
    return "", cell

DATE_RE = re.compile(r"(\d{1,2})\s+([A-Za-z]{3,9})\.?\s+(\d{4})")

def parse_date(attr, content):
    m = re.search(r'data-sort-value\s*=\s*"?(\d{4})-(\d{2})-(\d{2})', attr + " " + content)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.search(r"\{\{Opdrts\|([^}]*)\}\}", content)
    if m:
        p = [x.strip() for x in m.group(1).split("|")]
        nums = [x for x in p if x.isdigit()]
        yr = [x for x in nums if len(x) == 4][0]
        mons = [x for x in p if x and not x.isdigit() and x != "year"]
        days = [x for x in nums if len(x) <= 2]
        return f"{int(yr):04d}-{month(mons[-1]):02d}-{int(days[-1]):02d}"
    txt = re.sub(r"<[^>]+>|\{\{[^}]*\}\}", " ", content)
    found = DATE_RE.findall(txt)
    if found:
        d, mo, y = found[-1]
        try:
            return f"{int(y):04d}-{month(mo):02d}-{int(d):02d}"
        except ValueError:
            return None
    return None

def parse_firm(c):
    m = re.search(r"\[(https?://\S+)\s+([^\]]+)\]", c)
    if m:
        return re.sub(r"<[^>]+>|'''|\{\{[^}]*\}\}", "", m.group(2)).strip(), m.group(1)
    m = re.search(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]", c)
    name = m.group(1) if m else re.sub(r"<ref.*|\{\{.*", "", c).strip()
    return name.strip(), None

def pct(c):
    c = re.sub(r"<ref.*?(</ref>|/>)|<!--.*?-->", "", c, flags=re.S)
    if re.search(r"<\s*0[.,]5", c) or "&lt;0.5" in c:
        return 0.25
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*%", c)
    return float(m.group(1).replace(",", ".")) if m else None

def header_rows(tbl):
    rows, cur = [], []
    for l in tbl.split("\n")[1:]:
        if l.startswith("|-"):
            if cur: rows.append(cur); cur = []
            continue
        if l.startswith("!"):
            cur += l[1:].split("!!")
        elif l.startswith("|") and cur:
            break  # first data row reached
    if cur: rows.append(cur)
    return rows

def role_of(c):
    a, v = split_attr(c)
    span = re.search(r'colspan\s*=\s*"?(\d+)', a)
    low = v.lower()
    if "polling" in low or "firm" in low: role = "firm"
    elif "fieldwork" in low or low.strip().startswith("date"): role = "date"
    elif "sample" in low: role = "sample"
    elif "abstention" in low or low.strip().startswith("abs"): role = "abs"
    else:
        links = [x for x in re.findall(r"\[\[([^\]|]+)", v) if not x.lower().startswith(("file:", "image:"))]
        role = ("cand", links[0].strip()) if links else ("other", v.strip())
    return role, int(span.group(1)) if span else 1

def header_cols(tbl):
    """Column roles; photo-only header cells take their name from the next header row."""
    rows = header_rows(tbl)
    if not rows:
        return []
    cols = []
    for c in rows[0]:
        role, n = role_of(c)
        cols += [role] * n
    holes = [i for i, r in enumerate(cols) if isinstance(r, tuple) and r[0] == "other"]
    for hr in rows[1:]:   # photo-only headers: take names from the first later row that has them
        names = [role_of(c)[0] for c in hr]
        names = [r for r in names if isinstance(r, tuple) and r[0] == "cand"]
        if holes and names and len(names) == len(holes):
            for i, r in zip(holes, names):
                cols[i] = r
            break
    return cols

def parse(text, min_vals=3, whole=False):
    """First-round tables by default; whole=True parses every table in `text` (e.g. one duel section)."""
    if whole:
        body = text
    else:
        start = text.find("== First round ==")
        end = text.find("== Second round ==")
        body = text[start:end if end > 0 else None]
    polls = []
    for tbl in re.findall(r"\{\|.*?\n\|\}", body, re.S):
        cols = header_cols(tbl)
        if "firm" not in cols or "date" not in cols:
            continue
        ncol = len(cols)
        carry, last = {}, None
        for r in re.split(r"\n\|-[^\n]*", tbl)[1:]:
            lines = [l for l in r.split("\n") if l.startswith("|") and not l.startswith("|}") and not l.startswith("{|")]
            if not lines:
                continue
            parsed = []
            for l in lines:
                for c in l[1:].split("||"):
                    a, v = split_attr(c)
                    m = re.match(r'\s*(rowspan\s*=\s*"?\d+"?)\s*(.*)', v, re.S) if not a else None
                    if m:
                        a, v = m.group(1), m.group(2)
                    parsed.append((a, v.strip()))
            big = [a for a, _ in parsed if re.search(r'colspan\s*=\s*"?(\d+)', a) and int(re.search(r'colspan\s*=\s*"?(\d+)', a).group(1)) >= 4]
            if big:
                continue  # timeline note row
            row = [None] * ncol
            it = iter(parsed)
            col = 0
            while col < ncol:
                if col in carry and carry[col][0] > 0:
                    row[col] = carry[col][1]; carry[col][0] -= 1; col += 1; continue
                try:
                    a, v = next(it)
                except StopIteration:
                    break
                span = re.search(r'colspan\s*=\s*"?(\d+)', a)
                rs = re.search(r'rowspan\s*=\s*"?(\d+)', a)
                for k in range(int(span.group(1)) if span else 1):
                    if col + k < ncol:
                        row[col + k] = (a, v)
                        if rs and int(rs.group(1)) > 1:
                            carry[col + k] = [int(rs.group(1)) - 1, (a, v)]
                col += int(span.group(1)) if span else 1
            fi, di = cols.index("firm"), cols.index("date")
            if not row[fi] or not row[di]:
                continue
            date = parse_date(*row[di])
            if not date:
                continue
            firm, url = parse_firm(row[fi][1])
            si = cols.index("sample") if "sample" in cols else None
            sample = re.sub(r"[^\d]", "", re.sub(r"<ref.*|\{\{.*", "", row[si][1])) if si is not None and row[si] else ""
            vals = {}
            for i, role in enumerate(cols):
                if isinstance(role, tuple) and role[0] == "cand" and row[i]:
                    p = pct(row[i][1])
                    if p is not None:
                        vals[role[1]] = p
            if len(vals) < min_vals:
                continue
            ai = cols.index("abs") if "abs" in cols else None
            abst = pct(row[ai][1]) if ai is not None and row[ai] else None   # pollster's expected abstention
            key = (firm, date, sample, id(tbl))
            if last and last["key"] == key:
                last["scenarios"].append(vals)
            else:
                last = {"key": key, "firm": firm, "url": url, "date": date, "sample": int(sample) if sample else None, "scenarios": [vals]}
                if abst is not None:
                    last["abs"] = abst
                polls.append(last)
    for p in polls:
        del p["key"]
    return polls

if __name__ == "__main__":
    polls = parse(open(sys.argv[1], encoding="utf-8").read())
    json.dump(polls, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(sys.argv[1], "->", len(polls), "polls", min(p["date"] for p in polls) if polls else "", max(p["date"] for p in polls) if polls else "")
