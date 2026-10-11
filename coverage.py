"""Diff data/cards.json against data/audit/market_catalog.json (fuzzy name match)."""
import difflib
import json
import re
from collections import defaultdict

STOP = {"credit", "card", "cards", "bank", "the", "of", "india", "a", "and", "with", "lifetime", "free", "by"}


def norm(s):
    return " ".join(w for w in re.sub(r"[^a-z0-9 ]", " ", s.lower()).split() if w not in STOP)


db = json.load(open("data/cards.json"))["cards"]
audit = json.load(open("data/audit/market_catalog.json"))["cards"]
db_names = {norm(c["name"] + " " + c["issuer"]): c["name"] for c in db}
db_keys = list(db_names)
missing = []
for a in audit:
    key = norm(a["name"] if a["issuer"].lower().split()[0] in a["name"].lower() else a["issuer"] + " " + a["name"])
    key2 = norm(a["name"] + " " + a["issuer"])
    hit = difflib.get_close_matches(key, db_keys, n=1, cutoff=0.75) or difflib.get_close_matches(key2, db_keys, n=1, cutoff=0.75)
    if not hit:
        missing.append(a)
by = defaultdict(list)
for a in missing:
    by[a["issuer"]].append(a["name"])
print(f"audit {len(audit)} cards, db {len(db)}; audit cards with no fuzzy match: {len(missing)}")
for k, v in sorted(by.items(), key=lambda kv: -len(kv[1]))[:25]:
    print(f"{len(v):3d} {k}: {', '.join(v[:6])}")
json.dump(missing, open("data/audit/unmatched.json", "w"), indent=1, ensure_ascii=False)
