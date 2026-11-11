"""Instagram engagement of the tracked candidates, via Meta's Business Discovery API.

Usage:
    IG_TOKEN=... IG_USER_ID=... python3 scripts/update_engagement.py
    python3 scripts/update_engagement.py --sample scripts/fixtures/ig_sample.json --out /tmp/engagement.js
    IG_TOKEN=... IG_USER_ID=... python3 scripts/update_engagement.py --check   # which accounts are reachable

Needs (see README): a professional Instagram account linked to a Facebook Page, a Meta app,
and a token with instagram_basic, pages_show_list, pages_read_engagement. IG_USER_ID is the id
of YOUR professional account; the candidates' accounts are looked up by username.
Only professional (business or creator) accounts can be read; personal accounts are reported
as unavailable. Never fails the workflow: problems become warnings.

Method (data/engagement.js keeps it next to the numbers):
- posts published between 14 and 2 days before the run (settled engagement), at most 50;
- fewer than 3 posts in the window: "not enough posts", no score;
- interactions of a post = likes + 3 x comments; the score is the MEDIAN over the posts
  (one viral post does not move it), with median likes and comments shown separately;
- engagement rate = median interactions / followers, in %.
"""
import datetime as dt, json, os, statistics as st, sys, urllib.error, urllib.parse, urllib.request

GRAPH = "https://graph.facebook.com/v21.0"   # bump when Meta retires this version
HERE = os.path.dirname(os.path.abspath(__file__))
SOCIAL = os.path.join(HERE, "..", "data", "social.js")
OUT = os.path.join(HERE, "..", "data", "engagement.js")
PREFIX = "window.ENGAGEMENT = "
METHOD = {"window_days": [14, 2], "min_posts": 3, "max_posts": 50, "comment_weight": 3,
          "source": "Meta Graph API, Business Discovery (comptes professionnels uniquement)"}
FIELDS = ("followers_count,media_count,media.limit(60)"
          "{timestamp,like_count,comments_count,permalink,media_type,media_product_type}")
TOKEN_WARN_DAYS = 10

def warn(msg): print(f"::warning::{msg}")

def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default

def get(url):
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:   # Graph API errors come back as JSON bodies
        try:
            return json.loads(e.read().decode("utf-8"))
        except Exception:
            return {"error": {"message": f"HTTP {e.code}"}}

def handles():
    d = json.loads(open(SOCIAL, encoding="utf-8").read().split("window.SOCIAL = ", 1)[1].rsplit(";", 1)[0])
    out = {}
    for cid, nets in d["followers"].items():
        h = (nets.get("instagram") or {}).get("handle")
        if h: out[cid] = h.lstrip("@")
    return out

def fetch_live(username, token, me):
    q = urllib.parse.urlencode({"fields": f"business_discovery.username({username}){{{FIELDS}}}", "access_token": token})
    return get(f"{GRAPH}/{me}?{q}")

def check_token(token):
    info = get(f"{GRAPH}/debug_token?" + urllib.parse.urlencode({"input_token": token, "access_token": token}))
    data = info.get("data") or {}
    if not data.get("is_valid", True):
        warn("Instagram token is invalid or expired: engagement not updated. Generate a new one (README).")
        return False
    exp = data.get("expires_at")
    if exp:   # 0 = never expires (system user token)
        left = (dt.datetime.fromtimestamp(exp, dt.timezone.utc) - dt.datetime.now(dt.timezone.utc)).days
        if left <= TOKEN_WARN_DAYS:
            warn(f"Instagram token expires in {left} days: renew it and update the IG_TOKEN secret.")
    return True

def measure(bd, today):
    """bd = the business_discovery object of one account."""
    lo, hi = today - dt.timedelta(days=METHOD["window_days"][0]), today - dt.timedelta(days=METHOD["window_days"][1])
    media = (bd.get("media") or {}).get("data") or []
    posts = []
    for m in media:
        ts = dt.datetime.strptime(m["timestamp"][:19], "%Y-%m-%dT%H:%M:%S").date()
        if lo <= ts <= hi:
            posts.append({"url": m.get("permalink"), "date": ts.isoformat(), "type": m.get("media_product_type") or m.get("media_type"),
                          "likes": m.get("like_count"), "comments": m.get("comments_count", 0)})
    n_window = len(posts)   # every post of the window, before the cap: what the candidate published
    posts = sorted(posts, key=lambda p: p["date"], reverse=True)[:METHOD["max_posts"]]
    oldest = min((m["timestamp"][:10] for m in media), default=None)
    truncated = bool(media) and oldest is not None and oldest > lo.isoformat() and len(media) >= 60
    days = (hi - lo).days + 1
    entry = {"date": today.isoformat(), "followers": bd.get("followers_count"), "n_posts": len(posts),
             "window": [lo.isoformat(), hi.isoformat()], "posted_in_window": n_window,
             "posts_per_week": round(7 * n_window / days, 1),
             "truncated": truncated or None, "posts": posts}
    if len(posts) < METHOD["min_posts"]:
        entry["status"] = "not_enough_posts"
        return entry
    # Comments are visible on every account (likes can be hidden): the measure comparable across all.
    entry["median_comments"] = st.median(p["comments"] for p in posts)
    if entry["followers"]:
        entry["comment_rate"] = round(100 * entry["median_comments"] / entry["followers"], 4)
    if any(p["likes"] is None for p in posts):
        # Likes hidden by the account: a comments-only score would not be comparable with the
        # others (it would look like a collapse), so no score and no rate, comments only.
        entry.update({"status": "likes_hidden", "likes_hidden": True})
        return entry
    w = METHOD["comment_weight"]
    inter = [p["likes"] + w * p["comments"] for p in posts]
    entry.update({"status": "ok", "median_likes": st.median(p["likes"] for p in posts),
                  "median_interactions": st.median(inter), "mean_interactions": round(st.mean(inter), 1)})
    if entry["followers"]:
        entry["rate"] = round(100 * entry["median_interactions"] / entry["followers"], 3)
    return entry

def main():
    today = dt.datetime.now(dt.timezone.utc).date()
    sample = arg("--sample")
    out_path = arg("--out", OUT)
    if sample and out_path == OUT:
        sys.exit("--sample needs --out: sample data must never be written to data/engagement.js")
    token, me = os.environ.get("IG_TOKEN"), os.environ.get("IG_USER_ID")
    if not sample and not (token and me):
        warn("IG_TOKEN / IG_USER_ID not set: Instagram engagement not updated.")
        return
    if not sample and not check_token(token):
        return
    canned = json.load(open(sample, encoding="utf-8")) if sample else None
    if sample:
        today = dt.date.fromisoformat(canned.get("today", today.isoformat()))

    try:
        data = json.loads(open(out_path, encoding="utf-8").read().split(PREFIX, 1)[1].rsplit(";", 1)[0])
    except (FileNotFoundError, IndexError):
        data = {"updated": None, "method": METHOD, "candidates": {}}
    data["method"] = METHOD

    reachable = {}
    for cid, user in handles().items():
        res = canned.get(user, {"error": {"message": "not in sample"}}) if canned else fetch_live(user, token, me)
        bd = res.get("business_discovery")
        acc = data["candidates"].setdefault(cid, {"handle": "@" + user, "history": []})
        acc["handle"] = "@" + user
        if not bd:
            msg = (res.get("error") or {}).get("message", "unknown error")
            acc["status"] = "unavailable"; acc["reason"] = msg[:200]
            reachable[cid] = f"unavailable ({msg[:80]})"
            warn(f"Instagram @{user}: not readable ({msg[:120]})")
            continue
        entry = measure(bd, today)
        acc["status"] = entry["status"]; acc.pop("reason", None)
        acc["history"] = [h for h in acc["history"] if h["date"] != entry["date"]] + [entry]
        reachable[cid] = f"{entry['status']}, {entry['n_posts']} posts" + (", likes hidden" if entry.get("likes_hidden") else "")

    if "--check" in sys.argv:
        for cid, s in reachable.items(): print(f"{cid:12} {s}")
        return
    data["updated"] = today.isoformat()
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("/* Généré par scripts/update_engagement.py (Instagram, Business Discovery). Ne pas éditer à la main. */\n")
        f.write(PREFIX); json.dump(data, f, ensure_ascii=False, indent=1); f.write(";\n")
    for cid, s in reachable.items(): print(f"{cid:12} {s}")

if __name__ == "__main__":
    main()
