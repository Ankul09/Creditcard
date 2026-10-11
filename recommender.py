"""Rank credit cards for a purchase using deterministic reward math."""
import json
import os
from datetime import date
from dataclasses import dataclass
from typing import List, Optional

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "cards.json")


@dataclass
class Purchase:
    amount: float
    category: Optional[str] = None
    merchant: Optional[str] = None


@dataclass
class Result:
    card: dict
    reward: float
    rate: float
    reason: str
    offer: float = 0.0
    offer_desc: str = ""

    @property
    def total(self) -> float:
        return self.reward + self.offer


def load_data(path: str = DATA_PATH) -> dict:
    with open(path) as f:
        return json.load(f)


def load_cards(path: str = DATA_PATH) -> List[dict]:
    return load_data(path)["cards"]


def _matching_rule(card: dict, p: Purchase) -> Optional[dict]:
    best = None
    for rule in card["rules"]:
        hit = (p.merchant and p.merchant.lower() in rule["merchants"]) or (
            p.category and p.category in rule["categories"]
        )
        if hit and (best is None or rule["rate"] > best["rate"]):
            best = rule
    return best


def best_offer(card: dict, p: Purchase, offers: List[dict], today: Optional[date] = None):
    today = today or date.today()
    best_val, best_desc = 0.0, ""
    for o in offers:
        if o["card"] != card["name"] or p.amount < o.get("min_spend", 0):
            continue
        if o.get("valid_till") and date.fromisoformat(o["valid_till"]) < today:
            continue
        if not ((p.merchant and p.merchant.lower() in o["merchants"])
                or (p.category and p.category in o["categories"])):
            continue
        val = o["value"] if o["type"] == "flat" else p.amount * o["value"]
        val = min(val, o.get("cap_inr", val))
        if val > best_val:
            best_val, best_desc = val, o["desc"]
    return best_val, best_desc


def evaluate(card: dict, p: Purchase, offers: Optional[List[dict]] = None) -> Result:
    offer, offer_desc = best_offer(card, p, offers or [])
    if p.category in card.get("excludes", []):
        return Result(card, 0.0, 0.0, f"{p.category} excluded from rewards", offer, offer_desc)
    rule = _matching_rule(card, p)
    if rule is None:
        reward = p.amount * card["base_rate"]
        reason = f"base rate {card['base_rate']:.1%}"
    else:
        boosted = min(p.amount * rule["rate"], rule["cap_inr"])
        # Spend beyond the cap earns the base rate.
        capped_spend = boosted / rule["rate"]
        reward = boosted + (p.amount - capped_spend) * card["base_rate"]
        reason = f"{rule['rate']:.1%} on this category (cap ₹{rule['cap_inr']:,}/month)"
        if boosted >= rule["cap_inr"]:
            reason += ", cap reached"
    return Result(card, reward, reward / p.amount if p.amount else 0, reason, offer, offer_desc)


def rank(p: Purchase, data: Optional[dict] = None) -> List[Result]:
    data = data or load_data()
    results = (evaluate(c, p, data.get("offers", [])) for c in data["cards"])
    return sorted(results, key=lambda r: r.total, reverse=True)
