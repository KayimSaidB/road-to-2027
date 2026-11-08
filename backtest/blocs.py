"""Candidate -> political bloc mapping (shared by the backtest scripts).

RADG radical left · GAU moderate left & ecologists · CEN centre · DRO right · EXD far/sovereigntist right · AUT other
Same definitions as data/intermediate_elections.json.
"""
BLOCS = ["RADG", "GAU", "CEN", "DRO", "EXD", "AUT"]

CANDIDATE_BLOC = {
    # radical left
    "Arlette Laguiller": "RADG", "Olivier Besancenot": "RADG", "Robert Hue": "RADG", "Daniel Gluckstein": "RADG",
    "Marie-George Buffet": "RADG", "José Bové": "RADG", "Gérard Schivardi": "RADG", "Jean-Luc Mélenchon": "RADG",
    "Philippe Poutou": "RADG", "Nathalie Arthaud": "RADG", "Fabien Roussel": "RADG", "François Ruffin": "RADG",
    "Pierre Laurent": "RADG", "André Chassaigne": "RADG", "Clémentine Autain": "RADG",
    # moderate left & ecologists
    "Lionel Jospin": "GAU", "Jean-Pierre Chevènement": "GAU", "Noël Mamère": "GAU", "Christiane Taubira": "GAU",
    "Ségolène Royal": "GAU", "Dominique Voynet": "GAU", "François Hollande": "GAU", "Eva Joly": "GAU",
    "Benoît Hamon": "GAU", "Manuel Valls": "GAU", "Arnaud Montebourg": "GAU", "Yannick Jadot": "GAU",
    "Anne Hidalgo": "GAU", "Raphaël Glucksmann": "GAU", "Marine Tondelier": "GAU", "Olivier Faure": "GAU",
    "Dominique Strauss-Kahn": "GAU", "Martine Aubry": "GAU", "Laurent Fabius": "GAU", "Jack Lang": "GAU",
    "Bernard Cazeneuve": "GAU", "Sandrine Rousseau": "GAU", "Cécile Duflot": "GAU", "Nicolas Hulot": "GAU",
    "Karim Bouamrane": "GAU", "Natacha Polony": "GAU", "Vincent Peillon": "GAU", "Alain Lipietz": "GAU",
    "Pierre Larrouturou": "GAU", "Sylvia Pinel": "GAU",
    # centre
    "François Bayrou": "CEN", "Corinne Lepage": "CEN", "Emmanuel Macron": "CEN", "Gabriel Attal": "CEN",
    "Édouard Philippe": "CEN", "Jean-Christophe Lagarde": "CEN", "Jean-Louis Borloo": "CEN", "Hervé Morin": "CEN",
    "Bruno Le Maire": "CEN", "Gérald Darmanin": "CEN", "Christine Lagarde": "CEN", "Dominique de Villepin": "CEN",
    # right
    "Jacques Chirac": "DRO", "Alain Madelin": "DRO", "Christine Boutin": "DRO", "Jean Saint-Josse": "DRO",
    "Nicolas Sarkozy": "DRO", "Frédéric Nihous": "DRO", "François Fillon": "DRO", "Alain Juppé": "DRO",
    "Valérie Pécresse": "DRO", "Xavier Bertrand": "DRO", "Michel Barnier": "DRO", "Laurent Wauquiez": "DRO",
    "Bruno Retailleau": "DRO", "David Lisnard": "DRO", "Éric Ciotti": "DRO", "Philippe Juvin": "DRO",
    "Denis Payre": "DRO", "Jean-François Copé": "DRO", "Nathalie Kosciusko-Morizet": "DRO", "Jean-Frédéric Poisson": "DRO",
    "Michèle Alliot-Marie": "DRO", "Henri Guaino": "DRO", "Édouard Balladur": "DRO",
    # far right & sovereigntist right
    "Jean-Marie Le Pen": "EXD", "Bruno Mégret": "EXD", "Philippe de Villiers": "EXD", "Marine Le Pen": "EXD",
    "Nicolas Dupont-Aignan": "EXD", "Éric Zemmour": "EXD", "Florian Philippot": "EXD", "Jordan Bardella": "EXD",
    "Sarah Knafo": "EXD", "Marion Maréchal": "EXD", "Charles Pasqua": "EXD",
    # other
    "Jacques Cheminade": "AUT", "Jean Lassalle": "AUT", "François Asselineau": "AUT",
}

def bloc_of(name):
    return CANDIDATE_BLOC.get(name, "AUT")
