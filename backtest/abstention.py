"""Abstention: who stays home, and what it does to each candidate (first round).

Usage: python3 backtest/abstention.py      -> data/abstention.json (read by export_model.py)
Inputs: data/abstention_inputs.json (copied from INSEE, Ipsos, OpinionWay, YouGov; sources inside).

Model. Split the registered voters into groups g along one dimension (age, profession, 2022 vote, sex):
    share_c = sum_g N_g t_g s_cg / sum_g N_g t_g
N_g registered voters in the group, t_g its turnout, s_cg candidate c's share among its voters.
A turnout scenario moves every group on the logit scale:
    logit t'_g = logit t_g + a_g * D      (D solved so that overall turnout hits the target)
a_g says how strongly group g follows overall swings. It is fitted on INSEE turnout by age,
2002-2022 (official signature lists, not a survey); a_g = 1 where nothing is measured.
Targeted levers (young people, working class, 2022 abstainers) add points to one group only.

1. Elasticities a_g by age (INSEE).
2. Backtest 2017 and 2022: polls are made of respondents "certain to vote"; actual turnout came out
   about 5 pts higher both times. Does reweighting the real electorate (Ipsos election-day survey)
   down to the polls' turnout reproduce the polls' errors?
3. 2027: candidate profiles by age, profession, 2022 vote and sex, from the pollsters' cross-tabs,
   shrunk toward the candidate's total where cells are small. Sensitivity table.
"""
import json, math, os, statistics as st, sys, datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from simulate import load, snapshot, ELECTIONS
from candidates_2027 import CANDS, NAME2ID

IN = json.load(open(os.path.join(HERE, "data", "abstention_inputs.json"), encoding="utf-8"))
K_SHRINK = 100      # pseudo-respondents pulling a small cell toward the candidate's total

def logit(p): return math.log(p / (1 - p))
def sig(x): return 1 / (1 + math.exp(-x))

# ---------------- 1. elasticities by age (INSEE) ----------------
def fit_elasticities(exclude_until=None):
    """a_g = slope (through 0) of group logit change on overall logit change, between consecutive
    presidential first rounds. exclude_until: drop changes ending in or after that year (out of sample)."""
    ins = IN["insee_turnout_t1_by_age"]
    years = [y for y in ["2002", "2007", "2012", "2017", "2022"] if exclude_until is None or int(y) < exclude_until]
    a = []
    for gi, _ in enumerate(ins["groups"]):
        num = den = 0.0
        for y0, y1 in zip(years, years[1:]):
            x = logit(ins["all"][y1] / 100) - logit(ins["all"][y0] / 100)
            yv = logit(ins[y1][gi] / 100) - logit(ins[y0][gi] / 100)
            num += x * yv; den += x * x
        a.append(num / den)
    return dict(zip(ins["groups"], a))

def age_a(groups, el):
    """Map INSEE bands (18-29, 30-64, 65+) onto finer bands."""
    y, m, o = el["18-29"], el["30-64"], el["65+"]
    table = {"18-24": y, "25-34": y, "18-34": y, "35-49": m, "35-54": m, "50-59": m,
             "50-64": m, "60-69": (m + o) / 2, "55+": (m + o) / 2, "65+": o, "70+": o}
    return [table[g] for g in groups]

# ---------------- turnout move and shares ----------------
def move(N, t, a, dT=0.0, extra=None):
    """t (fractions) -> t' with overall turnout + dT (fraction), uniform-logit shift weighted by a,
    then `extra` (fractions, per group) added on top."""
    tot = sum(N)
    T0 = sum(n * x for n, x in zip(N, t)) / tot
    lo, hi = -6.0, 6.0
    for _ in range(80):
        mid = (lo + hi) / 2
        T = sum(n * sig(logit(x) + ai * mid) for n, x, ai in zip(N, t, a)) / tot
        lo, hi = (mid, hi) if T < T0 + dT else (lo, mid)
    t2 = [sig(logit(x) + ai * lo) for x, ai in zip(t, a)]
    if extra:
        t2 = [min(0.99, max(0.01, x + e)) for x, e in zip(t2, extra)]
    return t2

def shares(N, t, S):
    """S[g] = vote shares in group g (list over candidates) -> overall shares, in % of valid votes."""
    w = [n * x for n, x in zip(N, t)]
    out = [sum(wg * S[g][c] for g, wg in enumerate(w)) for c in range(len(S[0]))]
    tot = sum(out)
    return [100 * v / tot for v in out]

# ---------------- 2. backtest ----------------
def dimension(year, dim):
    ip = IN["ipsos_t1"][year]
    d = ip[dim]
    pop = IN["population_18plus"][dim]
    N = list(pop["n"])
    t = [x / 100 if x is not None else None for x in d["turnout"]]
    S = [list(r) if r is not None else None for r in d["vote"]]
    if None in t:   # residual group (professions not shown by Ipsos): solved from the totals
        i = t.index(None)
        T0 = ip["turnout"] / 100
        known = sum(n * x for j, (n, x) in enumerate(zip(N, t)) if j != i)
        t[i] = (T0 * sum(N) - known) / N[i]
        res = []
        for c, allc in enumerate(ip["all"]):
            v = allc * T0 * sum(N) - sum(N[j] * t[j] * S[j][c] for j in range(len(N)) if j != i)
            res.append(max(0.0, v / (N[i] * t[i])))
        S[i] = [100 * v / sum(res) for v in res]
    if dim == "age6":
        a = None
    else:
        a = [1.0] * len(N)
    return N, t, S, a

def backtest():
    out = {}
    for y in ("2017", "2022"):
        ip = IN["ipsos_t1"][y]
        result, polls = load(int(y))
        eday = dt.date.fromisoformat(ELECTIONS[int(y)])
        dT = (IN["certain_to_vote_j7"][y] - IN["official_turnout_t1"][y]) / 100
        el = fit_elasticities(exclude_until=int(y))      # only turnout changes known before year y
        yr = {"turnout_actual": IN["official_turnout_t1"][y], "certain_to_vote_j7": IN["certain_to_vote_j7"][y],
              "surprise_pts": round(-100 * dT, 2), "elasticities_used": {k: round(v, 2) for k, v in el.items()}, "dims": {}}
        for dim in ("age6", "prof6"):
            N, t, S, a = dimension(y, dim)
            variants = {"insee": age_a(IN["population_18plus"]["age6"]["groups"], el), "uniform": [1.0] * len(N)} if dim == "age6" else {"uniform": a}
            base = shares(N, t, S)
            repro = max(abs(b - x) for b, x in zip(base, ip["all"]))
            for vname, av in variants.items():
                moved = shares(N, move(N, t, av, dT), S)
                rows = []
                for h in (30, 7):
                    pav = snapshot(polls, result, eday, h)
                    for ci, name in enumerate(ip["cands"]):
                        if name.startswith("_"): continue
                        parts = name.split("+")
                        if not all(p in result and p in pav for p in parts): continue
                        res = sum(result[p] for p in parts); pol = sum(pav[p] for p in parts)
                        rows.append({"h": h, "cand": name, "result": round(res, 2), "poll": round(pol, 2),
                                     "err": round(pol - res, 2), "pred": round(moved[ci] - base[ci], 2)})
                summ = {}
                for h in (30, 7):
                    R = [r for r in rows if r["h"] == h]
                    e = [r["err"] for r in R]; p = [r["pred"] for r in R]
                    big = [r for r in R if abs(r["pred"]) >= 0.3]
                    summ[f"J-{h}"] = {
                        "mae_polls": round(st.mean(abs(x) for x in e), 2),
                        "mae_corrected": round(st.mean(abs(x - q) for x, q in zip(e, p)), 2),
                        "corr": round(st.correlation(e, p), 2) if len(R) > 2 else None,
                        "sign_ok": f"{sum(1 for r in big if (r['err'] > 0) == (r['pred'] > 0))}/{len(big)}"}
                yr["dims"][f"{dim}:{vname}"] = {"repro_max_gap_vs_ipsos": round(repro, 2), "summary": summ, "rows": rows}
        out[y] = yr
    return out

# ---------------- 3. 2027 profiles ----------------
AGE5 = IN["population_18plus"]["age5"]["groups"]
AGE3_TO_5 = {"18-24": ["18-34"], "25-34": ["18-34"], "35-49": ["35-54"], "50-64": ["35-54", "55+"], "65+": ["55+"]}
C27 = IN["certain_2027"]

def vote2022_population():
    o = IN["official_2022_t1"]
    result, _ = load(2022)
    expr = o["exprimes"] / o["inscrits"]
    named = {"Macron": "Emmanuel Macron", "Le Pen": "Marine Le Pen", "Mélenchon": "Jean-Luc Mélenchon",
             "Jadot": "Yannick Jadot", "Pécresse": "Valérie Pécresse", "Zemmour": "Éric Zemmour"}
    n = {k: expr * result[v] / 100 for k, v in named.items()}
    n["Autre"] = expr - sum(n.values())
    n["Non votant"] = 1 - expr
    return [100 * n[g] for g in C27["vote2022"]["groups"]]

def dims_2027(el):
    t_age5 = []
    for g in AGE5:
        src = AGE3_TO_5[g]
        t_age5.append(st.mean(C27["age3"]["t"][C27["age3"]["groups"].index(s)] for s in src) / 100)
    return {
        "age": {"label": "Âge", "groups": AGE5, "N": IN["population_18plus"]["age5"]["n"], "t": t_age5, "a": age_a(AGE5, el)},
        "csp": {"label": "Catégorie sociale", "groups": C27["csp3"]["groups"], "N": IN["population_18plus"]["csp3"]["n"],
                "t": [x / 100 for x in C27["csp3"]["t"]], "a": [1.0] * 3},
        "vote2022": {"label": "Vote au 1er tour 2022", "groups": C27["vote2022"]["groups"], "N": vote2022_population(),
                     "t": [x / 100 for x in C27["vote2022"]["t"]], "a": [1.0] * len(C27["vote2022"]["groups"])},
        "sex": {"label": "Sexe", "groups": C27["sex"]["groups"], "N": IN["population_18plus"]["sex"]["n"],
                "t": [x / 100 for x in C27["sex"]["t"]], "a": [1.0, 1.0]},
    }
SRC_DIM = {"age": ("age5", "age3"), "csp": ("csp3",), "vote2022": ("vote2022",), "sex": ("sex",)}

def profiles(dim, D):
    """index I_cg = (shrunk share of c among group g voters) / (c's share among all voters); sum_g v_g I_cg = 1."""
    w0 = [n * x for n, x in zip(D["N"], D["t"])]
    v = [x / sum(w0) for x in w0]
    acc, used = {}, {}
    for src in IN["crosstabs_2027"]:
        key = next((k for k in SRC_DIM[dim] if k in src["dims"]), None)
        if not key: continue
        sg = src["dims"][key]["groups"]
        base = src["dims"][key].get("base")
        if base is None:      # no published bases: composition of the dimension x total respondents
            ww = [D["N"][D["groups"].index(g)] * D["t"][D["groups"].index(g)] for g in sg]
            base = [src["n"] * x / sum(ww) for x in ww]
        for name, row in src["rows"].items():
            cid = NAME2ID.get(name)
            if not cid or row["all"] <= 0: continue
            sh = [(n * s + K_SHRINK * row["all"]) / (n + K_SHRINK) for n, s in zip(base, row[key])]
            for hi, hg in enumerate(D["groups"]):
                srcs = AGE3_TO_5[hg] if key == "age3" else [hg]
                for s in srcs:
                    j = sg.index(s)
                    wgt = base[j] / len(srcs)
                    a = acc.setdefault(cid, [[0.0, 0.0] for _ in D["groups"]])
                    a[hi][0] += wgt * sh[j] / row["all"]; a[hi][1] += wgt
            used.setdefault(cid, set()).add(src["id"])
    idx = {}
    for cid, a in acc.items():
        raw = [num / den for num, den in a]
        norm = sum(vg * r for vg, r in zip(v, raw))
        idx[cid] = [round(r / norm, 3) for r in raw]
    # candidates without cross-tabs: Bardella = Le Pen's profile; others = their bloc's average
    notes = {}
    for cid, name, short, bloc, typ in CANDS:
        if cid in idx: continue
        if cid == "bardella" and "lepen" in idx:
            idx[cid] = idx["lepen"]; notes[cid] = "profil de Marine Le Pen (pas de croisement publié)"
        else:
            mates = [c[0] for c in CANDS if c[3] == bloc and c[0] in idx and c[0] != cid]
            if mates:
                idx[cid] = [round(st.mean(idx[m][g] for m in mates), 3) for g in range(len(D["groups"]))]
                notes[cid] = "moyenne de son camp (pas de croisement publié)"
    return idx, {k: sorted(v) for k, v in used.items()}, notes

def mult(D, idx, dT=0.0, extra=None):
    t2 = move(D["N"], D["t"], D["a"], dT, extra)
    w = [n * x for n, x in zip(D["N"], t2)]; w0 = [n * x for n, x in zip(D["N"], D["t"])]
    return {c: (sum(wg * i for wg, i in zip(w, I)) / sum(w)) / (sum(wg * i for wg, i in zip(w0, I)) / sum(w0)) for c, I in idx.items()}

def apply(base, *mults):
    s = {c: v * math.prod(m.get(c, 1.0) for m in mults) for c, v in base.items()}
    tot = sum(s.values())
    return {c: 100 * v / tot for c, v in s.items()}

def main():
    el = fit_elasticities()
    print("1) Elasticités à la participation globale (INSEE 2002-2022, échelle logit) :",
          {k: round(v, 2) for k, v in el.items()})
    for y in (2017, 2022):
        print(f"   sans les variations jusqu'à {y} :", {k: round(v, 2) for k, v in fit_elasticities(y).items()})

    bt = backtest()
    print("\n2) Backtest : les sondages (« certains d'aller voter ») vs l'électorat réel")
    for y, yr in bt.items():
        print(f"   {y} : certains d'aller voter {yr['certain_to_vote_j7']} %, participation réelle {yr['turnout_actual']} % "
              f"(surprise +{yr['surprise_pts']} pts)")
        for k, d in yr["dims"].items():
            print(f"     {k:16s} reproduction Ipsos ±{d['repro_max_gap_vs_ipsos']} pt ·",
                  " · ".join(f"{h}: MAE {s['mae_polls']} -> {s['mae_corrected']}, corr {s['corr']}, signe {s['sign_ok']}" for h, s in d["summary"].items()))
        rows = [r for r in yr["dims"]["age6:insee"]["rows"] if r["h"] == 7]
        print("       J-7, âge (INSEE) :", ", ".join(f"{r['cand'].split()[-1]} err {r['err']:+.1f} préd {r['pred']:+.1f}" for r in rows))

    D = dims_2027(el)
    prof, srcs, notes = {}, {}, {}
    for k, d in D.items():
        prof[k], srcs[k], notes[k] = profiles(k, d)

    # sensitivity, on the OpinionWay totals (illustration; the simulator uses the live poll average)
    ow = next(s for s in IN["crosstabs_2027"] if s["id"].startswith("opinionway"))
    base = {NAME2ID[n]: r["all"] for n, r in ow["rows"].items() if n in NAME2ID}
    base = {c: 100 * v / sum(base.values()) for c, v in base.items()}
    def extra(dim, groups, pts):
        return [pts / 100 if g in groups else 0.0 for g in D[dim]["groups"]]
    scen = {
        "participation −5 pts (âge)": [mult(D["age"], prof["age"], -0.05)],
        "participation −5 pts (vote 2022)": [mult(D["vote2022"], prof["vote2022"], -0.05)],
        "participation +5 pts (âge)": [mult(D["age"], prof["age"], 0.05)],
        "participation +5 pts (vote 2022)": [mult(D["vote2022"], prof["vote2022"], 0.05)],
        "18-34 ans −10 pts": [mult(D["age"], prof["age"], 0, extra("age", ["18-24", "25-34"], -10))],
        "CSP- −10 pts": [mult(D["csp"], prof["csp"], 0, extra("csp", ["CSP-"], -10))],
        "abstentionnistes 2022 +10 pts": [mult(D["vote2022"], prof["vote2022"], 0, extra("vote2022", ["Non votant"], 10))],
        "femmes −5 pts": [mult(D["sex"], prof["sex"], 0, extra("sex", ["Femme"], -5))],
    }
    sens = {}
    print("\n3) 2027 : effet sur le 1er tour (pts, base OpinionWay 22/10/2026)")
    order = sorted(base, key=base.get, reverse=True)
    print("   " + " " * 34 + " ".join(f"{c[:9]:>9s}" for c in order))
    for name, ms in scen.items():
        after = apply(base, *ms)
        sens[name] = {c: round(after[c] - base[c], 2) for c in order}
        print(f"   {name:34s}" + " ".join(f"{sens[name][c]:+9.2f}" for c in order))

    out = {
        "note": "Généré par backtest/abstention.py. Profils = indice (part du candidat dans le groupe / part totale), normalisé sur la composition des votants.",
        "elasticities": {k: round(v, 3) for k, v in el.items()},
        "backtest": bt,
        "dims": {k: {"label": d["label"], "groups": d["groups"], "N": [round(x, 2) for x in d["N"]],
                     "t": [round(x, 3) for x in d["t"]], "a": [round(x, 3) for x in d["a"]],
                     "idx": prof[k], "sources": srcs[k], "notes": notes[k]} for k, d in D.items()},
        "sensitivity_opinionway": sens,
    }
    json.dump(out, open(os.path.join(HERE, "data", "abstention.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

if __name__ == "__main__":
    main()
