/* Road to 2027: rendering. Data lives in data/*.js; nothing here needs weekly edits. */
(function () {
  "use strict";
  const SITE = window.SITE, POLLS = (window.POLLS && window.POLLS.polls) || [];
  const SOCIAL = window.SOCIAL || { followers: {}, members: {} };
  const ENG = window.ENGAGEMENT || { updated: null, method: {}, candidates: {} };
  // Last update = the most recent date among the data files (polls and followers are
  // refreshed by the workflow; data/site.js only by hand). ISO strings compare as dates.
  const LAST_UPDATE = [SITE.updated, window.POLLS && window.POLLS.fetched, SOCIAL.updated, window.MODEL && window.MODEL.asof]
    .filter(Boolean).sort().at(-1);
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
  // Poll scores only. "<0.5%" in a poll is stored as 0.25 (parse_history.BELOW_HALF_VALUE): show it as published.
  const pct = v => v > 0 && v < 0.5 ? "< 0,5 %" : nf1.format(v) + " %";
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
  /* ---------- which line-up of a poll do we read? ----------
     Polls often test several line-ups ("hypothèses"). Every candidate of a poll is read from the same
     one, the reference line-up: the one closest to the STANDARD FIELD (names tested in at least half of
     the polls of the previous 60 days). Score = tracked candidates included - 1.5 x unusual names added
     (Lagarde, Ruffin... when few pollsters test them), so an 18-candidate line-up with four unusual
     names loses to the usual 11-candidate one. Ties: fewer names, then the order of the source. */
  const STD_DAYS = 60, STD_SHARE = 0.5, EXTRA_PENALTY = 1.5;
  const namesIn = (poll, i) => Object.keys(poll.scenarios[i]).concat(Object.keys((poll.others || [])[i] || {}));
  const stdCache = {};
  function stdField(date) {
    if (!stdCache[date]) {
      const t = T(date), win = POLLS.filter(p => T(p.date) <= t && T(p.date) > t - STD_DAYS * DAY), cnt = {};
      for (const p of win) for (const n of new Set(p.scenarios.flatMap((_, i) => namesIn(p, i)))) cnt[n] = (cnt[n] || 0) + 1;
      stdCache[date] = new Set(Object.keys(cnt).filter(n => cnt[n] >= STD_SHARE * win.length));
    }
    return stdCache[date];
  }
  function lineup(poll) {
    if (!poll._lu) {
      const field = stdField(poll.date);
      let best = null;
      poll.scenarios.forEach((sc, i) => {
        const names = namesIn(poll, i), tracked = CANDS.filter(c => c.id in sc).map(c => c.id);
        const extras = names.filter(n => !field.has(n)).sort((x, y) => (((poll.others || [])[i] || {})[y] || 0) - (((poll.others || [])[i] || {})[x] || 0));
        const score = tracked.length - EXTRA_PENALTY * extras.length;
        if (!best || score > best.score || (score === best.score && names.length < best.n)) best = { i, score, n: names.length, tracked, extras };
      });
      poll._lu = best;
    }
    return poll._lu;
  }
  const refScenario = poll => poll.scenarios[lineup(poll).i];
  // Two polls are comparable when their reference line-ups pit the same tracked candidates, with the
  // same unusual additions: only then does a change between them mean something.
  const lineupKey = poll => { const l = lineup(poll); return l.tracked.slice().sort().join(",") + "|" + l.extras.slice().sort().join(","); };
  const comparable = (a, b) => lineupKey(a) === lineupKey(b);
  function lineupText(poll) {
    const l = lineup(poll), ex = l.extras.map(n => n.split(" ").slice(-1)[0]);
    return l.n + " candidats testés" + (ex.length ? ", dont " + ex.join(", ") + " (hors champ habituel)" : "") +
      (poll.scenarios.length > 1 ? " · " + poll.scenarios.length + " hypothèses dans ce sondage" : "");
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
  const median = a => { const b = a.slice().sort((x, y) => x - y), m = b.length >> 1; return b.length % 2 ? b[m] : (b[m - 1] + b[m]) / 2; };
  const LATEST_POLL = POLLS.reduce((m, p) => p.date > m ? p.date : m, "");
  function summary(id) {
    const s = series(id, POLLS);
    if (!s.length) return null;
    const last = s[s.length - 1];
    const sameFirm = [...s].reverse().filter(x => x !== last && x.poll.firm === last.poll.firm);
    const prevSame = sameFirm.find(x => comparable(x.poll, last.poll)) || null;        // like-for-like only
    const prevOther = !prevSame && sameFirm.length ? sameFirm[0] : null;                  // exists, but not comparable
    const recent = s.filter(x => x.t > T(LATEST_POLL) - 30 * DAY);                        // one value per poll
    return { last, prevSame, prevOther, all: s, n30: recent.length,
      med: recent.length ? median(recent.map(x => x.v)) : null,
      lo30: recent.length ? Math.min(...recent.map(x => x.v)) : null, hi30: recent.length ? Math.max(...recent.map(x => x.v)) : null };
  }
  // The last poll's change, only against a comparable poll (same institute, same candidates tested).
  function lastChange(s, asText) {
    let txt = null;
    if (s.prevSame) {
      const d = s.last.v - s.prevSame.v;
      txt = (d > 0 ? "▲ " : d < 0 ? "▼ " : "") + pts(d) + " par rapport à son sondage comparable du " + fmtD(s.prevSame.poll.date, { year: undefined });
    } else if (s.prevOther) {
      txt = "Pas de comparaison avec son sondage du " + fmtD(s.prevOther.poll.date, { year: undefined }) + " : candidats testés différents";
    }
    if (asText) return txt;
    return txt ? h("span", { class: "meta", style: { display: "block" } }, txt) : null;
  }
  const FIRMS = [...new Set(POLLS.map(p => p.firm))].sort((a, b) => a.localeCompare(b, "fr"));
  // One page per poll, at a shareable address: #sondage-<institut>-<date>
  const slugify = x => x.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  const POLL_BY_SLUG = {};
  for (const p of POLLS) {
    let k = "sondage-" + slugify(p.firm) + "-" + p.date, n = 2;
    while (POLL_BY_SLUG[k]) k = "sondage-" + slugify(p.firm) + "-" + p.date + "-" + n++;
    POLL_BY_SLUG[k] = p; p._slug = k;
  }
  const pollSlug = p => p._slug;

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
      const flip = x + w > W - 4;              // near the right edge: label to the left of its line
      const start = flip ? x - w : x;
      let r = 0; while (rows[r] && rows[r] > start - 2) r++;
      rows[r] = flip ? x : x + w; return { e, x, r, flip };
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
    for (const l of evL) if (l.r < 3) ge.append(h("text", { x: l.flip ? l.x - 3 : l.x + 3, y: 10 + l.r * 14 + 2, "text-anchor": l.flip ? "end" : null }, l.e.short));
    // opt.marker {t, label}: a chosen moment (past elections: "J-145")
    if (opt.marker && opt.marker.t >= opt.x0 && opt.marker.t <= opt.x1) {
      const xm = X(opt.marker.t), flip = xm > W - m.r - 70;
      ge.append(h("line", { x1: xm, x2: xm, y1: m.t - 2, y2: H - m.b, stroke: "var(--ink)", "stroke-width": 1.5 }));
      ge.append(h("text", { x: flip ? xm - 5 : xm + 5, y: m.t + 12, class: "lab", "text-anchor": flip ? "end" : null }, opt.marker.label));
    }
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
      // A point with result:true is the vote itself: a diamond, joined to the last poll by a dashed line.
      const polls = P.filter(p => !p.result), res = P.find(p => p.result);
      if (polls.length > 1) sg.append(h("path", { d: "M" + polls.map(p => X(p.t) + "," + Y(p.v)).join("L"), fill: "none", stroke: s.color, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }));
      if (res && polls.length) { const l = polls[polls.length - 1]; sg.append(h("line", { x1: X(l.t), y1: Y(l.v), x2: X(res.t), y2: Y(res.v), stroke: s.color, "stroke-width": 1.5, "stroke-dasharray": "3 3" })); }
      for (const p of polls) sg.append(h("circle", { cx: X(p.t), cy: Y(p.v), r: opt.dot || 3.5, fill: p.hollow ? "var(--surface)" : s.color, stroke: p.hollow ? s.color : "var(--surface)", "stroke-width": p.hollow ? 2 : 1.5 }));
      if (res) sg.append(h("rect", { x: X(res.t) - 5.5, y: Y(res.v) - 5.5, width: 11, height: 11, transform: `rotate(45 ${X(res.t)} ${Y(res.v)})`, fill: s.color, stroke: "var(--surface)", "stroke-width": 1.5 }));
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
      // Click opens the measurement (opt.onPick): directly with a mouse; on touch, the first tap
      // shows the tooltip and a second tap on the same point opens it.
      let tapped = -1;
      svg.addEventListener("pointerdown", ev => {
        const i = near(ev);
        if (opt.onPick && (ev.pointerType === "mouse" || i === tapped)) { opt.onPick(snap[i]); return; }
        tapped = i; show(i);
      });
      if (opt.onPick) svg.style.cursor = "pointer";
      svg.addEventListener("pointerleave", hide);
      svg.addEventListener("blur", hide);
      svg.addEventListener("focus", () => show(idx < 0 ? snap.length - 1 : idx));
      svg.addEventListener("keydown", ev => {
        if (ev.key === "ArrowLeft") { show(Math.max(0, idx - 1)); ev.preventDefault(); }
        else if (ev.key === "ArrowRight") { show(Math.min(snap.length - 1, idx + 1)); ev.preventDefault(); }
        else if (ev.key === "Enter" && opt.onPick && idx >= 0) { opt.onPick(snap[idx]); ev.preventDefault(); }
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
  const state = { range: "campagne", firm: "all", focus: null, hrange: "12m" };
  try { const s = JSON.parse(localStorage.getItem("road-to-2027-filters") || "{}"); if (s.range) state.range = s.range; if (s.firm && FIRMS.includes(s.firm)) state.firm = s.firm; if (["6m", "12m", "all"].includes(s.hrange)) state.hrange = s.hrange; } catch (e) { /* storage unavailable */ }
  const save = () => { try { localStorage.setItem("road-to-2027-filters", JSON.stringify({ range: state.range, firm: state.firm, hrange: state.hrange })); } catch (e) { /* ignore */ } };
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
    else if (POLL_BY_SLUG[id]) renderPoll(POLL_BY_SLUG[id]);
    else if (id === "elections" && HIST.length) renderHistoryIndex();
    else if (HIST_BY_ID[id]) renderElection(HIST_BY_ID[id]);
    else { document.title = "Road to 2027"; renderHome(); }
    if (id) main.focus({ preventScroll: true });
    window.scrollTo(0, 0);
    requestAnimationFrame(() => redraws.forEach(f => f()));
  }
  let rt;
  new ResizeObserver(() => { clearTimeout(rt); rt = setTimeout(() => redraws.forEach(f => f()), 120); }).observe(main);
  window.addEventListener("hashchange", route);
  document.getElementById("upd").textContent = "Mise à jour du " + fmtD(LAST_UPDATE);

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
    const headline = s => s.med != null ? s.med : s.last.v;
    sums.sort((a, b) => headline(b.s) - headline(a.s));
    const cards = h("div", { class: "cards" });
    const sx0 = T("2026-07-01"), sx1 = today();
    sums.forEach(({ c, s }, i) => {
      const l = s.last, sp = h("div", { class: "spark" });
      cards.append(h("a", { class: "card", href: "#" + c.id, css: { "--c": color(c) } },
        h("span", { class: "rank num", "aria-hidden": "true" }, i + 1),
        h("span", { class: "who" }, h("span", { class: "key" }), h("span", { class: "name" }, c.name)),
        h("span", { class: "party" }, c.party),
        h("span", null,
          h("span", { class: "val" }, h("b", { class: "num" }, pct(headline(s))),
            h("span", { class: "delta" }, s.med != null ? "médiane 30 jours" : "dernier sondage")),
          h("span", { class: "meta", style: { display: "block" } }, s.n30 > 1 ? s.n30 + " sondages sur 30 jours, de " + nf1.format(s.lo30) + " à " + pct(s.hi30)
            : s.n30 === 1 ? "1 seul sondage sur 30 jours" : "aucun sondage sur 30 jours"),
          h("span", { class: "meta", style: { display: "block" } }, "Dernier : " + pct(l.v) + " · " + l.poll.firm + ", " + fmtRange(l.poll.start, l.poll.date)),
          lastChange(s)),
        sp,
        h("span", { class: "go" }, "Voir la fiche →")));
      redraws.push(() => sparkline(sp, s.all.filter(x => x.t >= sx0), color(c), sx0, sx1));
    });
    main.append(h("section", { "aria-labelledby": "std-t" },
      h("div", { class: "sec-head" }, h("div", null,
        h("h2", { id: "std-t" }, "Le classement : médiane des sondages des 30 derniers jours"),
        h("p", null, "Chaque sondage compte pour une valeur, lue dans son hypothèse la plus proche du champ habituel des candidats. La médiane résiste mieux qu'une moyenne à un sondage atypique. La flèche du dernier sondage ne compare qu'au sondage précédent du même institut avec les mêmes candidats testés."))),
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
      const x0 = rangeFrom(), x1 = Math.max(today(), T(LAST_UPDATE)) + 2 * DAY;
      const polls = POLLS.filter(p => T(p.date) >= x0 && (state.firm === "all" || p.firm === state.firm));
      const S = CANDS.map(c => ({ key: c.id, label: c.short, color: color(c), dim: state.focus && state.focus !== c.id, points: series(c.id, polls) }));
      note.textContent = polls.length + " sondage" + (polls.length > 1 ? "s" : "") + " affiché" + (polls.length > 1 ? "s" : "") +
        ". Chaque point est un sondage ; la ligne relie les sondages successifs sans les moyenner. Les écarts d'un point à l'autre reflètent souvent les différences entre instituts.";
      lineChart(chartHost, {
        series: S, height: 380, x0, x1, yFmt: (v, lab) => lab ? nf1.format(v) : v + " %", labels: true, events: SITE.events, yMinMax: 10,
        aria: "Intentions de vote au premier tour, un point par sondage, " + polls.length + " sondages",
        snap: polls.map(p => T(p.date)),
        onPick: t => { const p = polls.find(q => T(q.date) === t); if (p) location.hash = pollSlug(p); },
        tooltip: t => {
          const ps = polls.filter(p => T(p.date) === t);
          const p = ps[0];
          const rows = CANDS.map(c => ({ c, x: pv(p, c.id) })).filter(r => r.x).sort((a, b) => b.x.v - a.x.v)
            .map(r => ({ color: color(r.c), value: pct(r.x.v), label: r.c.short + (r.x.n > 1 && r.x.hi > r.x.lo ? " (" + nf1.format(r.x.lo) + "–" + nf1.format(r.x.hi) + " selon hypothèse)" : "") }));
          const ev = SITE.events.find(e => Math.abs(T(e.date) - t) <= 2 * DAY);
          return { title: p.firm + (ps.length > 1 ? " (+ " + ps.slice(1).map(q => q.firm).join(", ") + ")" : ""), sub: "Terrain " + fmtRange(p.start, p.date) + (p.sample ? " · " + nf0.format(p.sample) + " personnes" : ""), rows, foot: (ev ? "Repère : " + ev.label + " · " : "") + "Hypothèse lue : " + lineupText(p) + ". Cliquez pour voir tout le sondage." };
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
    main.append(engagementSection());
    main.append(membersSection());
    main.append(methodSection());
  }

  function cellWho(c) { return h("span", { class: "who" }, h("span", { class: "key", css: { "--c": color(c) } }), c.name); }

  function pollTable(polls, cands, summaryText) {
    const tb = h("tbody");
    for (const p of polls) {
      tb.append(h("tr", null,
        h("td", null, h("a", { href: p.url || POLLS_INDEX(), target: "_blank", rel: "noopener" }, p.firm), h("small", null, fmtRange(p.start, p.date) + (p.sample ? " · " + nf0.format(p.sample) : "")), h("small", null, lineupText(p)), h("small", null, h("a", { href: "#" + pollSlug(p) }, "Voir tout le sondage →"))),
        cands.map(c => { const x = pv(p, c.id); return x ? h("td", { title: x.n > 1 ? x.n + " hypothèses : " + nf1.format(x.lo) + " à " + nf1.format(x.hi) + " %" : null }, nf1.format(x.v) + (x.hi > x.lo ? "*" : "")) : h("td", { class: "empty" }, "–"); })));
    }
    return h("details", { class: "more" }, h("summary", null, summaryText),
      h("div", { class: "tbl" }, h("table", null,
        h("thead", null, h("tr", null, h("th", null, "Institut, terrain, effectif"), cands.map(c => h("th", null, c.short)))), tb)),
      h("p", { class: "note" }, "En %. * : le score varie selon les hypothèses testées ; valeur de l'hypothèse la plus complète, fourchette au survol. – : absent de cette hypothèse."));
  }
  const POLLS_INDEX = () => window.POLLS.index;

  function latestPerFirm() {
    const cutoff = T(LAST_UPDATE) - 45 * DAY;
    const latest = [];
    for (const f of FIRMS) {
      const p = [...POLLS].reverse().find(q => q.firm === f);
      if (p && T(p.date) >= cutoff) latest.push(p);
    }
    latest.sort((a, b) => T(b.date) - T(a.date));
    const head = h("tr", null, h("th", null, "Candidat"), latest.map(p => h("th", null, h("a", { href: p.url || POLLS_INDEX(), target: "_blank", rel: "noopener" }, p.firm), h("br"), h("a", { href: "#" + pollSlug(p), title: "Voir tout le sondage" }, fmtD(p.date, { year: undefined })))));
    const tb = h("tbody");
    const hv = id => { const x = summary(id); return x ? (x.med != null ? x.med : x.last.v) : 0; };
    const order = [...CANDS].sort((a, b) => hv(b.id) - hv(a.id));
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

  /* ---------- Instagram engagement (data/engagement.js, scripts/update_engagement.py) ---------- */
  const pctN = (v, d) => new Intl.NumberFormat("fr-FR", { maximumFractionDigits: d }).format(v) + " %";
  const nfw = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 });
  function engMethodNote() {
    const m = ENG.method || {}, w = m.window_days || [14, 2];
    return "Posts Instagram publiés entre " + w[0] + " et " + w[1] + " jours avant le relevé, pour laisser aux interactions le temps de s'accumuler (au plus " +
      (m.max_posts || 50) + " posts analysés). Interactions d'un post = likes + " + (m.comment_weight || 3) + " × commentaires ; on retient la médiane, qu'un post viral ne déforme pas. " +
      "Taux d'engagement = interactions médianes ÷ abonnés ; taux de commentaires = commentaires médians ÷ abonnés, seul indicateur disponible quand un compte masque ses likes.";
  }
  function engWindow(last) {   // "12 posts du 28 oct. au 9 nov., soit 6,5 par semaine"
    if (!last || !last.window) return "";
    const n = last.posted_in_window != null ? last.posted_in_window : last.n_posts;
    return n + " post" + (n > 1 ? "s" : "") + " du " + fmtD(last.window[0], { year: undefined }) + " au " + fmtD(last.window[1], { year: undefined }) +
      ", soit " + nfw.format(last.posts_per_week) + " par semaine" + (last.n_posts < n ? " (" + last.n_posts + " analysés)" : "");
  }
  function engStatus(acc) {
    if (!acc) return "pas encore relevé";
    if (acc.status === "unavailable") return "compte non lisible (compte personnel ?)";
    if (acc.status === "not_enough_posts") return "moins de " + ((ENG.method || {}).min_posts || 3) + " posts sur la période";
    return null;
  }
  function engagementSection() {
    const head = h("div", { class: "sec-head" }, h("div", null, h("h2", { id: "eng-t" }, "Engagement sur Instagram"),
      h("p", null, "Ce que suscite un post typique, au-delà du nombre d'abonnés. Le volume d'interactions favorise les gros comptes, le taux d'engagement les communautés actives. Le rythme de publication dit sur quoi porte la comparaison.")));
    if (!ENG.updated) return h("section", { "aria-labelledby": "eng-t" }, head,
      h("p", { class: "empty-state" }, "Mesure en cours de mise en place : les premiers relevés arrivent dès que l'accès à l'API Instagram est configuré."));
    const rank = r => r.acc && r.acc.status === "ok" ? 2 : r.acc && r.acc.status === "likes_hidden" ? 1 : 0;
    const rows = CANDS.map(c => ({ c, acc: ENG.candidates[c.id], last: lastPoint((ENG.candidates[c.id] || {}).history) }))
      .sort((a, b) => rank(b) - rank(a) || ((b.last && (b.last.median_interactions || b.last.median_comments)) || 0) - ((a.last && (a.last.median_interactions || a.last.median_comments)) || 0));
    const ref = rows.map(r => r.last).find(l => l && l.window);
    const tb = h("tbody");
    for (const { c, acc, last } of rows) {
      const who = h("td", null, h("a", { href: "#" + c.id, style: { textDecoration: "none" } }, cellWho(c)));
      const posted = last && last.window ? h("td", null, h("b", null, last.posted_in_window), h("small", null, nfw.format(last.posts_per_week) + " / sem.")) : h("td", { class: "empty" }, "–");
      const st = engStatus(acc);
      if (st) { tb.append(h("tr", null, who, posted, h("td", { class: "empty", colspan: 4, style: { textAlign: "left" } }, st))); continue; }
      const hidden = acc.status === "likes_hidden";
      tb.append(h("tr", null, who, posted,
        hidden ? h("td", { class: "empty", colspan: 2, style: { textAlign: "center" } }, "likes masqués par le compte")
          : [h("td", null, h("b", null, compact(last.median_interactions)), h("small", null, compact(last.median_likes) + " likes")),
             h("td", null, last.rate != null ? pctN(last.rate, 2) : "–")],
        h("td", null, compact(last.median_comments)),
        h("td", null, last.comment_rate != null ? pctN(last.comment_rate, 3) : "–")));
    }
    const table = h("div", { class: "tbl" }, h("table", null, h("thead", null, h("tr", null, h("th", null, "Candidat"), h("th", null, "Posts publiés"),
      h("th", null, "Interactions par post"), h("th", null, "Taux d'engagement"), h("th", null, "Commentaires par post"), h("th", null, "Taux de commentaires"))), tb));
    const charts = h("div", { class: "eng-charts" },
      engBars(rows, "rate", "Taux d'engagement", "interactions médianes par post ÷ abonnés", 2, "likes masqués"),
      engBars(rows, "comment_rate", "Taux de commentaires", "commentaires médians par post ÷ abonnés · disponible pour tous", 3, null));
    // Two tabs: the charts (default) and the full table. Plain buttons + hidden panels.
    const tabs = [["Graphiques", charts], ["Tableau complet", table]];
    const bar = h("div", { class: "eng-tabs", role: "tablist", "aria-label": "Affichage de l'engagement" });
    tabs.forEach(([label, panel], i) => {
      const id = "eng-tab-" + i;
      panel.setAttribute("role", "tabpanel"); panel.setAttribute("aria-labelledby", id); panel.hidden = i > 0;
      bar.append(h("button", { type: "button", id, role: "tab", "aria-selected": String(i === 0), onclick: e => {
        [...bar.children].forEach((b, j) => { b.setAttribute("aria-selected", String(j === i)); tabs[j][1].hidden = j !== i; });
      } }, label));
    });
    return h("section", { "aria-labelledby": "eng-t" }, head,
      ref ? h("p", { class: "note", style: { margin: "0 0 10px" } }, "Période comparée : posts publiés du " + fmtD(ref.window[0]) + " au " + fmtD(ref.window[1]) + " (relevé du " + fmtD(ref.date) + ").") : null,
      bar, charts, table,
      h("p", { class: "note" }, engMethodNote() + " Le détail et les liens vers chaque post sont sur la fiche du candidat."));
  }
  /* One horizontal bar chart: one candidate per row, sorted, own scale from 0, value always printed.
     The posting rhythm stays under each name so readers know what is being compared. */
  function engBars(rows, key, title, sub, digits, missingLabel) {
    const items = rows.filter(r => r.last && (r.last[key] != null || (missingLabel && r.acc && r.acc.status === "likes_hidden")));
    const withVal = items.filter(r => r.last[key] != null).sort((a, b) => b.last[key] - a.last[key]);
    const without = items.filter(r => r.last[key] == null);
    const max = Math.max(...withVal.map(r => r.last[key]), 1e-9);
    const top = withVal[0];
    const fig = h("figure", { class: "eng-fig" },
      h("figcaption", null, h("b", null, title), h("span", null, sub),
        top ? h("span", { class: "eng-find" }, "Le plus élevé : " + top.c.name + " (" + pctN(top.last[key], digits) + ")") : null));
    const list = h("div", { class: "eng-bars" });
    for (const r of withVal) {
      const v = r.last[key];
      list.append(h("div", { class: "eng-row", css: { "--c": color(r.c), "--w": (100 * v / max).toFixed(1) + "%" } },
        h("span", { class: "eng-who" }, h("a", { href: "#" + r.c.id }, r.c.short || r.c.name), h("small", null, nfw.format(r.last.posts_per_week) + " posts / sem.")),
        h("span", { class: "eng-track" }, h("i")),
        h("span", { class: "eng-val num" }, pctN(v, digits))));
    }
    for (const r of without) list.append(h("div", { class: "eng-row is-missing" },
      h("span", { class: "eng-who" }, h("a", { href: "#" + r.c.id }, r.c.short || r.c.name), h("small", null, nfw.format(r.last.posts_per_week) + " posts / sem.")),
      h("span", { class: "eng-track eng-none" }, missingLabel), h("span", { class: "eng-val" }, "–")));
    fig.append(list);
    return fig;
  }
  function engagementPanel(c, col) {
    const acc = ENG.candidates[c.id], last = acc && lastPoint(acc.history);
    const box = h("div", { class: "panel" }, h("h3", null, "Engagement sur Instagram" + (acc ? " · " + acc.handle : "")));
    if (!ENG.updated) { box.append(h("p", { class: "empty-state" }, "Mesure en cours de mise en place.")); return box; }
    if (last && last.window) box.append(h("p", { style: { margin: "4px 0 10px", fontSize: ".92rem", color: "var(--ink2)" } }, h("b", null, "Publications : "), engWindow(last) + "."));
    const st = engStatus(acc);
    if (st) { box.append(h("p", { class: "empty-state" }, st[0].toUpperCase() + st.slice(1) + ".")); }
    else {
      const hidden = acc.status === "likes_hidden";
      box.append(h("div", { class: "nets" },
        hidden ? h("div", { class: "net", css: { "--c": "var(--rule)" } }, h("span", null, "Interactions par post"), h("b", { class: "muted" }, "–"), h("span", null, "Likes masqués par le compte"))
          : h("div", { class: "net", css: { "--c": col } }, h("span", null, "Interactions par post (médiane)"), h("b", { class: "num" }, compact(last.median_interactions)),
              h("span", null, compact(last.median_likes) + " likes · " + compact(last.median_comments) + " commentaires")),
        hidden ? null : h("div", { class: "net", css: { "--c": col } }, h("span", null, "Taux d'engagement"), h("b", { class: "num" }, last.rate != null ? pctN(last.rate, 2) : "–"),
          h("span", null, "interactions ÷ abonnés")),
        h("div", { class: "net", css: { "--c": col } }, h("span", null, "Commentaires par post (médiane)"), h("b", { class: "num" }, compact(last.median_comments)),
          h("span", null, "taux : " + (last.comment_rate != null ? pctN(last.comment_rate, 3) : "–")))));
      const H = acc.history.filter(x => x.rate != null);
      if (H.length > 1) { const sp = h("div", { class: "spark", style: { height: "40px", marginTop: "8px" } }); box.append(sp);
        redraws.push(() => sparkline(sp, H.map(x => ({ t: T(x.date), v: x.rate })), col, T(H[0].date), T(lastPoint(H).date))); }
    }
    if (last && last.posts && last.posts.length) box.append(h("details", { class: "more" }, h("summary", null, "Posts analysés (" + last.posts.length + ")"),
      h("ul", { style: { margin: 0, paddingLeft: "1.1em", fontSize: ".85rem" } }, last.posts.map(p => h("li", null, fmtD(p.date) + " · ",
        h("a", { href: p.url, target: "_blank", rel: "noopener" }, p.likes != null ? compact(p.likes) + " likes, " + compact(p.comments) + " commentaires" : compact(p.comments) + " commentaires"))))));
    box.append(h("p", { class: "note" }, engMethodNote()));
    return box;
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
          h("p", null, "Quand un sondage teste plusieurs hypothèses, on lit tous les candidats dans la même : celle qui ressemble le plus au champ habituel (les noms testés dans au moins la moitié des sondages des 60 derniers jours), pénalisée pour chaque nom inhabituel ajouté. Le chiffre mis en avant est la médiane des sondages des 30 derniers jours ; les flèches ne comparent un sondage qu'au précédent du même institut avec les mêmes candidats testés. Aucun redressement.")),
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
    main.append(h("section", { class: "fiche-head", css: { "--c": col } },
      h("div", null,
        h("p", { class: "eyebrow" }, "Présidentielle 2027 · J-" + daysLeft()),
        h("h1", null, h("span", { class: "key" }), c.name),
        h("p", { class: "party" }, c.party)),
      s ? h("div", { class: "bigfig" },
        h("b", { class: "num" }, pct(s.med != null ? s.med : s.last.v)),
        h("p", null, (s.med != null ? "Médiane des " + s.n30 + " sondage" + (s.n30 > 1 ? "s" : "") + " des 30 derniers jours" +
            (s.n30 > 1 ? ", de " + nf1.format(s.lo30) + " à " + pct(s.hi30) : "") + "." : "Aucun sondage sur 30 jours : dernier sondage connu.")),
        h("p", null, "Dernier sondage : " + pct(s.last.v) + ", " + s.last.poll.firm + ", " + fmtRange(s.last.poll.start, s.last.poll.date) +
          " (" + lineupText(s.last.poll) + ")." + (lastChange(s, true) ? " " + lastChange(s, true) + "." : "")))
        : h("div", { class: "bigfig" }, h("p", null, "Pas encore testé dans les sondages."))));

    // polls chart for this candidate
    const host = h("div");
    const seg = h("div", { class: "seg", role: "group", "aria-label": "Période" });
    RANGES.forEach(r => seg.append(h("button", { type: "button", "aria-pressed": String(state.range === r.id), onclick: () => { state.range = r.id; save();[...seg.children].forEach((b, i) => b.setAttribute("aria-pressed", String(RANGES[i].id === r.id))); draw(); } }, r.label)));
    const sel = h("select", { id: "firm-filter-c", onchange: e => { state.firm = e.target.value; save(); draw(); } },
      h("option", { value: "all" }, "Tous les instituts"), FIRMS.map(f => h("option", { value: f, selected: state.firm === f }, f)));
    function draw() {
      const x0 = rangeFrom(), x1 = Math.max(today(), T(LAST_UPDATE)) + 2 * DAY;
      const polls = POLLS.filter(p => T(p.date) >= x0 && (state.firm === "all" || p.firm === state.firm));
      const pts_ = series(c.id, polls);
      lineChart(host, {
        series: [{ key: c.id, label: c.short, color: col, points: pts_ }], height: 320, x0, x1, whiskers: true, area: false, dot: 4,
        yFmt: v => v + " %", yMinMax: 5, events: SITE.events.filter(e => !e.who || !e.who.length || e.who.includes(c.id)),
        aria: "Intentions de vote pour " + c.name + ", " + pts_.length + " sondages",
        snap: pts_.map(p => p.t),
        onPick: t => { const p = pts_.find(q => q.t === t); if (p) location.hash = pollSlug(p.poll); },
        tooltip: t => {
          const ps = pts_.filter(p => p.t === t);
          return {
            title: fmtD(new Date(t).toISOString().slice(0, 10)), rows: ps.map(p => ({ color: col, value: pct(p.v), label: p.poll.firm + (p.poll.sample ? " · " + nf0.format(p.poll.sample) : "") })),
            foot: "Cliquez pour voir tout le sondage. " + ps.map(p => p.poll.firm + " : " + lineupText(p.poll) + (p.hi > p.lo ? " ; de " + nf1.format(p.lo) + " à " + pct(p.hi) + " selon l'hypothèse" : "")).join(" · ")
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
    main.append(h("section", null, engagementPanel(c, col)));

    // timeline
    const evs = SITE.events.filter(e => e.who && e.who.includes(c.id));
    if (evs.length) main.append(h("section", { "aria-labelledby": "tl-t" }, h("div", { class: "sec-head" }, h("h2", { id: "tl-t" }, "Repères")),
      h("ul", { class: "timeline" }, evs.map(e => h("li", null, h("time", { datetime: e.date }, fmtD(e.date)), h("span", null, e.label))))));
  }

  /* ---------- one poll, every line-up and every candidate (#sondage-...) ---------- */
  function renderPoll(p) {
    const lu = lineup(p), C = Object.fromEntries(CANDS.map(c => [c.id, c]));
    document.title = p.firm + " · " + fmtD(p.date) + " · Road to 2027";
    const all = p.scenarios.flatMap((sc, i) => Object.values(sc).concat(Object.values((p.others || [])[i] || {})));
    const max = Math.max(...all, 1), many = p.scenarios.length > 1;
    main.append(h("a", { class: "back", href: "#", onclick: e => { if (history.length > 1) { e.preventDefault(); history.back(); } } }, "← Retour"),
      h("section", { class: "sb-head" },
        h("p", { class: "eyebrow" }, "Sondage · présidentielle 2027 · premier tour"),
        h("h1", null, p.firm),
        h("p", { class: "lead" }, "Terrain " + fmtRange(p.start, p.date) + (p.sample ? " · " + nf0.format(p.sample) + " personnes interrogées" : "") +
          " · " + p.scenarios.length + " hypothèse" + (many ? "s" : "") + " de candidatures testée" + (many ? "s" : "") + "."),
        h("p", { class: "note" }, h("a", { href: p.url || POLLS_INDEX(), target: "_blank", rel: "noopener" }, "Voir la publication d'origine du sondage"))));
    const grid = h("div", { class: "poll-grid" }), field = stdField(p.date);
    p.scenarios.forEach((sc, i) => {
      const oth = (p.others || [])[i] || {};
      const rows = Object.entries(sc).map(([id, v]) => ({ id, name: C[id] ? C[id].name : id, v, tracked: true }))
        .concat(Object.entries(oth).map(([name, v]) => ({ name, v, tracked: false }))).sort((a, b) => b.v - a.v);
      const isRef = i === lu.i;
      const extras = rows.filter(r => !field.has(r.tracked ? r.id : r.name)).map(r => r.name.split(" ").slice(-1)[0]);
      grid.append(h("figure", { class: "eng-fig" + (isRef ? " is-ref" : "") },
        h("figcaption", null, h("b", null, "Hypothèse " + (i + 1) + " · " + rows.length + " candidats"),
          isRef && many ? h("span", { class: "ref-badge" }, "Hypothèse retenue sur ce site") : null,
          h("span", null, extras.length ? "Hors champ habituel : " + extras.join(", ") : "Champ habituel des candidats")),
        h("div", { class: "eng-bars" }, rows.map(r => h("div", { class: "eng-row" + (r.tracked ? "" : " is-other"), css: { "--c": r.tracked ? color(C[r.id]) : "var(--ink3)", "--w": (100 * r.v / max).toFixed(1) + "%" } },
          h("span", { class: "eng-who" }, r.tracked ? h("a", { href: "#" + r.id }, r.name) : h("span", null, r.name)),
          h("span", { class: "eng-track" }, h("i")),
          h("span", { class: "eng-val num" }, pct(r.v)))))));
    });
    main.append(h("section", { "aria-labelledby": "poll-t" },
      h("div", { class: "sec-head" }, h("div", null, h("h2", { id: "poll-t" }, many ? "Toutes les hypothèses, tous les candidats" : "Tous les candidats testés"),
        h("p", null, "En couleur, les candidats suivis sur ce site ; en gris, les autres candidats testés." + (many ? " Même échelle pour toutes les hypothèses." : "")))),
      grid,
      many ? h("p", { class: "note" }, "Pourquoi l'hypothèse " + (lu.i + 1) + " ? Sur ce site, tous les candidats d'un sondage sont lus dans la même hypothèse : celle qui ressemble le plus au champ habituel " +
        "(les noms testés dans au moins la moitié des sondages des 60 derniers jours), chaque nom inhabituel ajouté comptant comme une pénalité. " +
        "C'est elle qui alimente les courbes, la médiane et les comparaisons.") : null));
  }

  /* ---------- past elections (#elections, #election-2017): data/history.js, scripts/build_history.py ---------- */
  const HIST = ((window.HISTORY && window.HISTORY.elections) || []).slice().sort((a, b) => b.year - a.year);
  const HIST_BY_ID = Object.fromEntries(HIST.map(e => ["election-" + e.year, e]));
  const HRANGES = [
    { id: "6m", label: "6 derniers mois", days: 183 },
    { id: "12m", label: "12 derniers mois", days: 365 },
    { id: "all", label: "Tout le cycle", days: null }
  ];
  const HMAX = 365;                                        // the day picker goes back one year
  const TODAY_H = Math.min(HMAX, Math.max(1, daysLeft())); // where the 2027 campaign stands today
  state.hday = TODAY_H;
  const HPRESETS = [...new Set([TODAY_H, 100, 60, 30, 20, 10, 7])].sort((a, b) => b - a);
  const HORIZONS = [180, 90, 30, 0];                       // fixed columns; 0 = the final week
  const STATS_FROM = 180;                                  // cross-election statistics: last 6 months
  const SWING_DAYS = 30;

  /* "What the polls said" d days before the vote: the latest poll of each institute among the polls
     of the window up to J-d, median over institutes (daily "rolling" polls count once). The window
     narrows as the vote nears, when polls are frequent. d = 0: the final week. */
  const hwindow = d => d >= 60 ? 21 : d >= 20 ? 14 : 7;
  const institute = f => f.trim().toLowerCase().split(/[\s\-\/]+/)[0];   // "Ipsos-Sopra Steria" -> "ipsos"
  const snapCache = new Map();
  function snapshot(e, d) {
    const key = e.year + ":" + d;
    if (!snapCache.has(key)) {
      const end = T(e.date) - d * DAY, w = hwindow(d), latest = {};
      for (const p of e.polls) {   // sorted by date: a later poll replaces an earlier one
        const t = T(p.date);
        if (t >= end - w * DAY && (d ? t <= end : t < end)) latest[institute(p.firm)] = p;
      }
      const vals = {};
      for (const p of Object.values(latest)) for (const [id, v] of Object.entries(p.v)) (vals[id] = vals[id] || []).push(v);
      const avg = Object.fromEntries(Object.entries(vals).map(([id, a]) => [id, median(a)]));   // median, as for 2027
      snapCache.set(key, { days: d, window: w, n: Object.keys(latest).length, avg });
    }
    return snapCache.get(key);
  }

  const byResult = e => e.candidates.slice().sort((a, b) => b.result - a.result);
  const byId = e => Object.fromEntries(e.candidates.map(c => [c.id, c]));
  const realDuel = e => byResult(e).slice(0, 2).map(c => c.id);
  const ranked = s => Object.keys(s.avg).sort((a, b) => s.avg[b] - s.avg[a]);
  const pollDuel = s => ranked(s).slice(0, 2);
  const sameDuel = (a, b) => a.length === 2 && a.slice().sort().join() === b.slice().sort().join();
  const winner = e => Object.keys(e.second).sort((a, b) => e.second[b] - e.second[a])[0];
  const hLabel = d => d ? "J-" + d : "Dernière semaine";
  const signedPts = v => (v > 0 ? "+" : v < 0 ? "−" : "±") + nf1.format(Math.abs(v)) + " pt";
  const names = (e, ids) => ids.map(id => byId(e)[id].short).join(" et ");
  const dayDate = (e, d) => fmtD(new Date(T(e.date) - d * DAY).toISOString().slice(0, 10));
  const rankOf = (e, id) => byResult(e).findIndex(c => c.id === id) + 1;
  const ord = n => n === 1 ? "1er" : n + "e";
  function mae(e, s) {   // mean gap between the poll average and the result, candidates tested only
    const C = byId(e), ids = Object.keys(s.avg);
    return ids.length ? ids.reduce((t, id) => t + Math.abs(s.avg[id] - C[id].result), 0) / ids.length : null;
  }
  // gaps[0]: biggest |result - polls|; d = result - polls (+: did better than the polls)
  const gaps = (e, s) => Object.keys(s.avg).map(id => ({ e, c: byId(e)[id], poll: s.avg[id], d: byId(e)[id].result - s.avg[id] }))
    .sort((a, b) => Math.abs(b.d) - Math.abs(a.d));
  function secondText(e) {
    const C = byId(e);
    return Object.keys(e.second).sort((a, b) => e.second[b] - e.second[a]).map(id => C[id].short + " " + pct(e.second[id])).join(" – ");
  }
  // Fastest moves over SWING_DAYS days between J-from and the vote (needs 2+ institutes at both ends).
  function swings(e, from) {
    const out = [];
    for (let d = Math.min(from, HMAX) - SWING_DAYS; d >= 0; d--) {
      const a = snapshot(e, d + SWING_DAYS), b = snapshot(e, d);
      if (a.n < 2 || b.n < 2) continue;
      for (const id of Object.keys(b.avg)) if (a.avg[id] != null) out.push({ e, c: byId(e)[id], from: d + SWING_DAYS, to: d, a: a.avg[id], b: b.avg[id], delta: b.avg[id] - a.avg[id] });
    }
    // keep each candidate's single strongest rise and fall, so one long move is not listed 10 times
    const best = {};
    for (const x of out) {
      const k = x.c.id + (x.delta > 0 ? "+" : "-");
      if (!best[k] || Math.abs(x.delta) > Math.abs(best[k].delta)) best[k] = x;
    }
    return Object.values(best).sort((x, y) => Math.abs(y.delta) - Math.abs(x.delta));
  }
  function eventsDuring(e, from, to, id) {   // events between J-from and J-to, the candidate's own first
    const t0 = T(e.date) - from * DAY - 3 * DAY, t1 = T(e.date) - to * DAY;
    return e.events.filter(x => T(x.date) >= t0 && T(x.date) <= t1).sort((a, b) => (b.who.includes(id) ? 1 : 0) - (a.who.includes(id) ? 1 : 0));
  }
  function swingText(x) {
    const ev = eventsDuring(x.e, x.from, x.to, x.c.id)[0];
    return signedPts(x.delta) + " entre J-" + x.from + " et " + hLabel(x.to).replace("Dernière semaine", "la dernière semaine") + " (" + nf1.format(x.a) + " → " + pct(x.b) + ")" + (ev ? ". Repère pendant cette période : " + ev.label : "");
  }
  // Who led the polls, day by day from J-from to the final week; blips under 3 days are smoothed out.
  function leaders(e, from) {
    const segs = [];
    for (let d = from; d >= 0; d--) {
      const s = snapshot(e, d), ids = ranked(s);
      if (ids.length < 2) continue;
      const last = segs[segs.length - 1];
      if (last && last.id === ids[0]) last.to = d; else segs.push({ id: ids[0], from: d, to: d });
    }
    const out = [];
    for (const g of segs) {
      const prev = out[out.length - 1];
      if (prev && (prev.id === g.id || g.from - g.to < 2)) prev.to = g.to; else out.push(Object.assign({}, g));
    }
    return out;
  }

  /* ---------- top 5, day by day (bump chart) ---------- */
  const TOP = 5;
  const realTop = e => byResult(e).slice(0, TOP).map(c => c.id);
  // how many of the poll top 5 hold their final rank
  const topOrder = (e, s) => { const r = realTop(e), n = ranked(s).slice(0, TOP).filter((id, i) => r[i] === id).length; return n + (n > 1 ? " déjà à leur place finale." : " déjà à sa place finale."); };
  const topHits = (e, s) => { const r = new Set(realTop(e)); return ranked(s).slice(0, TOP).filter(id => r.has(id)).length; };
  // ranks[d] = ids in poll order at J-d (null: fewer than 2 institutes in the window)
  function topSeries(e, from) {
    const out = [];
    for (let d = from; d >= 0; d--) { const s = snapshot(e, d); out.push({ d, s, ids: s.n >= 2 ? ranked(s) : null }); }
    return out;
  }
  function bumpChart(host, e, from) {
    host.textContent = "";
    host.classList.add("chart");
    const C = byId(e), W = Math.max(280, host.clientWidth || 640), narrow = W < 560;
    const days = topSeries(e, from).filter(x => x.ids);
    if (!days.length) { host.append(h("p", { class: "empty-state" }, "Pas assez de sondages sur cette période.")); return; }
    const rowH = narrow ? 34 : 42, m = { l: narrow ? 8 : 96, r: narrow ? 70 : 120, t: 22, b: 26 }, H = m.t + m.b + rowH * (TOP - 1) + 26;
    const gapR = 34;                                     // space between the final week and the result column
    const xr = W - m.r, pw = xr - gapR - m.l;
    const d0 = days[0].d;
    const X = d => m.l + (d0 - d) / Math.max(1, d0) * pw, Y = r => m.t + r * rowH;
    const svg = h("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", tabindex: 0,
      "aria-label": "Classement des cinq premiers dans les sondages de J-" + d0 + " au premier tour " + e.year + ", puis résultat officiel" });
    const g = h("g");
    for (let r = 0; r < TOP; r++) {
      g.append(h("line", { x1: m.l, x2: xr, y1: Y(r), y2: Y(r), stroke: "var(--grid)", "stroke-width": 1 }));
      g.append(h("text", { x: m.l - 6, y: Y(r) + 4, "text-anchor": "end", style: narrow ? { display: "none" } : null }, ord(r + 1)));
    }
    // x ticks: J-N every 30 days (60 on narrow screens)
    const stride = narrow ? 60 : 30;
    for (let d = Math.floor(d0 / stride) * stride; d > 0; d -= stride) if (d <= d0 && X(d) - m.l > 10) {
      g.append(h("line", { x1: X(d), x2: X(d), y1: H - m.b, y2: H - m.b + 4, stroke: "var(--rule)" }));
      g.append(h("text", { x: X(d), y: H - 8, "text-anchor": "middle" }, "J-" + d));
    }
    g.append(h("text", { x: xr, y: H - 8, "text-anchor": "middle", class: "lab" }, "Résultat"));
    svg.append(g);
    // chosen day
    const ge = h("g", { class: "evt" });
    if (state.hday <= d0) {
      const xm = X(state.hday);
      ge.append(h("line", { x1: xm, x2: xm, y1: 4, y2: H - m.b, stroke: "var(--ink)", "stroke-width": 1.5 }));
      ge.append(h("text", { x: xm + (xm > xr - 80 ? -5 : 5), y: 12, class: "lab", "text-anchor": xm > xr - 80 ? "end" : null }, "J-" + state.hday));
    }
    svg.append(ge);
    // one line per candidate, broken when out of the top 5
    const gs = h("g"), res = realTop(e);
    for (const c of byResult(e)) {
      const pts = days.map(x => ({ d: x.d, r: x.ids.indexOf(c.id) })), segs = [];
      let cur = null;
      for (const p of pts) {
        if (p.r >= 0 && p.r < TOP) { if (!cur) segs.push(cur = []); cur.push(p); } else cur = null;
      }
      const fr = res.indexOf(c.id);
      if (!segs.length && fr < 0) continue;
      const sg = h("g");
      for (const s of segs) sg.append(h("path", { d: "M" + s.map(p => X(p.d).toFixed(1) + "," + Y(p.r)).join("L"), fill: "none", stroke: color(c), "stroke-width": 3, "stroke-linejoin": "round", "stroke-linecap": "round" }));
      const last = pts[pts.length - 1];
      if (fr >= 0) {
        if (last.r >= 0 && last.r < TOP) sg.append(h("line", { x1: X(last.d), y1: Y(last.r), x2: xr, y2: Y(fr), stroke: color(c), "stroke-width": 1.5, "stroke-dasharray": "3 3" }));
        sg.append(h("rect", { x: xr - 6, y: Y(fr) - 6, width: 12, height: 12, transform: `rotate(45 ${xr} ${Y(fr)})`, fill: color(c), stroke: "var(--surface)", "stroke-width": 1.5 }));
        sg.append(h("text", { x: xr + 12, y: Y(fr) + 4, class: "lab" }, c.short + (narrow ? "" : " " + pct(c.result))));
      }
      // start label: the first day of the window, on the left
      const first = pts[0];
      if (!narrow && first.r >= 0 && first.r < TOP) sg.append(h("text", { x: m.l - 30, y: Y(first.r) + 4, "text-anchor": "end", class: "lab" }, c.short));
      gs.append(sg);
    }
    svg.append(gs);
    host.append(svg);

    // hover: the top 5 of that day
    const cross = h("line", { y1: m.t - 8, y2: H - m.b, stroke: "var(--ink)", "stroke-width": 1, opacity: 0 }), hi = h("g");
    svg.append(cross, hi);
    const tip = h("div", { class: "tip", hidden: true, role: "status" });
    host.append(tip);
    let idx = -1;
    const show = i => {
      i = Math.max(0, Math.min(days.length, i)); idx = i;
      const final = i === days.length, x = final ? xr : X(days[i].d);
      cross.setAttribute("x1", x); cross.setAttribute("x2", x); cross.setAttribute("opacity", .35);
      hi.textContent = ""; tip.textContent = "";
      const ids = final ? res : days[i].ids.slice(0, TOP), s = final ? null : days[i].s;
      ids.forEach((id, r) => hi.append(h("circle", { cx: x, cy: Y(r), r: 6, fill: color(C[id]), stroke: "var(--surface)", "stroke-width": 2 })));
      tip.append(h("div", { class: "t" }, final ? "Résultat officiel du premier tour" : hLabel(days[i].d).replace("Dernière semaine", "J-0") + " · " + dayDate(e, days[i].d)));
      tip.append(h("div", { class: "s" }, final ? fmtD(e.date) : s.n + " instituts · " + topHits(e, s) + " des " + TOP + " premiers finaux dans ce top " + TOP));
      ids.forEach((id, r) => tip.append(h("div", { class: "r" }, h("i", { style: { background: color(C[id]) } }), h("b", null, pct(final ? C[id].result : s.avg[id])),
        h("span", null, ord(r + 1) + " " + C[id].short + (final ? "" : " · finalement " + ord(rankOf(e, id)))))));
      tip.hidden = false;
      const scale = host.clientWidth / W, tw = tip.offsetWidth, px = x * scale;
      tip.style.transform = `translate(${px + 14 + tw > host.clientWidth ? Math.max(0, px - tw - 14) : px + 14}px, ${(m.t + rowH * (TOP - 1)) * scale}px)`;
    };
    const hide = () => { cross.setAttribute("opacity", 0); hi.textContent = ""; tip.hidden = true; };
    const near = ev => {
      const r = svg.getBoundingClientRect(), x = (ev.clientX - r.left) * (W / r.width);
      if (x > xr - gapR / 2) return days.length;
      let best = 0, bd = Infinity;
      days.forEach((p, i) => { const dd = Math.abs(X(p.d) - x); if (dd < bd) { bd = dd; best = i; } });
      return best;
    };
    svg.addEventListener("pointermove", ev => show(near(ev)));
    svg.addEventListener("pointerdown", ev => show(near(ev)));
    svg.addEventListener("pointerleave", hide);
    svg.addEventListener("blur", hide);
    svg.addEventListener("focus", () => show(idx < 0 ? days.length : idx));
    svg.addEventListener("keydown", ev => {
      if (ev.key === "ArrowLeft") { show(idx - 1); ev.preventDefault(); }
      else if (ev.key === "ArrowRight") { show(idx + 1); ev.preventDefault(); }
      else if (ev.key === "Escape") hide();
    });
  }

  /* day picker: slider (J-365 on the left, the vote on the right) + preset buttons */
  function dayControl(describe, onChange) {
    const out = h("output", { style: { fontFamily: "var(--font-display)", fontSize: "2rem", fontWeight: 800, fontStretch: "85%", lineHeight: 1 } });
    const sub = h("span", { class: "muted" });
    const input = h("input", { type: "range", min: 1, max: HMAX, step: 1, value: state.hday, "aria-label": "Nombre de jours avant le premier tour",
      style: { width: "100%", direction: "rtl", accentColor: "var(--ink)" }, oninput: ev => set(+ev.target.value) });
    const chips = h("div", { class: "sb-presets", role: "group", "aria-label": "Moments clés" },
      HPRESETS.map(d => h("button", { type: "button", class: "chip", "data-d": d, onclick: () => set(d) }, "J-" + d + (d === TODAY_H ? " · comme 2027 aujourd'hui" : ""))));
    function paint() {
      out.textContent = "J-" + state.hday;
      sub.textContent = describe(state.hday);
      input.value = state.hday;
      chips.querySelectorAll("button").forEach(b => {
        const on = +b.dataset.d === state.hday;
        b.setAttribute("aria-pressed", String(on));
        b.style.background = on ? "var(--ink)" : ""; b.style.color = on ? "var(--surface)" : ""; b.style.borderColor = on ? "var(--ink)" : "";
      });
    }
    function set(d) { state.hday = d; paint(); onChange(); }
    paint();
    return h("div", { class: "panel", style: { display: "grid", gap: "10px" } },
      h("div", { style: { display: "flex", alignItems: "baseline", gap: "6px 14px", flexWrap: "wrap" } }, out, sub),
      input, h("div", { class: "sb-ends" }, h("span", null, "J-" + HMAX), h("span", null, "Premier tour")), chips);
  }

  const tile = (col, title, big, ...lines) => h("div", { class: "net", css: { "--c": col } }, h("span", null, title), h("b", null, big), ...lines.filter(Boolean).map(l => h("span", null, l)));

  /* ---------- #elections ---------- */
  function renderHistoryIndex() {
    document.title = "Élections passées · Road to 2027";
    main.append(h("a", { class: "back", href: "#" }, "← 2027"),
      h("section", { class: "sb-head" },
        h("p", { class: "eyebrow" }, "Présidentielles de " + HIST[HIST.length - 1].year + " à " + HIST[0].year),
        h("h1", null, "Les élections passées"),
        h("p", { class: "lead" }, "Les mêmes courbes que pour 2027, mais avec la fin de l'histoire : chaque point est un sondage, et chaque ligne s'arrête sur le résultat officiel du premier tour. De quoi voir ce que les sondages ont vu venir, et ce qu'ils ont manqué.")));

    // the same day, in every election
    const head = h("div", { class: "nets", style: { marginBottom: "14px" } });
    const tb = h("tbody");
    function paint() {
      const d = state.hday, rows = HIST.map(e => ({ e, s: snapshot(e, d) })).filter(r => r.s.n);
      const favWon = rows.filter(r => ranked(r.s)[0] === winner(r.e)).length;
      const duelOk = rows.filter(r => sameDuel(pollDuel(r.s), realDuel(r.e))).length;
      const errs = rows.map(r => mae(r.e, r.s)).filter(x => x != null);
      head.textContent = "";
      head.append(
        tile("var(--ink)", "Le premier des sondages à J-" + d + " a gagné", favWon + " fois sur " + rows.length),
        tile("var(--ink)", "Le duel du second tour était annoncé", duelOk + " fois sur " + rows.length),
        tile("var(--ink)", "Écart moyen sondages / résultat", errs.length ? nf1.format(errs.reduce((a, b) => a + b, 0) / errs.length) + " pt" : "–", "par candidat suivi"));
      tb.textContent = "";
      for (const e of HIST) {
        const s = snapshot(e, d), C = byId(e);
        if (!s.n) { tb.append(h("tr", null, h("td", null, h("a", { href: "#election-" + e.year }, e.year)), h("td", { class: "empty", colspan: 4, style: { textAlign: "left" } }, "aucun sondage publié autour de J-" + d))); continue; }
        const lead = C[ranked(s)[0]], w = C[winner(e)], g = gaps(e, s)[0];
        tb.append(h("tr", null,
          h("td", null, h("a", { href: "#election-" + e.year }, e.year), h("small", null, dayDate(e, d))),
          h("td", { style: { textAlign: "left" } }, cellWho(lead), h("small", null, pct(s.avg[lead.id]) + (lead === w ? " · a gagné" : " · vainqueur : " + w.short))),
          h("td", { style: { textAlign: "left" } }, (sameDuel(pollDuel(s), realDuel(e)) ? "✓ " : "✗ ") + names(e, pollDuel(s)), h("small", null, "réel : " + names(e, realDuel(e)))),
          h("td", null, nf1.format(mae(e, s)) + " pt", h("small", null, s.n + " institut" + (s.n > 1 ? "s" : ""))),
          h("td", { style: { textAlign: "left" } }, g.c.short + " " + signedPts(g.d), h("small", null, nf1.format(g.poll) + " % → " + pct(g.c.result)))));
      }
    }
    main.append(h("section", { "aria-labelledby": "hd-t" },
      h("div", { class: "sec-head" }, h("div", null, h("h2", { id: "hd-t" }, "Le même jour, dans chaque élection"),
        h("p", null, "Choisissez un moment de la campagne : où en étaient les sondages, à la même distance du vote, en 2002, 2007, 2012, 2017 et 2022 ? Par défaut, J-" + TODAY_H + " : là où en est 2027 aujourd'hui."))),
      dayControl(d => "avant chaque premier tour", paint),
      h("div", { style: { marginTop: "14px" } }, head),
      h("div", { class: "tbl" }, h("table", null, h("thead", null, h("tr", null, h("th", null, "Élection"), h("th", { style: { textAlign: "left" } }, "En tête des sondages"),
        h("th", { style: { textAlign: "left" } }, "Duel annoncé"), h("th", null, "Écart moyen au résultat"), h("th", { style: { textAlign: "left" } }, "Plus gros écart"))), tb)),
      h("p", { class: "note" }, "Pour chaque élection : le dernier sondage de chaque institut publié dans les 1 à 3 semaines avant ce jour-là, puis la médiane entre instituts (comme pour 2027). « Plus gros écart » : le candidat dont le résultat s'est le plus éloigné de ces sondages (+ : il a fait mieux que prévu).")));
    paint();

    // cards
    const cards = h("div", { class: "cards" });
    for (const e of HIST) {
      const w = byId(e)[winner(e)], fw = snapshot(e, 0), ok = sameDuel(pollDuel(fw), realDuel(e)), miss = gaps(e, fw)[0];
      const sp = h("div", { class: "spark" }), eday = T(e.date), x0 = eday - 365 * DAY;
      cards.append(h("a", { class: "card", href: "#election-" + e.year, css: { "--c": color(w) } },
        h("span", { class: "who" }, h("span", { class: "key" }), h("span", { class: "name" }, "Présidentielle " + e.year)),
        h("span", { class: "party" }, "Second tour : " + secondText(e)),
        h("span", null,
          h("span", { class: "val" }, h("b", { style: { fontSize: "1.6rem" } }, ok ? "Duel annoncé" : "Duel manqué")),
          h("span", { class: "meta", style: { display: "block" } }, "Dernière semaine de sondages : " + names(e, pollDuel(fw)) + " en tête ; qualifiés : " + names(e, realDuel(e)) + "."),
          miss ? h("span", { class: "meta", style: { display: "block" } }, "Plus gros écart : " + miss.c.short + " " + signedPts(miss.d) + " par rapport aux sondages.") : null),
        sp,
        h("span", { class: "go" }, "Voir l'élection →")));
      const pts_ = e.polls.filter(p => p.v[w.id] != null && T(p.date) >= x0).map(p => ({ t: T(p.date), v: p.v[w.id] }));
      redraws.push(() => sparkline(sp, pts_, color(w), x0, eday));
    }
    main.append(h("section", { "aria-labelledby": "hi-t" },
      h("div", { class: "sec-head" }, h("div", null, h("h2", { id: "hi-t" }, HIST.length + " présidentielles"),
        h("p", null, "« Duel annoncé » : les deux premiers de la dernière semaine de sondages sont bien les deux qualifiés du premier tour. La courbe est celle du vainqueur, sur les douze derniers mois."))),
      cards));

    // surprises and swings, all elections together
    const misses = HIST.flatMap(e => gaps(e, snapshot(e, 0))).slice().sort((a, b) => Math.abs(b.d) - Math.abs(a.d)).slice(0, 5);
    const moves = HIST.flatMap(e => swings(e, STATS_FROM)).sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta)).slice(0, 6);
    const item = (x, text) => h("li", null, h("span", { class: "who" }, h("span", { class: "key", css: { "--c": color(x.c) } }), h("a", { href: "#election-" + x.e.year }, x.c.name + ", " + x.e.year)), " : " + text);
    main.append(h("section", { class: "duo" },
      h("div", { class: "panel" }, h("h3", null, "Les plus grandes surprises du dernier moment"),
        h("p", { class: "note", style: { marginTop: "4px" } }, "Écart entre la dernière semaine de sondages et le résultat."),
        h("ol", { style: { margin: "10px 0 0", paddingLeft: "1.2em", display: "grid", gap: "8px", fontSize: ".92rem" } },
          misses.map(x => item(x, signedPts(x.d) + " (" + nf1.format(x.poll) + " % dans les sondages, " + pct(x.c.result) + " dans les urnes)")))),
      h("div", { class: "panel" }, h("h3", null, "Les dynamiques les plus spectaculaires"),
        h("p", { class: "note", style: { marginTop: "4px" } }, "Plus fortes variations des sondages en " + SWING_DAYS + " jours, sur les six derniers mois de chaque campagne."),
        h("ol", { style: { margin: "10px 0 0", paddingLeft: "1.2em", display: "grid", gap: "8px", fontSize: ".92rem" } },
          moves.map(x => item(x, swingText(x)))))));

    // how far were the polls, at fixed horizons
    const ltb = h("tbody");
    for (const e of HIST) {
      ltb.append(h("tr", null, h("td", null, h("a", { href: "#election-" + e.year }, e.year)),
        HORIZONS.map(d => {
          const s = snapshot(e, d), m = mae(e, s);
          if (m == null) return h("td", { class: "empty" }, "–");
          return h("td", null, nf1.format(m) + " pt", h("small", null, (sameDuel(pollDuel(s), realDuel(e)) ? "duel trouvé" : "duel : " + names(e, pollDuel(s))) + " · " + s.n + " institut" + (s.n > 1 ? "s" : "")));
        })));
    }
    main.append(h("section", { "aria-labelledby": "hl-t" },
      h("div", { class: "sec-head" }, h("div", null, h("h2", { id: "hl-t" }, "Les limites des sondages"),
        h("p", null, "Écart moyen, en points, entre les sondages et le résultat de chaque candidat suivi. Plus le vote approche, plus l'écart se réduit, sans jamais disparaître : les sondages mesurent une intention à un moment donné, pas une prévision."))),
      h("div", { class: "tbl" }, h("table", null,
        h("thead", null, h("tr", null, h("th", null, "Élection"), HORIZONS.map(d => h("th", null, hLabel(d))))), ltb)),
      h("p", { class: "note" }, "À chaque horizon : le dernier sondage de chaque institut publié dans les 1 à 3 semaines précédentes, puis la médiane entre instituts, comme pour 2027 (les enquêtes quotidiennes ne pèsent pas plus que les autres). « Duel » : les deux premiers de cette médiane.")));
  }

  /* ---------- #election-2017 ---------- */
  function renderElection(e) {
    document.title = "Présidentielle " + e.year + " · Road to 2027";
    const C = byId(e), cands = byResult(e), eday = T(e.date), fw = snapshot(e, 0);
    main.append(h("a", { class: "back", href: "#elections" }, "← Les élections passées"));
    const duelOk = sameDuel(pollDuel(fw), realDuel(e)), miss = gaps(e, fw)[0];
    main.append(h("section", { class: "fiche-head", css: { "--c": color(C[winner(e)]) } },
      h("div", null,
        h("p", { class: "eyebrow" }, "Premier tour le " + fmtD(e.date)),
        h("h1", null, h("span", { class: "key" }), "Présidentielle " + e.year),
        h("p", { class: "party" }, "Second tour : " + secondText(e) + "."),
        h("nav", { class: "sb-presets", "aria-label": "Autres élections", style: { marginTop: "14px" } },
          HIST.map(x => h("a", { class: "chip", href: "#election-" + x.year, "aria-current": x === e ? "page" : null,
            style: x === e ? { background: "var(--ink)", color: "var(--surface)", borderColor: "var(--ink)", textDecoration: "none" } : { textDecoration: "none" } }, x.year)))),
      h("div", { class: "bigfig" },
        h("b", null, duelOk ? "Duel annoncé" : "Duel manqué"),
        h("p", null, "Dernière semaine de sondages : " + names(e, pollDuel(fw)) + " en tête. Qualifiés au premier tour : " + names(e, realDuel(e)) + "."),
        miss ? h("p", null, "Plus gros écart : " + miss.c.name + ", " + pct(miss.c.result) + " au premier tour contre " + pct(miss.poll) + " dans les sondages (" + signedPts(miss.d) + ").") : null)));

    // the chosen day: standings, then what happened next
    const board = h("div"), next = h("div", { class: "nets" }), race = h("p", { style: { margin: "12px 0 0", fontSize: ".92rem" } });
    function paintDay() {
      const d = state.hday, s = snapshot(e, d), w = C[winner(e)];
      board.textContent = ""; next.textContent = ""; race.textContent = "";
      if (!s.n) { board.append(h("p", { class: "empty-state" }, "Aucun sondage publié dans les " + s.window + " jours avant J-" + d + " (" + dayDate(e, d) + ").")); return; }
      const ids = ranked(s), max = Math.max(...ids.map(id => s.avg[id]), ...cands.map(c => c.result));
      const tb = h("tbody");
      ids.forEach((id, i) => {
        const c = C[id], fr = rankOf(e, id);
        tb.append(h("tr", null,
          h("td", null, h("span", { class: "muted num" }, (i + 1) + ". "), cellWho(c)),
          h("td", null, h("span", { class: "sb-cell" }, h("span", { class: "sb-bar" }, h("i", { css: { "--w": (100 * s.avg[id] / max).toFixed(1) + "%", "--c": color(c) } })), h("span", { class: "num" }, pct(s.avg[id])))),
          h("td", null, pct(c.result), h("small", null, ord(fr) + (fr < i + 1 ? " ▲" : fr > i + 1 ? " ▼" : ""))),
          h("td", null, signedPts(c.result - s.avg[id]))));
      });
      for (const c of cands) if (s.avg[c.id] == null) tb.append(h("tr", null, h("td", null, h("span", { class: "muted num" }, "– "), cellWho(c)),
        h("td", { class: "empty" }, "pas encore testé"), h("td", null, pct(c.result), h("small", null, ord(rankOf(e, c.id)))), h("td", { class: "empty" }, "–")));
      board.append(h("div", { class: "tbl" }, h("table", { class: "sb-table" },
        h("thead", null, h("tr", null, h("th", null, "Classement à J-" + d), h("th", null, "Sondages"), h("th", null, "Résultat"), h("th", null, "Écart"))), tb)),
        h("p", { class: "note" }, "Médiane du dernier sondage de " + s.n + " institut" + (s.n > 1 ? "s" : "") + ", publiés dans les " + s.window + " jours avant le " + dayDate(e, d) + ". ▲▼ : place finale meilleure ou moins bonne qu'à ce moment-là."));

      const lead = C[ids[0]], g = gaps(e, s), up = g.filter(x => x.d > 0)[0], down = g.filter(x => x.d < 0)[0];
      const sw = swings(e, d), rise = sw.find(x => x.delta > 0), fall = sw.find(x => x.delta < 0);
      next.append(
        tile(color(lead), "En tête à J-" + d, lead.short + " " + pct(s.avg[lead.id]), lead === w ? "Il a gagné l'élection." : "Finalement " + ord(rankOf(e, lead.id)) + " au premier tour ; vainqueur : " + w.short + "."),
        tile("var(--ink)", "Duel annoncé à J-" + d, (sameDuel(pollDuel(s), realDuel(e)) ? "✓ " : "✗ ") + names(e, pollDuel(s)), "Qualifiés : " + names(e, realDuel(e)) + "."),
        ids.length >= TOP ? tile("var(--ink)", "Top " + TOP + " à J-" + d, topHits(e, s) + "/" + TOP + " trouvés",
          "Finalement dans le top " + TOP + " du premier tour ; " + topOrder(e, s)) : null,
        up ? tile(color(up.c), "A le plus déjoué les sondages", up.c.short + " " + signedPts(up.d), nf1.format(up.poll) + " % à J-" + d + ", " + pct(up.c.result) + " au premier tour.") : null,
        down ? tile(color(down.c), "A le plus déçu", down.c.short + " " + signedPts(down.d), nf1.format(down.poll) + " % à J-" + d + ", " + pct(down.c.result) + " au premier tour.") : null,
        rise ? tile(color(rise.c), "Plus forte poussée en " + SWING_DAYS + " jours", rise.c.short + " " + signedPts(rise.delta), swingText(rise).replace(/^[^ ]+ pt /, "")) : null,
        fall ? tile(color(fall.c), "Plus forte chute en " + SWING_DAYS + " jours", fall.c.short + " " + signedPts(fall.delta), swingText(fall).replace(/^[^ ]+ pt /, "")) : null);
      const segs = leaders(e, d);
      if (segs.length) race.append(h("b", null, "Course en tête depuis J-" + d + " : "),
        ...segs.map((sg, i) => [i ? " → " : "", h("span", { class: "who", style: { display: "inline-flex" } }, h("span", { class: "key", css: { "--c": color(C[sg.id]) } }), C[sg.id].short),
          " (" + (sg.from === sg.to ? hLabel(sg.from) : "J-" + sg.from + " à " + (sg.to ? "J-" + sg.to : "la fin")) + ")"]).flat(),
        segs.length > 1 ? " · " + (segs.length - 1) + " changement" + (segs.length > 2 ? "s" : "") + " de leader." : " · aucun changement de leader.");
    }
    const onDay = [paintDay];
    main.append(h("section", { "aria-labelledby": "ht-t" },
      h("div", { class: "sec-head" }, h("div", null, h("h2", { id: "ht-t" }, "Remonter le temps"),
        h("p", null, "Choisissez un moment de la campagne pour voir où en étaient les sondages, puis ce qui s'est passé jusqu'au vote. Par défaut, J-" + TODAY_H + " : la distance qui nous sépare aujourd'hui du premier tour de 2027."))),
      dayControl(d => dayDate(e, d), () => onDay.forEach(f => f())),
      h("div", { class: "duo", style: { marginTop: "16px" } },
        h("div", { class: "panel" }, board),
        h("div", { class: "panel" }, h("h3", null, "Et ensuite ?"), next, race))));
    paintDay();

    // the top 5, day by day
    const bhost = h("div"), bnote = h("p", { class: "note" });
    const drawBump = () => {
      bumpChart(bhost, e, HMAX);
      const s = snapshot(e, state.hday);
      bnote.textContent = (s.n >= 2 && ranked(s).length >= TOP ? "À J-" + state.hday + ", " + topHits(e, s) + " des " + TOP + " premiers du scrutin étaient déjà dans le top " + TOP + " des sondages. " : "") +
        "Chaque jour : classement de la médiane des instituts (dernier sondage de chacun, comme plus haut). Une ligne s'interrompt quand le candidat sort du top " + TOP + ". Les losanges donnent le classement officiel du premier tour.";
    };
    redraws.push(drawBump);
    onDay.push(drawBump);
    main.append(h("section", { "aria-labelledby": "hb-t" },
      h("div", { class: "sec-head" }, h("div", null, h("h2", { id: "hb-t" }, "L'évolution du top " + TOP),
        h("p", null, "Qui occupait les cinq premières places des sondages, jour après jour, de J-" + HMAX + " au premier tour. Survolez la courbe pour voir le classement d'un jour."))),
      h("div", { class: "panel" }, bhost, bnote)));

    // race chart: polls, then the result
    let firm = "all", focus = null;
    const firms = [...new Set(e.polls.map(p => p.firm))].sort((a, b) => a.localeCompare(b, "fr"));
    const host = h("div"), note = h("p", { class: "note" }), legend = h("ul", { class: "legend" });
    const seg = h("div", { class: "seg", role: "group", "aria-label": "Période" });
    HRANGES.forEach(r => seg.append(h("button", { type: "button", "aria-pressed": String(state.hrange === r.id), onclick: () => {
      state.hrange = r.id; save(); [...seg.children].forEach((b, i) => b.setAttribute("aria-pressed", String(HRANGES[i].id === r.id))); draw(); } }, r.label)));
    const sel = h("select", { id: "firm-filter-h", onchange: ev => { firm = ev.target.value; draw(); } },
      h("option", { value: "all" }, "Tous les instituts"), firms.map(f => h("option", { value: f }, f)));
    cands.forEach(c => legend.append(h("li", null, h("button", { type: "button", "aria-pressed": "false", css: { "--c": color(c) }, onclick: ev => {
      focus = focus === c.id ? null : c.id;
      legend.querySelectorAll("button").forEach(b => b.setAttribute("aria-pressed", "false"));
      if (focus) ev.currentTarget.setAttribute("aria-pressed", "true");
      draw();
    } }, h("span", { class: "ln" }), c.short))));
    legend.append(h("li", { class: "hint" }, "Cliquez sur un nom pour le mettre en avant."));
    function draw() {
      const r = HRANGES.find(x => x.id === state.hrange), mt = eday - state.hday * DAY;
      // the chosen day always stays on the chart
      const x0 = Math.min(r.days ? eday - r.days * DAY : T(e.polls[0].date), mt - 14 * DAY), x1 = eday + 3 * DAY;
      const polls = e.polls.filter(p => T(p.date) >= x0 && (firm === "all" || p.firm === firm));
      const S = cands.map(c => ({ key: c.id, label: c.short, color: color(c), dim: focus && focus !== c.id,
        points: polls.filter(p => p.v[c.id] != null).map(p => ({ t: T(p.date), v: p.v[c.id], lo: (p.r || {})[c.id] ? p.r[c.id][0] : null, hi: (p.r || {})[c.id] ? p.r[c.id][1] : null }))
          .concat([{ t: eday, v: c.result, result: true }]) }));
      note.textContent = polls.length + " sondage" + (polls.length > 1 ? "s" : "") + " affiché" + (polls.length > 1 ? "s" : "") +
        ". Chaque point est un sondage, lu dans l'hypothèse la plus proche du champ habituel des candidats (même règle que pour 2027). Le losange est le résultat officiel du premier tour ; les pointillés le relient au dernier sondage. Le trait noir marque le jour choisi.";
      lineChart(host, {
        series: S, height: 400, x0, x1, labels: true, events: e.events, yMinMax: 10,
        marker: { t: mt, label: "J-" + state.hday },
        yFmt: (v, lab) => lab ? nf1.format(v) : v + " %",
        aria: "Intentions de vote au premier tour de " + e.year + ", " + polls.length + " sondages, puis résultat officiel",
        snap: polls.map(p => T(p.date)).concat([eday]),
        onPick: t => { const p = polls.find(q => T(q.date) === t); if (p && p.url) window.open(p.url, "_blank", "noopener"); },
        tooltip: t => {
          if (t === eday) return { title: "Résultat officiel du premier tour", sub: fmtD(e.date),
            rows: cands.map(c => ({ color: color(c), value: pct(c.result), label: c.short })), foot: "Autres candidats : " + pct(e.others) + "." };
          const ps = polls.filter(p => T(p.date) === t), p = ps[0];
          const rows = cands.filter(c => p.v[c.id] != null).sort((a, b) => p.v[b.id] - p.v[a.id])
            .map(c => ({ color: color(c), value: pct(p.v[c.id]), label: c.short + ((p.r || {})[c.id] ? " (" + nf1.format(p.r[c.id][0]) + "–" + nf1.format(p.r[c.id][1]) + " selon hypothèse)" : "") }));
          const ev = e.events.find(x => Math.abs(T(x.date) - t) <= 2 * DAY);
          return { title: p.firm + (ps.length > 1 ? " (+ " + ps.slice(1).map(q => q.firm).join(", ") + ")" : ""),
            sub: "Terrain achevé le " + fmtD(p.date) + " (J-" + Math.round((eday - t) / DAY) + ")" + (p.sample ? " · " + nf0.format(p.sample) + " personnes" : ""), rows,
            foot: (ev ? "Repère : " + ev.label + " · " : "") + (p.n > 1 ? p.n + " hypothèses dans ce sondage · " : "") + "Cliquez pour ouvrir la source." };
        }
      });
    }
    redraws.push(draw);
    onDay.push(draw);
    main.append(h("section", { "aria-labelledby": "hr-t" },
      h("div", { class: "sec-head" }, h("div", null, h("h2", { id: "hr-t" }, "Des sondages au résultat"),
        h("p", null, "Les huit candidats arrivés en tête du premier tour, suivis dans tous les sondages publiés, jusqu'au vote.")),
        h("div", { class: "filters" }, seg, h("label", { class: "sel", for: "firm-filter-h" }, "Institut", sel))),
      h("div", { class: "panel" }, legend, host, note)));

    // what the polls said, horizon by horizon (+ the chosen day)
    const wtable = h("div", { class: "tbl" });
    function paintTable() {
      const hs = [...new Set(HORIZONS.concat([state.hday]))].sort((a, b) => b - a), S = hs.map(d => snapshot(e, d));
      const tb = h("tbody");
      for (const c of cands) tb.append(h("tr", null, h("td", null, cellWho(c)),
        S.map(s => s.avg[c.id] == null ? h("td", { class: "empty" }, s.n ? "non testé" : "–")
          : h("td", null, pct(s.avg[c.id]), h("small", null, signedPts(c.result - s.avg[c.id])))),
        h("td", null, h("b", null, pct(c.result)))));
      tb.append(h("tr", null, h("td", null, h("b", null, "Duel en tête")),
        S.map(s => Object.keys(s.avg).length < 2 ? h("td", { class: "empty" }, "–") : h("td", null, (sameDuel(pollDuel(s), realDuel(e)) ? "✓ " : "✗ ") + names(e, pollDuel(s)))),
        h("td", null, h("b", null, names(e, realDuel(e))))));
      tb.append(h("tr", null, h("td", null, h("b", null, "Top " + TOP + " en tête")),
        S.map(s => ranked(s).length < TOP ? h("td", { class: "empty" }, "–") : h("td", null, topHits(e, s) + "/" + TOP, h("small", null, ranked(s).slice(0, TOP).map(id => C[id].short).join(", ")))),
        h("td", null, h("small", null, realTop(e).map(id => C[id].short).join(", ")))));
      tb.append(h("tr", null, h("td", null, h("b", null, "Écart moyen")),
        S.map(s => { const m = mae(e, s); return m == null ? h("td", { class: "empty" }, "–") : h("td", null, nf1.format(m) + " pt"); }), h("td", null, "")));
      wtable.textContent = "";
      wtable.append(h("table", null, h("thead", null, h("tr", null, h("th", null, "Candidat"),
        S.map(s => h("th", { style: s.days === state.hday ? { color: "var(--ink)" } : null }, hLabel(s.days) + (s.days === state.hday ? " ◂" : ""), h("br"), h("span", { style: { fontWeight: 400 } }, s.n + " institut" + (s.n > 1 ? "s" : "")))),
        h("th", null, "Résultat"))), tb));
    }
    onDay.push(paintTable);
    paintTable();
    main.append(h("section", { "aria-labelledby": "hw-t" },
      h("div", { class: "sec-head" }, h("div", null, h("h2", { id: "hw-t" }, "Ce que disaient les sondages"),
        h("p", null, "Médiane des instituts à plusieurs moments de la campagne (◂ : le jour choisi), comparée au résultat. En petit : l'écart entre le résultat et les sondages (+ : le candidat a fait mieux que prévu)."))),
      wtable,
      h("p", { class: "note" }, "À chaque moment : le dernier sondage de chaque institut publié dans les 1 à 3 semaines précédentes, puis la médiane entre instituts. « Non testé » : le candidat n'était pas encore proposé par les instituts.")));

    // official results
    const max = Math.max(...cands.map(c => c.result));
    const rtb = h("tbody");
    for (const c of cands) rtb.append(h("tr", null, h("td", null, cellWho(c)), h("td", { style: { textAlign: "left" } }, c.party),
      h("td", null, h("span", { class: "sb-cell" }, h("span", { class: "sb-bar" }, h("i", { css: { "--w": (100 * c.result / max).toFixed(1) + "%", "--c": color(c) } })), h("span", { class: "num" }, pct(c.result))))));
    rtb.append(h("tr", null, h("td", null, "Autres candidats"), h("td", null, ""), h("td", null, pct(e.others))));
    const [a, b] = Object.keys(e.second).sort((x, y) => e.second[y] - e.second[x]);
    main.append(h("section", { class: "duo" },
      h("div", { class: "panel" }, h("h3", null, "Premier tour"), h("div", { class: "tbl", style: { marginTop: "8px" } }, h("table", { class: "sb-table" }, rtb))),
      h("div", { class: "panel" }, h("h3", null, "Second tour"),
        h("div", { class: "sb-duel-top", style: { marginTop: "12px" } }, h("b", null, C[a].short + " " + pct(e.second[a])), h("span", null, C[b].short + " " + pct(e.second[b]))),
        h("div", { class: "sb-duel-split", style: { height: "16px" } }, h("i", { css: { "--w": e.second[a] + "%", "--c": color(C[a]) } }), h("i", { css: { "--w": e.second[b] + "%", "--c": color(C[b]) } })),
        h("p", { class: "note" }, "En % des suffrages exprimés. Résultats officiels du Conseil constitutionnel, via ", h("a", { href: e.source, target: "_blank", rel: "noopener" }, "Wikipédia"), "."))));

    if (e.events.length) main.append(h("section", { "aria-labelledby": "he-t" }, h("div", { class: "sec-head" }, h("h2", { id: "he-t" }, "Repères de la campagne")),
      h("ul", { class: "timeline" }, e.events.map(x => h("li", null, h("time", { datetime: x.date }, fmtD(x.date) + " · J-" + Math.round((eday - T(x.date)) / DAY)), h("span", null, x.label))))));

    // every poll, newest first
    const ptb = h("tbody");
    for (const p of e.polls.slice().reverse()) ptb.append(h("tr", null,
      h("td", null, h("a", { href: p.url, target: "_blank", rel: "noopener" }, p.firm), h("small", null, fmtD(p.date) + (p.sample ? " · " + nf0.format(p.sample) : "") + (p.n > 1 ? " · " + p.n + " hypothèses" : ""))),
      cands.map(c => p.v[c.id] == null ? h("td", { class: "empty" }, "–") : h("td", null, nf1.format(p.v[c.id]) + ((p.r || {})[c.id] ? "*" : "")))));
    main.append(h("section", null, h("details", { class: "more" }, h("summary", null, "Voir les " + e.polls.length + " sondages (tableau et sources)"),
      h("div", { class: "tbl" }, h("table", null, h("thead", null, h("tr", null, h("th", null, "Institut, fin du terrain, effectif"), cands.map(c => h("th", null, c.short)))), ptb)),
      h("p", { class: "note" }, "En %. * : le score varie selon les hypothèses testées. – : absent de l'hypothèse retenue. Sondages repérés via ", h("a", { href: e.polls_index, target: "_blank", rel: "noopener" }, "Wikipédia"), " ; sondages régionaux exclus."))));
  }

  route();
  // fonts change text metrics: redraw once everything has loaded
  window.addEventListener("load", () => redraws.forEach(f => f()));
})();
