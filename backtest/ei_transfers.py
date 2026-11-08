"""Estimate the round-1 -> round-2 vote transfer table from official results by commune.

Ecological inference (constrained regression): for each commune, round-2 outcomes (as shares of
registered voters) = round-1 shares x transfer table. Each row of the table is a probability
distribution (>= 0, sums to 1). Fitted nationally and per département; the département fits are
aggregated with round-1 weights, which limits the bias of a single national fit.

Usage: python3 backtest/ei_transfers.py 2022
Source files: data.gouv.fr, Ministère de l'Intérieur, résultats définitifs par commune.
"""
import csv, io, json, os, sys
import numpy as np
from scipy.optimize import minimize

HERE = os.path.dirname(os.path.abspath(__file__))
YEAR = sys.argv[1] if len(sys.argv) > 1 else "2022"
RAW = os.path.join(HERE, "raw", "results")

def read(path):
    txt = open(path, "rb").read().decode("latin-1")
    rows = list(csv.reader(io.StringIO(txt), delimiter=";"))
    head, data = rows[0], rows[1:]
    out = {}
    base = head.index("N°Panneau")
    for r in data:
        if len(r) < base:
            continue
        key = (r[0], r[2])
        rec = {"ins": int(r[head.index("Inscrits")]), "abs": int(r[head.index("Abstentions")]),
               "blank_null": int(r[head.index("Blancs")]) + int(r[head.index("Nuls")])}
        k = base
        while k + 3 < len(r) and r[k].strip():
            name = (r[k + 3] + " " + r[k + 2]).strip().title()
            rec[name] = int(r[k + 4])
            k += 7 if len(r) > k + 7 and r[k + 6] != "" else 7
        out[key] = rec
    return out

t1 = read(os.path.join(RAW, f"t1_{YEAR}_communes.txt"))
t2 = read(os.path.join(RAW, f"t2_{YEAR}_communes.txt"))
keys = [k for k in t1 if k in t2 and t1[k]["ins"] > 0 and abs(t1[k]["ins"] - t2[k]["ins"]) / t1[k]["ins"] < 0.03]
cands1 = [c for c in t1[keys[0]] if c not in ("ins", "abs", "blank_null")]
cands2 = [c for c in t2[keys[0]] if c not in ("ins", "abs", "blank_null")]
rows_in = cands1 + ["blank_null", "abs"]
cols_out = cands2 + ["blank_null", "abs"]
print(f"{YEAR}: {len(keys)} communes; round 1 = {len(cands1)} candidates; round 2 = {cands2}")

def matrices(ks):
    X = np.array([[t1[k].get(c, 0) / t1[k]["ins"] for c in rows_in] for k in ks])
    Y = np.array([[t2[k].get(c, 0) / t2[k]["ins"] for c in cols_out] for k in ks])
    w = np.array([t1[k]["ins"] for k in ks], dtype=float)
    return X, Y, w

def fit(X, Y, w, B0=None):
    R, C = X.shape[1], Y.shape[1]
    sw = np.sqrt(w / w.sum())[:, None]
    Xw, Yw = X * sw, Y * sw
    def f(b):
        B = b.reshape(R, C); E = Xw @ B - Yw
        return (E * E).sum(), (2 * Xw.T @ E).ravel()
    cons = [{"type": "eq", "fun": (lambda b, i=i: b.reshape(R, C)[i].sum() - 1), "jac": (lambda b, i=i: np.eye(R)[i].repeat(C) if False else np.kron(np.eye(R)[i], np.ones(C)))} for i in range(R)]
    x0 = (B0 if B0 is not None else np.full((R, C), 1 / C)).ravel()
    res = minimize(f, x0, jac=True, bounds=[(0, 1)] * (R * C), constraints=cons, method="SLSQP", options={"maxiter": 500, "ftol": 1e-12})
    return res.x.reshape(R, C)

X, Y, w = matrices(keys)
B_nat = fit(X, Y, w)

# département-level fits, aggregated with each département's round-1 volumes
deps = sorted({k[0] for k in keys})
num = np.zeros_like(B_nat); den = np.zeros(len(rows_in))
for d in deps:
    ks = [k for k in keys if k[0] == d]
    if len(ks) < 60:          # too few communes for a stable fit: use the national table
        Xd, Yd, wd = matrices(ks); vol = (Xd * wd[:, None]).sum(0)
        num += B_nat * vol[:, None]; den += vol; continue
    Xd, Yd, wd = matrices(ks)
    Bd = fit(Xd, Yd, wd, B_nat)
    vol = (Xd * wd[:, None]).sum(0)
    num += Bd * vol[:, None]; den += vol
B_dep = num / den[:, None]

def check(B):
    pred = (X * w[:, None]).sum(0) @ B / w.sum()
    real = (Y * w[:, None]).sum(0) / w.sum()
    return {c: (round(100 * p, 2), round(100 * r, 2)) for c, p, r in zip(cols_out, pred, real)}

out = {"year": YEAR, "method": "ecological inference by département (constrained least squares), weighted by registered voters",
       "source": "data.gouv.fr, Ministère de l'Intérieur, résultats définitifs par commune",
       "rows": rows_in, "cols": cols_out,
       "national_fit": {r: {c: round(float(v), 3) for c, v in zip(cols_out, row)} for r, row in zip(rows_in, B_nat)},
       "departement_fit": {r: {c: round(float(v), 3) for c, v in zip(cols_out, row)} for r, row in zip(rows_in, B_dep)},
       "check_vs_real_pct_registered": check(B_dep)}
os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
json.dump(out, open(os.path.join(HERE, "data", f"transfers_{YEAR}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

print("\nReport de voix estimé (ajustement par département), % de chaque électorat du 1er tour")
print(f"{'':24}" + "".join(f"{c[:12]:>13}" for c in cols_out))
for r, row in zip(rows_in, B_dep):
    print(f"{r[:24]:24}" + "".join(f"{100*v:>12.0f}%" for v in row))
print("\nContrôle (% des inscrits, estimé vs réel):", out["check_vs_real_pct_registered"])
