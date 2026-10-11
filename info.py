"""Answer questions about a specific card from the database (templated, no free text)."""
import re
from typing import List, Optional

STOP = {"credit", "card", "cards", "bank", "the", "of", "india", "a", "and", "with", "by", "for", "in", "from"}
INTENTS = [  # (intent, keywords) - first match wins
    ("waiver", ["waive", "waived", "waiver"]),
    ("fee", ["annual fee", "joining fee", "fee", "fees", "charges", "cost", "price"]),
    ("lounge", ["lounge", "airport"]),
    ("forex", ["forex", "foreign", "international markup", "markup"]),
    ("jewellery", ["jewellery", "jewelry", "gold"]),
    ("rewards", ["reward", "rewards", "cashback", "cash back", "earn", "points", "miles", "rate"]),
    ("status", ["available", "apply", "still", "discontinued", "closed", "active", "status"]),
]


def _tokens(s: str) -> set:
    return {w for w in re.sub(r"[^a-z0-9+]", " ", s.lower()).split() if w not in STOP}


def find_cards(text: str, cards: List[dict], min_score: float = 0.99) -> List[dict]:
    """Cards whose name tokens all appear in the text; the longest/most specific names win."""
    q = _tokens(text)
    hits = []
    for c in cards:
        t = _tokens(c["name"])
        if t and len(t & q) / len(t) >= min_score and len(t) >= 2:
            hits.append((len(t), c.get("confidence") == "high", c.get("confidence") == "medium", c))
    if not hits:
        return []
    top = max(h[0] for h in hits)
    best = [h for h in hits if h[0] == top]
    best.sort(key=lambda h: (h[1], h[2]), reverse=True)
    return [h[3] for h in best]


def intent_of(text: str) -> str:
    low = text.lower()
    for name, kws in INTENTS:
        if any(re.search(r"(?<![a-z])" + re.escape(k) + r"(?![a-z])", low) for k in kws):
            return name
    return "summary"


def _inr(v) -> str:
    return "not found" if v is None else f"₹{v:,.0f}"


def _pct(v) -> str:
    if v is None:
        return "not found"
    return f"{v * 100:.2f}".rstrip("0").rstrip(".") + "%"


def _status_text(s: str) -> str:
    return {"closed_to_new": "closed to new applicants"}.get(s, s)


def answer(card: dict, intent: str) -> str:
    n = card["name"]
    lines: List[str] = []
    if intent == "fee":
        lines.append(f"{n}: joining fee {_inr(card.get('joining_fee'))}, annual fee {_inr(card.get('annual_fee'))}.")
        if card.get("fee_waiver_spend"):
            lines.append(f"Annual fee waived on spends of {_inr(card['fee_waiver_spend'])} a year.")
        if card.get("lifetime_free"):
            lines.append("Listed as lifetime free.")
    elif intent == "waiver":
        w = card.get("fee_waiver_spend")
        lines.append(f"{n}: annual fee {_inr(card.get('annual_fee'))}; " +
                     (f"waived on {_inr(w)} of annual spend." if w else "no waiver threshold found."))
    elif intent == "lounge":
        lines.append(f"{n}: " + (card.get("lounge_access") or "lounge access not found in our data."))
    elif intent == "forex":
        lines.append(f"{n}: forex markup {_pct(card.get('forex_markup'))}.")
    elif intent == "jewellery":
        ex = "jewellery" in (card.get("excludes") or []) or "gold" in (card.get("excludes") or [])
        rule = next((r for r in card.get("rules", []) if "jewellery" in r.get("categories", [])), None)
        if ex:
            lines.append(f"{n}: jewellery/gold spends earn no rewards.")
        elif rule:
            lines.append(f"{n}: jewellery earns about {_pct(rule['rate'])}" +
                         (f" (cap ₹{rule['cap_inr']:,.0f}/month)." if rule.get("cap_inr") else "."))
        else:
            lines.append(f"{n}: jewellery treatment is not stated in our data; check the card's terms.")
    elif intent == "rewards":
        lines.append(f"{n}: " + (card.get("main_benefit") or "reward details not found."))
        for r in card.get("rules", [])[:4]:
            where = ", ".join(r.get("merchants") or r.get("categories") or [])
            cap = f", cap ₹{r['cap_inr']:,.0f}/month" if r.get("cap_inr") else ""
            lines.append(f"  - {where}: ~{_pct(r.get('rate'))}{cap}")
        if card.get("base_rate") is not None:
            lines.append(f"  - everything else: ~{_pct(card['base_rate'])}")
    elif intent == "status":
        lines.append(f"{n}: status: {_status_text(card.get('status', 'unknown'))}.")
    else:
        lines.append(f"{n} ({card.get('issuer')}): {card.get('main_benefit') or 'summary not found.'}")
        lines.append(f"Annual fee {_inr(card.get('annual_fee'))}"
                     + (f", waived at {_inr(card['fee_waiver_spend'])} spend" if card.get("fee_waiver_spend") else "")
                     + (f". Lounge: {card['lounge_access']}" if card.get("lounge_access") else "") + ".")
        for b in (card.get("key_benefits") or [])[:4]:
            lines.append(f"  - {b}")
    status = card.get("status", "unknown")
    if status in ("discontinued", "closed_to_new"):
        lines.append("Note: this card is " + ("discontinued" if status == "discontinued" else "closed to new applicants") + " and can't be newly applied for.")
    lines.append(f"(Data confidence: {card.get('confidence', 'low')}, unverified. Please confirm on the bank's website.)")
    return "\n".join(lines)


def lookup(text: str, cards: List[dict]) -> Optional[str]:
    hits = find_cards(text, cards)
    if not hits:
        return None
    return answer(hits[0], intent_of(text))
