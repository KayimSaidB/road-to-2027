"""Model applied to 2027 today (J-163). First round: v1 errors (sigma fitted on 2002–2022).
Second round: 2027 duel polls (last 21 days), fallback for unpolled pairs, with or without the
"Le Pen duel correction" (duel polls overstated a Le Pen by 2.6–5.4 pts in 2002, 2017, 2022).

Usage: python3 backtest/predict_2027.py
"""
import json, math, os, random, statistics as st, datetime as dt, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from simulate import fit_sigma, fit_sigma_duel, simulate, fallback_duel, J, D, ELECTIONS

EDAY, TODAY = D("2027-04-18"), D("2026-11-06")
H = (EDAY - TODAY).days
LE_PEN = {"Marine Le Pen", "Jean-Marie Le Pen", "Jordan Bardella"}

polls = [p for p in J("polls_2027.json") if "election" not in p["firm"].lower()]
win = [p for p in polls if TODAY - dt.timedelta(days=21) < D(p["date"]) <= TODAY]
vals = {}
for p in win:  # most complete hypothesis of each poll (Attal and Philippe both running when tested)
    best = max(p["scenarios"], key=len); tot = sum(best.values())
    for c, v in best.items(): vals.setdefault(c, []).append(100 * v / tot)
avg = {c: st.mean(v) for c, v in vals.items() if len(v) >= max(2, len(win) // 3)}
t = sum(avg.values()); avg = {c: 100 * v / t for c, v in avg.items()}

duels = {}
for title, ps in J("duels_2027.json").items():
    for p in ps:
        s = p["scenarios"][0]
        if len(s) == 2 and TODAY - dt.timedelta(days=21) < D(p["date"]) <= TODAY:
            (a, va), (b, vb) = s.items()
            duels.setdefault(frozenset((a, b)), []).append({a: 100 * va / (va + vb), b: 100 * vb / (va + vb)})
duels = {k: {c: st.mean(d[c] for d in v) for c in k} for k, v in duels.items()}

years = list(ELECTIONS)
sig = fit_sigma(years, min((163, 120, 90, 60, 30, 7), key=lambda h: abs(h - H)))
sdu = fit_sigma_duel(years)
pairs = simulate(avg, sig, 0.0, 0.0, random.Random(2027), n=20000)

def run(correction, sd_extra=0.0):
    winp, srcs = {}, {}
    for (A, B), pv in pairs.items():
        key = frozenset((A, B))
        m = duels[key][A] if key in duels else fallback_duel(avg, A, B)
        srcs[(A, B)] = "sondages" if key in duels else "repli"
        if correction:
            if A in LE_PEN: m -= correction
            if B in LE_PEN: m += correction
        s = math.sqrt(sdu ** 2 + sd_extra ** 2)
        pa = 0.5 * (1 + math.erf((m - 50) / (s * math.sqrt(2))))
        winp[A] = winp.get(A, 0) + pv * pa; winp[B] = winp.get(B, 0) + pv * (1 - pa)
    return winp, srcs

qual = {}
for p, v in pairs.items():
    for c in p: qual[c] = qual.get(c, 0) + v
raw, srcs = run(0)
adj, _ = run(3.5, 1.5)
print(f"2027 au {TODAY} (J-{H}) · {len(win)} sondages · sigma 1er tour {sig:.2f} · sigma duel {sdu:.2f}\n")
print(f"{'candidat':22} {'moy. sondages':>13} {'accès 2nd tour':>15} {'victoire brute':>15} {'victoire corrigée':>18}")
for c in sorted(avg, key=lambda c: -qual.get(c, 0)):
    if qual.get(c, 0) < 0.005: continue
    print(f"{c:22} {avg[c]:>12.1f}% {100*qual.get(c,0):>14.0f}% {100*raw.get(c,0):>14.0f}% {100*adj.get(c,0):>17.0f}%")
print("\nDuels les plus probables :")
for (A, B), v in sorted(pairs.items(), key=lambda kv: -kv[1])[:6]:
    key = frozenset((A, B))
    m = duels[key][A] if key in duels else fallback_duel(avg, A, B)
    surname = A.split(" ", 1)[1]
    print(f"  {A:20} vs {B:18} {100*v:4.0f}%   {surname} {m:4.1f} % ({srcs[(A, B)]})")
