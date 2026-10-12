"""Follow-up questions the agent asks, based on what the customer has and hasn't told us."""
import re
from typing import List

from recommender import Purchase

AIRLINES = ["indigo", "air india", "vistara", "akasa", "spicejet", "emirates", "qatar", "singapore", "lufthansa", "air asia"]
INTL_RE = re.compile(r"international|abroad|overseas|foreign|usa|uk|dubai|singapore|europe|thailand", re.I)
INCOME_RE = re.compile(r"(lpa|lakh)\s*(per|a)?\s*(year|annum|pa)|salary|income|earn", re.I)
PRIME_RE = re.compile(r"\bprime\b", re.I)


def questions(p: Purchase, text: str, max_q: int = 4) -> List[str]:
    low = text.lower()
    qs: List[str] = []
    cat = p.category

    if cat == "travel":
        if not p.tentative and not re.search(r"confirmed|fixed|final|booked", low):
            qs.append("Is the trip confirmed, or might your plans change? (Some cards, like IDFC FIRST Select/Wealth, include trip cancellation cover.)")
        if not any(a in low for a in AIRLINES):
            qs.append("Which airline are you flying? (Airline co-brand cards give bonuses on their own airline.)")
        if not p.merchant and not p.channel:
            qs.append("Will you book directly on the airline's site, through a travel app (MakeMyTrip, Scapia...) or a bank travel portal (HDFC SmartBuy, Axis Travel EDGE, HSBC Travel with Points)? The best card changes with this.")
        if not INTL_RE.search(low):
            qs.append("Is it a domestic or international trip? (Forex markup and international bonuses differ.)")
    elif cat == "fuel":
        if not p.merchant:
            qs.append("Which pump do you use (IndianOil, HPCL, BPCL, Jio-bp, Shell)? Pump-specific cards earn 4-7%.")
        if not p.monthly:
            qs.append("About how much do you spend on fuel each month? (Caps on pump cards are monthly.)")
    elif cat == "jewellery":
        if not p.merchant:
            qs.append("Which jeweller (Tanishq, Malabar, Kalyan, CaratLane...)? Most cards earn nothing on jewellery, but some have brand-specific rewards.")
        qs.append("Is it jewellery, or gold coins/bars? Is it a one-time purchase or a monthly gold scheme? (Coins, bars and schemes are often excluded.)")
        qs.append("Will you pay in full or on EMI? (EMI purchases usually earn nothing.)")
    elif cat == "online_shopping":
        if not p.merchant:
            qs.append("Which site or app (Amazon, Flipkart, Myntra, Swiggy...)? Several cards give 5% only on specific brands.")
        if p.merchant == "amazon" and not PRIME_RE.search(low):
            qs.append("Are you an Amazon Prime member? (ICICI Amazon Pay's 5% needs Prime; non-Prime gets 3%.)")
    elif cat == "dining":
        if not p.merchant:
            qs.append("Is it food delivery (Swiggy/Zomato) or a restaurant? Some cards reward only one of them.")
    elif cat == "groceries":
        if not p.merchant:
            qs.append("Which store or app (BigBasket, Blinkit, Zepto, a supermarket)? Rates differ by merchant.")
    else:
        if not p.channel:
            qs.append("Are you paying online or in a store? Several cards earn much more online.")
        qs.append("What are you buying (electronics, groceries, bills, travel...)? Specific categories often have higher rates than a flat card.")

    if not p.monthly and cat not in ("fuel", "groceries", "dining", "bill_payments") and not p.held:
        qs.append("Is this a one-off purchase, or will you spend about this much every month? (It decides whether an annual fee is worth paying.)")
    if not p.held:
        qs.append("Which credit cards do you already hold? I can then rank only those, since you've already paid their fees.")
        if not INCOME_RE.search(low):
            qs.append("What is your approximate annual income, and are you salaried or self-employed? (Many good cards have income or relationship requirements.)")
    # keep the most useful category questions, but always leave room for the 'cards you hold' question
    held_q = [q for q in qs if q.startswith("Which credit cards")]
    rest = [q for q in qs if q not in held_q]
    return rest[: max_q - len(held_q)] + held_q
