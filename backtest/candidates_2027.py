"""Candidates offered in the 2027 simulator (shared by export_model.py and abstention.py).

id, full name, short, bloc (voter family), type (as a finalist)
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
]
NAME2ID = {c[1]: c[0] for c in CANDS}
