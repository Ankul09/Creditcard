"""Turn a free-text purchase description into a Purchase."""
import json
import os
import re
from typing import Optional

from recommender import Purchase

CATEGORIES = ["jewellery", "international", "bill_payments", "online_shopping", "dining", "travel", "groceries", "fuel", "other"]

KEYWORDS = {
    "jewellery": ["jewellery", "jewelry", "gold", "diamond", "tanishq", "malabar", "kalyan", "caratlane", "joyalukkas", "necklace", "ring"],
    "online_shopping": ["amazon", "flipkart", "myntra", "online", "shopping"],
    "dining": ["swiggy", "zomato", "restaurant", "dinner", "lunch", "food", "cafe"],
    "travel": ["flight", "hotel", "train", "makemytrip", "goibibo", "travel", "irctc"],
    "groceries": ["bigbasket", "blinkit", "zepto", "grocery", "groceries", "supermarket"],
    "fuel": ["petrol", "diesel", "fuel", "gas station"],
}
MERCHANTS = ["bpcl", "hpcl", "indianoil", "iocl", "tanishq", "malabar", "kalyan", "caratlane", "joyalukkas", "amazon", "flipkart", "myntra", "uber", "swiggy", "zomato", "bigbasket", "blinkit", "zepto"]


def _parse_amount(text: str) -> Optional[float]:
    m = re.search(r"(?:₹|rs\.?|inr)?\s*(\d[\d,]*(?:\.\d+)?)\s*(k|lakh|lac)?", text, re.I)
    if not m:
        return None
    value = float(m.group(1).replace(",", ""))
    unit = (m.group(2) or "").lower()
    return value * {"k": 1_000, "lakh": 100_000, "lac": 100_000}.get(unit, 1)


class OffTopic(ValueError):
    """The message isn't about choosing a credit card for a purchase."""


OFF_TOPIC_MESSAGE = (
    "I can only help you pick the best credit card for a purchase. "
    "Tell me what you're buying and roughly how much, e.g. 'Rs 5000 on Swiggy'."
)
OFF_TOPIC_WORDS = ["weather", "temperature", "rain", "forecast", "joke", "news", "score", "cricket",
                   "stock price", "recipe", "movie time", "who is", "what is the capital", "translate"]
PURCHASE_HINTS = ["buy", "purchase", "spend", "spending", "pay", "bill", "card", "shopping", "order", "book",
                  "rs", "inr", "rupee", "₹"]
CURRENCY_RE = re.compile(r"(₹|\brs\.?|\binr\b|\brupees?\b|\d\s*(k|lakh|lac)\b)", re.I)


def is_on_topic(text: str) -> bool:
    low = text.lower()
    has_money = bool(CURRENCY_RE.search(text))
    has_purchase_word = (
        any(re.search(r"\b" + re.escape(w) + r"\b", low) for w in PURCHASE_HINTS)
        or any(m in low for m in MERCHANTS)
        or any(k in low for kws in KEYWORDS.values() for k in kws)
    )
    if any(w in low for w in OFF_TOPIC_WORDS) and not has_money:
        return False
    return has_money or has_purchase_word


def parse_rules(text: str) -> Purchase:
    if not is_on_topic(text):
        raise OffTopic(OFF_TOPIC_MESSAGE)
    amount = _parse_amount(text)
    if amount is None:
        raise ValueError("How much are you planning to spend? e.g. 'Rs 5000 on Swiggy'.")
    low = text.lower()
    merchant = next((m for m in MERCHANTS if m in low), None)
    category = next((c for c, kws in KEYWORDS.items() if any(k in low for k in kws)), "other")
    return Purchase(amount, category, merchant)


def parse_llm(text: str) -> Purchase:
    """Use Claude for messy input. Requires ANTHROPIC_API_KEY and `pip install anthropic`."""
    import anthropic

    if not is_on_topic(text):
        raise OffTopic(OFF_TOPIC_MESSAGE)
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=os.environ.get("CARD_AI_MODEL", "claude-haiku-5-5"),
        max_tokens=200,
        system=(
            "Extract a purchase from the user's text. Reply with only JSON: "
            '{"amount": number in INR, "category": one of %s, "merchant": lowercase name or null}.'
            % CATEGORIES
        ),
        messages=[{"role": "user", "content": text}],
    )
    data = json.loads(msg.content[0].text)
    return Purchase(float(data["amount"]), data.get("category") or "other", data.get("merchant"))


def parse(text: str) -> Purchase:
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return parse_llm(text)
        except OffTopic:
            raise
        except Exception:
            pass  # fall back to the rule-based parser
    return parse_rules(text)
