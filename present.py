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
        "verified": bool(c.get("last_verified")), "conditional": r.conditional, "eligibility": c.get("eligibility"), "speculative": r.speculative,
    }


def to_dict(rec: Recommendation) -> dict:
    p = rec.purchase
    return {
        "purchase": {"amount": p.amount, "category": p.category, "merchant": p.merchant,
                     "channel": p.channel, "monthly": p.monthly, "tentative": p.tentative},
        "primary": _row(rec.primary, p) if rec.primary else None,
        "alternatives": [_row(r, p) for r in rec.alternatives],
        "flagged": [_row(r, p) for r in rec.flagged],
        "trip_cover": [dict(_row(r, p), cover=r.card["trip_cancellation"].get("cover_inr"),
                            claims=r.card["trip_cancellation"].get("max_claims"),
                            cover_note=r.card["trip_cancellation"].get("conditions")) for r in rec.trip_cover],
        "if_eligible": [_row(r, p) for r in rec.if_eligible],
        "fee_heavy": [_row(r, p) for r in rec.fee_heavy],
        "hidden": [{"name": r.card["name"], "status": r.card.get("status"), "value": round(r.total)} for r in rec.hidden],
    }


def to_text(rec: Recommendation) -> str:
    d = to_dict(rec)
    p = d["purchase"]
    if not d["primary"]:
        hint = " Which pump or merchant is it? Card offers differ by merchant." if p["category"] in ("fuel", "jewellery") and not p["merchant"] else ""
        return "I can't recommend a card with confirmed earning for this purchase." + hint
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
    if p["category"] == "fuel" and not p["merchant"]:
        lines.append("  Tip: tell me your pump (IndianOil, HPCL, BPCL, Jio-bp, Shell). Pump-specific cards earn 4-7%, far more than this.")
    lines.append(f"  Data confidence: {b['confidence']}" + ("" if b["verified"] else " (not human-verified)"))
    heavy_names = {a["name"] for a in d["fee_heavy"]}
    d["alternatives"] = [a for a in d["alternatives"] if a["value"] > 0 and a["net"] > 0 and a["name"] not in heavy_names]
    if d["alternatives"]:
        lines.append("Alternatives:")
        for a in d["alternatives"][:4]:
            lines.append(f"  - {a['name']}: ~₹{a['value']:,} (net ₹{a['net']:,}, {a['confidence']})")
    if d["trip_cover"]:
        head = ("Your plan may change, so this pick comes from cards with trip cancellation cover."
                if p.get("tentative") else "If your plans might change (trip cancellation cover):")
        lines.append(head)
        for a in d["trip_cover"]:
            cover = f"up to ₹{a['cover']:,}" if a["cover"] else "amount unconfirmed"
            share = f" (about {min(100, round(100 * a['cover'] / p['amount']))}% of this ticket)" if a["cover"] and p["amount"] else ""
            claims = f", {a['claims']} claims" if a["claims"] else ""
            lines.append(f"  - {a['name']}: cover {cover}{claims}{share}; fee ₹{a['fee']:,}; earns ~₹{a['value']:,} here")
        lines.append("  Covers only the non-refundable part, cancellations at least 24 hours before travel, a limited number of "
                     "claims; confirm the current policy and covered reasons with the bank.")
    if d["if_eligible"]:
        lines.append("Higher return if you qualify (not open to everyone):")
        for a in d["if_eligible"]:
            fee = f"₹{a['fee']:,}" if a["fee"] is not None else "unknown"
            who = a.get("eligibility") or "restricted eligibility (see card terms)"
            lines.append(f"  - {a['name']}: ~₹{a['value']:,} gross, annual fee {fee}. Eligibility: {who}")
    if d["fee_heavy"]:
        lines.append("Higher return but the annual fee outweighs it for a single purchase (worth it if you repeat this spend):")
        for a in d["fee_heavy"]:
            fee = f"₹{a['fee']:,}" if a["fee"] is not None else "unknown"
            lines.append(f"  - {a['name']}: ~₹{a['value']:,} gross, annual fee {fee}")
    if d["flagged"]:
        lines.append("Higher on paper but not recommended (unverified data):")
        for a in d["flagged"][:3]:
            joined = " ".join(a["notes"]).lower()
            why = ("invite-only/restricted" if any(k in joined for k in ("invite", "navy", "army", "armed"))
                   else "earning on this category unconfirmed" if "not confirmed" in joined or "unconfirmed" in joined
                   else "low-confidence data")
            lines.append(f"  - {a['name']}: ~₹{a['value']:,} ({why})")
    if d["hidden"]:
        lines.append("Not shown because applications are closed: " + ", ".join(h["name"] for h in d["hidden"]))
    return "\n".join(lines)
