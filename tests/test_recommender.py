"""Known-answer tests for the reward model. Run: python3 -m unittest discover -s tests -v"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from recommender import Purchase, evaluate, is_restricted, recommend  # noqa: E402


def card(name="T", base=0.01, rules=None, **kw):
    c = {"name": name, "annual_fee": 0, "base_rate": base, "rules": rules or [], "excludes": [], "status": "active",
         "confidence": "high"}
    c.update(kw)
    return c


class RewardMath(unittest.TestCase):
    def test_flat_rule_with_cap_spills_to_base(self):
        c = card(rules=[{"merchants": [], "categories": ["online_shopping"], "rate": 0.05, "cap_inr": 2000}])
        r = evaluate(c, Purchase(100000, "online_shopping"))
        # 2000 at 5% (uses 40,000 of spend) + 60,000 at 1%
        self.assertAlmostEqual(r.reward, 2600)

    def test_tiers_like_axis_cashback(self):
        tiers = [{"from_inr": 0, "to_inr": 5000, "rate": 0.02}, {"from_inr": 5000, "to_inr": 40000, "rate": 0.05},
                 {"from_inr": 40000, "to_inr": None, "rate": 0.07}]
        c = card(base=0.0075, rules=[{"merchants": [], "categories": ["online_shopping"], "rate": 0.05,
                                      "tiers": tiers, "cap_inr": 4000}])
        self.assertAlmostEqual(evaluate(c, Purchase(30000, "online_shopping")).reward, 100 + 1250)
        self.assertAlmostEqual(evaluate(c, Purchase(100000, "online_shopping")).reward, 4000 + 0.0075 * (100000 - (40000 + (4000 - 1850) / 0.07)), places=2)

    def test_two_tier_points_magnus_style(self):
        tiers = [{"from_inr": 0, "to_inr": 150000, "rate": 0.012, "rate_best": 0.024},
                 {"from_inr": 150000, "to_inr": None, "rate": 0.035, "rate_best": 0.07}]
        c = card(rules=[{"merchants": [], "categories": ["other"], "rate": 0.012, "tiers": tiers}])
        r = evaluate(c, Purchase(300000, "other"))
        self.assertAlmostEqual(r.reward, 150000 * 0.012 + 150000 * 0.035)
        self.assertAlmostEqual(r.reward_best, 150000 * 0.024 + 150000 * 0.07)

    def test_merchant_locked_rule_does_not_apply_elsewhere(self):
        c = card(rules=[{"merchants": ["hpcl"], "categories": ["fuel"], "rate": 0.05}], excludes=["fuel"])
        self.assertAlmostEqual(evaluate(c, Purchase(3000, "fuel", "hpcl")).reward, 150)
        self.assertEqual(evaluate(c, Purchase(3000, "fuel", "bpcl")).reward, 0)
        self.assertEqual(evaluate(c, Purchase(3000, "fuel")).reward, 0)

    def test_exclusion_gives_zero(self):
        c = card(excludes=["jewellery"])
        self.assertEqual(evaluate(c, Purchase(300000, "jewellery")).reward, 0)

    def test_per_transaction_limit(self):
        c = card(rules=[{"merchants": [], "categories": ["fuel"], "rate": 0.05, "max_txn_inr": 2000}])
        self.assertAlmostEqual(evaluate(c, Purchase(1500, "fuel")).reward, 75)
        self.assertAlmostEqual(evaluate(c, Purchase(3000, "fuel")).reward, 30)

    def test_channel_rules(self):
        c = card(base=0.0, rules=[{"merchants": [], "categories": ["other"], "rate": 0.05, "channel": "online"},
                                  {"merchants": [], "categories": ["other"], "rate": 0.01, "channel": "offline"}])
        self.assertAlmostEqual(evaluate(c, Purchase(10000, "other", None, "offline")).reward, 100)
        self.assertAlmostEqual(evaluate(c, Purchase(10000, "other", None, "online")).reward, 500)

    def test_rule_with_unpriced_tiers_is_ignored_not_a_crash(self):
        c = card(base=None, rules=[{"merchants": [], "categories": ["other"], "rate": None,
                                    "tiers": [{"from_inr": 0, "to_inr": None, "rate": None, "points_per_100": 1}]}])
        r = evaluate(c, Purchase(10000, "other"))
        self.assertFalse(r.rated)

    def test_unknown_reward_structure_is_unrated(self):
        c = card(base=None)
        self.assertFalse(evaluate(c, Purchase(1000, "other")).rated)


class Policy(unittest.TestCase):
    def data(self, *cards):
        return {"cards": list(cards), "offers": []}

    def test_low_confidence_never_primary(self):
        good = card("Good", base=0.02, confidence="medium")
        flashy = card("Flashy", base=0.10, confidence="low")
        rec = recommend(Purchase(10000, "other"), self.data(good, flashy))
        self.assertEqual(rec.primary.card["name"], "Good")
        self.assertEqual([r.card["name"] for r in rec.flagged], ["Flashy"])

    def test_closed_cards_are_reported_not_silently_dropped(self):
        good = card("Good", base=0.02)
        closed = card("Closed", base=0.05, status="closed_to_new")
        rec = recommend(Purchase(10000, "other"), self.data(good, closed))
        self.assertEqual(rec.primary.card["name"], "Good")
        self.assertEqual([r.card["name"] for r in rec.hidden], ["Closed"])

    def test_invite_only_is_not_primary(self):
        pub = card("Public", base=0.02)
        inv = card("Invite", base=0.05, main_benefit="Invite-only premium card")
        self.assertTrue(is_restricted(inv))
        rec = recommend(Purchase(10000, "other"), self.data(pub, inv))
        self.assertEqual(rec.primary.card["name"], "Public")

    def test_fee_weighed_for_one_off_but_waived_for_big_recurring_spend(self):
        premium = card("Premium", base=0.033, annual_fee=12500, fee_waiver_spend=1000000)
        free = card("Free", base=0.02)
        one_off = recommend(Purchase(20000, "other"), self.data(premium, free))
        self.assertEqual(one_off.primary.card["name"], "Free")
        monthly = recommend(Purchase(300000, "other", monthly=True), self.data(premium, free))
        self.assertEqual(monthly.primary.card["name"], "Premium") if not is_restricted(premium) else None

    def test_recurring_category_spreads_fee_over_year(self):
        pump = card("Pump", base=0.0, annual_fee=500, rules=[{"merchants": ["hpcl"], "categories": ["fuel"], "rate": 0.05}])
        none = card("Plain", base=0.01)
        rec = recommend(Purchase(5000, "fuel", "hpcl"), self.data(pump, none))
        self.assertEqual(rec.primary.card["name"], "Pump")

    def test_base_rate_on_jewellery_is_speculative_not_primary(self):
        flat = card("Flat", base=0.05)  # no jewellery rule, no exclusion: do not assume it earns on jewellery
        safe = card("Safe", base=0.0, rules=[{"merchants": [], "categories": ["jewellery"], "rate": 0.01}])
        rec = recommend(Purchase(100000, "jewellery"), self.data(flat, safe))
        self.assertEqual(rec.primary.card["name"], "Safe")
        self.assertEqual([r.card["name"] for r in rec.flagged], ["Flat"])

    def test_conditional_rate_is_never_primary(self):
        cond = card("Cond", rules=[{"merchants": [], "categories": ["travel"], "rate": 0.05, "conditional": "direct booking"}])
        plain = card("Plain", base=0.02)
        rec = recommend(Purchase(100000, "travel"), self.data(cond, plain))
        self.assertEqual(rec.primary.card["name"], "Plain")
        self.assertEqual([r.card["name"] for r in rec.alternatives], ["Cond"])

    def test_no_reliable_card_gives_no_primary(self):
        rec = recommend(Purchase(5000, "fuel"), self.data(card("X", base=0.01)))
        self.assertIsNone(rec.primary)


if __name__ == "__main__":
    unittest.main()
