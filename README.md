# Road to 2027

Suivi indépendant et sourcé de huit candidats à la présidentielle 2027 :
intentions de vote, abonnés sur les réseaux sociaux, adhérents des partis.

Site 100 % statique : aucun build, aucune dépendance, aucun cookie.

```
index.html            page + styles
app.js                rendu (courbes SVG, cartes, fiches candidats). Pas de modification hebdo.
data/site.js          candidats, couleurs, repères sur les courbes, date de mise à jour
data/polls.js         sondages (GÉNÉRÉ, ne pas éditer à la main)
data/social.js        abonnés et adhérents (édité à la main)
scripts/update_polls.py
```

## Mise à jour hebdomadaire (≈ 15 min)

1. **Sondages** : `python3 scripts/update_polls.py`
   Récupère la page Wikipédia qui recense les sondages, garde les 8 candidats suivis
   et le lien vers la publication d'origine de chaque sondage. Vérifier en un coup d'œil
   le dernier sondage contre sa source (le script signale ceux sans lien).
2. **Abonnés / adhérents** : ajouter un point `{date, value, source, detail}` dans
   `data/social.js` pour chaque relevé. `approx: true` pour une valeur arrondie ou une
   date approximative (point creux). Pas de source, pas de point.
3. **Repères** : ajouter un événement dans `SITE.events` si besoin (`who` = candidats concernés,
   `[]` = repère général).
4. Changer `updated` dans `data/site.js`, puis redéployer.

Ajouter un candidat : une ligne dans `SITE.candidates` (avec un `slot` de couleur libre),
son nom Wikipédia dans `TRACKED` de `scripts/update_polls.py`, relancer le script.
Au-delà de 8 candidats, la palette ne garantit plus des couleurs distinguables :
il faudra regrouper ou paginer plutôt que d'inventer une 9e couleur.

## Tester en local

```
python3 -m http.server 8000   # puis http://localhost:8000
```

## Déployer

N'importe quel hébergement statique : Cloudflare Pages, Netlify, GitHub Pages.
Déposer le dossier tel quel (sans `scripts/`).

## Règles éditoriales

- Aucune moyenne entre instituts. Un sondage est daté à la fin de son terrain.
- Quand un sondage teste plusieurs hypothèses, on lit tous les candidats dans
  la même : celle qui inclut le plus de candidats suivis. La fourchette entre
  hypothèses est affichée.
- Les flèches comparent un candidat à lui-même, dans le sondage précédent du même institut.
- **Loi du 19 juillet 1977** : ne publier ni ne commenter aucun sondage la veille et le jour
  de chaque tour (17-18 avril 2027 pour le premier tour). Geler les mises à jour ces jours-là.
- Avant la mise en ligne : remplir `contact` et `host` dans `data/site.js`
  (mentions légales obligatoires : éditeur, hébergeur).

## Simulator (#simulateur)

`sandbox.js` + `data/model.js` (generated: `python3 backtest/export_model.py` after updating
`backtest/data/polls_2027.json` and `duels_2027.json`). Everything runs in the browser
(8,000 simulations per change).
Levers: field (incl. Bardella replacing Le Pen), alliances and withdrawals, campaign shocks
(Fillon 2017, Zemmour 2022, Mélenchon 2022), tactical voting by camp, weight of duel polls
vs legislative transfers, barrage context 2022↔2024, Le Pen correction, horizon.
Method and limits: see `backtest/README.md`.
