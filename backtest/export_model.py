"""Export everything the simulator needs to data/model.js (read by sandbox.js).

Usage: python3 backtest/export_model.py   (after update of polls_2027.json / duels_2027.json)
Every number here comes from backtest/data/*.json; assumptions are labelled "hypothese".
"""
import json, os, statistics as st, datetime as dt, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from simulate import fit_sigma, fit_sigma_duel, ELECTIONS

def J(p): return json.load(open(os.path.join(HERE, "data", p), encoding="utf-8"))
def D(s): return dt.date.fromisoformat(s)

TODAY = D("2026-11-06")
EDAY = D("2027-04-18")
WINDOW = 21

# candidates offered in the simulator: id, full name, short, bloc (voter family), type (as a finalist)
CANDS = [
    ("arthaud", "Nathalie Arthaud", "Arthaud", "GAUCHE", "RADG"),
    ("melenchon", "Jean-Luc Mélenchon", "Mélenchon", "GAUCHE", "LFI"),
    ("roussel", "Fabien Roussel", "Roussel", "GAUCHE", "RADG"),
    ("tondelier", "Marine Tondelier", "Tondelier", "GAUCHE", "GAUCHE"),
    ("glucksmann", "Raphaël Glucksmann", "Glucksmann", "GAUCHE", "GAUCHE"),
    ("attal", "Gabriel Attal", "Attal", "CENTRE", "CENTRE"),
    ("philippe", "Édouard Philippe", "Philippe", "CENTRE", "CENTRE"),
    ("villepin", "Dominique de Villepin", "Villepin", "CENTRE", "CENTRE"),
    ("lisnard", "David Lisnard", "Lisnard", "DROITE", "DROITE"),
    ("retailleau", "Bruno Retailleau", "Retailleau", "DROITE", "DROITE"),
    ("dupontaignan", "Nicolas Dupont-Aignan", "Dupont-Aignan", "RN_ALLIES", "EXD"),
    ("lepen", "Marine Le Pen", "Le Pen", "RN_ALLIES", "EXD"),
    ("bardella", "Jordan Bardella", "Bardella", "RN_ALLIES", "EXD"),
    ("zemmour", "Éric Zemmour", "Zemmour", "RN_ALLIES", "EXD"),
]
NAME2ID = {c[1]: c[0] for c in CANDS}

# ---- first round: average of each poll's most complete hypothesis over the last 21 days ----
polls = [p for p in J("polls_2027.json") if "election" not in p["firm"].lower()]
win = [p for p in polls if TODAY - dt.timedelta(days=WINDOW) < D(p["date"]) <= TODAY]
vals, firms = {}, set()
for p in win:
    best = max(p["scenarios"], key=lambda s: sum(1 for c in s if c in NAME2ID))
    tot = sum(best.values()); firms.add(p["firm"])
    for c, v in best.items():
        if c in NAME2ID: vals.setdefault(NAME2ID[c], []).append(100 * v / tot)
# candidates absent from most-complete hypotheses: use every hypothesis that includes them
for p in win:
    for s in p["scenarios"]:
        tot = sum(s.values())
        for c, v in s.items():
            cid = NAME2ID.get(c)
            if cid and cid not in vals: vals.setdefault("_" + cid, []).append(100 * v / tot)
base = {}
for k, v in vals.items():
    cid = k.lstrip("_")
    if cid not in base: base[cid] = {"v": round(st.mean(v), 2), "n": len(v)}
# Bardella: 90 % of Le Pen's score in the 4 polls that tested both in the same survey (2024)
base["bardella"] = {"v": round(0.90 * base["lepen"]["v"], 2), "n": 4, "note": "0,90 x Le Pen (4 sondages testant les deux, 2024)"}
DEFAULT_IN = [cid for cid in base if cid != "bardella" and base[cid]["n"] >= 2]

# ---- withdrawal transfers measured inside polls (same poll with and without X), since July 2026 ----
recent = [p for p in polls if D(p["date"]) >= D("2026-07-01")]
measured = {}
for p in recent:
    S = p["scenarios"]
    for a in S:
        for b in S:
            extra = set(a) - set(b)
            if len(extra) == 1 and set(b) <= set(a):
                x = extra.pop()
                if x not in NAME2ID or a[x] <= 0: continue
                measured.setdefault(NAME2ID[x], []).append({NAME2ID[c]: (b[c] - a[c]) / a[x] for c in b if c in NAME2ID})
withdraw = {}
for x, L in measured.items():
    if len(L) < 5: continue
    keys = set().union(*L)
    w = {c: max(0.0, st.mean(d.get(c, 0) for d in L)) for c in keys}
    t = sum(w.values())
    withdraw[x] = {"n": len(L), "to": {c: round(v / t, 3) for c, v in w.items() if v / t >= 0.01}}

# ---- duel polls: last 21 days, else last 3 polls within 6 months ----
duels = {}
for title, ps in J("duels_2027.json").items():
    rows = []
    for p in ps:
        s = p["scenarios"][0]
        if len(s) != 2: continue
        (a, va), (b, vb) = s.items()
        if a in NAME2ID and b in NAME2ID:
            rows.append((p["date"], NAME2ID[a], 100 * va / (va + vb), NAME2ID[b]))
    if not rows: continue
    rows.sort()
    a_id, b_id = rows[0][1], rows[0][3]
    w21 = [r for r in rows if TODAY - dt.timedelta(days=WINDOW) < D(r[0]) <= TODAY]
    use = w21 or [r for r in rows if D(r[0]) > TODAY - dt.timedelta(days=183)][-3:]
    if not use: continue
    duels[f"{a_id}|{b_id}"] = {"a": a_id, "b": b_id, "share_a": round(st.mean(r[2] for r in use), 2), "n": len(use),
                               "last": use[-1][0], "recent": bool(w21)}

# ---- second-round transfer rates (share of a first-round electorate: [to the RN's opponent, to the RN]) ----
def leg(year, key, bloc):
    r = J(f"leg_duels_{year}.json")[key]["rates"][bloc]
    return [r["opponent"][0], r["rn"][0]]
LEG = {}
for ctx in ("2022", "2024"):
    LEG[ctx] = {
        "LFI": {"CENTRE": leg(ctx, "GAUCHE_LFI", "CENTRE"), "DROITE": leg(ctx, "GAUCHE_LFI", "DROITE")},
        "GAUCHE": {"CENTRE": leg(ctx, "GAUCHE_AUTRE", "CENTRE"), "DROITE": leg(ctx, "GAUCHE_AUTRE", "DROITE")},
        "CENTRE": {"GAUCHE": leg(ctx, "CENTRE", "GAUCHE"), "DROITE": leg(ctx, "CENTRE", "DROITE")},
        "DROITE": {"GAUCHE": leg(ctx, "DROITE", "GAUCHE"), "CENTRE": leg(ctx, "DROITE", "CENTRE")},
    }
    LEG[ctx]["RADG"] = LEG[ctx]["LFI"]
# rows the legislative runoffs can't measure (voters of another left candidate facing a left finalist,
# far-right voters facing a non-RN finalist): explicit assumptions, by context
ASSUMED = {
    "2022": {"GAUCHE_to_LEFT": [23, 14], "EXD_vs_LEFT": [1, 85], "EXD_vs_CENTRE": [10, 73], "EXD_vs_DROITE": [25, 65]},
    "2024": {"GAUCHE_to_LEFT": [65, 6], "EXD_vs_LEFT": [1, 85], "EXD_vs_CENTRE": [10, 73], "EXD_vs_DROITE": [25, 65]},
}

sig = {h: round(fit_sigma(list(ELECTIONS), h), 2) for h in (163, 120, 90, 60, 30, 7)}
model = {
    "asof": TODAY.isoformat(), "election": EDAY.isoformat(), "horizon_days": (EDAY - TODAY).days,
    "n_polls": len(win), "firms": sorted(firms),
    "candidates": [{"id": c[0], "name": c[1], "short": c[2], "bloc": c[3], "type": c[4],
                    "base": base.get(c[0], {}).get("v"), "n": base.get(c[0], {}).get("n", 0),
                    "note": base.get(c[0], {}).get("note")} for c in CANDS if c[0] in base],
    "default_in": DEFAULT_IN,
    "withdraw": withdraw,
    "duels": duels,
    "leg": LEG, "assumed": ASSUMED,
    "sigma_first": sig, "sigma_duel": round(fit_sigma_duel(list(ELECTIONS)), 2),
    "lepen_correction": {"mean": 3.5, "sd": 1.5},
    "backtest": {"p_winner_j163": [0.58, 0.42, 0.94, 0.03, 0.79], "fav_won_j163": "3 sur 5"},
}
out = os.path.join(HERE, "..", "data", "model.js")
with open(out, "w", encoding="utf-8") as f:
    f.write("/* Généré par backtest/export_model.py : paramètres du simulateur. Ne pas éditer à la main. */\nwindow.MODEL = ")
    json.dump(model, f, ensure_ascii=False, separators=(",", ":"))
    f.write(";\n")
print(f"{len(win)} sondages, {len(model['candidates'])} candidats, défaut: {DEFAULT_IN}")
print("base:", {c['id']: c['base'] for c in model['candidates']})
print("retraits mesurés:", {k: v['n'] for k, v in withdraw.items()})
print("duels:", {k: (v['share_a'], v['n'], v['last']) for k, v in duels.items()})
print("sigma 1er tour:", sig, "sigma duel:", model["sigma_duel"])
