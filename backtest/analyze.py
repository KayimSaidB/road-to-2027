"""Backtest: how far were first-round polls from the result, N days before each election?
And would a simple Monte Carlo built on those errors have given sensible odds?

Usage: python3 backtest/analyze.py   (reads backtest/data/polls_*.json, writes backtest/data/backtest.json)
"""
import json, math, os, random, statistics as st, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
ELECTIONS = {2002: "2002-04-21", 2007: "2007-04-22", 2012: "2012-04-22", 2017: "2017-04-23", 2022: "2022-04-10"}
# Second round, % of valid votes (Conseil constitutionnel)
SECOND = {
    2002: {"Jacques Chirac": 82.21, "Jean-Marie Le Pen": 17.79},
    2007: {"Nicolas Sarkozy": 53.06, "Ségolène Royal": 46.94},
    2012: {"François Hollande": 51.64, "Nicolas Sarkozy": 48.36},
    2017: {"Emmanuel Macron": 66.10, "Marine Le Pen": 33.90},
    2022: {"Emmanuel Macron": 58.55, "Marine Le Pen": 41.45},
}
HORIZONS = [163, 120, 90, 60, 30, 7]
WINDOW = 21          # days of polls used at each horizon ("what was known then")
MAJOR = 5.0          # candidates at or above this result are scored

def D(s): return dt.date.fromisoformat(s)

def load(y):
    polls = json.load(open(os.path.join(HERE, "data", f"polls_{y}.json"), encoding="utf-8"))
    res = [p for p in polls if p["firm"].lower().startswith(str(y)) and "election" in p["firm"].lower()]
    result = max(res, key=lambda p: len(p["scenarios"][0]))["scenarios"][0]
    real = [p for p in polls if "election" not in p["firm"].lower()]
    return result, real

def snapshot(polls, result, eday, h):
    """Average of polls in the WINDOW days up to J-h. For each poll, the scenario closest to the
    final field (hindsight on who runs: field uncertainty is measured separately)."""
    end = eday - dt.timedelta(days=h)
    win = [p for p in polls if end - dt.timedelta(days=WINDOW) < D(p["date"]) <= end]
    final = {c for c, v in result.items() if v >= MAJOR}
    vals, missing = {}, set()
    for p in win:
        best = max(p["scenarios"], key=lambda s: (len(final & set(s)), -len(set(s) - set(result))))
        for c, v in best.items():
            if c in result:
                vals.setdefault(c, []).append(v)
        missing |= final - set(best)
    avg = {c: st.mean(v) for c, v in vals.items()}
    return avg, len(win), sorted(missing - set(avg))

def top2(d): return tuple(sorted(sorted(d, key=d.get, reverse=True)[:2]))

out = {"horizons": HORIZONS, "elections": {}}
errors = {h: [] for h in HORIZONS}       # (poll, result) pairs for major candidates
for y, e in ELECTIONS.items():
    result, polls = load(y)
    eday = D(e)
    rows = {}
    for h in HORIZONS:
        avg, n, missing = snapshot(polls, result, eday, h)
        if not avg:
            continue
        scored = {c: (round(avg[c], 1), result[c]) for c in result if result[c] >= MAJOR and c in avg}
        for c, (p, r) in scored.items():
            errors[h].append((p, r, y, c))
        rows[h] = {"n_polls": n, "missing_from_field": missing, "poll_top2": top2(avg), "real_top2": top2(result),
                   "top2_ok": top2(avg) == top2(result), "leader_ok": max(avg, key=avg.get) == max(result, key=result.get),
                   "scored": scored}
    out["elections"][y] = {"date": e, "result": result, "second": SECOND[y], "by_horizon": rows}

# Error model: result - poll ~ N(0, sigma_h * sqrt(p / 20))   (bigger candidates move more)
def sigma(pairs):
    z = [(r - p) / math.sqrt(max(p, 1) / 20) for p, r, *_ in pairs]
    return math.sqrt(sum(v * v for v in z) / len(z)) if z else None

out["sigma"] = {h: round(sigma(errors[h]), 2) for h in HORIZONS}
out["mae"] = {h: round(st.mean(abs(r - p) for p, r, *_ in errors[h]), 2) for h in HORIZONS}

# Monte Carlo, leave-one-election-out: sigma fitted on the OTHER elections only.
def simulate(avg, sig, n=20000, seed=1):
    rnd = random.Random(seed)
    names = list(avg)
    qual = {c: 0 for c in names}
    pairs = {}
    for _ in range(n):
        draw = {c: max(0.1, avg[c] + rnd.gauss(0, sig * math.sqrt(max(avg[c], 1) / 20))) for c in names}
        t = top2(draw)
        pairs[t] = pairs.get(t, 0) + 1
        for c in t:
            qual[c] += 1
    return {c: qual[c] / n for c in names}, {k: v / n for k, v in pairs.items()}

cal = []
for y, e in ELECTIONS.items():
    result, polls = load(y)
    for h in HORIZONS:
        others = [x for x in errors[h] if x[2] != y]
        sig = sigma(others)
        avg, n, _ = snapshot(polls, result, D(e), h)
        if not avg or not sig:
            continue
        q, pairs = simulate(avg, sig)
        real = top2(result)
        out["elections"][y]["by_horizon"][h]["sim"] = {
            "sigma_used": round(sig, 2),
            "p_real_pair": round(pairs.get(real, 0), 3),
            "p_qualify": {c: round(v, 3) for c, v in sorted(q.items(), key=lambda kv: -kv[1])[:6]},
            "fav_pair": [list(k) for k, _ in sorted(pairs.items(), key=lambda kv: -kv[1])[:1]][0],
            "p_fav_pair": round(max(pairs.values()), 3),
        }
        for c in q:
            if result.get(c, 0) >= 1:
                cal.append((q[c], 1 if c in real else 0, h))

# Calibration of "chance to reach round 2": Brier score and binned reliability
out["calibration"] = {}
for h in HORIZONS:
    pts = [(p, o) for p, o, hh in cal if hh == h]
    bins = {}
    for p, o in pts:
        b = min(4, int(p * 5))
        bins.setdefault(b, []).append((p, o))
    out["calibration"][h] = {
        "brier": round(st.mean((p - o) ** 2 for p, o in pts), 4),
        "bins": {f"{b*20}-{b*20+20}%": {"n": len(v), "mean_p": round(st.mean(p for p, _ in v), 2), "observed": round(st.mean(o for _, o in v), 2)} for b, v in sorted(bins.items())},
    }

json.dump(out, open(os.path.join(HERE, "data", "backtest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=list)

# ---- printed summary ----
print("Écart moyen sondages/résultat (candidats >= 5 %), en points, et sigma du modèle")
print("  J-" + "  J-".join(f"{h:<5}" for h in HORIZONS))
print("  MAE  " + "  ".join(f"{out['mae'][h]:<6}" for h in HORIZONS))
print("  sigma" + "  ".join(f"{out['sigma'][h]:<6}" for h in HORIZONS))
for y in ELECTIONS:
    print(f"\n{y}  réel: {top2(out['elections'][y]['result'])}")
    for h, r in out["elections"][y]["by_horizon"].items():
        s = r.get("sim", {})
        print(f"  J-{h:<4} {r['n_polls']:>3} sondages  top2 sondages={'OK ' if r['top2_ok'] else 'NON'} {r['poll_top2']}"
              f"  P(vrai duel)={s.get('p_real_pair', '-')}  duel favori={s.get('fav_pair')} {s.get('p_fav_pair')}"
              + (f"  absents du champ: {r['missing_from_field']}" if r['missing_from_field'] else ""))
print("\nCalibration (chance d'accéder au 2nd tour), Brier par horizon:", {h: out["calibration"][h]["brier"] for h in HORIZONS})
for h in (163, 30):
    print(f"  J-{h}", out["calibration"][h]["bins"])
