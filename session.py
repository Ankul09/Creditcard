"""Multi-turn conversation: a short general answer first; tailored questions only if the customer wants them."""
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from answer import _has_amount, handle
from clarify import questions
from info import find_all_cards
from present import to_text
from recommender import Recommendation

YES_RE = re.compile(r"^\s*(yes|yeah|yep|yup|sure|ok(ay)?|please|go ahead|more|refine|tailor|y|why not|definitely)\b", re.I)
NO_RE = re.compile(r"^\s*(no|nope|nah|stop|done|that'?s? (all|enough|fine)|thanks?|thank you|fine|good|enough)\b", re.I)
DETAILS_RE = re.compile(r"\b(details?|explain|full answer|why|alternatives?|options)\b", re.I)
INCOME_NUM = re.compile(r"(\d+(?:\.\d+)?)\s*(lakh|lac|l\b|lpa|crore|cr\b|k\b)?", re.I)


def _income_from(text: str) -> Optional[float]:
    m = INCOME_NUM.search(text)
    if not m:
        return None
    num, unit = float(m.group(1)), (m.group(2) or "").lower()
    if unit in ("lakh", "lac", "l", "lpa"):
        return num * 1e5
    if unit in ("crore", "cr"):
        return num * 1e7
    if unit == "k":
        return num * 1e3 * (12 if num < 500 else 1)  # "80k" ~ monthly salary
    return num * 12 if num < 1e5 else num  # bare number: assume monthly if small


def _short(rec: Recommendation, held: bool) -> str:
    p = rec.primary
    if not p:
        return "I can't recommend a card with confirmed earning for this purchase yet."
    fee = p.card.get("annual_fee")
    fee_txt = "no annual fee" if not fee else f"annual fee ₹{fee:,}"
    lead = "Best among your cards" if held else "Best overall for this"
    others = [a.card["name"] for a in rec.alternatives[:2]]
    line = f"{lead}: {p.card['name']} (about ₹{p.total:,.0f} back, {fee_txt})."
    if others:
        line += f" Also worth a look: {' and '.join(others)}."
    return line


@dataclass
class Session:
    base_text: str = ""
    extra: List[str] = field(default_factory=list)
    held: Optional[List[str]] = None
    income: Optional[float] = None
    stage: Optional[str] = None  # "offer" | "asking" | None
    pending: List[Tuple[str, str]] = field(default_factory=list)  # (key, question)
    last_pick: Optional[str] = None
    last_result: Optional[dict] = None

    def text(self) -> str:
        return " ".join([self.base_text] + self.extra)


def _key(q: str) -> str:
    for k, needle in (("tentative", "confirmed"), ("airline", "airline are"), ("booking", "book directly"), ("intl", "domestic or"),
                      ("pump", "pump"), ("monthly_fuel", "each month"), ("jeweller", "jeweller"), ("coins", "gold coins"),
                      ("emi", "EMI"), ("site", "site or app"), ("prime", "Prime"), ("dining", "food delivery"),
                      ("store", "store or app"), ("channel", "online or in a store"), ("what", "What are you buying"),
                      ("recurring", "one-off"), ("held", "credit cards do you already hold"), ("income", "annual income")):
        if needle in q:
            return k
    return "other"


def _apply_answer(s: Session, key: str, ans: str, data: dict) -> None:
    low = ans.lower()
    if key == "held":
        names = [c["name"] for c in find_all_cards(ans, data["cards"])]
        if names:
            s.held = names
        return
    if key == "income":
        s.income = _income_from(ans)
        return
    if key == "tentative":
        if re.search(r"confirm|fixed|final|booked|certain|definite", low):
            s.extra.append("confirmed")
        elif re.search(r"tentative|might|may|not sure|unsure|flexible|change|maybe|yes", low):
            s.extra.append("tentative")
        return
    if key == "recurring":
        if re.search(r"month|every|recurr|regular|often|yes", low) and not re.search(r"one[- ]?off|once|single|no\b", low):
            s.extra.append("every month")
        return
    if key == "intl":
        if re.search(r"intern|abroad|overseas|foreign", low):
            s.extra.append("international")
        return
    if key in ("emi", "coins"):
        s.extra.append(("on emi" if re.search(r"\bemi\b|install", low) else "") + (" gold coins" if re.search(r"coin|bar", low) else ""))
        return
    s.extra.append(ans)  # airline, booking channel, pump, jeweller, site, what, channel...


def reply(s: Session, text: str, data: dict) -> str:
    msg = text.strip()

    if s.stage == "offer":
        if YES_RE.match(msg):
            s.stage = "asking"
            return _ask_next(s, "Great, a few quick questions.")
        if NO_RE.match(msg):
            s.stage = None
            return "Okay. Ask me about another purchase any time."
        if DETAILS_RE.match(msg) and s.last_result:
            return to_text(s.last_result["rec"])
    elif s.stage == "asking":
        key, _ = s.pending[0]
        new_purchase = _has_amount(msg) and key != "income" and not YES_RE.match(msg)
        if NO_RE.match(msg) and key != "income":
            s.stage = None
            return "No problem. " + (f"My answer stays: {s.last_pick}." if s.last_pick else "")
        if not new_purchase:
            s.pending.pop(0)
            _apply_answer(s, key, msg, data)
            return _refresh(s, data)

    # a new question or purchase
    s.__init__()
    s.base_text = msg
    res = handle(msg, data)
    if res["type"] != "recommendation":
        return res["text"]
    s.held = res.get("held")
    s.last_result = res
    s.last_pick = res["rec"].primary.card["name"] if res["rec"].primary else None
    s.pending = [(_key(q), q) for q in res["questions"]]
    s.stage = "offer" if s.pending else None
    out = _short(res["rec"], bool(res.get("held")))
    if s.pending:
        out += "\n\nThis is a general answer. Want a more tailored one? Say 'yes' and I'll ask a few quick questions (or 'details' for the full breakdown)."
    return out


def _refresh(s: Session, data: dict) -> str:
    res = handle(s.text(), data, held=s.held, income=s.income)
    if res["type"] != "recommendation":
        return res["text"]
    s.last_result = res
    s.held = res.get("held") or s.held
    new_pick = res["rec"].primary.card["name"] if res["rec"].primary else None
    note = ""
    if new_pick and new_pick != s.last_pick:
        note = f"Updated pick: {new_pick} (was {s.last_pick}).\n" if s.last_pick else f"Pick: {new_pick}.\n"
    elif new_pick:
        note = f"Still {new_pick}.\n"
    unchanged = bool(new_pick) and new_pick == s.last_pick
    s.last_pick = new_pick or s.last_pick
    detail = "" if unchanged else _short(res["rec"], bool(s.held))
    if s.pending:
        return (note + detail).rstrip() + "\n\n" + _next_question(s)
    s.stage = None
    return note + detail + "\n\nThat's all I need. Ask me about another purchase any time."


def _next_question(s: Session) -> str:
    return f"Question: {s.pending[0][1]}  (say 'done' any time to stop)"


def _ask_next(s: Session, lead: str) -> str:
    return f"{lead}\n{_next_question(s)}" if s.pending else "Nothing more to ask."


class Sessions:
    """In-memory sessions keyed by an id (CLI uses one; the web page sends one per browser)."""

    def __init__(self) -> None:
        self._s: Dict[str, Session] = {}

    def get(self, sid: str) -> Session:
        return self._s.setdefault(sid, Session())
