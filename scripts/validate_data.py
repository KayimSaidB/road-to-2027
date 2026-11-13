import json
from pathlib import Path
def validate_polls() ->None:
    
    path = Path("data/polls.js")
    content = path.read_text(encoding="utf-8")
    prefix = "window.POLLS = "
    if prefix not in content:
        raise SystemExit("Unexpected generated file format")
    payload_text = content.split(prefix, 1)[1].rsplit(";", 1)[0]
    payload = json.loads(payload_text)

    if not isinstance(payload.get("polls"), list):
        raise SystemExit("Invalid polls payload")
    if not payload["polls"]:
        raise SystemExit("No polls were generated")

    required_fields = {"firm", "url", "start", "date", "sample", "scenarios"}
    for i, poll in enumerate(payload["polls"]):
        missing = required_fields - poll.keys()
        if missing:
            raise SystemExit(
                f"Poll {i + 1} is missing fields: {', '.join(sorted(missing))}"
            )

        if not poll["url"]:
            raise SystemExit(f"Poll {i + 1} has an empty URL")

        if poll["start"] > poll["date"]:
            print(
                f"::warning::Poll {i + 1} has start date after end date: "
                f"{poll['start']} > {poll['date']}"
            )
        print(f"Successfully validated {len(payload['polls'])} polls")

            
def validate_models() ->None:
    model_text = Path("data/model.js").read_text(encoding="utf-8")
    model = json.loads(model_text.split("window.MODEL = ", 1)[1].rsplit(";", 1)[0])
    if not model.get("candidates") or not model.get("sigma_first"):
        raise SystemExit("Invalid simulator model")
    if model["n_polls"] == 0:
        print("::warning::No 2027 poll in the last 21 days: simulator base unchanged")
    print(f"Simulator model as of {model['asof']}: {model['n_polls']} polls, {len(model['duels'])} duels")

def validate_socials() -> None:
    social_text = Path("data/social.js").read_text(encoding="utf-8")
    social = json.loads(social_text.split("window.SOCIAL = ", 1)[1].rsplit(";", 1)[0])
    for cid, nets in social["followers"].items():
        for net, acc in nets.items():
            for pt in acc["points"]:
                if not pt.get("source") or not isinstance(pt.get("value"), int) or pt["value"] <= 0:
                    raise SystemExit(f"Invalid follower point: {cid} {net} {pt}")
    print(f"Social data as of {social['updated']}")
   
    
def validate_engagement() -> None:
    eng_text = Path("data/engagement.js").read_text(encoding="utf-8")
    eng = json.loads(eng_text.split("window.ENGAGEMENT = ", 1)[1].rsplit(";", 1)[0])
    for cid, acc in eng["candidates"].items():
        for e in acc.get("history", []):
            if e.get("rate") is not None and not (0 <= e["rate"] < 100):
                raise SystemExit(f"Implausible engagement rate: {cid} {e['date']} {e['rate']}")
            if any("SAMPLE" in (p.get("url") or "") for p in e.get("posts", [])):
                raise SystemExit("Sample data found in data/engagement.js")
    print(f"Engagement data as of {eng['updated']}")
      
   
def validate_data():     
    validate_polls()
    validate_models()
    validate_socials()
    validate_engagement()


validate_data()



