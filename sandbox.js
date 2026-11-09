/* Road to 2027: simulator (#simulateur). Parameters come from data/model.js (backtest/export_model.py). */
(function () {
  "use strict";
  const M = window.MODEL;
  if (!M) return;
  const C = Object.fromEntries(M.candidates.map(c => [c.id, c]));
  const SLOT = Object.fromEntries((window.SITE ? window.SITE.candidates : []).map(c => [c.id, c.slot]));
  const colorOf = id => SLOT[id] ? `var(--c${SLOT[id]})` : "var(--ink3)";
  const nf1 = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 });
  const pc = v => nf1.format(v) + " %";
  const pp = v => (v < 0.005 ? "< 1" : v > 0.995 ? "> 99" : Math.round(100 * v)) + " %";

  /* Proximity of a voter family (bloc) to a finalist type, used only where nothing was measured. Assumption. */
  const PROX = {
    GAUCHE: { RADG: .80, LFI: .75, GAUCHE: .85, CENTRE: .45, DROITE: .12, EXD: .08 },
    CENTRE: { RADG: .10, LFI: .10, GAUCHE: .50, CENTRE: .95, DROITE: .60, EXD: .15 },
    DROITE: { RADG: .03, LFI: .03, GAUCHE: .20, CENTRE: .55, DROITE: .95, EXD: .45 },
    RN_ALLIES: { RADG: .05, LFI: .05, GAUCHE: .05, CENTRE: .12, DROITE: .45, EXD: .95 },
  };
  const LEFT = t => t === "LFI" || t === "RADG" || t === "GAUCHE";

  const SHOCKS = {
    affaire: { label: "Affaire en campagne (type Fillon 2017 : −5 pts)", apply: (s, id) => Math.min(5, s[id]) },
    effondrement: { label: "Effondrement (type Zemmour 2022 : −50 %)", apply: (s, id) => s[id] * 0.5 },
    dynamique: { label: "Dynamique de fin de campagne (type Mélenchon 2022 : +5 pts)", apply: () => -5 },
  };

  // Horizons with a fitted poll error (backtest), longest first; "today" = the closest one.
  const HORIZONS = Object.keys(M.sigma_first).map(Number).sort((a, b) => b - a);
  const HZ_TODAY = HORIZONS.reduce((best, h) => Math.abs(h - M.horizon_days) < Math.abs(best - M.horizon_days) ? h : best);

  const DEFAULT = () => ({
    field: new Set(M.default_in), bardella: false,
    centre: "", gauche: "", droite: "", radicale: false, follow: 60,
    shocks: [], utile: { GAUCHE: false, CENTRE: false, DROITE: false },
    horizon: HZ_TODAY, wPoll: 50, ctx: 50, lepenCorr: true,
  });

  const PRESETS = [
    { id: "now", label: "Situation actuelle", set: s => s },
    { id: "bardella", label: "Bardella à la place de Le Pen", set: s => (s.bardella = true, s) },
    { id: "centre", label: "Centre uni derrière Philippe", set: s => (s.centre = "philippe", s) },
    { id: "gauche", label: "Gauche hors LFI unie derrière Glucksmann", set: s => (s.gauche = "glucksmann", s) },
    { id: "droite", label: "Droite unie derrière Retailleau", set: s => (s.droite = "retailleau", s) },
    { id: "b2024", label: "Barrage fort, type législatives 2024", set: s => (s.ctx = 100, s) },
    { id: "b2022", label: "Barrage faible, type législatives 2022", set: s => (s.ctx = 0, s) },
    { id: "polls", label: "Sondages de duel seuls, sans correction", set: s => (s.wPoll = 100, s.lepenCorr = false, s) },
    { id: "fillon", label: "Affaire pour la favorite (type Fillon)", set: s => (s.shocks = [{ id: "lepen", kind: "affaire" }], s) },
    { id: "late", label: "Vote utile à gauche + dynamique Mélenchon", set: s => (s.utile.GAUCHE = true, s.shocks = [{ id: "melenchon", kind: "dynamique" }], s) },
  ];

  /* ---------- first round (mean scenario) ---------- */
  function profile(x, inSet, s) {
    const w = M.withdraw[x];
    let prof = {};
    if (w) {
      for (const [c, v] of Object.entries(w.to)) if (inSet.has(c)) prof[c] = v;
      const cov = Object.values(prof).reduce((a, b) => a + b, 0);
      if (cov >= 0.5) { for (const c in prof) prof[c] /= cov; return { prof, measured: true }; }
      prof = {};
    }
    for (const c of inSet) prof[c] = Math.pow(PROX[C[x].bloc][C[c].type], 2) * Math.max(s[c] || 0.5, 0.5);
    const t = Object.values(prof).reduce((a, b) => a + b, 0);
    for (const c in prof) prof[c] /= t;
    return { prof, measured: false };
  }
  function give(s, from, amount, inSet, target, follow) {
    let rest = amount;
    if (target && inSet.has(target)) { s[target] += amount * follow; rest = amount * (1 - follow); }
    const { prof } = profile(from, inSet, s);
    for (const [c, v] of Object.entries(prof)) s[c] += rest * v;
  }
  function firstRound(st) {
    const field = new Set(st.field);
    if (st.bardella) { field.delete("lepen"); field.add("bardella"); }
    const targets = {};
    const out = id => { if (field.has(id)) { field.delete(id); return true; } return false; };
    if (st.centre) for (const c of ["philippe", "attal", "villepin"]) if (c !== st.centre && out(c)) targets[c] = st.centre;
    if (st.gauche) for (const c of ["glucksmann", "tondelier", "roussel"]) if (c !== st.gauche && out(c)) targets[c] = st.gauche;
    if (st.droite) for (const c of ["retailleau", "lisnard"]) if (c !== st.droite && out(c)) targets[c] = st.droite;
    const rn = st.bardella ? "bardella" : "lepen";
    if (st.radicale) for (const c of ["zemmour", "dupontaignan"]) if (out(c)) targets[c] = rn;
    const s = {}, notes = [];
    for (const c of field) s[c] = C[c].base || 0;
    for (const c of M.candidates) {
      if (field.has(c.id)) continue;
      let v = c.base || 0;
      if (c.id === "bardella") continue;
      if (c.id === "lepen" && st.bardella) v = Math.max(0, C.lepen.base - C.bardella.base);
      if (v > 0) give(s, c.id, v, field, targets[c.id], st.follow / 100);
    }
    for (const sh of st.shocks) {
      if (!field.has(sh.id)) continue;
      const d = SHOCKS[sh.kind].apply(s, sh.id);
      if (d > 0) { s[sh.id] -= d; const f = new Set(field); f.delete(sh.id); give(s, sh.id, d, f, null, 0); }
      else {
        const gain = -d, others = [...field].filter(c => c !== sh.id);
        const w = Object.fromEntries(others.map(c => [c, s[c] * Math.pow(PROX[C[c].bloc][C[sh.id].type], 2)]));
        const t = Object.values(w).reduce((a, b) => a + b, 0);
        let taken = 0;
        for (const c of others) { const x = Math.min(s[c] * 0.6, gain * w[c] / t); s[c] -= x; taken += x; }
        s[sh.id] += taken;
      }
    }
    for (const b of ["GAUCHE", "CENTRE", "DROITE"]) {
      if (!st.utile[b]) continue;
      const mem = [...field].filter(c => C[c].bloc === b);
      if (mem.length < 2) continue;
      const lead = mem.reduce((a, c) => s[c] > s[a] ? c : a);
      for (const c of mem) if (c !== lead) { const x = 0.4 * s[c]; s[c] -= x; s[lead] += x; }
    }
    const tot = Object.values(s).reduce((a, b) => a + b, 0);
    for (const c in s) s[c] = 100 * s[c] / tot;
    return { shares: s, field };
  }

  /* ---------- second round ---------- */
  function mix(a, b, k) { return [a[0] * (1 - k) + b[0] * k, a[1] * (1 - k) + b[1] * k]; }
  function rates(c, O, k) {   // [to O (the RN's opponent), to the RN finalist] for voters of c
    const t = C[O].type, b = C[c].bloc;
    const L = ctx => M.leg[ctx], A = ctx => M.assumed[ctx];
    const pick = f => mix(f("2022"), f("2024"), k);
    if (b === "RN_ALLIES") return pick(x => A(x)[LEFT(t) ? "EXD_vs_LEFT" : t === "CENTRE" ? "EXD_vs_CENTRE" : "EXD_vs_DROITE"]);
    if (b === "GAUCHE") {
      if (LEFT(t)) return (C[c].type === t || (C[c].type === "RADG" && t === "LFI")) ? [85, 3] : pick(x => A(x).GAUCHE_to_LEFT);
      return pick(x => L(x)[t].GAUCHE);
    }
    if (b === "CENTRE") return t === "CENTRE" ? [90, 2] : pick(x => L(x)[t === "RADG" ? "LFI" : t].CENTRE);
    if (b === "DROITE") return t === "DROITE" ? [90, 5] : pick(x => L(x)[t === "RADG" ? "LFI" : t].DROITE);
    return [30, 30];
  }
  function transferDuel(A, B, s, k) {
    const ea = C[A].type === "EXD", eb = C[B].type === "EXD";
    let va = s[A] * 0.97 + s[B] * 0.01, vb = s[B] * 0.97 + s[A] * 0.01, measured = ea !== eb;
    for (const c in s) {
      if (c === A || c === B) continue;
      let ra, rb;
      if (ea !== eb) {
        const O = ea ? B : A, r = rates(c, O, k);
        if (O === A) { ra = r[0]; rb = r[1]; } else { ra = r[1]; rb = r[0]; }
      } else {      // no far-right finalist (or two): proximity assumption
        const fa = PROX[C[c].bloc][C[A].type], fb = PROX[C[c].bloc][C[B].type];
        ra = 100 * fa * fa / (fa + fb); rb = 100 * fb * fb / (fa + fb);
      }
      va += s[c] * ra / 100; vb += s[c] * rb / 100;
    }
    return { share: 100 * va / (va + vb), measured };
  }
  function duelPoll(A, B) {
    const d = M.duels[A + "|" + B] || M.duels[B + "|" + A];
    if (!d) return null;
    return { share: d.a === A ? d.share_a : 100 - d.share_a, n: d.n, last: d.last, recent: d.recent };
  }
  const erf = x => { const t = 1 / (1 + 0.3275911 * Math.abs(x)); const y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-x * x); return x >= 0 ? y : -y; };
  const Phi = (x, sd) => 0.5 * (1 + erf(x / (sd * Math.SQRT2)));

  function rng(seed) { return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
  function gauss(r) { let u = 0, v = 0; while (!u) u = r(); v = r(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); }

  function run(st, n = 8000) {
    const { shares, field } = firstRound(st);
    const ids = [...field], sig = M.sigma_first[st.horizon];
    const r = rng(2027), pairs = new Map(), qual = {};
    for (let i = 0; i < n; i++) {
      let a = null, b = null, va = -1, vb = -1;
      for (const c of ids) {
        const v = shares[c] + sig * Math.sqrt(Math.max(shares[c], 1) / 20) * gauss(r);
        if (v > va) { b = a; vb = va; a = c; va = v; } else if (v > vb) { b = c; vb = v; }
      }
      const key = a < b ? a + "|" + b : b + "|" + a;
      pairs.set(key, (pairs.get(key) || 0) + 1);
    }
    const win = {}, duels = [];
    for (const [key, cnt] of pairs) {
      const p = cnt / n, [A, B] = key.split("|");
      qual[A] = (qual[A] || 0) + p; qual[B] = (qual[B] || 0) + p;
      const poll = duelPoll(A, B), tr = transferDuel(A, B, shares, st.ctx / 100);
      const w = poll ? st.wPoll / 100 : 0;
      let m = poll ? w * poll.share + (1 - w) * tr.share : tr.share;
      const rnA = C[A].type === "EXD", rnB = C[B].type === "EXD";
      const corr = st.lepenCorr && rnA !== rnB ? M.lepen_correction.mean : 0;
      m += rnA && !rnB ? -corr : rnB && !rnA ? corr : 0;
      const sd = Math.sqrt(M.sigma_duel ** 2 + (corr ? M.lepen_correction.sd ** 2 : 0) + (poll ? 0 : 4) + (tr.measured || poll ? 0 : 4));
      const pa = Phi(m - 50, sd);
      win[A] = (win[A] || 0) + p * pa; win[B] = (win[B] || 0) + p * (1 - pa);
      duels.push({ A, B, p, poll, tr: tr.share, trMeasured: tr.measured, m, pa, corr });
    }
    duels.sort((x, y) => y.p - x.p);
    return { shares, field, qual, win, duels, sig };
  }

  /* ---------- UI ---------- */
  function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || v === false) continue;
      if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
      else if (k === "css") for (const [p, val] of Object.entries(v)) el.style.setProperty(p, val);
      else el.setAttribute(k, v === true ? "" : v);
    }
    for (const kid of kids.flat()) if (kid != null && kid !== false) el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
    return el;
  }
  const ORDER = ["arthaud", "melenchon", "roussel", "tondelier", "glucksmann", "attal", "philippe", "villepin", "lisnard", "retailleau", "dupontaignan", "lepen", "bardella", "zemmour"].filter(id => C[id]);

  window.__sandbox = { run, DEFAULT, PRESETS };  // exposed for tests
  window.renderSandbox = function (main) {
    let st = DEFAULT();
    const baseline = run(DEFAULT());
    const controls = h("div", { class: "sb-controls" });
    const results = h("div", { class: "sb-results", "aria-live": "polite" });
    const presets = h("div", { class: "sb-presets", role: "group", "aria-label": "Scénarios prêts à l'emploi" });
    PRESETS.forEach(p => presets.append(h("button", { type: "button", class: "chip", onclick: () => { st = p.set(DEFAULT()); build(); update(); } }, p.label)));

    main.append(
      h("a", { class: "back", href: "#" }, "← Les huit candidats"),
      h("section", { class: "sb-head" },
        h("p", { class: "eyebrow" }, "Présidentielle 2027 · J-" + M.horizon_days + " · simulation, pas un sondage"),
        h("h1", null, "Simulateur"),
        h("p", { class: "lead" }, "Retirez des candidats, formez des alliances, rejouez des chocs de campagne et changez les hypothèses de report de voix. Les probabilités se recalculent à chaque changement, à partir des sondages des 21 derniers jours (" + M.n_polls + " sondages) et de l'erreur historique des sondages entre 2002 et 2022."),
        h("p", { class: "sb-warn" }, "À lire avant de jouer : cinq mois avant le vote, le favori des sondages a gagné 3 fois sur 5 depuis 2002. Ce modèle ne prévoit pas les événements de campagne ; c'est à vous de les ajouter.")),
      h("section", { class: "sb-presets-wrap" }, h("h2", { class: "sb-h" }, "Scénarios prêts à l'emploi"), presets),
      h("div", { class: "sb-grid" }, controls, results));

    function fieldset(title, ...kids) { return h("fieldset", { class: "sb-fs" }, h("legend", null, title), ...kids); }
    function check(id, label, checked, onchange, extra) {
      return h("label", { class: "sb-check", for: id }, h("input", { type: "checkbox", id, checked, onchange: e => { onchange(e.target.checked); update(); } }), extra || null, h("span", null, label));
    }
    function select(id, label, value, options, onchange) {
      return h("label", { class: "sb-sel", for: id }, h("span", null, label),
        h("select", { id, onchange: e => { onchange(e.target.value); update(); } }, options.map(([v, l]) => h("option", { value: v, selected: v === value }, l))));
    }
    function slider(id, label, value, min, max, left, right, onchange) {
      const out = h("output", { for: id }, String(value));
      return h("div", { class: "sb-slider" },
        h("label", { for: id }, label),
        h("input", { type: "range", id, min, max, step: 5, value, oninput: e => { out.textContent = e.target.value; onchange(+e.target.value); update(); } }),
        h("div", { class: "sb-ends" }, h("span", null, left), out, h("span", null, right)));
    }

    function build() {
      controls.textContent = "";
      const cands = h("div", { class: "sb-cands" });
      for (const id of ORDER) {
        if (id === "bardella") continue;
        cands.append(check("in-" + id, C[id].short + " · " + nf1.format(C[id].base) + " %", st.field.has(id),
          v => { v ? st.field.add(id) : st.field.delete(id); }, h("i", { class: "key", css: { "--c": colorOf(id) } })));
      }
      controls.append(
        fieldset("1. Qui se présente ?",
          h("p", { class: "sb-help" }, "Décocher un candidat redistribue ses électeurs : selon les sondages qui l'ont testé avec et sans lui quand ils existent (Philippe, Attal), sinon selon la proximité politique (hypothèse)."),
          cands,
          check("bardella", "Jordan Bardella remplace Marine Le Pen (90 % de son score, mesuré dans 4 sondages)", st.bardella, v => { st.bardella = v; })),
        fieldset("2. Alliances et désistements",
          select("al-centre", "Centre", st.centre, [["", "Pas d'accord"], ["philippe", "Candidat unique : Philippe"], ["attal", "Candidat unique : Attal"]], v => { st.centre = v; }),
          select("al-gauche", "Gauche hors LFI", st.gauche, [["", "Pas d'accord"], ["glucksmann", "Derrière Glucksmann"], ["tondelier", "Derrière Tondelier"]], v => { st.gauche = v; }),
          select("al-droite", "Droite", st.droite, [["", "Pas d'accord"], ["retailleau", "Derrière Retailleau"], ["lisnard", "Derrière Lisnard"]], v => { st.droite = v; }),
          check("al-rad", "Zemmour et Dupont-Aignan se rallient au candidat RN", st.radicale, v => { st.radicale = v; }),
          slider("follow", "Électeurs qui suivent la consigne du candidat retiré (%)", st.follow, 0, 100, "aucun", "tous", v => { st.follow = v; })),
        fieldset("3. Campagne",
          shockEditor(),
          h("p", { class: "sb-help" }, "Vote utile : les petits candidats d'un camp cèdent 40 % de leurs électeurs au premier de ce camp, comme la gauche en 2022."),
          check("u-g", "Vote utile à gauche", st.utile.GAUCHE, v => { st.utile.GAUCHE = v; }),
          check("u-c", "Vote utile au centre", st.utile.CENTRE, v => { st.utile.CENTRE = v; }),
          check("u-d", "Vote utile à droite", st.utile.DROITE, v => { st.utile.DROITE = v; })),
        fieldset("4. Second tour",
          slider("wpoll", "Poids des sondages de duel face aux reports mesurés aux législatives (%)", st.wPoll, 0, 100, "reports seuls", "sondages seuls", v => { st.wPoll = v; }),
          slider("ctx", "Contexte de barrage contre le RN", st.ctx, 0, 100, "faible (2022)", "fort (2024)", v => { st.ctx = v; }),
          check("corr", "Corriger les duels avec le RN de 3,5 pts (sondages trop favorables à Le Pen en 2002, 2017 et 2022)", st.lepenCorr, v => { st.lepenCorr = v; })),
        fieldset("5. Incertitude",
          select("hz", "Erreur des sondages comme à", String(st.horizon),
            HORIZONS.filter(h => h <= HZ_TODAY).map(h => [String(h), "J-" + h + (h === HZ_TODAY ? " (aujourd'hui)" : "")]), v => { st.horizon = +v; }),
          h("p", { class: "sb-help" }, "Choisir J-30 montre ce que donneraient les mêmes sondages s'ils restaient stables jusqu'à un mois du vote.")),
        h("button", { type: "button", class: "sb-reset", onclick: () => { st = DEFAULT(); build(); update(); } }, "Revenir à la situation actuelle"));
    }

    function shockEditor() {
      const wrap = h("div", { class: "sb-shocks" });
      const list = h("ul", { class: "sb-shock-list" });
      st.shocks.forEach((s, i) => list.append(h("li", null, h("span", null, C[s.id].short + " : " + SHOCKS[s.kind].label),
        h("button", { type: "button", "aria-label": "Retirer ce choc", onclick: () => { st.shocks.splice(i, 1); build(); update(); } }, "Retirer"))));
      const who = h("select", { id: "sh-who", "aria-label": "Candidat touché" }, ORDER.filter(id => id !== "bardella").map(id => h("option", { value: id }, C[id].short)));
      const kind = h("select", { id: "sh-kind", "aria-label": "Type de choc" }, Object.entries(SHOCKS).map(([k, v]) => h("option", { value: k }, v.label)));
      wrap.append(h("div", { class: "sb-shock-add" }, who, kind, h("button", { type: "button", onclick: () => { st.shocks.push({ id: who.value, kind: kind.value }); build(); update(); } }, "Ajouter")), list);
      return wrap;
    }

    function bar(v, col) { return h("span", { class: "sb-bar" }, h("i", { css: { "--w": Math.max(0, Math.min(100, 100 * v)) + "%", "--c": col } })); }
    function delta(v, b) {
      const d = Math.round(100 * (v - b));
      return Math.abs(d) >= 1 ? h("small", { class: "sb-d" }, (d > 0 ? "+" : "−") + Math.abs(d) + " pt") : null;
    }

    function update() {
      const r = run(st);
      results.textContent = "";
      const ids = [...r.field].sort((a, b) => (r.win[b] || 0) - (r.win[a] || 0) || (r.qual[b] || 0) - (r.qual[a] || 0) || r.shares[b] - r.shares[a]);
      const fav = ids[0];
      results.append(h("div", { class: "sb-summary" },
        h("p", { class: "eyebrow" }, "Résultat de " + "8 000 simulations"),
        h("p", { class: "sb-big" }, h("b", null, C[fav].short), " gagne dans ", h("b", null, pp(r.win[fav] || 0)), " des simulations"),
        h("p", { class: "sb-sub" }, "Duel le plus probable : " + C[r.duels[0].A].short + " – " + C[r.duels[0].B].short + " (" + pp(r.duels[0].p) + " des simulations)"),
        h("a", { class: "sb-jump", href: "#sb-controls-anchor", onclick: e => { e.preventDefault(); controls.scrollIntoView({ behavior: "smooth" }); } }, "Modifier les hypothèses ↓")));
      const tb = h("tbody");
      for (const id of ids) {
        const b1 = baseline.shares[id], q = r.qual[id] || 0, w = r.win[id] || 0;
        tb.append(h("tr", null,
          h("td", null, h("span", { class: "who" }, h("i", { class: "key", css: { "--c": colorOf(id) } }), C[id].short)),
          h("td", { class: "num" }, pc(r.shares[id]), b1 != null && Math.abs(r.shares[id] - b1) >= 0.5 ? h("small", { class: "sb-d" }, (r.shares[id] > b1 ? "+" : "−") + nf1.format(Math.abs(r.shares[id] - b1))) : null),
          h("td", null, h("span", { class: "sb-cell" }, bar(q, colorOf(id)), h("span", { class: "num" }, pp(q)), delta(q, baseline.qual[id] || 0))),
          h("td", null, h("span", { class: "sb-cell" }, bar(w, colorOf(id)), h("span", { class: "num" }, pp(w)), delta(w, baseline.win[id] || 0)))));
      }
      results.append(h("div", { class: "tbl" }, h("table", { class: "sb-table" },
        h("thead", null, h("tr", null, h("th", null, "Candidat"), h("th", null, "1er tour simulé"), h("th", null, "Accès au 2nd tour"), h("th", null, "Victoire"))), tb)),
        h("p", { class: "note" }, "Écarts en petit : par rapport à la situation actuelle. 1er tour simulé : moyenne des sondages après vos retraits, alliances et chocs, en % des exprimés."));

      const dl = h("div", { class: "sb-duels" });
      for (const d of r.duels.filter(d => d.p >= 0.01).slice(0, 6)) {
        const [lead, other, ps] = d.pa >= 0.5 ? [d.A, d.B, d.pa] : [d.B, d.A, 1 - d.pa];
        const sh = v => d.pa >= 0.5 ? v : 100 - v;
        const parts = [];
        if (d.poll) parts.push("sondages " + nf1.format(sh(d.poll.share)) + " % (" + d.poll.n + ", " + (d.poll.recent ? "récents" : "dernier le " + d.poll.last) + ")");
        else parts.push("pas de sondage de ce duel");
        parts.push((d.trMeasured ? "reports législatives " : "proximité (hypothèse) ") + nf1.format(sh(d.tr)) + " %");
        if (d.corr) parts.push("correction RN " + (C[lead].type === "EXD" ? "−" : "+") + nf1.format(d.corr));
        dl.append(h("div", { class: "sb-duel" },
          h("div", { class: "sb-duel-top" }, h("b", null, C[lead].short + " – " + C[other].short), h("span", { class: "muted" }, pp(d.p) + " des simulations")),
          h("div", { class: "sb-duel-split", "aria-label": C[lead].short + " " + nf1.format(sh(d.m)) + " %" },
            h("i", { css: { "--w": sh(d.m) + "%", "--c": colorOf(lead) } }), h("i", { css: { "--w": (100 - sh(d.m)) + "%", "--c": colorOf(other) } })),
          h("p", null, h("b", null, C[lead].short + " " + nf1.format(sh(d.m)) + " %"), " · gagne ce duel dans " + pp(ps) + " des cas"),
          h("p", { class: "sb-src" }, parts.join(" · "))));
      }
      results.append(h("h2", { class: "sb-h" }, "Les duels de second tour les plus probables"), dl,
        h("details", { class: "more" }, h("summary", null, "Comment c'est calculé"),
          h("div", { class: "sb-method" },
            h("p", null, "1er tour : moyenne de la dernière hypothèse la plus complète de chaque sondage (21 derniers jours), puis vos changements. Chaque simulation tire une erreur par candidat, de la taille des erreurs observées au même horizon entre 2002 et 2022 (environ " + nf1.format(r.sig) + " pts pour un candidat à 20 %)."),
            h("p", null, "2nd tour : mélange des sondages de duel et d'une estimation par reports de voix. Les reports viennent des seconds tours des législatives contre le RN (2022 : barrage faible ; 2024 : barrage fort), séparés selon que le candidat de gauche était LFI ou non. Les sondages de duel ne bougent pas avec vos hypothèses de 1er tour, la partie reports oui."),
            h("p", null, "Hypothèses non mesurées (signalées « proximité ») : reports entre candidats sans duel testé, et électeurs d'un autre candidat de gauche face à un finaliste de gauche."),
            h("p", null, "Fiabilité : appliqué à 2002–2022 à J-163, le modèle donnait au futur vainqueur 58, 42, 94, 3 et 79 % de chances. En 2017, il aurait misé sur Fillon."))));
    }

    build();
    update();
  };
})();
