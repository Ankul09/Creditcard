"""Single entry point used by the CLI and the web server."""
import re
from typing import Optional

from clarify import questions
from info import find_all_cards, lookup
from parser import CURRENCY_RE, NUMBER_RE, OffTopic, parse
from present import to_dict, to_text
from recommender import recommend

HELD_RE = re.compile(r"\b(i\s+(have|hold|own|use|got)|i'?ve\s+got|my\s+cards?|already\s+(have|hold|own)|i\s+currently\s+(have|hold))\b", re.I)


def _has_amount(text: str) -> bool:
    return bool(CURRENCY_RE.search(text)) or any(float(n.group().replace(",", "")) >= 100 for n in NUMBER_RE.finditer(text))


def handle(text: str, data: dict) -> dict:
    """Returns {"type": "info"|"message"|"recommendation", ...}."""
    cards = data["cards"]
    held = [c["name"] for c in find_all_cards(text, cards)] if HELD_RE.search(text) else None
    if not _has_amount(text):
        info = lookup(text, cards)
        if info:
            return {"type": "info", "text": info}
    try:
        p = parse(text)
    except ValueError as e:
        kind = "refusal" if isinstance(e, OffTopic) else "message"
        return {"type": "message", "kind": kind, "text": str(e)}
    p.held = held or None
    rec = recommend(p, data)
    return {"type": "recommendation", "rec": rec, "questions": questions(p, text), "held": held}


def to_json(result: dict) -> dict:
    if result["type"] != "recommendation":
        return {"info": result["text"]} if result["type"] == "info" else {"error": result["text"]}
    out = to_dict(result["rec"])
    out["questions"] = result["questions"]
    out["held"] = result["held"]
    return out


def render(result: dict, explain: bool) -> str:
    if result["type"] != "recommendation":
        return result["text"]
    rec = result["rec"]
    if explain:
        body = to_text(rec)
    else:
        body = rec.primary.card["name"] if rec.primary else "No reliable recommendation for this purchase."
    if result["held"]:
        body = ("Among the cards you hold: " if rec.primary else "") + body
    if result["questions"]:
        body += "\n\nTo narrow this down, tell me:\n" + "\n".join(f"  {i}. {q}" for i, q in enumerate(result["questions"], 1))
    return body
