"""Add the latest follower counts from Le Podium 2027 to data/social.js.

Usage:
    python3 scripts/update_social.py              # fetch https://lepodium2027.fr/
    python3 scripts/update_social.py page.html    # parse a saved copy

Le Podium publishes its readings in the page (<script id="data">) and allows reuse
with attribution ("Reprise autorisée avec mention de la source"). Covered: X, Instagram,
TikTok, Facebook. YouTube and party membership stay manual.

One point per account and per reading date: a newer reading is appended, a reading
with the same date replaces the previous point from Le Podium. Never raises on a
network problem: the poll update must not fail because of this source.
"""
import datetime as dt, json, os, re, sys, urllib.request

URL = "https://lepodium2027.fr/"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "data", "social.js")
PREFIX = "window.SOCIAL = "
NETWORKS = ("x", "instagram", "tiktok", "facebook")
JUMP_WARN = 0.25  # flag (not block) a change of more than 25 % since the last point

# site id -> Le Podium entity id
IDS = {
    "lepen": "marine-le-pen", "melenchon": "jean-luc-melenchon", "glucksmann": "raphael-glucksmann",
    "roussel": "fabien-roussel", "attal": "gabriel-attal", "philippe": "edouard-philippe",
    "tondelier": "marine-tondelier", "lisnard": "david-lisnard",
}

def warn(msg):
    print(f"::warning::{msg}")

def load_page():
    if len(sys.argv) > 1:
        return open(sys.argv[1], encoding="utf-8").read()
    req = urllib.request.Request(URL, headers={"User-Agent": "road-to-2027-updater/1.0 (+https://kayimsaidb.github.io/road-to-2027/)"})
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8")

def main():
    try:
        page = load_page()
        m = re.search(r'<script type="application/json" id="data">(.*?)</script>', page, re.S)
        data = json.loads(m.group(1))
        entities = {e["id"]: e for e in data["entities"]}
    except Exception as exc:  # network, layout change, invalid JSON
        warn(f"Le Podium 2027 unreadable, followers not updated: {exc}")
        return

    text = open(OUT, encoding="utf-8").read()
    head, body = text.split(PREFIX, 1)
    social = json.loads(body.rsplit(";", 1)[0])

    added, replaced = 0, 0
    for cid, pid in IDS.items():
        ent = entities.get(pid)
        if not ent:
            warn(f"{pid} missing from Le Podium")
            continue
        for net in NETWORKS:
            reading = (ent.get("nets") or {}).get(net) or {}
            value, ts = reading.get("n"), reading.get("t")
            if not value or not ts:
                continue  # no confirmed account on this network (e.g. Glucksmann on TikTok)
            date = dt.datetime.fromtimestamp(ts, dt.timezone.utc).date().isoformat()
            acc = social["followers"].setdefault(cid, {}).setdefault(net, {"handle": None, "points": []})
            pts = acc["points"]
            point = {"date": date, "value": int(value), "approx": False, "source": f"{URL}{pid}",
                     "detail": "Le Podium 2027, relevé automatique sur la page publique du compte officiel"}
            last = pts[-1] if pts else None
            if last and last["date"] > date:
                continue  # we already hold a newer reading
            if last and last["value"] and abs(value - last["value"]) / last["value"] > JUMP_WARN:
                warn(f"{cid} {net}: {last['value']} -> {value} since {last['date']} (check before merging)")
            if last and last["date"] == date:
                if "lepodium2027.fr" in last["source"] and last["value"] != point["value"]:
                    pts[-1] = point; replaced += 1
                continue
            pts.append(point); added += 1

    if added or replaced:
        social["updated"] = dt.datetime.now(dt.timezone.utc).date().isoformat()
        with open(OUT, "w", encoding="utf-8") as f:
            f.write(head + PREFIX)
            json.dump(social, f, ensure_ascii=False, indent=1)
            f.write(";\n")
    print(f"Le Podium 2027: {added} new points, {replaced} replaced")

if __name__ == "__main__":
    main()
