"""Is the Mélenchon–Le Pen duel (≈30/70 in polls) overestimating Le Pen?

1. Rebuild the Harris Interactive figure (wave 8, 19–21 Oct 2026) from its own first round and
   its published transfer table (raw/pollsters/harris_v8.txt, p.33).
2. Replace the transfers with historically observed behaviour (Ipsos 2017/2022 election-day
   tables) to see how far the result can move.
Rows not published by Harris (small candidates) use stated assumptions.
"""
J, L, N = "Mélenchon", "Le Pen", "none"

# Harris V8, first round, hypothesis "Attal et Philippe candidats" (Wikipedia row, same report)
R1 = {"Arthaud": 1, "Mélenchon": 17, "Roussel": 1, "Tondelier": 2, "Glucksmann": 12, "Attal": 5,
      "Philippe": 13, "Retailleau": 6, "Dupont-Aignan": 2, "Le Pen": 35, "Zemmour": 6}

def r(j, l, n): return {J: j / 100, L: l / 100, N: n / 100}
HARRIS = {  # published (p.33)
    "Mélenchon": r(93, 3, 4), "Glucksmann": r(23, 14, 63), "Attal": r(15, 28, 57),
    "Philippe": r(6, 33, 61), "Retailleau": r(1, 70, 29), "Le Pen": r(1, 98, 1),
}
SMALL = {  # assumptions for rows Harris doesn't publish
    "Arthaud": "Mélenchon", "Roussel": "Mélenchon", "Tondelier": "Glucksmann",
    "Dupont-Aignan": "Retailleau",
}
ZEMMOUR = r(1, 85, 14)  # assumption: 2022 Zemmour voters gave Le Pen 73 % even against Macron

def duel(T):
    j = l = 0.0
    for c, v in R1.items():
        row = T.get(c) or (ZEMMOUR if c == "Zemmour" else T[SMALL[c]])
        j += v * row[J]; l += v * row[L]
    return 100 * j / (j + l)

def show(label, T):
    print(f"  {label:70} Mélenchon {duel(T):5.1f} %   Le Pen {100 - duel(T):5.1f} %")

print("Duel Mélenchon – Le Pen (en % des exprimés)\n")
show("Harris publié : 30 / 70. Reconstruction avec ses propres reports", HARRIS)

# Historical behaviour against Le Pen (Ipsos election day):
#   moderate-left voters for the anti-Le Pen finalist: Hamon 2017 71/2/27, Jadot 2022 65/6/29
#   right voters: Fillon 2017 48/20/32, Pécresse 2022 53/18/29 (for Macron, a centrist)
#   centrist voters: no history against a radical-left finalist -> bracketed below
T = dict(HARRIS)
T["Glucksmann"] = r(65, 6, 29)
show("Électeurs Glucksmann comme ceux de Jadot en 2022 (65/6)", T)
T2 = dict(T)
T2["Attal"] = T2["Philippe"] = r(30, 25, 45)
show("+ centristes 30 Mélenchon / 25 Le Pen (barrage partiel)", T2)
T3 = dict(T)
T3["Attal"] = T3["Philippe"] = r(42, 17, 41)
show("+ centristes comme les électeurs Mélenchon pour Macron en 2022 (42/17)", T3)
T4 = dict(T3)
T4["Retailleau"] = r(20, 50, 30)
show("+ électeurs LR moins pro-Le Pen (20/50) : borne haute très favorable", T4)
T5 = dict(HARRIS); T5["Le Pen"] = r(3, 91, 6)
show("Contrôle : fidélité Le Pen comme en 2022 (91 %) au lieu de 98 %", T5)

# ---- Legislative runoffs (leg_duels.py): centre / right voters in left-vs-RN constituencies ----
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
print("\nAvec les reports mesurés dans les duels gauche-RN des législatives (centristes et droite) :")
for y in ("2022", "2024"):
    d = json.load(open(os.path.join(HERE, "data", f"leg_duels_{y}.json"), encoding="utf-8"))["GAUCHE"]["rates"]
    def leg(bloc): o, rn = d[bloc]["opponent"][0], d[bloc]["rn"][0]; return r(o, rn, 100 - o - rn)
    for glk, gl in (("Glucksmann selon Harris", HARRIS["Glucksmann"]), ("Glucksmann comme Jadot 2022", r(65, 6, 29))):
        T = dict(HARRIS); T["Glucksmann"] = gl
        T["Attal"] = T["Philippe"] = leg("CENTRE"); T["Retailleau"] = leg("DROITE")
        show(f"Législatives {y} (centre {d['CENTRE']['opponent'][0]}/{d['CENTRE']['rn'][0]}, droite {d['DROITE']['opponent'][0]}/{d['DROITE']['rn'][0]}) + {glk}", T)

# ---- Same, with runoffs where the left candidate was LFI (data/left_alliance_parties.csv) ----
print("\nAvec les reports des seuls duels LFI-RN des législatives :")
for y in ("2022", "2024"):
    d = json.load(open(os.path.join(HERE, "data", f"leg_duels_{y}.json"), encoding="utf-8"))["GAUCHE_LFI"]["rates"]
    def leg(bloc): o, rn = d[bloc]["opponent"][0], d[bloc]["rn"][0]; return r(o, rn, 100 - o - rn)
    for glk, gl in (("Glucksmann selon Harris", HARRIS["Glucksmann"]), ("Glucksmann comme Jadot 2022", r(65, 6, 29))):
        T = dict(HARRIS); T["Glucksmann"] = gl
        T["Attal"] = T["Philippe"] = leg("CENTRE"); T["Retailleau"] = leg("DROITE")
        show(f"LFI-RN {y} (centre {d['CENTRE']['opponent'][0]}/{d['CENTRE']['rn'][0]}, droite {d['DROITE']['opponent'][0]}/{d['DROITE']['rn'][0]}) + {glk}", T)
