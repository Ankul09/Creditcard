"""Rank credit cards for a purchase using deterministic reward math."""
import json
import os
from datetime import date
from dataclasses import dataclass
from typing import List, Optional

UNAVAILABLE = {"discontinued", "closed_to_new"}  # cannot be newly applied for
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
        if rule.get("rate") is None:
            continue
        if p.amount < (rule.get("min_txn_inr") or 0):
            continue
        if rule.get("max_txn_inr") and p.amount > rule["max_txn_inr"]:
            continue
        merchants = [m.lower() for m in rule["merchants"]]
        if merchants:  # merchant-locked rule: only earns at those merchants
            hit = bool(p.merchant) and p.merchant.lower() in merchants
        else:
            hit = bool(p.category) and p.category in rule["categories"]
        if hit and (best is None or rule["rate"] > best["rate"]):
            best = rule
    return best


def best_offer(card: dict, p: Purchase, offers: List[dict], today: Optional[date] = None):
    today = today or date.today()
    best_val, best_desc = 0.0, ""
    for o in offers:
        if card["name"] not in o.get("cards", [o["card"]]) or p.amount < (o.get("min_spend") or 0):
            continue
        if o.get("valid_till") and date.fromisoformat(o["valid_till"]) < today:
            continue
        merchants = [m.lower() for m in o["merchants"]]
        if merchants:  # merchant-locked offer
            if not (p.merchant and p.merchant.lower() in merchants):
                continue
        elif not (p.category and p.category in o["categories"]):
            continue
        if "making charges" in o.get("desc", "").lower():
            continue  # discount applies to making charges only; share of bill unknown
        val = o["value"] if o["type"] == "flat" else p.amount * o["value"]
        val = min(val, o.get("cap_inr") or val)
        if val > best_val:
            best_val, best_desc = val, o["desc"]
    return best_val, best_desc


def evaluate(card: dict, p: Purchase, offers: Optional[List[dict]] = None) -> Result:
    offer, offer_desc = best_offer(card, p, offers or [])
    rule = _matching_rule(card, p)
    if rule is None and p.category in card.get("excludes", []):
        return Result(card, 0.0, 0.0, f"{p.category} excluded from rewards", offer, offer_desc)
    if rule is None:
        reward = p.amount * (card.get("base_rate") or 0)
        reason = f"base rate {(card.get('base_rate') or 0):.1%}"
    else:
        cap = rule.get("cap_inr")
        boosted = p.amount * rule["rate"]
        if cap is not None:
            boosted = min(boosted, cap)
        # Spend beyond the cap earns the base rate.
        capped_spend = boosted / rule["rate"] if rule["rate"] else p.amount
        reward = boosted + (p.amount - capped_spend) * (card.get("base_rate") or 0)
        reason = f"{rule['rate']:.1%} on this category"
        if cap is not None:
            reason += f" (cap ₹{cap:,}/month)"
            if boosted >= cap:
                reason += ", cap reached"
    return Result(card, reward, reward / p.amount if p.amount else 0, reason, offer, offer_desc)


def rank(p: Purchase, data: Optional[dict] = None) -> List[Result]:
    data = data or load_data()
    available = [c for c in data["cards"] if c.get("status") not in UNAVAILABLE]
    results = (evaluate(c, p, data.get("offers", [])) for c in available)
    return sorted(results, key=lambda r: r.total, reverse=True)
