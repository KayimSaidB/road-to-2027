# Backtest: elections 2002–2022

Purpose: test, on past elections, whether a scenario model built on polls makes sense
before we publish anything for 2027.

```
raw/polls_YYYY.txt          Wikipedia source pages (first-round polls)
raw/results/                official results by commune (data.gouv.fr), 2022
raw/transfers/              Ipsos reports (PDF)
parse_history.py            polls_YYYY.txt -> data/polls_YYYY.json
analyze.py                  poll errors by horizon + Monte Carlo + calibration -> data/backtest.json
ei_transfers.py YEAR        vote transfers estimated from results by commune -> data/transfers_YEAR.json
data/transfers_survey_2022.json   Ipsos election-day transfers (figures stated on the page)
```

Rerun:
```
for y in 2002 2007 2012 2017 2022; do python3 backtest/parse_history.py backtest/raw/polls_$y.txt backtest/data/polls_$y.json; done
python3 backtest/analyze.py
python3 backtest/ei_transfers.py 2022
```

## Method (v1)
- At each horizon J-h: average of polls from the 21 days before J-h. For each poll, the
  scenario closest to the final field (so we measure the polls' error *given the right
  candidates*; field uncertainty is counted separately).
- Error model: result − poll ~ N(0, σ_h·√(p/20)), with σ_h fitted on the *other* elections
  (leave-one-out), independent draws, 20,000 simulations.
- Transfers: constrained regression by département on ~35,000 communes, compared with the
  Ipsos survey.

## Known limits of v1
- 5 elections: few cases, so σ is uncertain.
- Independent errors: in reality they are correlated (votes move between neighbouring
  candidates). This is the next improvement.
- Ecological transfers are biased for small electorates and diverge from the survey for
  the large ones: not usable alone.

## Do earlier elections help? (analyze_blend.py)
Sources tested at the level of blocs, blended with polls and weights chosen out of sample:
previous presidential, last legislative, last European, and "swings" (previous presidential +
change between two European or two legislative elections). Municipal: not usable (local labels,
no comparable national aggregate).

Mean error per bloc, each source alone vs J-163 polls: polls 4.7 · previous presidential 5.7 ·
European 5.9 · European swing 6.2 · legislative swing 8.0 · legislative 8.3 (16 in 2017).

Out of sample (weights chosen on the other 4 elections): no blend beats polls alone on bloc error.
Candidate error improves only at J-163, with "40 % polls / 60 % previous presidential" (5.7 -> 5.3
with weight steps of 0.1; it fails in 2017). The gain disappears when more sources are allowed
(overfitting). From J-60, the best weight is 100 % polls everywhere.
Decision: legislative results are not used as a prior. Earlier elections serve as context
(bloc reservoirs) and for the vote-transfer tables, not for forecasting.

## Second round (second_round.py)
Ipsos transfer tables, 2017 and 2022 (data/transfers_survey.json, copied from the PDFs).

1. Applying the **2017** transfer rates to the actual 2022 first round gives Macron 62.6 %
   (range 61.7–63.1 depending on the unpublished assumptions), against **58.55 %** actual:
   +4 pts. Transfers shift between elections: in 2017, 52 % of Mélenchon voters went to
   Macron; in 2022 it was 42 %, against an incumbent.
   Control with the 2022 table itself: 56.2 % (−2.4), the error coming from the rows Ipsos
   does not publish (first-round abstainers and blank voters, small candidates).
2. **Direct second-round polls** (Macron–Le Pen) underestimated the winner both times:
   2017 −1 to −5 pts, 2022 −3 pts at J-163 and −5 pts at J-7.
=> For 2027: second-round uncertainty of about ±5 pts whatever the method; neither method
is reliable on its own; untested pairings (no incumbent) will be the least certain.

## Model v2 (simulate.py, predict_2027.py)
- Correlated first-round errors (bloc moving together + tactical voting within a bloc): **no
  out-of-sample gain** (log-loss on the real pairing 1.12 for v1 vs 1.35 for v2; Brier on
  qualification 0.048 vs 0.050). With 5 elections, correlations can't be estimated. Decision:
  v1 errors are kept for uncertainty; correlations will only serve the sandbox mechanics
  (withdrawals, alliances) via the transfers measured in polls.
- Second round from duel polls, σ fitted out of sample (≈3.7 pts). Chance given to the real
  winner: 0.66 on average; at J-163: 0.58 / 0.42 / 0.94 / 0.03 (2017, Fillon favourite) / 0.79.
- **Duel polls with a Le Pen**: they underestimated the opponent in 2002 (−2.7), 2017 (−3.3 to
  −5.4) and 2022 (−2.6 to −3.9), at every horizon. Duels without a Le Pen: errors in both
  directions (2007 −1.3, 2012 +5.7). => optional correction of 3.5 ± 1.5 pts.
- Mélenchon–Le Pen (check_melenchon_lepen.py): the 30/70 Harris figure is reproduced exactly
  from its transfer table; it rests on 63 % of Glucksmann voters not expressing a choice. With
  historically observed transfers: Mélenchon 36 to 43 %.

## Legislative runoffs as a measure of barrage (leg_duels.py)
Two-candidate runoffs against FN/RN, 2017, 2022, 2024 (results by constituency, data.gouv.fr).
Transfer rates by first-round bloc, constrained regression per runoff type, 90 % bootstrap.
Left-alliance candidates' party: data/left_alliance_parties.csv (Sciences Po CEVIPOF 2022 +
Wikipedia, cross-checked).

| Runoff vs RN | centrist voters -> opp. / RN | right voters -> opp. / RN |
|---|---|---|
| Centre vs FN 2017 (105) | — | 57 / 20 |
| Left vs RN 2022 (65) | 20 / 29 | 20 / 40 |
| of which LFI (32) / other left (29) | 31 / 23 · 30 / 26 | 7 / 46 · 27 / 39 |
| Left vs RN 2024 (146) | 56 / 11 | 51 / 19 |
| of which LFI (44) / other left (96) | 50 / 13 · 59 / 15 | 44 / 24 · 52 / 21 |

- Validation: left voters in centre-vs-RN runoffs, 2022 legislative 42 / 19 vs Ipsos presidential
  2022 42 / 17 for Mélenchon voters.
- Out-of-sample test: 2017 legislative rates applied to the 2022 presidential first round give
  Macron 54.6 % (actual 58.55, −4.0), no better than duel polls (−2.2 to −3.0), same direction.
- LFI penalty: mostly among right-wing voters, and it goes to abstention more than to the RN.
- 2022 estimates are unstable (pooled 20/29 vs subsets 31/23 and 30/26): small samples.
- Mélenchon–Le Pen with the LFI-vs-RN rates: 35.5 to 40.7 % (2022 context), 42.3 to 46.8 %
  (2024 context), vs 30 % in polls.
=> In the model: legislative estimate = one source among others, weight ≤ 0.5, with a
"barrage context" lever (2022 vs 2024) in the sandbox; Le Pen correction applies to both sources.

## Abstention (abstention.py)
Question: who stays home, and does it move the candidates? Inputs in `data/abstention_inputs.json`
(copied from INSEE, Ipsos, OpinionWay and YouGov; sources listed inside, PDFs in `raw/abstention/`).

```
python3 backtest/abstention.py      # -> data/abstention.json, then rerun export_model.py
```

Model: registered voters split into groups (age, social category, 2022 vote, sex).
`share_c = Σ N_g·t_g·s_cg / Σ N_g·t_g`. A turnout change moves every group on the logit scale,
`logit t'_g = logit t_g + a_g·D`, plus optional extra points for one group (young people, working
class, 2022 abstainers). 2027 profiles come from cross-tabs (OpinionWay 22/10/2026, YouGov 15/10/2026),
with each cell pulled toward the candidate's total by 100 pseudo-respondents (18-24 cells are ~90
people: OpinionWay's "Lisnard 19 % among 18-24" is noise).

1. **Who follows turnout swings (INSEE 2002–2022, official signature lists).** Slope of each age
   group's logit turnout on the overall one: 18-29 **1.14**, 30-64 **1.13**, 65+ **0.65**. Over-65s
   barely move; when turnout falls, it falls among the under-65s.
2. **Backtest 2017 and 2022.** Polls are made of people "certain to vote" (Ipsos-Cevipof one week
   before: 73 % in 2017, 69 % in 2022); actual turnout was **+4.8 and +4.7 pts** higher. Reweighting
   the real electorate (Ipsos election-day survey) down to the polls' turnout moves candidates by
   **0.1 to 0.4 pt**. Poll error at J-7 (mean per candidate): 2017 1.55 → 1.62 once corrected,
   2022 2.42 → 2.37. Right direction in 2022 (corr 0.81, but tiny: Mélenchon −8.2 observed, −0.2
   predicted), wrong direction in 2017 (corr −0.28). The age model reproduces Ipsos's total within
   0.3 pt (2022) to 1.5 pts (2017; the 2026 age pyramid is used for both).
   => The *level* of turnout does not explain poll errors.
3. **2027 sensitivity** (pts, on OpinionWay's totals; `sensitivity_opinionway` in the JSON):

| Scenario | Le Pen | Mélenchon | Glucksmann | Philippe |
|---|---|---|---|---|
| Turnout −5 pts, read by age | +0.0 | −0.2 | +0.1 | +0.1 |
| Turnout −5 pts, read by 2022 vote | +0.4 | −0.2 | −0.1 | −0.1 |
| 18-34 year-olds −10 pts | +0.2 | −0.5 | +0.2 | +0.1 |
| Employees and manual workers −10 pts | −0.5 | −0.1 | +0.1 | +0.1 |
| 2022 abstainers +10 pts | −0.3 | +0.2 | +0.1 | +0.0 |
| Women −5 pts | −0.1 | −0.0 | +0.1 | −0.0 |

- The two readings of overall turnout disagree on Le Pen: by age her voters are average; by 2022 vote
  they are the most mobilised (86 % of 2022 Le Pen voters "certain to vote", vs 69 % of Mélenchon's
  and 41 % of 2022 abstainers).
- Gender: no lever. The actual turnout gap is ~2 pts (Ipsos 2022: men 73, women 75), and the two polls
  disagree on the sign (Mélenchon: women 20 / men 12 at OpinionWay, 12 / 17 at YouGov). YouGov's men
  say they are more "certain to vote" (68 vs 63) although women vote as much: certainty is biased by sex.
- Order of magnitude: a whole group must move a lot to shift a candidate by 1 pt (18-34 −20 pts:
  Mélenchon about −1). It matters for a close race for second place, not for the favourite.

Limits: dimensions are applied one at a time and multiplied, so the youth and 2022-abstainer levers
overlap (young people abstained more in 2022). No age × profession joint table in the cross-tabs.
Candidates without cross-tabs: Bardella = Le Pen's profile, Villepin = average of his camp.
Second round not modelled here: the transfer tables (Ipsos, legislative runoffs) already include
abstention, and the "barrage context" lever covers it.

**Decision: dropped.** Effects of a few tenths of a point, no gain in the backtest: abstention is
neither a correction nor a simulator lever. The script and data stay here so the test can be rerun.
