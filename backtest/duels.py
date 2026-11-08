"""Second-round (duel) polls from a Wikipedia poll page: {"A vs. B": [poll, ...]}."""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from parse_history import parse

def duels(raw):
    i = raw.index("== Second round ==")
    j = raw.find("\n== ", i + 10)
    sec = raw[i:j if j > 0 else None]
    allh = [m.start() for m in re.finditer(r"\n=+([^=\n]+)=+", sec) if "graphical" not in m.group(1).lower()]
    heads = [(m.start(), re.sub(r"\s*–\s*", " vs. ", m.group(1).strip()))
             for m in re.finditer(r"\n=+\s*([^=\n]+?(?: vs\.? |\s*–\s*)[^=\n]+?)\s*=+", sec)]
    out = {}
    for k, (pos, title) in enumerate(heads):
        nxt = [h for h in allh if h > pos]
        end = nxt[0] if nxt else len(sec)   # stop at the next heading (skips "By region" sub-tables)
        polls = [p for p in parse(sec[pos:end], min_vals=2, whole=True) if "election" not in p["firm"].lower()]
        if polls:
            out[title] = polls
    return out

if __name__ == "__main__":
    raw = open(sys.argv[1], encoding="utf-8").read()
    d = duels(raw)
    json.dump(d, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    for t, ps in d.items():
        print(f"{t:28} {len(ps):>3} sondages, {min(p['date'] for p in ps)} -> {max(p['date'] for p in ps)}")
