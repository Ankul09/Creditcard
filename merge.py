"""Merge data/banks/*.json into data/cards.json.

Later files (alphabetical) win on duplicate card names, except manual.json which loses to bank files.
Offers are deduplicated by (desc, valid_till, merchants) and dropped if expired.
"""
import glob
import json
import os
from datetime import date

ROOT = os.path.dirname(__file__)
today = date.today()
files = sorted(glob.glob(os.path.join(ROOT, "data", "banks", "*.json")))
files.sort(key=lambda f: os.path.basename(f) != "manual.json", reverse=False)  # manual first, so others override

CONF = {"high": 2, "medium": 1, "low": 0}


def _rank(c):
    """Higher confidence wins; ties go to the newer record (later file / later retrieved_on)."""
    return (CONF.get(c.get("confidence"), 0), c.get("retrieved_on") or "")


cards, offers, gaps = {}, {}, {}
for f in files:
    src = json.load(open(f))
    for c in src.get("cards", []):
        old = cards.get(c["name"])
        if old is None or _rank(c) >= _rank(old):
            cards[c["name"]] = c
    for o in src.get("offers", []):
        if o.get("valid_till") and date.fromisoformat(o["valid_till"]) < today:
            continue
        key = (o.get("desc"), o.get("valid_till"), tuple(o.get("merchants", [])))
        if key in offers:
            offers[key]["cards"].append(o["card"])
        else:
            offers[key] = dict(o, cards=[o["card"]])
    gaps[os.path.basename(f)] = src.get("gaps", [])

for c in cards.values():
    c.setdefault("status", "unknown")

out = {
    "_note": "Merged from data/banks/*.json by merge.py. Publicly sourced and UNVERIFIED; last_verified stays null until a human confirms a record. 'rate' = effective reward value as a fraction of spend; 'cap_inr' = max reward value per statement month (omitted if unknown); 'excludes' = categories earning nothing.",
    "cards": list(cards.values()),
    "offers": [dict(o, card=o["cards"][0]) for o in offers.values()],
    "gaps": gaps,
}
json.dump(out, open(os.path.join(ROOT, "data", "cards.json"), "w"), indent=2, ensure_ascii=False)
print(f"{len(cards)} cards, {len(offers)} live offers from {len(files)} files")
