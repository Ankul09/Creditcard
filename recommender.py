"""Rank credit cards for a purchase using deterministic reward math.

Model (see docs/COLLECTION_BRIEF.md, Addendum v2):
- rule.rate is the conservative INR value per rupee spent; rule.rate_best is the value at the best redemption.
- rule.tiers are spend bands within one month; rule.cap_inr caps the reward value of the boosted rule.
- rule.channel limits a rule to online/offline spend; merchant-locked rules only earn at those merchants.
- Cards with an unknown reward structure are never ranked; low-confidence cards are never the main answer.
"""
import json
import os
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional, Tuple

UNAVAILABLE = {"discontinued", "closed_to_new"}  # cannot be newly applied for
GST = 1.18
DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "cards.json")
RECURRING_CATEGORIES = {"fuel", "groceries", "dining", "bill_payments", "online_shopping"}  # repeat ~monthly
# Categories most cards exclude from base earn: a base rate is NOT evidence the card earns here.
SENSITIVE_CATEGORIES = {"jewellery", "fuel", "rent", "utilities", "insurance", "wallet_load", "government",
                        "education", "emi", "gaming", "toll", "gift_cards"}
RESTRICTED_NAME_HINTS = ("indian navy", "indian army", "indian air force", "assam rifles", "armed forces",
                         "icai", "doctor", "defence", "burgundy")


@dataclass
class Purchase:
    amount: float
    category: Optional[str] = None
    merchant: Optional[str] = None
    channel: Optional[str] = None  # "online" | "offline" | None (unknown)
    monthly: bool = False  # True: the user said the amount is a recurring monthly spend

    @property
    def occurrences(self) -> int:
        """Times per year we assume this spend repeats (used to weigh the annual fee)."""
        return 12 if self.monthly or self.category in RECURRING_CATEGORIES else 1


@dataclass
class Result:
    card: dict
    reward: float  # conservative reward value, INR, for this spend in one month
    rate: float
    reason: str
    offer: float = 0.0
    offer_desc: str = ""
    reward_best: Optional[float] = None  # at best redemption, if different
    notes: List[str] = field(default_factory=list)
    rated: bool = True
    speculative: bool = False  # earning on this category is not confirmed for the card
    conditional: Optional[str] = None  # the rate applies only under this condition

    @property
    def total(self) -> float:
        return self.reward + self.offer

    @property
    def fee(self) -> float:
        return (self.card.get("annual_fee") or 0) * GST

    def fee_waived(self, purchase: Purchase) -> bool:
        w = self.card.get("fee_waiver_spend")
        return bool(w) and purchase.amount * purchase.occurrences >= w

    def net(self, purchase: Purchase) -> float:
        """Value after the annual fee: per year for recurring spend, else for this one purchase."""
        fee = 0.0 if self.fee_waived(purchase) else self.fee
        return self.total * purchase.occurrences - fee


def load_data(path: str = DATA_PATH) -> dict:
    with open(path) as f:
        return json.load(f)


def load_cards(path: str = DATA_PATH) -> List[dict]:
    return load_data(path)["cards"]


# ---------------------------------------------------------------- rule matching

def _rule_matches(rule: dict, p: Purchase) -> bool:
    if rule.get("rate") is None and not rule.get("tiers"):
        return False
    if p.amount < (rule.get("min_txn_inr") or 0):
        return False
    if rule.get("max_txn_inr") and p.amount > rule["max_txn_inr"]:
        return False
    ch = rule.get("channel") or "any"
    if ch != "any" and p.channel and ch != p.channel:
        return False
    if rule.get("portal_only") and not p.merchant:
        return False
    merchants = [m.lower() for m in rule.get("merchants", [])]
    if merchants:  # merchant-locked rule: only earns at those merchants
        return bool(p.merchant) and p.merchant.lower() in merchants
    return bool(p.category) and p.category in rule.get("categories", [])


def _accrue(amount: float, rule: dict, key: str, base: float) -> Tuple[float, float]:
    """Reward value for `amount` under `rule` (key = 'rate' or 'rate_best'); returns (reward, boosted_spend)."""
    cap = rule.get("cap_inr")
    if rule.get("tiers"):
        bands = [(t.get("from_inr") or 0, t.get("to_inr"), t.get(key, t["rate"])) for t in rule["tiers"]]
    else:
        bands = [(0, None, rule.get(key) if rule.get(key) is not None else rule["rate"])]
    reward = spend_used = 0.0
    for lo, hi, rate in sorted(bands, key=lambda b: b[0]):
        if amount <= lo:
            break
        seg = min(amount, hi if hi is not None else amount) - lo
        if seg <= 0:
            continue
        value = seg * rate
        if cap is not None and reward + value > cap:
            room = max(cap - reward, 0.0)
            spend_used += room / rate if rate else seg
            reward = cap
            break
        reward += value
        spend_used += seg
    # spend beyond the boosted allowance earns the base rate
    return reward + max(amount - spend_used, 0.0) * base, spend_used


def _headline(rule: dict) -> str:
    if rule.get("tiers"):
        return "/".join(f"{t['rate']:.1%}" for t in sorted(rule["tiers"], key=lambda t: t.get("from_inr") or 0)) + " tiered"
    return f"{rule['rate']:.1%}"


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
    base = card.get("base_rate")
    rules = [r for r in card.get("rules", []) if _rule_matches(r, p)]
    notes: List[str] = []
    jewellery = p.category == "jewellery"
    if jewellery and card.get("jewellery_unconfirmed"):
        notes.append("jewellery treatment unconfirmed")

    if not rules:
        excluded = p.category in card.get("excludes", []) or (jewellery and "gold" in card.get("excludes", []))
        if excluded:
            return Result(card, 0.0, 0.0, f"{p.category} excluded from rewards", offer, offer_desc, notes=notes)
        if base is None:
            return Result(card, 0.0, 0.0, "reward rate unknown", offer, offer_desc, notes=notes, rated=False)
        reward = p.amount * base
        speculative = p.category in SENSITIVE_CATEGORIES
        if speculative:
            notes.append(f"earning on {p.category} is not confirmed for this card")
        # portal-only accelerators the customer could use instead
        for r in card.get("rules", []):
            if r.get("portal_only") and p.category in r.get("categories", []):
                notes.append(f"up to {_headline(r)} via portal")
        return Result(card, reward, base, f"base rate {base:.1%}", offer, offer_desc, notes=notes,
                      speculative=speculative)

    base_v = base or 0.0
    scored = []
    for r in rules:
        rew, used = _accrue(p.amount, r, "rate", base_v)
        scored.append((rew, used, r))
    reward, used, rule = max(scored, key=lambda s: s[0])
    best_rew, _ = _accrue(p.amount, rule, "rate_best", base_v)
    reason = f"{_headline(rule)} on this category"
    cap = rule.get("cap_inr")
    if cap is not None:
        reason += f" (cap ₹{cap:,.0f}/{rule.get('period', 'month')})"
        if reward - max(p.amount - used, 0.0) * base_v >= cap - 1e-6:
            reason += ", cap reached"
    if rule.get("desc") and ("quarter" in rule["desc"].lower() or "year" in rule["desc"].lower()):
        notes.append("check cap period in card terms")
    cond = rule.get("conditional") or None
    if cond:
        notes.append(f"applies only if: {cond}")
    return Result(card, reward, reward / p.amount if p.amount else 0, reason, offer, offer_desc,
                  reward_best=best_rew if best_rew > reward + 1e-6 else None, notes=notes, conditional=cond)


# ---------------------------------------------------------------- ranking policy

def is_restricted(card: dict) -> bool:
    text = " ".join([card.get("eligibility") or "", card["name"], card.get("main_benefit") or ""])
    low = text.lower()
    return "invite" in low or any(h in low for h in RESTRICTED_NAME_HINTS)


def rank(p: Purchase, data: Optional[dict] = None) -> List[Result]:
    """All available, rated cards sorted by net value (see Result.net)."""
    data = data or load_data()
    available = [c for c in data["cards"] if c.get("status") not in UNAVAILABLE]
    results = [evaluate(c, p, data.get("offers", [])) for c in available]
    return sorted((r for r in results if r.rated), key=lambda r: r.net(p), reverse=True)


@dataclass
class Recommendation:
    purchase: Purchase
    primary: Optional[Result]
    alternatives: List[Result]
    flagged: List[Result]  # beat the primary on paper but are unverified, invite-only or restricted
    hidden: List[Result]  # closed/discontinued cards that would have ranked above the primary


def recommend(p: Purchase, data: Optional[dict] = None, limit: int = 5) -> Recommendation:
    """Main answer = best net value among apply-able cards with medium/high confidence data."""
    data = data or load_data()
    solid, flagged = [], []
    for r in rank(p, data):
        c = r.card
        if r.speculative or c.get("confidence") not in ("high", "medium") or is_restricted(c):
            flagged.append(r)
        else:
            solid.append(r)
    unconditional = [r for r in solid if not r.conditional]
    primary = unconditional[0] if unconditional else None
    threshold = primary.net(p) if primary else float("-inf")
    flagged = [r for r in flagged if r.net(p) > threshold][:limit]
    hidden = []
    for c in data["cards"]:
        if c.get("status") in UNAVAILABLE:
            r = evaluate(c, p, data.get("offers", []))
            if r.rated and r.net(p) > threshold and c.get("confidence") in ("high", "medium"):
                hidden.append(r)
    hidden = sorted(hidden, key=lambda r: r.net(p), reverse=True)[:3]
    alternatives = [r for r in solid if r is not primary][:limit]
    return Recommendation(p, primary, alternatives, flagged, hidden)
