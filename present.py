"""Turn a Recommendation into plain text / JSON for the CLI and web page."""
from typing import List

from recommender import Purchase, Recommendation, Result


def _row(r: Result, p: Purchase) -> dict:
    c = r.card
    return {
        "name": c["name"], "value": round(r.total), "net": round(r.net(p)), "reason": r.reason,
        "best_value": round(r.reward_best + r.offer) if r.reward_best else None,
        "fee": c.get("annual_fee"), "fee_waived": r.fee_waived(p), "confidence": c.get("confidence", "low"),
        "status": c.get("status", "unknown"), "offer": r.offer_desc, "benefit": c.get("main_benefit"),
        "notes": r.notes + ([c["eligibility"]] if c.get("eligibility") else []),
        "verified": bool(c.get("last_verified")),
    }


def to_dict(rec: Recommendation) -> dict:
    p = rec.purchase
    return {
        "purchase": {"amount": p.amount, "category": p.category, "merchant": p.merchant,
                     "channel": p.channel, "monthly": p.monthly},
        "primary": _row(rec.primary, p) if rec.primary else None,
        "alternatives": [_row(r, p) for r in rec.alternatives],
        "flagged": [_row(r, p) for r in rec.flagged],
        "hidden": [{"name": r.card["name"], "status": r.card.get("status"), "value": round(r.total)} for r in rec.hidden],
    }


def to_text(rec: Recommendation) -> str:
    d = to_dict(rec)
    p = d["purchase"]
    if not d["primary"]:
        return "I couldn't find a card with reliable data for this purchase."
    b = d["primary"]
    occ = 12 if p["monthly"] or p["category"] in ("fuel", "groceries", "dining", "bill_payments", "online_shopping") else 1
    per = f"over a year if you repeat this monthly" if occ == 12 else "after the first-year fee"
    lines: List[str] = [
        f"Best card: {b['name']}",
        f"  ~₹{b['value']:,} back on ₹{p['amount']:,.0f} ({b['reason']}); annual fee "
        f"{'₹%s' % format(b['fee'], ',') if b['fee'] is not None else 'unknown'}"
        f"{' (waived at this spend)' if b['fee_waived'] else ''}. Net {per}: ₹{b['net']:,}",
    ]
    if b["best_value"]:
        lines.append(f"  Up to ~₹{b['best_value']:,} with the best redemption (transfers/travel).")
    for n in b["notes"]:
        lines.append(f"  Note: {n}")
    lines.append(f"  Data confidence: {b['confidence']}" + ("" if b["verified"] else " (not human-verified)"))
    d["alternatives"] = [a for a in d["alternatives"] if a["value"] > 0 and a["net"] > 0]
    if d["alternatives"]:
        lines.append("Alternatives:")
        for a in d["alternatives"][:4]:
            lines.append(f"  - {a['name']}: ~₹{a['value']:,} (net ₹{a['net']:,}, {a['confidence']})")
    if d["flagged"]:
        lines.append("Higher on paper but not recommended (unverified, invite-only or restricted):")
        for a in d["flagged"][:3]:
            why = "invite-only/restricted" if any(k in " ".join(a["notes"]).lower() for k in ("invite", "navy", "army", "armed")) else "low-confidence data"
            lines.append(f"  - {a['name']}: ~₹{a['value']:,} ({why})")
    if d["hidden"]:
        lines.append("Not shown because applications are closed: " + ", ".join(h["name"] for h in d["hidden"]))
    return "\n".join(lines)
