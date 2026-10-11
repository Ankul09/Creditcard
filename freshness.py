"""Validate card data and flag stale, unverified or expired records."""
from datetime import date, timedelta
from typing import List, Optional

MAX_AGE_DAYS = {"card": 90, "offer": 14}
CARD_FIELDS = ["name", "issuer", "annual_fee", "base_rate", "rules", "source_url", "last_verified"]
OFFER_FIELDS = ["card", "type", "value", "valid_till", "desc", "source_url", "last_verified"]


def _check_verified(kind: str, label: str, rec: dict, today: date, issues: List[str]) -> None:
    if not rec.get("source_url"):
        issues.append(f"{kind} {label}: missing source_url")
    lv = rec.get("last_verified")
    if not lv:
        issues.append(f"{kind} {label}: never verified")
    elif date.fromisoformat(lv) < today - timedelta(days=MAX_AGE_DAYS[kind]):
        issues.append(f"{kind} {label}: stale (verified {lv}, max age {MAX_AGE_DAYS[kind]}d)")


def validate(data: dict, today: Optional[date] = None) -> List[str]:
    today = today or date.today()
    issues: List[str] = []
    names = [c.get("name") for c in data["cards"]]
    for n in {n for n in names if names.count(n) > 1}:
        issues.append(f"duplicate card name: {n}")
    for c in data["cards"]:
        label = c.get("name", "?")
        issues += [f"card {label}: missing {f}" for f in CARD_FIELDS if f not in c]
        _check_verified("card", label, c, today, issues)
    for o in data.get("offers", []):
        label = o.get("desc", "?")
        issues += [f"offer {label}: missing {f}" for f in OFFER_FIELDS if f not in o]
        if o.get("card") not in names:
            issues.append(f"offer {label}: unknown card {o.get('card')}")
        if o.get("valid_till") and date.fromisoformat(o["valid_till"]) < today:
            issues.append(f"offer {label}: expired {o['valid_till']}")
        _check_verified("offer", label, o, today, issues)
    return issues
