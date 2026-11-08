"""Model v2: first round with correlated errors + second round from duel polls.

First round, candidate c in bloc b, poll average p_c, horizon h:
    e_c = s_h * sqrt(p_c/20) * ( a * z_b  +  sqrt(1-a^2) * u_c )
    u_c = z_c - k * mean(z over c's bloc)     (k: tactical voting inside a bloc, zero-sum)
    a = how much a whole bloc moves together. a = k = 0 is model v1.
Second round, pair (A, B): mean of duel polls in the 21 days up to J-h (else last poll in the
120 days before), drawn ~ N(mean, s_duel). Pairs nobody polled: bloc-affinity fallback.
All parameters chosen out of sample (leave-one-election-out).

Usage: python3 backtest/simulate.py
"""
import json, math, os, random, statistics as st, datetime as dt, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from blocs import BLOCS, bloc_of

ELECTIONS = {2002: "2002-04-21", 2007: "2007-04-22", 2012: "2012-04-22", 2017: "2017-04-23", 2022: "2022-04-10"}
WINNER = {2002: "Jacques Chirac", 2007: "Nicolas Sarkozy", 2012: "François Hollande", 2017: "Emmanuel Macron", 2022: "Emmanuel Macron"}
SECOND = {2002: ("Jacques Chirac", 82.21), 2007: ("Nicolas Sarkozy", 53.06), 2012: ("François Hollande", 51.64),
          2017: ("Emmanuel Macron", 66.10), 2022: ("Emmanuel Macron", 58.55)}
HORIZONS = [163, 120, 90, 60, 30, 7]
WINDOW, MAJOR, NSIM = 21, 5.0, 6000

def D(s): return dt.date.fromisoformat(s)
def J(path): return json.load(open(os.path.join(HERE, "data", path), encoding="utf-8"))

# ---------------- data ----------------
def load(y):
    polls = J(f"polls_{y}.json")
    res = [p for p in polls if p["firm"].lower().startswith(str(y)) and "election" in p["firm"].lower()]
    result = max(res, key=lambda p: len(p["scenarios"][0]))["scenarios"][0]
    return result, [p for p in polls if "election" not in p["firm"].lower()]

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
    return {c: st.mean(v) for c, v in vals.items() if c in result}

SURNAME = lambda full: full.split(" ", 1)[1] if " " in full else full
def duel_lookup(y):
    """{frozenset(surnameA, surnameB): [(date, share_of_first_named...)]} with shares per full name."""
    out = {}
    for title, polls in J(f"duels_{y}.json").items():
        for p in polls:
            s = p["scenarios"][0]
            if len(s) != 2: continue
            (a, va), (b, vb) = list(s.items())
            out.setdefault(frozenset((a, b)), []).append((p["date"], {a: 100 * va / (va + vb), b: 100 * vb / (va + vb)}))
    return out

def duel_mean(dl, A, B, eday, h):
    key = frozenset((A, B))
    if key not in dl: return None
    end = eday - dt.timedelta(days=h)
    rows = [(d, s) for d, s in dl[key] if D(d) <= end]
    win = [s[A] for d, s in rows if D(d) > end - dt.timedelta(days=WINDOW)]
    if not win:
        win = [s[A] for d, s in rows if D(d) > end - dt.timedelta(days=120)][-3:]
    return st.mean(win) if win else None

# Fallback for unpolled pairs: affinity of each voter bloc for a finalist's bloc (0..1).
# Shaped on Ipsos 2017/2022 election-day transfers and Harris 2027 cross-tabs (see README).
AFF = {
    "RADG": {"RADG": .95, "GAU": .75, "CEN": .50, "DRO": .20, "EXD": .12, "AUT": .3},
    "GAU":  {"RADG": .55, "GAU": .95, "CEN": .70, "DRO": .30, "EXD": .06, "AUT": .3},
    "CEN":  {"RADG": .12, "GAU": .60, "CEN": .97, "DRO": .55, "EXD": .15, "AUT": .3},
    "DRO":  {"RADG": .03, "GAU": .20, "CEN": .52, "DRO": .95, "EXD": .40, "AUT": .3},
    "EXD":  {"RADG": .05, "GAU": .05, "CEN": .10, "DRO": .45, "EXD": .95, "AUT": .3},
    "AUT":  {b: .30 for b in BLOCS},
}
def fallback_duel(first, A, B):
    va = vb = 0.0
    for c, v in first.items():
        if c == A: va += v; continue
        if c == B: vb += v; continue
        fa, fb = AFF[bloc_of(c)][bloc_of(A)], AFF[bloc_of(c)][bloc_of(B)]
        tot = fa + fb
        va += v * fa * fa / tot; vb += v * fb * fb / tot   # the closer finalist gets most; distance -> abstention
    return 100 * va / (va + vb)

# ---------------- first-round error scale (v1 sigma, leave-one-out) ----------------
def fit_sigma(train_years, h):
    z = []
    for y in train_years:
        result, polls = load(y)
        avg = snapshot(polls, result, D(ELECTIONS[y]), h)
        for c, p in avg.items():
            if result[c] >= MAJOR:
                z.append((result[c] - p) / math.sqrt(max(p, 1) / 20))
    return math.sqrt(sum(v * v for v in z) / len(z))

def fit_sigma_duel(train_years):
    errs = []
    for y in train_years:
        A, real = SECOND[y]
        result, _ = load(y)
        B = [c for c in sorted(result, key=result.get, reverse=True)[:2] if c != A][0]
        dl = duel_lookup(y)
        for h in HORIZONS:
            m = duel_mean(dl, A, B, D(ELECTIONS[y]), h)
            if m is not None:
                errs.append(real - m)
    return math.sqrt(sum(e * e for e in errs) / len(errs)) if errs else 5.0

# ---------------- simulation ----------------
def simulate(avg, sig, a, k, rnd, n=NSIM):
    names = list(avg)
    blocs = {}
    for c in names: blocs.setdefault(bloc_of(c), []).append(c)
    pairs = {}
    for _ in range(n):
        zb = {b: rnd.gauss(0, 1) for b in blocs}
        zc = {c: rnd.gauss(0, 1) for c in names}
        draw = {}
        for b, cs in blocs.items():
            m = st.mean(zc[c] for c in cs) if len(cs) > 1 else 0.0
            for c in cs:
                u = zc[c] - k * m
                e = sig * math.sqrt(max(avg[c], 1) / 20) * (a * zb[b] + math.sqrt(1 - a * a) * u)
                draw[c] = max(0.05, avg[c] + e)
        t = tuple(sorted(sorted(draw, key=draw.get, reverse=True)[:2]))
        pairs[t] = pairs.get(t, 0) + 1
    return {p: v / n for p, v in pairs.items()}

def evaluate(y, h, sig, a, k, sig_duel, seed=7):
    result, polls = load(y)
    eday = D(ELECTIONS[y])
    avg = snapshot(polls, result, eday, h)
    if not avg: return None
    pairs = simulate(avg, sig, a, k, random.Random(seed))
    real_pair = tuple(sorted(sorted(result, key=result.get, reverse=True)[:2]))
    qual = {}
    for p, v in pairs.items():
        for c in p: qual[c] = qual.get(c, 0) + v
    dl = duel_lookup(y)
    win = {}
    used_fallback = 0.0
    for (A, B), pv in pairs.items():
        m = duel_mean(dl, A, B, eday, h)
        if m is None:
            m = fallback_duel(avg, A, B); used_fallback += pv
        pa = 0.5 * (1 + math.erf((m - 50) / (sig_duel * math.sqrt(2))))
        win[A] = win.get(A, 0) + pv * pa; win[B] = win.get(B, 0) + pv * (1 - pa)
    real_q = set(real_pair)
    brier = st.mean((qual.get(c, 0) - (1 if c in real_q else 0)) ** 2 for c in result if result[c] >= 1)
    return {"p_real_pair": pairs.get(real_pair, 0), "brier_qual": brier, "p_winner": win.get(WINNER[y], 0),
            "fav": max(win, key=win.get), "p_fav": max(win.values()), "fallback_share": used_fallback,
            "top_pairs": sorted(((list(p), round(v, 3)) for p, v in pairs.items()), key=lambda x: -x[1])[:3]}

if __name__ == "__main__":
    GRID = [(a, k) for a in (0.0, 0.4, 0.7) for k in (0.0, 0.5, 1.0)]
    years = list(ELECTIONS)
    out = {}
    print("Paramètres choisis hors échantillon. Score : log-perte sur l'accès au 2nd tour (plus bas = mieux)\n")
    summary = {"v1": [], "v2": []}
    for h in HORIZONS:
        for test in years:
            train = [y for y in years if y != test]
            sig = fit_sigma(train, h)
            sdu = fit_sigma_duel(train)
            def loss(a, k, ys):
                tot = 0.0
                for y in ys:
                    r = evaluate(y, h, fit_sigma([t for t in train if t != y] or train, h), a, k, sdu)
                    if r: tot += -math.log(max(r["p_real_pair"], 1e-3))
                return tot
            a, k = min(GRID, key=lambda ak: loss(*ak, train))
            v1 = evaluate(test, h, sig, 0.0, 0.0, sdu)
            v2 = evaluate(test, h, sig, a, k, sdu)
            if not v2: continue
            out.setdefault(h, {})[test] = {"a": a, "k": k, "sigma": round(sig, 2), "sigma_duel": round(sdu, 2), "v1": v1, "v2": v2}
            summary["v1"].append((h, test, v1)); summary["v2"].append((h, test, v2))
        row = out.get(h, {})
        print(f"J-{h:<4} " + "  ".join(
            f"{y}: duel réel {r['v1']['p_real_pair']:.2f}->{r['v2']['p_real_pair']:.2f} (a={r['a']},k={r['k']}), "
            f"P(vainqueur) {r['v2']['p_winner']:.2f}" for y, r in row.items()))
    print()
    for v in ("v1", "v2"):
        ll = [-math.log(max(r["p_real_pair"], 1e-3)) for _, _, r in summary[v]]
        bq = [r["brier_qual"] for _, _, r in summary[v]]
        pw = [r["p_winner"] for _, _, r in summary[v]]
        print(f"{v}: log-perte duel réel {st.mean(ll):.3f} · Brier qualification {st.mean(bq):.4f} · P(vrai vainqueur) moyenne {st.mean(pw):.2f}")
    print("\nP(vrai vainqueur) par horizon (v2) :")
    for h in HORIZONS:
        print(f"  J-{h:<4} " + "  ".join(f"{y}:{r['v2']['p_winner']:.2f}{'*' if r['v2']['fallback_share']>0.3 else ''}" for y, r in out.get(h, {}).items())
              + "   (* = surtout le modèle de repli, duel non sondé)")
    json.dump({str(h): {str(y): r for y, r in v.items()} for h, v in out.items()},
              open(os.path.join(HERE, "data", "v2_backtest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
