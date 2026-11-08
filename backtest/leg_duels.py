"""Barrage behaviour in legislative runoffs (2024): how did first-round voters of each bloc split
when the runoff was left vs RN, centre vs RN, right vs RN?

Per constituency (shares of registered voters): runoff votes for X = sum over first-round blocs
of bloc share x transfer rate. Rates fitted per runoff type by constrained least squares
(rates >= 0, a bloc's rates to the two finalists sum to <= 1; the rest = blank/null/abstention).
Optional: left candidates split by party (data/left_alliance_parties.csv) to isolate LFI.

Usage: python3 backtest/leg_duels.py [2024]
"""
import csv, json, os, sys
import numpy as np
from scipy.optimize import minimize

HERE = os.path.dirname(os.path.abspath(__file__))
YEAR = sys.argv[1] if len(sys.argv) > 1 else "2024"
RAW = os.path.join(HERE, "raw", "leg")

BLOC = {  # ministry nuances 2024 -> first-round blocs
    **{n: "GAUCHE" for n in ("EXG", "DXG", "FI", "COM", "SOC", "RDG", "VEC", "DVG", "UG", "ECO", "NUP")},
    **{n: "CENTRE" for n in ("ENS", "HOR", "DVC", "UDI", "REM", "MDM")},
    **{n: "DROITE" for n in ("LR", "DVD")},
    **{n: "RN_ALLIES" for n in ("RN", "UXD", "REC", "EXD", "DXD", "DSV", "FN", "DLF")},
    **{n: "AUTRES" for n in ("REG", "DIV")},
}
SIDE = {"UG": "GAUCHE", "NUP": "GAUCHE", "SOC": "GAUCHE", "FI": "GAUCHE", "VEC": "GAUCHE", "COM": "GAUCHE", "DVG": "GAUCHE",
        "ENS": "CENTRE", "HOR": "CENTRE", "DVC": "CENTRE", "UDI": "CENTRE", "LR": "DROITE", "DVD": "DROITE",
        "REM": "CENTRE", "MDM": "CENTRE", "RN": "RN", "UXD": "RN", "FN": "RN"}
ROWS = ["GAUCHE", "CENTRE", "DROITE", "RN_ALLIES", "AUTRES", "BLANC_NUL_T1", "ABST_T1"]

def num(s): return int(float(str(s).replace(" ", ""))) if s not in ("", None) else 0

def read(path):
    out = {}
    with open(path, encoding="utf-8") as f:
        r = csv.reader(f, delimiter=";")
        head = next(r)
        for row in r:
            d = dict(zip(head, row))
            key = (d["Code département"], d["Code circonscription législative"])
            cands = []
            k = 1
            while f"Nuance candidat {k}" in d and d[f"Nuance candidat {k}"]:
                cands.append({"nuance": d[f"Nuance candidat {k}"], "nom": d[f"Nom candidat {k}"], "prenom": d[f"Prénom candidat {k}"],
                              "voix": num(d[f"Voix {k}"])})
                k += 1
            out[key] = {"ins": num(d["Inscrits"]), "abs": num(d["Abstentions"]), "bn": num(d["Blancs"]) + num(d["Nuls"]), "cands": cands}
    return out

def read_2022(path, enc="latin-1", head_line=0):
    """Ministry 2017/2022 layout: one row per constituency, 9 fields per candidate."""
    out = {}
    txt = open(path, "rb").read().decode(enc).splitlines()[head_line:]
    head = txt[0].split(";"); base = head.index("N°Panneau")
    for line in txt[1:]:
        r = line.split(";")
        if len(r) < base: continue
        cands, k = [], base
        while k + 5 < len(r) and r[k].strip():
            cands.append({"nuance": r[k + 4], "nom": r[k + 2], "prenom": r[k + 3], "voix": num(r[k + 5])}); k += 9
        H = {h: i for i, h in enumerate(head[:base])}
        out[(r[0].zfill(2), r[2].zfill(2))] = {"ins": num(r[H["Inscrits"]]), "abs": num(r[H["Abstentions"]]),
                                               "bn": num(r[H["Blancs"]]) + num(r[H["Nuls"]]), "cands": cands}
    return out

if YEAR == "2017":
    t1 = read_2022(os.path.join(RAW, "leg2017_t1_circo.csv"), "utf-8", 1)
    t2 = read_2022(os.path.join(RAW, "leg2017_t2_circo.csv"), "utf-8", 1)
elif YEAR == "2022":
    t1 = read_2022(os.path.join(RAW, "leg2022_t1_cirlg.txt"))
    t2 = read_2022(os.path.join(RAW, "leg2022_t2_cirlg.txt"))
else:
    t1 = read(os.path.join(RAW, f"leg{YEAR}_t1_circo.csv"))
    t2 = read(os.path.join(RAW, f"leg{YEAR}_t2_circo.csv"))

party = {}
pfile = os.path.join(HERE, "data", "left_alliance_parties.csv")
if os.path.exists(pfile):
    for r in csv.DictReader(open(pfile, encoding="utf-8")):
        if r["year"] == YEAR:
            party[(r["dept_code"].zfill(2) if r["dept_code"].isdigit() else r["dept_code"], int(r["circo"]))] = r["party"]

def circo_num(code): return int(code[-2:])

duels = {}
for key, r2 in t2.items():
    if len(r2["cands"]) != 2 or key not in t1: continue
    sides = [SIDE.get(c["nuance"]) for c in r2["cands"]]
    if "RN" not in sides or None in sides or sides.count("RN") != 1: continue
    other = [s for s in sides if s != "RN"][0]
    r1 = t1[key]
    if abs(r1["ins"] - r2["ins"]) / r1["ins"] > 0.03: continue
    x = {b: 0 for b in ROWS}
    for c in r1["cands"]:
        x[BLOC.get(c["nuance"], "AUTRES")] += c["voix"]
    x["BLANC_NUL_T1"] = r1["bn"]; x["ABST_T1"] = r1["abs"]
    vec = np.array([x[b] / r1["ins"] for b in ROWS])
    opp = [c for c in r2["cands"] if SIDE.get(c["nuance"]) != "RN"][0]
    rn = [c for c in r2["cands"] if SIDE.get(c["nuance"]) == "RN"][0]
    y = np.array([opp["voix"] / r2["ins"], rn["voix"] / r2["ins"]])
    typ = other
    if other == "GAUCHE" and party:
        p = party.get((key[0], circo_num(key[1])), "UNKNOWN")
        typ = "GAUCHE_LFI" if p == "LFI" else ("GAUCHE_AUTRE" if p in ("PS", "ECO", "PCF", "DIV", "AUTRE", "GEN", "PP") or p not in ("UNKNOWN", "") else "GAUCHE_?")
    duels.setdefault(typ, []).append((key, vec, y, opp["voix"] / (opp["voix"] + rn["voix"])))

if party:  # keep the pooled left-vs-RN estimate alongside the per-party ones
    duels["GAUCHE"] = [d for t, v in duels.items() if t.startswith("GAUCHE_") for d in v]

def fit(data):
    X = np.array([d[1] for d in data]); Y = np.array([d[2] for d in data])
    R = len(ROWS)
    def f(b):
        B = b.reshape(R, 2); E = X @ B - Y
        return (E * E).sum(), (2 * X.T @ E).ravel()
    cons = [{"type": "ineq", "fun": (lambda b, i=i: 1 - b[2 * i] - b[2 * i + 1])} for i in range(R)]
    x0 = np.full(2 * R, 0.3)
    res = minimize(f, x0, jac=True, bounds=[(0, 1)] * (2 * R), constraints=cons, method="SLSQP", options={"maxiter": 1000, "ftol": 1e-14})
    return res.x.reshape(R, 2)

def boot(data, n=200, seed=1):
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        idx = rng.integers(0, len(data), len(data))
        out.append(fit([data[i] for i in idx]))
    return np.array(out)

result = {}
print(f"Législatives {YEAR}, duels de second tour contre le RN/UXD. Taux de report estimés (% de chaque électorat du 1er tour)\n")
for typ, data in sorted(duels.items(), key=lambda kv: -len(kv[1])):
    if len(data) < 25:
        print(f"{typ}: {len(data)} duels, trop peu pour estimer\n"); continue
    B = fit(data); bs = boot(data)
    lo, hi = np.percentile(bs, 5, axis=0), np.percentile(bs, 95, axis=0)
    share = np.mean([d[3] for d in data])
    result[typ] = {"n": len(data), "mean_opponent_share": round(100 * share, 1),
                   "rates": {r: {"opponent": [round(100 * B[i, 0]), round(100 * lo[i, 0]), round(100 * hi[i, 0])],
                                 "rn": [round(100 * B[i, 1]), round(100 * lo[i, 1]), round(100 * hi[i, 1])]} for i, r in enumerate(ROWS)}}
    print(f"{typ}: {len(data)} duels, adversaire du RN à {100*share:.1f} % en moyenne")
    for i, r in enumerate(ROWS):
        print(f"   {r:13} -> adversaire {100*B[i,0]:4.0f} % [{100*lo[i,0]:3.0f}-{100*hi[i,0]:3.0f}]   RN {100*B[i,1]:4.0f} % [{100*lo[i,1]:3.0f}-{100*hi[i,1]:3.0f}]")
    print()
json.dump(result, open(os.path.join(HERE, "data", f"leg_duels_{YEAR}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
