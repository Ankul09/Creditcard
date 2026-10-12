"""Routing, follow-up questions and 'cards I hold'. Run: python3 -m unittest discover -s tests -v"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from answer import handle  # noqa: E402
from clarify import questions  # noqa: E402
from recommender import Purchase  # noqa: E402


def card(name, base=0.01, **kw):
    c = {"name": name, "issuer": "T", "annual_fee": 0, "base_rate": base, "rules": [], "excludes": [], "status": "active",
         "confidence": "high"}
    c.update(kw)
    return c


DATA = {"cards": [card("Alpha Rewards Card", 0.02), card("Beta Premium Card", 0.05, annual_fee=9999, confidence="medium"),
                  card("Gamma Plus Card", 0.01)], "offers": []}


class Routing(unittest.TestCase):
    def test_off_topic_is_refused(self):
        r = handle("what's the weather in pune", DATA)
        self.assertEqual((r["type"], r["kind"]), ("message", "refusal"))

    def test_card_info_question(self):
        r = handle("annual fee of Alpha Rewards Card", DATA)
        self.assertEqual(r["type"], "info")

    def test_purchase_gets_recommendation_and_questions(self):
        r = handle("Rs 5000 petrol", DATA)
        self.assertEqual(r["type"], "recommendation")
        self.assertTrue(any("pump" in q for q in r["questions"]))

    def test_held_cards_restrict_ranking(self):
        r = handle("Rs 20000 shopping, I have Alpha Rewards Card and Gamma Plus Card", DATA)
        self.assertEqual(r["rec"].primary.card["name"], "Alpha Rewards Card")
        self.assertEqual(sorted(r["held"]), ["Alpha Rewards Card", "Gamma Plus Card"])


class Questions(unittest.TestCase):
    def test_travel_asks_about_tentative_and_airline(self):
        qs = questions(Purchase(50000, "travel"), "flight ticket 50000")
        self.assertTrue(any("confirmed" in q for q in qs))
        self.assertTrue(any("airline" in q for q in qs))
        self.assertTrue(any(q.startswith("Which credit cards") for q in qs))

    def test_answered_questions_are_not_repeated(self):
        qs = questions(Purchase(50000, "travel", tentative=True), "indigo flight 50000 tentative international, directly on the airline site")
        self.assertFalse(any("confirmed" in q for q in qs))
        self.assertFalse(any("Which airline" in q for q in qs))

    def test_never_more_than_four(self):
        self.assertLessEqual(len(questions(Purchase(50000, "travel"), "flight 50000")), 4)


if __name__ == "__main__":
    unittest.main()
