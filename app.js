/* Road to 2027: rendering. Data lives in data/*.js; nothing here needs weekly edits. */
(function () {
  "use strict";
  const SITE = window.SITE, POLLS = (window.POLLS && window.POLLS.polls) || [];
  const SOCIAL = window.SOCIAL || { followers: {}, members: {} };
  const DAY = 864e5;
  const CANDS = SITE.candidates;
  const BY_ID = Object.fromEntries(CANDS.map(c => [c.id, c]));
  const NETWORKS = [
    { id: "x", label: "X (Twitter)" }, { id: "instagram", label: "Instagram" }, { id: "tiktok", label: "TikTok" },
    { id: "youtube", label: "YouTube" }, { id: "facebook", label: "Facebook" }
  ];

  /* ---------- helpers ---------- */
  const T = s => Date.parse(s + "T00:00:00Z");
  const color = c => `var(--c${c.slot})`;
  const nf1 = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 });
  const nf0 = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });
  const pct = v => nf1.format(v) + " %";
  const pts = v => (v > 0 ? "+" : v < 0 ? "−" : "±") + nf1.format(Math.abs(v)) + " pt";
  const compact = v => v >= 1e6 ? nf1.format(v / 1e6) + " M" : v >= 1e4 ? nf0.format(v / 1e3) + " k" : nf0.format(v);
  const fmtD = (s, o) => new Date(T(s)).toLocaleDateString("fr-FR", Object.assign({ day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }, o));
  const fmtRange = (a, b) => {
    if (!a || a === b) return fmtD(b);
    const A = new Date(T(a)), B = new Date(T(b));
    if (A.getUTCMonth() === B.getUTCMonth()) return A.getUTCDate() + "–" + fmtD(b);
    return fmtD(a, { year: undefined }) + " – " + fmtD(b);
  };
  const today = () => { const d = new Date(); return Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()); };

  function h(tag, attrs, ...kids) {
    const SVG = ["svg", "g", "path", "line", "circle", "rect", "text", "polyline"].includes(tag);
    const el = SVG ? document.createElementNS("http://www.w3.org/2000/svg", tag) : document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || v === false) continue;
      if (k === "style" && typeof v === "object") Object.assign(el.style, v);
      else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
      else if (k === "css") for (const [p, val] of Object.entries(v)) el.style.setProperty(p, val);
      else el.setAttribute(k, v === true ? "" : v);
    }
    for (const kid of kids.flat()) if (kid != null && kid !== false) el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
    return el;
  }

  /* ---------- poll data ---------- */
  // One reference scenario per poll: the hypothesis that includes the most of the tracked
  // candidates (first one on ties). Every candidate is read from that same hypothesis, so values
  // in a poll stay comparable. lo/hi/n = range across all hypotheses that include the candidate.
  function refScenario(poll) {
    if (!poll._ref) {
      let best = poll.scenarios[0], bn = -1;
      for (const s of poll.scenarios) { const n = CANDS.filter(c => c.id in s).length; if (n > bn) { bn = n; best = s; } }
      poll._ref = best;
    }
    return poll._ref;
  }
  function pv(poll, id) {
    const ref = refScenario(poll);
    if (!(id in ref)) return null;
    let lo = Infinity, hi = -Infinity, n = 0;
    for (const s of poll.scenarios) if (id in s) { lo = Math.min(lo, s[id]); hi = Math.max(hi, s[id]); n++; }
    return { v: ref[id], lo, hi, n };
  }
  function series(id, polls) {
    const out = [];
    for (const p of polls) { const x = pv(p, id); if (x) out.push(Object.assign({ t: T(p.date), poll: p }, x)); }
    return out;
  }
  function summary(id) {
    const s = series(id, POLLS);
    if (!s.length) return null;
    const last = s[s.length - 1];
    const prevSame = [...s].reverse().find(x => x !== last && x.poll.firm === last.poll.firm);
    const t30 = last.t - 30 * DAY;
    const recent = s.filter(x => x.t >= t30);
    return { last, prevSame, lo30: Math.min(...recent.map(x => x.v)), hi30: Math.max(...recent.map(x => x.v)), n30: recent.length, all: s };
  }
  const FIRMS = [...new Set(POLLS.map(p => p.firm))].sort((a, b) => a.localeCompare(b, "fr"));

  /* ---------- chart engine (SVG, hand-rolled) ---------- */
  function niceStep(max, ticks) {
    const raw = max / ticks, mag = Math.pow(10, Math.floor(Math.log10(raw)));
    for (const m of [1, 2, 2.5, 5, 10]) if (m * mag >= raw) return m * mag;
    return 10 * mag;
  }
  const MONTHS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];

  /* opt: {series:[{key,label,color,points:[{t,v,lo,hi,hollow}],dim}], height, yFmt, x0, x1, events,
           labels(bool), snap:[t], tooltip(t)->{title,sub,rows,foot}, aria} */
  function lineChart(host, opt) {
    host.textContent = "";
    host.classList.add("chart");
    const W = Math.max(280, host.clientWidth || 640);
    const narrow = W < 560;
    const showLabels = opt.labels && !narrow;
    const H = opt.height || 300;
    const evs = (opt.events || []).filter(e => T(e.end || e.date) >= opt.x0 && T(e.date) <= opt.x1);
    // event label rows (avoid overlaps)
    const m = { l: 34, r: showLabels ? 112 : 14, b: 26, t: 10 };
    const pw = () => W - m.l - m.r;
    const X = t => m.l + (t - opt.x0) / (opt.x1 - opt.x0) * pw();
    const rows = [];
    const evL = narrow ? [] : evs.map(e => {
      const x = X(T(e.date)), w = e.short.length * 5.8 + 8;
      let r = 0; while (rows[r] && rows[r] > x - 2) r++;
      rows[r] = x + w; return { e, x, r };
    });
    m.t = 10 + (narrow ? 0 : Math.min(rows.length, 3) * 14);
    const all = opt.series.flatMap(s => s.points);
    const ymaxRaw = Math.max(opt.yMinMax || 1, ...all.map(p => p.hi != null ? p.hi : p.v));
    const step = niceStep(ymaxRaw, H < 200 ? 3 : 5);
    const ymax = Math.ceil(ymaxRaw * 1.04 / step) * step;
    const ph = H - m.t - m.b;
    const Y = v => m.t + ph - v / ymax * ph;

    const svg = h("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": opt.aria || "", tabindex: opt.tooltip ? 0 : null });
    // grid + y ticks
    const g = h("g");
    for (let v = 0; v <= ymax + 1e-9; v += step) {
      g.append(h("line", { x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v), stroke: v === 0 ? "var(--rule)" : "var(--grid)", "stroke-width": 1 }));
      g.append(h("text", { x: m.l - 6, y: Y(v) + 4, "text-anchor": "end" }, opt.yFmt(v)));
    }
    // x ticks (months)
    const d0 = new Date(opt.x0), months = [];
    for (let d = new Date(Date.UTC(d0.getUTCFullYear(), d0.getUTCMonth() + 1, 1)); d.getTime() <= opt.x1; d = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 1))) months.push(d);
    const stride = Math.max(1, Math.ceil(months.length / (pw() / 64)));
    months.forEach((d, i) => {
      if (i % stride) return;
      const x = X(d.getTime());
      g.append(h("line", { x1: x, x2: x, y1: H - m.b, y2: H - m.b + 4, stroke: "var(--rule)" }));
      const lab = MONTHS[d.getUTCMonth()] + (d.getUTCMonth() === 0 || i === 0 ? " " + d.getUTCFullYear() : "");
      g.append(h("text", { x, y: H - 8, "text-anchor": "middle" }, lab));
    });
    svg.append(g);
    // events
    const ge = h("g", { class: "evt" });
    for (const e of evs) {
      const x1 = X(Math.max(opt.x0, T(e.date))), x2 = e.end ? X(T(e.end) + DAY) : x1;
      if (x2 - x1 > 2) ge.append(h("rect", { x: x1, y: m.t, width: x2 - x1, height: ph, fill: "var(--wash)" }));
      ge.append(h("line", { x1, x2: x1, y1: m.t - 2, y2: H - m.b, stroke: "var(--ink3)", "stroke-dasharray": "2 3", "stroke-width": 1, opacity: .6 }));
    }
    for (const l of evL) if (l.r < 3) ge.append(h("text", { x: l.x + 3, y: 10 + l.r * 14 + 2 }, l.e.short));
    svg.append(ge);
    // series
    const gs = h("g");
    const order = [...opt.series].sort((a, b) => (a.dim ? 0 : 1) - (b.dim ? 0 : 1));
    for (const s of order) {
      const P = s.points;
      if (!P.length) continue;
      const op = s.dim ? 0.18 : 1;
      const sg = h("g", { opacity: op });
      if (opt.whiskers) for (const p of P) if (p.lo != null && p.hi > p.lo)
        sg.append(h("line", { x1: X(p.t), x2: X(p.t), y1: Y(p.lo), y2: Y(p.hi), stroke: s.color, "stroke-width": 2, opacity: .45, "stroke-linecap": "round" }));
      if (opt.area && P.length > 1) {
        const d = "M" + P.map(p => X(p.t) + "," + Y(p.v)).join("L") + `L${X(P[P.length - 1].t)},${Y(0)}L${X(P[0].t)},${Y(0)}Z`;
        sg.append(h("path", { d, fill: s.color, opacity: .1 }));
      }
      if (P.length > 1) sg.append(h("path", { d: "M" + P.map(p => X(p.t) + "," + Y(p.v)).join("L"), fill: "none", stroke: s.color, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }));
      for (const p of P) sg.append(h("circle", { cx: X(p.t), cy: Y(p.v), r: opt.dot || 3.5, fill: p.hollow ? "var(--surface)" : s.color, stroke: p.hollow ? s.color : "var(--surface)", "stroke-width": p.hollow ? 2 : 1.5 }));
      gs.append(sg);
    }
    svg.append(gs);
    // direct labels at line ends (de-overlapped)
    if (showLabels) {
      const L = opt.series.filter(s => s.points.length && !s.dim).map(s => {
        const p = s.points[s.points.length - 1];
        return { s, y: Y(p.v), x: X(p.t), v: p.v };
      }).sort((a, b) => a.y - b.y);
      for (let i = 1; i < L.length; i++) if (L[i].y - L[i - 1].y < 14) L[i].y = L[i - 1].y + 14;
      const over = L.length ? L[L.length - 1].y - (H - m.b) : 0;
      if (over > 0) L.forEach(l => l.y -= over);
      const gl = h("g");
      for (const l of L) {
        const x = W - m.r + 6;
        gl.append(h("line", { x1: x, x2: x + 10, y1: l.y, y2: l.y, stroke: l.s.color, "stroke-width": 3, "stroke-linecap": "round" }));
        gl.append(h("text", { x: x + 15, y: l.y + 4, class: "lab" }, l.s.label + " " + opt.yFmt(l.v, true)));
      }
      svg.append(gl);
    }
    host.append(svg);

    // hover layer: crosshair snaps to the nearest measurement date
    if (opt.tooltip && opt.snap && opt.snap.length) {
      const snap = [...new Set(opt.snap)].filter(t => t >= opt.x0 && t <= opt.x1).sort((a, b) => a - b);
      const cross = h("line", { y1: m.t, y2: H - m.b, stroke: "var(--ink)", "stroke-width": 1, opacity: 0 });
      const hi = h("g");
      svg.append(cross, hi);
      const tip = h("div", { class: "tip", hidden: true, role: "status" });
      host.append(tip);
      let idx = -1;
      const show = i => {
        if (i < 0 || i >= snap.length) return;
        idx = i;
        const t = snap[i], x = X(t);
        cross.setAttribute("x1", x); cross.setAttribute("x2", x); cross.setAttribute("opacity", .35);
        hi.textContent = "";
        for (const s of opt.series) if (!s.dim) for (const p of s.points) if (p.t === t)
          hi.append(h("circle", { cx: x, cy: Y(p.v), r: 5.5, fill: s.color, stroke: "var(--surface)", "stroke-width": 2 }));
        const c = opt.tooltip(t);
        tip.textContent = "";
        tip.append(h("div", { class: "t" }, c.title));
        if (c.sub) tip.append(h("div", { class: "s" }, c.sub));
        for (const r of c.rows || []) tip.append(h("div", { class: "r" }, h("i", { style: { background: r.color } }), h("b", null, r.value), h("span", null, r.label)));
        if (c.foot) tip.append(h("div", { class: "f" }, c.foot));
        tip.hidden = false;
        const scale = host.clientWidth / W;
        const tw = tip.offsetWidth, px = x * scale;
        tip.style.transform = `translate(${px + 14 + tw > host.clientWidth ? Math.max(0, px - tw - 14) : px + 14}px, ${m.t * scale}px)`;
      };
      const hide = () => { cross.setAttribute("opacity", 0); hi.textContent = ""; tip.hidden = true; };
      const near = ev => {
        const r = svg.getBoundingClientRect(), x = (ev.clientX - r.left) * (W / r.width);
        let best = 0, bd = Infinity;
        snap.forEach((t, i) => { const d = Math.abs(X(t) - x); if (d < bd) { bd = d; best = i; } });
        return best;
      };
      svg.addEventListener("pointermove", ev => show(near(ev)));
      svg.addEventListener("pointerdown", ev => show(near(ev)));
      svg.addEventListener("pointerleave", hide);
      svg.addEventListener("blur", hide);
      svg.addEventListener("focus", () => show(idx < 0 ? snap.length - 1 : idx));
      svg.addEventListener("keydown", ev => {
        if (ev.key === "ArrowLeft") { show(Math.max(0, idx - 1)); ev.preventDefault(); }
        else if (ev.key === "ArrowRight") { show(Math.min(snap.length - 1, idx + 1)); ev.preventDefault(); }
        else if (ev.key === "Escape") hide();
      });
    }
  }

  function sparkline(host, points, col, x0, x1) {
    host.textContent = "";
    const W = 200, H = 44;
    if (points.length < 2) return;
    const ys = points.map(p => p.v), lo = Math.min(...ys), hi = Math.max(...ys);
    const pad = (hi - lo) * .15 || 1;
    const X = t => 3 + (t - x0) / (x1 - x0) * (W - 6), Y = v => H - 4 - (v - (lo - pad)) / ((hi + pad) - (lo - pad)) * (H - 8);
    const d = points.map(p => X(p.t).toFixed(1) + "," + Y(p.v).toFixed(1)).join("L");
    const last = points[points.length - 1];
    host.append(h("svg", { viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: "none", width: "100%", height: "100%", "aria-hidden": "true" },
      h("path", { d: `M${d}L${X(last.t)},${H}L${X(points[0].t)},${H}Z`, fill: col, opacity: .12 }),
      h("path", { d: "M" + d, fill: "none", stroke: col, "stroke-width": 2, "vector-effect": "non-scaling-stroke", "stroke-linejoin": "round" })));
    host.style.position = "relative";
    host.append(h("span", { style: { position: "absolute", left: `calc(${X(last.t) / W * 100}% - 4px)`, top: `calc(${Y(last.v) / H * 100}% - 4px)`, width: "8px", height: "8px", borderRadius: "50%", background: col, border: "2px solid var(--surface)" } }));
  }

  /* ---------- state & routing ---------- */
  const state = { range: "campagne", firm: "all", focus: null };
  try { const s = JSON.parse(localStorage.getItem("road-to-2027-filters") || "{}"); if (s.range) state.range = s.range; if (s.firm && FIRMS.includes(s.firm)) state.firm = s.firm; } catch (e) { /* storage unavailable */ }
  const save = () => { try { localStorage.setItem("road-to-2027-filters", JSON.stringify({ range: state.range, firm: state.firm })); } catch (e) { /* ignore */ } };
  const RANGES = [
    { id: "campagne", label: "Depuis juillet 2026", from: () => T("2026-07-01") },
    { id: "12m", label: "12 mois", from: () => today() - 365 * DAY },
    { id: "all", label: "Depuis 2024", from: () => T("2024-07-01") }
  ];
  const rangeFrom = () => RANGES.find(r => r.id === state.range).from();

  const main = document.getElementById("main");
  const redraws = [];
  function route() {
    redraws.length = 0;
    main.textContent = "";
    const id = location.hash.replace(/^#/, "");
    if (BY_ID[id]) renderCandidate(BY_ID[id]);
    else if (id === "simulateur" && window.renderSandbox) { document.title = "Simulateur · Road to 2027"; window.renderSandbox(main); }
    else { document.title = "Road to 2027"; renderHome(); }
    if (id) main.focus({ preventScroll: true });
    window.scrollTo(0, 0);
    requestAnimationFrame(() => redraws.forEach(f => f()));
  }
  let rt;
  new ResizeObserver(() => { clearTimeout(rt); rt = setTimeout(() => redraws.forEach(f => f()), 120); }).observe(main);
  window.addEventListener("hashchange", route);
  document.getElementById("upd").textContent = "Mise à jour du " + fmtD(SITE.updated);

  const daysLeft = () => Math.max(0, Math.ceil((T(SITE.election.date) - today()) / DAY));

  /* ---------- home ---------- */
  function renderHome() {
    const recent = POLLS.filter(p => T(p.date) >= T("2026-07-01"));
    const firms = new Set(recent.map(p => p.firm));
    main.append(h("section", { class: "hero" },
      h("div", null,
        h("p", { class: "eyebrow" }, "Présidentielle 2027 · J-" + daysLeft() + " avant le " + SITE.election.label),
        h("h1", null, "État des lieux"),
      ),
      h("div", null,
        h("p", { class: "lead" }, "Huit candidats suivis sur trois indicateurs publics : intentions de vote, audience sur les réseaux sociaux, adhérents des partis. Chaque chiffre renvoie à sa source."),
        window.MODEL ? h("p", { style: { margin: "14px 0 0" } }, h("a", { class: "cta", href: "#simulateur" }, "Ouvrir le simulateur : retraits, alliances, reports de voix →")) : null,
        h("div", { class: "facts", style: { marginTop: "20px" } },
          h("div", null, h("b", { class: "num" }, recent.length), h("span", null, "sondages depuis le 1er juillet 2026")),
          h("div", null, h("b", { class: "num" }, firms.size), h("span", null, "instituts différents")),
          h("div", null, h("b", { class: "num" }, fmtD(SITE.election.date, { year: undefined })), h("span", null, h("a", { href: SITE.election.source, target: "_blank", rel: "noopener" }, "Premier tour"), ", 2027")))
      )));

    // standings
    const sums = CANDS.map(c => ({ c, s: summary(c.id) })).filter(x => x.s);
    sums.sort((a, b) => b.s.last.v - a.s.last.v);
    const cards = h("div", { class: "cards" });
    const sx0 = T("2026-07-01"), sx1 = today();
    sums.forEach(({ c, s }, i) => {
      const l = s.last, sp = h("div", { class: "spark" });
      const d = s.prevSame ? l.v - s.prevSame.v : null;
      cards.append(h("a", { class: "card", href: "#" + c.id, css: { "--c": color(c) } },
        h("span", { class: "rank num", "aria-hidden": "true" }, i + 1),
        h("span", { class: "who" }, h("span", { class: "key" }), h("span", { class: "name" }, c.name)),
        h("span", { class: "party" }, c.party),
        h("span", null,
          h("span", { class: "val" }, h("b", { class: "num" }, pct(l.v)),
            d !== null ? h("span", { class: "delta num" }, (d > 0 ? "▲ " : d < 0 ? "▼ " : "") + pts(d)) : null),
          h("span", { class: "meta", style: { display: "block" } }, l.poll.firm + ", " + fmtRange(l.poll.start, l.poll.date) +
            (d !== null ? " · écart avec son sondage du " + fmtD(s.prevSame.poll.date, { year: undefined }) : "")),
          h("span", { class: "meta", style: { display: "block" } }, s.n30 > 1 ? "De " + nf1.format(s.lo30) + " à " + pct(s.hi30) + " sur 30 jours (" + s.n30 + " sondages)" : "1 sondage sur 30 jours")),
        sp,
        h("span", { class: "go" }, "Voir la fiche →")));
      redraws.push(() => sparkline(sp, s.all.filter(x => x.t >= sx0), color(c), sx0, sx1));
    });
    main.append(h("section", { "aria-labelledby": "std-t" },
      h("div", { class: "sec-head" }, h("div", null,
        h("h2", { id: "std-t" }, "Le classement dans le dernier sondage de chaque candidat"),
        h("p", null, "La flèche compare au sondage précédent du même institut, seule comparaison qui ne mélange pas les méthodes. La fourchette sur 30 jours montre l'écart entre instituts."))),
      cards));

    // race chart
    const chartHost = h("div");
    const legend = h("ul", { class: "legend" });
    const filters = h("div", { class: "filters" });
    const seg = h("div", { class: "seg", role: "group", "aria-label": "Période" });
    RANGES.forEach(r => seg.append(h("button", { type: "button", "aria-pressed": String(state.range === r.id), onclick: () => { state.range = r.id; save();[...seg.children].forEach((b, i) => b.setAttribute("aria-pressed", String(RANGES[i].id === r.id))); drawRace(); } }, r.label)));
    const sel = h("select", { id: "firm-filter", onchange: e => { state.firm = e.target.value; save(); drawRace(); } },
      h("option", { value: "all" }, "Tous les instituts"), FIRMS.map(f => h("option", { value: f, selected: state.firm === f }, f)));
    filters.append(seg, h("label", { class: "sel", for: "firm-filter" }, "Institut", sel));
    CANDS.forEach(c => legend.append(h("li", null, h("button", {
      type: "button", "aria-pressed": "false", css: { "--c": color(c) }, onclick: e => {
        state.focus = state.focus === c.id ? null : c.id;
        [...legend.querySelectorAll("button")].forEach(b => b.setAttribute("aria-pressed", "false"));
        if (state.focus) e.currentTarget.setAttribute("aria-pressed", "true");
        drawRace();
      }
    }, h("span", { class: "ln" }), c.short))));
    legend.append(h("li", { class: "hint" }, "Cliquez sur un nom pour le mettre en avant."));
    const note = h("p", { class: "note" });
    function drawRace() {
      const x0 = rangeFrom(), x1 = Math.max(today(), T(SITE.updated)) + 2 * DAY;
      const polls = POLLS.filter(p => T(p.date) >= x0 && (state.firm === "all" || p.firm === state.firm));
      const S = CANDS.map(c => ({ key: c.id, label: c.short, color: color(c), dim: state.focus && state.focus !== c.id, points: series(c.id, polls) }));
      note.textContent = polls.length + " sondage" + (polls.length > 1 ? "s" : "") + " affiché" + (polls.length > 1 ? "s" : "") +
        ". Chaque point est un sondage ; la ligne relie les sondages successifs sans les moyenner. Les écarts d'un point à l'autre reflètent souvent les différences entre instituts.";
      lineChart(chartHost, {
        series: S, height: 380, x0, x1, yFmt: (v, lab) => lab ? nf1.format(v) : v + " %", labels: true, events: SITE.events, yMinMax: 10,
        aria: "Intentions de vote au premier tour, un point par sondage, " + polls.length + " sondages",
        snap: polls.map(p => T(p.date)),
        tooltip: t => {
          const ps = polls.filter(p => T(p.date) === t);
          const p = ps[0];
          const rows = CANDS.map(c => ({ c, x: pv(p, c.id) })).filter(r => r.x).sort((a, b) => b.x.v - a.x.v)
            .map(r => ({ color: color(r.c), value: pct(r.x.v), label: r.c.short + (r.x.n > 1 && r.x.hi > r.x.lo ? " (" + nf1.format(r.x.lo) + "–" + nf1.format(r.x.hi) + " selon hypothèse)" : "") }));
          const ev = SITE.events.find(e => Math.abs(T(e.date) - t) <= 2 * DAY);
          return { title: p.firm + (ps.length > 1 ? " (+ " + ps.slice(1).map(q => q.firm).join(", ") + ")" : ""), sub: "Terrain " + fmtRange(p.start, p.date) + (p.sample ? " · " + nf0.format(p.sample) + " personnes" : ""), rows, foot: ev ? "Repère : " + ev.label : (p.scenarios.length > 1 ? p.scenarios.length + " hypothèses testées ; scores de la plus complète." : null) };
        }
      });
    }
    redraws.push(drawRace);
    main.append(h("section", { "aria-labelledby": "race-t" },
      h("div", { class: "sec-head" }, h("div", null,
        h("h2", { id: "race-t" }, "Intentions de vote au premier tour"),
        h("p", null, "Tous les sondages publiés, institut par institut. Quand un sondage teste plusieurs hypothèses de candidatures, on retient pour tous les candidats la même : celle qui inclut le plus de candidats suivis ici.")),
        filters),
      h("div", { class: "panel" }, legend, chartHost, note,
        pollTable(POLLS.filter(p => T(p.date) >= T("2026-07-01")).reverse(), CANDS, "Voir tous les sondages depuis juillet 2026 (tableau)"))));

    // latest per institute
    main.append(latestPerFirm());
    main.append(audienceSection());
    main.append(membersSection());
    main.append(methodSection());
  }

  function cellWho(c) { return h("span", { class: "who" }, h("span", { class: "key", css: { "--c": color(c) } }), c.name); }

  function pollTable(polls, cands, summaryText) {
    const tb = h("tbody");
    for (const p of polls) {
      tb.append(h("tr", null,
        h("td", null, h("a", { href: p.url || POLLS_INDEX(), target: "_blank", rel: "noopener" }, p.firm), h("small", null, fmtRange(p.start, p.date) + (p.sample ? " · " + nf0.format(p.sample) : ""))),
        cands.map(c => { const x = pv(p, c.id); return x ? h("td", { title: x.n > 1 ? x.n + " hypothèses : " + nf1.format(x.lo) + " à " + nf1.format(x.hi) + " %" : null }, nf1.format(x.v) + (x.hi > x.lo ? "*" : "")) : h("td", { class: "empty" }, "–"); })));
    }
    return h("details", { class: "more" }, h("summary", null, summaryText),
      h("div", { class: "tbl" }, h("table", null,
        h("thead", null, h("tr", null, h("th", null, "Institut, terrain, effectif"), cands.map(c => h("th", null, c.short)))), tb)),
      h("p", { class: "note" }, "En %. * : le score varie selon les hypothèses testées ; valeur de l'hypothèse la plus complète, fourchette au survol. – : absent de cette hypothèse."));
  }
  const POLLS_INDEX = () => window.POLLS.index;

  function latestPerFirm() {
    const cutoff = T(SITE.updated) - 45 * DAY;
    const latest = [];
    for (const f of FIRMS) {
      const p = [...POLLS].reverse().find(q => q.firm === f);
      if (p && T(p.date) >= cutoff) latest.push(p);
    }
    latest.sort((a, b) => T(b.date) - T(a.date));
    const head = h("tr", null, h("th", null, "Candidat"), latest.map(p => h("th", null, h("a", { href: p.url || POLLS_INDEX(), target: "_blank", rel: "noopener" }, p.firm), h("br"), fmtD(p.date, { year: undefined }))));
    const tb = h("tbody");
    const order = [...CANDS].sort((a, b) => ((summary(b.id) || { last: { v: 0 } }).last.v) - ((summary(a.id) || { last: { v: 0 } }).last.v));
    for (const c of order) tb.append(h("tr", null, h("td", null, h("a", { href: "#" + c.id, style: { textDecoration: "none" } }, cellWho(c))),
      latest.map(p => { const x = pv(p, c.id); return x ? h("td", null, pct(x.v)) : h("td", { class: "empty" }, "non testé"); })));
    return h("section", { "aria-labelledby": "lf-t" },
      h("div", { class: "sec-head" }, h("div", null, h("h2", { id: "lf-t" }, "Le dernier sondage de chaque institut"),
        h("p", null, "Les instituts ayant publié dans les 45 derniers jours, côte à côte. Aucune moyenne : chaque colonne est un sondage, avec un lien vers sa publication."))),
      h("div", { class: "tbl" }, h("table", null, h("thead", null, head), tb)));
  }

  function lastPoint(arr) { return arr && arr.length ? arr[arr.length - 1] : null; }

  function audienceSection() {
    const F = SOCIAL.followers || {};
    const tb = h("tbody");
    let any = false;
    for (const c of CANDS) {
      const row = h("tr", null, h("td", null, h("a", { href: "#" + c.id, style: { textDecoration: "none" } }, cellWho(c))));
      for (const n of NETWORKS) {
        const acc = (F[c.id] || {})[n.id];
        const p = acc && lastPoint(acc.points);
        if (p) { any = true; row.append(h("td", { title: (acc.handle || "") + " · " + fmtD(p.date) }, h("a", { href: p.source, target: "_blank", rel: "noopener" }, (p.approx ? "≈ " : "") + compact(p.value)), h("small", null, fmtD(p.date, { year: undefined })))); }
        else row.append(h("td", { class: "empty" }, "–"));
      }
      tb.append(row);
    }
    return h("section", { "aria-labelledby": "aud-t" },
      h("div", { class: "sec-head" }, h("div", null, h("h2", { id: "aud-t" }, "Audience sur les réseaux sociaux"),
        h("p", null, "Abonnés aux comptes personnels des candidats, au dernier relevé daté. Les réseaux ne s'additionnent pas : une même personne peut suivre plusieurs comptes."))),
      any ? h("div", { class: "tbl" }, h("table", null, h("thead", null, h("tr", null, h("th", null, "Candidat"), NETWORKS.map(n => h("th", null, n.label)))), tb))
        : h("p", { class: "empty-state" }, "Relevés en cours de collecte."),
      h("p", { class: "note" }, "≈ : valeur arrondie ou date approximative. Cliquez sur un chiffre pour voir sa source. X, Instagram, TikTok et Facebook : relevés de ",
        h("a", { href: "https://lepodium2027.fr/", target: "_blank", rel: "noopener" }, "Le Podium 2027"), ", repris deux fois par semaine ; YouTube : relevés manuels."));
  }

  function membersSection() {
    const M = SOCIAL.members || {};
    const tb = h("tbody");
    for (const c of CANDS) {
      const m = M[c.id], p = m && lastPoint(m.points);
      const first = m && m.points && m.points.length > 1 ? m.points[0] : null;
      tb.append(h("tr", null, h("td", null, h("a", { href: "#" + c.id, style: { textDecoration: "none" } }, cellWho(c))),
        h("td", { style: { textAlign: "left" } }, m ? m.party : "–"),
        p ? h("td", null, h("a", { href: p.source, target: "_blank", rel: "noopener" }, (p.approx ? "≈ " : "") + nf0.format(p.value)), h("small", null, fmtD(p.date))) : h("td", { class: "empty" }, "aucun chiffre publié"),
        first ? h("td", null, nf0.format(first.value), h("small", null, fmtD(first.date))) : h("td", { class: "empty" }, "–"),
        h("td", { style: { textAlign: "left", whiteSpace: "normal", minWidth: "16em" } }, m && m.kind ? m.kind : "", m && m.note ? h("small", null, m.note) : null)));
    }
    return h("section", { "aria-labelledby": "mem-t" },
      h("div", { class: "sec-head" }, h("div", null, h("h2", { id: "mem-t" }, "Adhérents des partis"),
        h("p", null, "Chiffres déclarés par les partis ou rapportés par la presse. Ils ne sont pas certifiés et les partis ne comptent pas tous de la même façon : à lire parti par parti, pas comme un classement."))),
      h("div", { class: "tbl" }, h("table", null, h("thead", null, h("tr", null, h("th", null, "Candidat"), h("th", { style: { textAlign: "left" } }, "Parti"), h("th", null, "Dernier chiffre"), h("th", null, "Premier relevé"), h("th", { style: { textAlign: "left" } }, "Ce qui est compté"))), tb)));
  }

  function methodSection() {
    return h("section", { "aria-labelledby": "meth-t", id: "methode" },
      h("div", { class: "sec-head" }, h("h2", { id: "meth-t" }, "Méthode et statut du site")),
      h("div", { class: "method" },
        h("div", null, h("h3", null, "Sondages"),
          h("p", null, "Les sondages sont repérés grâce à la page Wikipédia qui les recense, puis reliés chacun à sa publication d'origine (institut, média ou notice de la Commission des sondages). Ils sont datés au dernier jour du terrain."),
          h("p", null, "Aucune moyenne entre instituts, aucun redressement. Quand un sondage teste plusieurs hypothèses, on retient pour tous les candidats celle qui inclut le plus de candidats suivis ici, pour que les scores d'un même sondage restent comparables. L'écart entre hypothèses est indiqué.")),
        h("div", null, h("h3", null, "Réseaux et adhérents"),
          h("p", null, "Abonnés : relevés datés, un par compte, chacun avec sa source. Adhérents : chiffres communiqués par les partis ou cités par la presse, jamais certifiés. LFI compte des soutiens inscrits en ligne, pas des adhérents à jour de cotisation."),
          h("p", null, "Un chiffre sans source n'est pas publié. Une case vide signifie qu'aucun chiffre public n'a été trouvé.")),
        h("div", null, h("h3", null, "Statut"),
          h("p", null, "Site indépendant, édité à titre personnel, sans lien avec aucun candidat ni aucun parti. Il n'appelle pas à voter et ne collecte aucune donnée sur ses visiteurs."),
          h("p", null, "Mise à jour au moins chaque semaine. Conformément à la loi, aucun sondage n'est publié la veille et le jour du scrutin."),
          h("p", null, "Contact : ", h("span", { class: "num" }, SITE.contact), ". Hébergement : " + SITE.host + "."))));
  }

  /* ---------- candidate page ---------- */
  function renderCandidate(c) {
    document.title = c.name + " · Road to 2027";
    const s = summary(c.id);
    const col = color(c);
    main.append(h("a", { class: "back", href: "#" }, "← Les huit candidats"));
    const d = s && s.prevSame ? s.last.v - s.prevSame.v : null;
    main.append(h("section", { class: "fiche-head", css: { "--c": col } },
      h("div", null,
        h("p", { class: "eyebrow" }, "Présidentielle 2027 · J-" + daysLeft()),
        h("h1", null, h("span", { class: "key" }), c.name),
        h("p", { class: "party" }, c.party)),
      s ? h("div", { class: "bigfig" },
        h("b", { class: "num" }, pct(s.last.v)),
        h("p", null, "Dernier sondage : " + s.last.poll.firm + ", " + fmtRange(s.last.poll.start, s.last.poll.date) + " · " +
          (d !== null ? pts(d) + " par rapport au sondage " + s.prevSame.poll.firm + " du " + fmtD(s.prevSame.poll.date, { year: undefined }) + " · " : "") +
          (s.n30 > 1 ? "De " + nf1.format(s.lo30) + " à " + pct(s.hi30) + " sur 30 jours." : "")))
        : h("div", { class: "bigfig" }, h("p", null, "Pas encore testé dans les sondages."))));

    // polls chart for this candidate
    const host = h("div");
    const seg = h("div", { class: "seg", role: "group", "aria-label": "Période" });
    RANGES.forEach(r => seg.append(h("button", { type: "button", "aria-pressed": String(state.range === r.id), onclick: () => { state.range = r.id; save();[...seg.children].forEach((b, i) => b.setAttribute("aria-pressed", String(RANGES[i].id === r.id))); draw(); } }, r.label)));
    const sel = h("select", { id: "firm-filter-c", onchange: e => { state.firm = e.target.value; save(); draw(); } },
      h("option", { value: "all" }, "Tous les instituts"), FIRMS.map(f => h("option", { value: f, selected: state.firm === f }, f)));
    function draw() {
      const x0 = rangeFrom(), x1 = Math.max(today(), T(SITE.updated)) + 2 * DAY;
      const polls = POLLS.filter(p => T(p.date) >= x0 && (state.firm === "all" || p.firm === state.firm));
      const pts_ = series(c.id, polls);
      lineChart(host, {
        series: [{ key: c.id, label: c.short, color: col, points: pts_ }], height: 320, x0, x1, whiskers: true, area: false, dot: 4,
        yFmt: v => v + " %", yMinMax: 5, events: SITE.events.filter(e => !e.who || !e.who.length || e.who.includes(c.id)),
        aria: "Intentions de vote pour " + c.name + ", " + pts_.length + " sondages",
        snap: pts_.map(p => p.t),
        tooltip: t => {
          const ps = pts_.filter(p => p.t === t);
          return {
            title: fmtD(new Date(t).toISOString().slice(0, 10)), rows: ps.map(p => ({ color: col, value: pct(p.v), label: p.poll.firm + (p.poll.sample ? " · " + nf0.format(p.poll.sample) : "") })),
            foot: ps.some(p => p.hi > p.lo) ? ps.filter(p => p.hi > p.lo).map(p => p.poll.firm + " : de " + nf1.format(p.lo) + " à " + pct(p.hi) + " selon les " + p.n + " hypothèses").join(" · ") : null
          };
        }
      });
    }
    redraws.push(draw);
    const mine = POLLS.filter(p => pv(p, c.id)).reverse();
    main.append(h("section", { "aria-labelledby": "cp-t" },
      h("div", { class: "sec-head" }, h("div", null, h("h2", { id: "cp-t" }, "Intentions de vote au premier tour"),
        h("p", null, "Un point par sondage. Le trait vertical montre l'écart entre les hypothèses de candidatures testées par l'institut.")),
        h("div", { class: "filters" }, seg, h("label", { class: "sel", for: "firm-filter-c" }, "Institut", sel))),
      h("div", { class: "panel" }, host, pollTable(mine, [c], "Voir les " + mine.length + " sondages (tableau et sources)"))));

    // audience + members
    const F = (SOCIAL.followers || {})[c.id] || {};
    const nets = h("div", { class: "nets" });
    let anyNet = false;
    for (const n of NETWORKS) {
      const acc = F[n.id];
      if (!acc) continue;
      if (!acc.points || !acc.points.length) {
        if (acc.note) nets.append(h("div", { class: "net", css: { "--c": "var(--rule)" } }, h("span", null, n.label), h("b", { class: "muted" }, "–"), h("span", null, acc.note)));
        continue;
      }
      anyNet = true;
      const P = acc.points, last = P[P.length - 1], first = P[0];
      const sp = h("div", { class: "spark" });
      nets.append(h("div", { class: "net", css: { "--c": col } },
        h("span", null, n.label + (acc.handle ? " · " + acc.handle : "")),
        h("b", { class: "num" }, h("a", { href: last.source, target: "_blank", rel: "noopener", style: { textDecoration: "none" } }, (last.approx ? "≈ " : "") + compact(last.value))),
        h("span", null, "au " + fmtD(last.date) + (P.length > 1 ? " · " + (last.value >= first.value ? "+" : "−") + compact(Math.abs(last.value - first.value)) + " depuis le " + fmtD(first.date, { year: undefined }) : "")),
        acc.note ? h("span", null, acc.note) : null,
        sp));
      if (P.length > 1) redraws.push(() => sparkline(sp, P.map(p => ({ t: T(p.date), v: p.value })), col, T(P[0].date), T(last.date)));
    }
    const M = (SOCIAL.members || {})[c.id];
    const memHost = h("div");
    const memBox = h("div", { class: "panel" }, h("h3", null, "Adhérents" + (M ? " · " + M.party : "")));
    if (M && M.points && M.points.length) {
      const P = M.points, last = P[P.length - 1];
      memBox.append(h("p", { style: { margin: "6px 0 8px" } }, h("b", { class: "num", style: { fontFamily: "var(--font-display)", fontSize: "1.9rem", fontWeight: 800, fontStretch: "85%" } }, (last.approx ? "≈ " : "") + nf0.format(last.value)),
        h("span", { class: "muted", style: { fontSize: ".85rem" } }, "  au " + fmtD(last.date) + (M.kind ? " · " + M.kind : ""))));
      if (P.length > 1) {
        memBox.append(memHost);
        redraws.push(() => lineChart(memHost, {
          series: [{ key: "m", label: "Adhérents", color: col, points: P.map(p => ({ t: T(p.date), v: p.value, hollow: p.approx })) }],
          height: 200, x0: T(P[0].date) - 10 * DAY, x1: T(last.date) + 10 * DAY, yFmt: v => compact(v), area: true, dot: 4,
          aria: "Évolution du nombre d'adhérents", snap: P.map(p => T(p.date)),
          tooltip: t => { const p = P.find(q => T(q.date) === t); return { title: (p.approx ? "≈ " : "") + nf0.format(p.value) + " adhérents", sub: fmtD(p.date), foot: p.detail }; }
        }));
      }
      if (M.note) memBox.append(h("p", { class: "note" }, M.note));
      memBox.append(h("details", { class: "more" }, h("summary", null, "Sources"), h("ul", { style: { margin: 0, paddingLeft: "1.1em", fontSize: ".85rem" } },
        P.map(p => h("li", null, fmtD(p.date) + " : " + nf0.format(p.value) + " · ", h("a", { href: p.source, target: "_blank", rel: "noopener" }, p.detail || "source"))))));
    } else memBox.append(h("p", { class: "empty-state" }, "Aucun chiffre d'adhérents publié et sourcé pour l'instant."));
    main.append(h("section", { class: "duo" },
      h("div", { class: "panel" }, h("h3", null, "Audience sur les réseaux sociaux"),
        anyNet ? nets : h("p", { class: "empty-state" }, "Relevés en cours de collecte."),
        h("p", { class: "note" }, "Cliquez sur un chiffre pour voir sa source. ≈ : valeur arrondie ou date approximative.")),
      memBox));

    // timeline
    const evs = SITE.events.filter(e => e.who && e.who.includes(c.id));
    if (evs.length) main.append(h("section", { "aria-labelledby": "tl-t" }, h("div", { class: "sec-head" }, h("h2", { id: "tl-t" }, "Repères")),
      h("ul", { class: "timeline" }, evs.map(e => h("li", null, h("time", { datetime: e.date }, fmtD(e.date)), h("span", null, e.label))))));
  }

  route();
  // fonts change text metrics: redraw once everything has loaded
  window.addEventListener("load", () => redraws.forEach(f => f()));
})();
