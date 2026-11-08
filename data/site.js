/* =====================================================================
   PARAMÈTRES DU SITE ET FICHES CANDIDATS (modifiable à la main)

   - Les sondages sont dans data/polls.js (généré par scripts/update_polls.py).
   - Abonnés et adhérents sont dans data/social.js (relevés à la main).
   - `slot` = couleur de la palette (1 à 8), fixe pour chaque candidat :
     ne jamais la réattribuer, même si un candidat se retire.
   ===================================================================== */
window.SITE = {
  updated: "2026-11-06",
  election: {
    date: "2027-04-18",
    label: "premier tour",
    source: "https://www.service-public.gouv.fr/particuliers/actualites/A15053?lang=fr"
  },
  contact: "contact@exemple.fr",   // à remplacer avant la mise en ligne publique
  host: "à compléter (hébergeur, adresse)",

  /* Ordre d'affichage : de gauche à droite sur l'échiquier, comme les tableaux de sondages. */
  candidates: [
    {id: "melenchon",  name: "Jean-Luc Mélenchon", short: "Mélenchon",  party: "La France insoumise", slot: 8},
    {id: "roussel",    name: "Fabien Roussel",     short: "Roussel",    party: "Parti communiste français", slot: 2},
    {id: "tondelier",  name: "Marine Tondelier",   short: "Tondelier",  party: "Les Écologistes", slot: 6},
    {id: "glucksmann", name: "Raphaël Glucksmann", short: "Glucksmann", party: "Place publique, soutenu par le PS", slot: 5},
    {id: "attal",      name: "Gabriel Attal",      short: "Attal",      party: "Renaissance", slot: 4},
    {id: "philippe",   name: "Édouard Philippe",   short: "Philippe",   party: "Horizons", slot: 3},
    {id: "lisnard",    name: "David Lisnard",      short: "Lisnard",    party: "Nouvelle Énergie", slot: 7},
    {id: "lepen",      name: "Marine Le Pen",      short: "Le Pen",     party: "Rassemblement national", slot: 1}
  ],

  /* Repères affichés sur les courbes. Source : notes chronologiques de la page Wikipédia des sondages. */
  events: [
    {date: "2025-03-31", label: "Le Pen condamnée à cinq ans d'inéligibilité (1re instance)", short: "Inéligibilité Le Pen", who: ["lepen"]},
    {date: "2026-05-22", label: "Gabriel Attal annonce sa candidature", short: "Attal candidat", who: ["attal"]},
    {date: "2026-07-07", label: "En appel, Marine Le Pen redevient éligible et annonce sa candidature", short: "Le Pen éligible", who: ["lepen"]},
    {date: "2026-08-23", label: "Raphaël Glucksmann annonce sa candidature", short: "Glucksmann candidat", who: ["glucksmann"]},
    {date: "2026-08-27", label: "Premier débat à sept : Retailleau, Glucksmann, Le Pen, Philippe, Mélenchon, Tondelier, Attal", short: "1er débat", who: ["glucksmann", "lepen", "philippe", "melenchon", "tondelier", "attal"]},
    {date: "2026-09-06", label: "Fabien Roussel annonce sa candidature", short: "Roussel candidat", who: ["roussel"]},
    {date: "2026-10-11", label: "Raphaël Glucksmann remporte la primaire socialiste", short: "Primaire PS", who: ["glucksmann"]},
    {date: "2026-10-17", end: "2026-10-18", label: "Émeutes des 17 et 18 octobre", short: "Émeutes", who: []}
  ]
};
