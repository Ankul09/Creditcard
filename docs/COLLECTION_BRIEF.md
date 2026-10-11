# Card collection brief (shared by all collector agents)

Goal: a COMPLETE database of every credit card available in the Indian market, including co-branded and
fintech cards, with each card's main benefit. Completeness matters more than depth: a missing card is the
worst failure (an earlier pass missed RBL IndianOil, IndianOil Axis, IDFC HPCL, etc.).
Today's date for data purposes: 2026-10-11.

## Process (two phases, in order)
1. ENUMERATE. For each issuer assigned to you, build the full list of cards, from at least THREE independent
   places: (a) the issuer's own credit-card listing/compare pages, (b) aggregator index pages (cardadvisor.in,
   bankbazaar.com, paisabazaar.com, cardtrail.in, cardexpress.in, wishfin.com), (c) searches for co-brand
   partners ("<issuer> co-branded credit card", "<issuer> <airline|oil company|retailer|app> credit card").
   Search explicitly for these co-brand families under your issuer: fuel (IndianOil, BPCL, HPCL, Shell, Jio-bp),
   airlines (Air India, IndiGo, Vistara, Akasa, Emirates, Singapore), hotels (Marriott, Taj, IHG, Club Marriott),
   travel (MakeMyTrip, Yatra, Cleartrip, EaseMyTrip, IRCTC, Ixigo), retail/e-commerce (Amazon, Flipkart,
   Myntra, Tata Neu/Croma, Reliance, Shoppers Stop, Lifestyle, Pantaloons, Titan, Tanishq, Big Basket, Swiggy,
   Zomato), telcos (Airtel, Jio), fintech/UPI (Paytm, PhonePe, Slice, Uni, Jupiter, Fi, OneCard, Scapia,
   super.money, Cred), sports (Manchester United, CSK, RCB), healthcare, corporate/business cards,
   secured/FD-backed cards, student/entry cards, credit-line-on-UPI cards, and metal/premium/invite-only cards.
   Include cards that are closed to new applicants or discontinued, with `status` set accordingly (do not drop them).
   Write the enumeration into the output file's `catalog` array first (name, status, source).
2. DETAIL. For every card in the catalog, fill the card record below. Verify each card exists today
   (status active | closed_to_new | discontinued | unknown).

## Sources
Prefer official issuer pages and MITC/T&C PDFs. Domains moved: hdfc.bank.in, icici.bank.in, axis.bank.in.
WebFetch fails on cross-host redirects: retry with the redirect URL, or `curl -L -A "Mozilla/5.0" -o <file> <url>`
via Bash. For PDFs use `pdftotext -layout` if installed, else `python3 -I` with pypdf if available.
WebSearch is US-only but returns Indian sites. Fall back to aggregators: source_type third_party, confidence low.
Put downloaded files only under the scratchpad / your own temp directory, never in the project.

## Rules
- NEVER invent numbers. If a figure is not found, set it to null (or omit the rule) and say so in `notes`.
- Record source conflicts in `notes` and keep the more conservative figure.
- Reuse the EXACT existing card name if the card already exists in data/cards.json (read it first; print the
  names for your issuers) so the merge replaces rather than duplicates. Do not drop existing cards: re-confirm
  or improve them. Do not downgrade a record that already has higher confidence unless you found it wrong.
- Cards belonging to another collector's issuers: skip them (listed in your assignment).
- Write ONLY your assigned output file(s) in /Users/ankul.gupta/Downloads/Creditcard_ai/data/banks/. Never edit
  any other file.

## Card record schema (one JSON object per card)
name, issuer, network (Visa|Mastercard|RuPay|Amex|Diners|null), status, co_brand_partner (null if none),
tier (entry|mid|premium|super_premium|business|secured|other), lifetime_free (bool|null),
joining_fee, annual_fee, fee_waiver_spend, forex_markup (fraction), lounge_access (short text or null),
main_benefit (ONE sentence: what this card is best for and its headline reward),
key_benefits (list of short strings: milestones, vouchers, welcome benefits, fee waivers),
base_rate, rules[{merchants[], categories[], rate, cap_inr?, desc}], excludes[],
source_url, source_type (official|third_party), sources[], data_status "unverified",
confidence (low|medium|high), retrieved_on "2026-10-11", last_verified null, notes.

Modelling rules (the recommender depends on these):
- `rate` = effective INR reward value as a fraction of spend (0.05 = 5%). State the point value you assumed in `desc`.
- `cap_inr` = max reward VALUE (INR) per month; convert point caps; omit if unknown. Quarterly caps: note in desc.
- A rule that only works at certain merchants/pumps/apps MUST list them lowercase in `merchants`; otherwise
  `merchants` is [] and `categories` applies. Categories: jewellery, online_shopping, dining, travel, groceries,
  fuel, bill_payments, international, other (use the closest; add specifics via merchants).
- `excludes` = categories earning nothing (jewellery, fuel, rent, wallet_load, utilities, insurance, education,
  government, emi, gaming, upi ...). Check explicitly whether jewellery/gold is excluded (MCC 5944/5094).
- Per-transaction limits and minimum transaction sizes go in desc and, if present, as rule keys
  `min_txn_inr` / `max_txn_inr`.
- Fuel surcharge waivers: put in desc (with cap), not in `rate`.

## Output file format
{"catalog":[{"name","status","source"}], "cards":[...], "offers":[], "gaps":["things not found / unsure"]}
Offers (optional): only currently valid ones (valid_till >= 2026-10-11): card, merchants[], categories[],
type percent|flat, value (fraction for percent), min_spend, cap_inr, valid_till, desc, source_url, last_verified null.
