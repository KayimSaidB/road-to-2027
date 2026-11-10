"""Candidates offered in the 2027 simulator (shared by export_model.py and abstention.py).

id, full name, short, bloc (voter family), type (as a finalist)

A newcomer whose political family is not established yet goes in bloc "AUTRES", type "AUTRE":
the simulator then treats them neutrally (equal proximity to everyone) until polls testing
scenarios with and without them measure where their voters go.
Anyone polled but missing from this list is counted in OTHERS ("Autres candidats") and
export_model.py prints a warning: add them here when they matter.
"""
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
    ("riner", "Teddy Riner", "Riner", "AUTRES", "AUTRE"),          # candidate since 9 Nov 2026, sans étiquette
]
NAME2ID = {c[1]: c[0] for c in CANDS}

# Aggregate of polled candidates not listed above (never a finalist in the simulator).
OTHERS = ("autres", "Autres candidats", "Autres", "AUTRES", "AUTRE")
