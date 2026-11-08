"""Do previous elections help? Blend polls with earlier results at the level of political blocs.

For a presidential election Y at horizon J-h:
  bloc total  = w_poll * polls + w_pres * previous presidential + w_leg * last legislative
                + w_euro * last European (+ w_muni * last municipal, if available)
  candidate   = bloc total x the candidate's share of the bloc in the polls
Weights are chosen on the 4 other elections and scored on the held-out one (leave-one-out),
so the improvement, if any, is measured honestly.

Usage: python3 backtest/analyze_blend.py   (needs data/intermediate_elections.json)
"""
import itertools, json, os, statistics as st, datetime as dt, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from blocs import BLOCS, bloc_of

ELECTIONS = {2002: "2002-04-21", 2007: "2007-04-22", 2012: "2012-04-22", 2017: "2017-04-23", 2022: "2022-04-10"}
PREV_PRES = {2002: (2002, "1995"), 2007: (2002, "2002"), 2012: (2012, "2007"), 2017: (2017, "2012"), 2022: (2022, "2017")}
LAST_LEG = {2002: "1997", 2007: "2002", 2012: "2007", 2017: "2012", 2022: "2017"}
LAST_EURO = {2002: "1999", 2007: "2004", 2012: "2009", 2017: "2014", 2022: "2019"}
LAST_MUNI = {2002: "2001", 2007: None, 2012: "2008", 2017: "2014", 2022: "2020"}  # 2007: no municipal since 2001 within term
HORIZONS = [163, 120, 90, 60, 30, 7]
WINDOW, MAJOR, STEP = 21, 5.0, 0.2

def D(s): return dt.date.fromisoformat(s)

def load(y):
    polls = json.load(open(os.path.join(HERE, "data", f"polls_{y}.json"), encoding="utf-8"))
    res = [p for p in polls if p["firm"].lower().startswith(str(y)) and "election" in p["firm"].lower()]
    result = max(res, key=lambda p: len(p["scenarios"][0]))["scenarios"][0]
    return result, [p for p in polls if "election" not in p["firm"].lower()]

def result_row(file_year, label):
    polls = json.load(open(os.path.join(HERE, "data", f"polls_{file_year}.json"), encoding="utf-8"))
    rows = [p for p in polls if p["firm"].lower().startswith(label) and "election" in p["firm"].lower()]
    return max(rows, key=lambda p: len(p["scenarios"][0]))["scenarios"][0]

def to_blocs(shares):
    b = {k: 0.0 for k in BLOCS}
    for c, v in shares.items():
        b[bloc_of(c)] += v
    t = sum(b.values())
    return {k: 100 * v / t for k, v in b.items()}

def norm_blocs(b):
    b = {k: (b.get(k) or 0.0) for k in BLOCS}
    t = sum(b.values())
    return {k: 100 * v / t for k, v in b.items()} if t else None

def snapshot(polls, result, eday, h):
    end = eday - dt.timedelta(days=h)
    win = [p for p in polls if end - dt.timedelta(days=WINDOW) < D(p["date"]) <= end]
    final = {c for c, v in result.items() if v >= MAJOR}
    vals = {}
    for p in win:
        best = max(p["scenarios"], key=lambda s: (len(final & set(s)), -len(set(s) - set(result))))
        tot = sum(best.values())
        for c, v in best.items():
            vals.setdefault(c, []).append(100 * v / tot)
    return {c: st.mean(v) for c, v in vals.items()}

inter = json.load(open(os.path.join(HERE, "data", "intermediate_elections.json"), encoding="utf-8"))

def inter_blocs(kind, year):
    if not year:
        return None
    src = inter.get(kind, {})
    if kind == "municipal":
        if not src.get("available"):
            return None
        src = src.get("data", {})
    e = src.get(year)
    if not e:
        return None
    b = dict(e["blocs"])
    if b.get("UNION_GAUCHE"):
        b["GAU"] = (b.get("GAU") or 0) + b.pop("UNION_GAUCHE")  # backtest years have no union; safeguard
    return norm_blocs({k: b.get(k) for k in BLOCS})

# Pre-compute everything per election and horizon
cases = {}
for y, e in ELECTIONS.items():
    result, polls = load(y)
    srcs = {"pres": to_blocs(result_row(*PREV_PRES[y])), "leg": inter_blocs("legislative", LAST_LEG[y]),
            "euro": inter_blocs("european", LAST_EURO[y]), "muni": inter_blocs("municipal", LAST_MUNI[y])}
    # swing sources: previous presidential + change of each bloc between two elections of one type
    PREV_EURO = {2007: "1999", 2012: "2004", 2017: "2009", 2022: "2014"}
    PREV_LEG = {2007: "1997", 2012: "2002", 2017: "2007", 2022: "2012"}
    for kind, last, prev, key in (("european", LAST_EURO, PREV_EURO, "swing_euro"), ("legislative", LAST_LEG, PREV_LEG, "swing_leg")):
        a_, b_ = inter_blocs(kind, last.get(y)), inter_blocs(kind, prev.get(y))
        srcs[key] = norm_blocs({k: max(0.0, srcs["pres"][k] + a_[k] - b_[k]) for k in BLOCS}) if a_ and b_ else None
    for h in HORIZONS:
        avg = snapshot(polls, result, D(e), h)
        if avg:
            cases[(y, h)] = {"avg": avg, "poll_blocs": to_blocs(avg), "srcs": srcs, "result": result}

# Municipal results are excluded: no usable national aggregate (see intermediate_elections.json)
SOURCES = ["poll", "pres", "leg", "euro", "swing_euro", "swing_leg"]
def weight_grid():
    n = round(1 / STEP)
    for combo in itertools.product(range(n + 1), repeat=len(SOURCES)):
        if sum(combo) == n:
            yield dict(zip(SOURCES, (c * STEP for c in combo)))

def predict(case, w):
    pb, srcs = case["poll_blocs"], case["srcs"]
    eff = {k: v for k, v in w.items() if v > 0 and (k == "poll" or srcs.get(k))}
    if not eff:              # requested sources don't exist for this election: polls only
        eff = {"poll": 1.0}
    tot = sum(eff.values())
    blend = {b: sum(wt * (pb[b] if k == "poll" else srcs[k][b]) for k, wt in eff.items()) / tot for b in BLOCS}
    out = {}
    for c, v in case["avg"].items():
        b = bloc_of(c)
        out[c] = blend[b] * v / pb[b] if pb[b] > 0 else v
    return out, blend

def errors(case, w):
    pred, blend = predict(case, w)
    res = case["result"]
    cand = [abs(pred[c] - res[c]) for c in res if res[c] >= MAJOR and c in pred]
    rb = to_blocs(res)
    return st.mean(cand), st.mean(abs(blend[b] - rb[b]) for b in BLOCS)

GRID = list(weight_grid())
POLL_ONLY = {k: (1.0 if k == "poll" else 0) for k in SOURCES}
report = {"horizons": {}, "note": "MAE in points; candidate = candidates with result >= 5 %; LOO = weights picked on the 4 other elections"}
print("Erreur moyenne (points) - candidats >= 5 % | blocs.  LOO = poids choisis sur les 4 autres élections\n")
print(f"{'horizon':8} {'sondages seuls':>16} {'mélange (LOO)':>16}   poids choisis par élection testée")
for h in HORIZONS:
    ys = [y for y in ELECTIONS if (y, h) in cases]
    base = [errors(cases[(y, h)], POLL_ONLY) for y in ys]
    loo, chosen = [], {}
    for test in ys:
        train = [y for y in ys if y != test]
        best = min(GRID, key=lambda w: st.mean(errors(cases[(y, h)], w)[0] for y in train))
        chosen[test] = {k: round(v, 1) for k, v in best.items() if v > 0}
        loo.append(errors(cases[(test, h)], best))
    insample = min(GRID, key=lambda w: st.mean(errors(cases[(y, h)], w)[0] for y in ys))
    report["horizons"][h] = {
        "poll_only": {"cand": round(st.mean(b[0] for b in base), 2), "bloc": round(st.mean(b[1] for b in base), 2)},
        "blend_loo": {"cand": round(st.mean(l[0] for l in loo), 2), "bloc": round(st.mean(l[1] for l in loo), 2)},
        "per_election": {y: {"poll_only": round(base[i][0], 2), "blend_loo": round(loo[i][0], 2), "weights": chosen[y]} for i, y in enumerate(ys)},
        "best_weights_all5": {k: round(v, 1) for k, v in insample.items() if v > 0},
    }
    r = report["horizons"][h]
    print(f"J-{h:<6} {r['poll_only']['cand']:>7} | {r['poll_only']['bloc']:<6} {r['blend_loo']['cand']:>7} | {r['blend_loo']['bloc']:<6}   "
          + "  ".join(f"{y}:{chosen[y]}" for y in ys))
    print(f"{'':9}détail candidats: " + "  ".join(f"{y} {base[i][0]:.1f}->{loo[i][0]:.1f}" for i, y in enumerate(ys)) + f"   | meilleurs poids sur les 5: {r['best_weights_all5']}")

# Single-source diagnostics: how good is each source alone at predicting bloc totals?
print("\nChaque source seule pour prédire les blocs (erreur moyenne par bloc, points):")
for s in ["pres", "leg", "euro", "swing_euro", "swing_leg"]:
    errs = []
    for y in ELECTIONS:
        src = cases[(y, 163)]["srcs"].get(s) if (y, 163) in cases else None
        if src:
            rb = to_blocs(cases[(y, 163)]["result"])
            errs.append((y, st.mean(abs(src[b] - rb[b]) for b in BLOCS)))
    if errs:
        print(f"  {s:5} " + "  ".join(f"{y}:{e:.1f}" for y, e in errs) + f"   moyenne {st.mean(e for _, e in errs):.1f}")
pb = [(y, st.mean(abs(cases[(y, 163)]["poll_blocs"][b] - to_blocs(cases[(y, 163)]["result"])[b]) for b in BLOCS)) for y in ELECTIONS if (y, 163) in cases]
print(f"  sondages J-163 " + "  ".join(f"{y}:{e:.1f}" for y, e in pb) + f"   moyenne {st.mean(e for _, e in pb):.1f}")

json.dump(report, open(os.path.join(HERE, "data", "blend.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
