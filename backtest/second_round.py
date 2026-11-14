"""Second round: (1) transfers from the PREVIOUS election applied to the actual first round,
(2) accuracy of direct second-round polls by horizon. Benchmarks for the 2027 simulator.

Usage: python3 backtest/second_round.py
"""
import csv, io, json, os, statistics as st, sys, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from parse_history import parse

M, L, B, A = "Emmanuel Macron", "Marine Le Pen", "blank_null", "abs"
surv = json.load(open(os.path.join(HERE, "data", "transfers_survey.json"), encoding="utf-8"))

# ---- 2022 first round, national totals (registered voters), from the commune file ----
def national(path):
    txt = open(path, "rb").read().decode("latin-1")
    rows = list(csv.reader(io.StringIO(txt), delimiter=";"))
    head = rows[0]; base = head.index("N°Panneau")
    tot = {"ins": 0, A: 0, B: 0}
    for r in rows[1:]:
        if len(r) < base: continue
        tot["ins"] += int(r[head.index("Inscrits")]); tot[A] += int(r[head.index("Abstentions")])
        tot[B] += int(r[head.index("Blancs")]) + int(r[head.index("Nuls")])
        k = base
        while k + 4 < len(r) and r[k].strip():
            name = (r[k + 3] + " " + r[k + 2]).strip().title()
            tot[name] = tot.get(name, 0) + int(r[k + 4]); k += 7
    return tot

t1 = national(os.path.join(HERE, "raw", "results", "t1_2022_communes.txt"))
t2 = national(os.path.join(HERE, "raw", "results", "t2_2022_communes.txt"))
real_macron = 100 * t2[M] / (t2[M] + t2[L])
real_abs = 100 * t2[A] / t2["ins"]

# ---- (1) 2017 transfer rows mapped onto 2022 electorates (by political proximity) ----
R17 = surv["2017"]["rows"]
def row(a, b, c, d): return {M: a, L: b, B: c, A: d}
ASSUMED = {  # not published by Ipsos in 2017: explicit assumptions, varied below
    "finalist_own": 0.96, "finalist_other": 0.02,
}
def matrix(abs_stay, abs_to_macron_share, bn_stay):
    own = ASSUMED["finalist_own"]; oth = ASSUMED["finalist_other"]; rest = (1 - own - oth) / 2
    mobil = 1 - abs_stay
    return {
        "Emmanuel Macron": row(own, oth, rest, rest),
        "Marine Le Pen": row(oth, own, rest, rest),
        "Jean-Luc Mélenchon": R17["Jean-Luc Mélenchon"], "Fabien Roussel": R17["Jean-Luc Mélenchon"],
        "Philippe Poutou": R17["Jean-Luc Mélenchon"], "Nathalie Arthaud": R17["Jean-Luc Mélenchon"],
        "Yannick Jadot": R17["Benoît Hamon"], "Anne Hidalgo": R17["Benoît Hamon"],
        "Valérie Pécresse": R17["François Fillon"],
        "Éric Zemmour": R17["Nicolas Dupont-Aignan"], "Nicolas Dupont-Aignan": R17["Nicolas Dupont-Aignan"],
        "Jean Lassalle": R17["Nicolas Dupont-Aignan"],
        B: row((1 - bn_stay) / 2, (1 - bn_stay) / 2, bn_stay * 0.7, bn_stay * 0.3),
        A: row(mobil * abs_to_macron_share, mobil * (1 - abs_to_macron_share), 0.0, abs_stay),
    }

def apply(T):
    out = {M: 0.0, L: 0.0, B: 0.0, A: 0.0}
    for src, n in t1.items():
        if src == "ins": continue
        for k, share in T[src].items():
            out[k] += n * share
    exp = out[M] + out[L]
    return 100 * out[M] / exp, 100 * out[A] / t1["ins"]

print("1) Report de voix 2017 (Ipsos) appliqué au 1er tour réel de 2022")
print(f"   Réel : Macron {real_macron:.2f} % des exprimés, abstention {real_abs:.1f} % des inscrits\n")
res = []
for abs_stay in (0.85, 0.90, 0.95):
    for share in (0.4, 0.5, 0.6):
        for bn_stay in (0.5, 0.7):
            m, a = apply(matrix(abs_stay, share, bn_stay)); res.append((m, a, abs_stay, share, bn_stay))
central = apply(matrix(0.90, 0.5, 0.7))
print(f"   Hypothèse centrale : Macron {central[0]:.2f} % (écart {central[0]-real_macron:+.2f} pt), abstention {central[1]:.1f} %")
print(f"   Fourchette sur les hypothèses non publiées (abstentionnistes, blancs, fidélité) : "
      f"Macron {min(r[0] for r in res):.1f} à {max(r[0] for r in res):.1f} %")

# same exercise with the 2022 table itself (in-sample, to see the floor of the method)
R22 = surv["2022"]["rows"]
T22 = matrix(0.90, 0.5, 0.7)
T22.update({"Jean-Luc Mélenchon": R22["Jean-Luc Mélenchon"], "Fabien Roussel": R22["Jean-Luc Mélenchon"], "Philippe Poutou": R22["Jean-Luc Mélenchon"],
            "Nathalie Arthaud": R22["Jean-Luc Mélenchon"], "Yannick Jadot": R22["Yannick Jadot"], "Anne Hidalgo": R22["Yannick Jadot"],
            "Valérie Pécresse": R22["Valérie Pécresse"], "Éric Zemmour": R22["Éric Zemmour"], "Nicolas Dupont-Aignan": R22["Éric Zemmour"],
            "Jean Lassalle": R22["Éric Zemmour"], M: R22[M], L: R22[L]})
m22, a22 = apply(T22)
print(f"   Contrôle avec le tableau 2022 lui-même : Macron {m22:.2f} % (écart {m22-real_macron:+.2f} pt)\n")

# ---- (2) direct second-round polls: error by horizon ----
def duel_polls(y, title):
    raw = open(os.path.join(HERE, "raw", f"polls_{y}.txt"), encoding="utf-8").read()
    i = raw.index(title); j = raw.find("\n===", i + len(title))
    sec = raw[i:j if j > 0 else None]
    return [p for p in parse("== First round ==\n" + sec.replace("{|", "{|", 1)) if "election" not in p["firm"].lower()]

def duel_polls2(y, title):
    # second-round tables have only 2 candidate columns: parse() requires >= 3 values, so relax via a local copy
    raw = open(os.path.join(HERE, "raw", f"polls_{y}.txt"), encoding="utf-8").read()
    i = raw.index(title); j = raw.find("\n===", i + len(title))
    sec = raw[i:j if j > 0 else None]
    polls = []
    for tbl in __import__("re").findall(r"\{\|.*?\n\|\}", sec, __import__("re").S):
        txt = "== First round ==\n" + tbl
        polls += ph_parse_min2(txt)
    return polls

def ph_parse_min2(text):
    # identical to parse_history.parse but keeps rows with 2 candidates
    code = open(os.path.join(HERE, "parse_history.py"), encoding="utf-8").read().replace("if len(vals) < 3:", "if len(vals) < 2:")
    ns = {}
    exec(compile(code.split('if __name__ == "__main__":')[0], "ph2", "exec"), ns)
    return [p for p in ns["parse"](text) if "election" not in p["firm"].lower()]

print("2) Sondages directs de second tour : écart avec le résultat (Macron, % des exprimés)")
for y, e, title, real in ((2017, "2017-05-07", "=== Graphical summary ===", 66.10), (2022, "2022-04-24", "=== Macron vs. Le Pen ===", 58.55)):
    raw = open(os.path.join(HERE, "raw", f"polls_{y}.txt"), encoding="utf-8").read()
    i = raw.index("== Second round ==")
    j = raw.find("\n===", raw.find("\n===", i) + 5)  # first sub-section of second round
    k = raw.find("===Other", i); k = k if k > 0 else raw.find("=== Other", i)
    sec = raw[i:k if k > 0 else None]
    polls = ph_parse_min2("== First round ==\n" + sec.split("== Second round ==", 1)[1])
    polls = [p for p in polls if M in p["scenarios"][0] and L in p["scenarios"][0]]
    ed = dt.date.fromisoformat(e)
    line = []
    for h in (163, 120, 90, 60, 30, 7):
        end = ed - dt.timedelta(days=h)
        w = [p["scenarios"][0][M] / (p["scenarios"][0][M] + p["scenarios"][0][L]) * 100 for p in polls
             if end - dt.timedelta(days=21) < dt.date.fromisoformat(p["date"]) <= end]
        line.append(f"J-{h}: {st.mean(w):.1f} ({st.mean(w)-real:+.1f}, {len(w)} sond.)" if w else f"J-{h}: -")
    print(f"   {y} (réel {real}) " + "  ".join(line))
