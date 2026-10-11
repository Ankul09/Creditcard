"""Run from cron/CI. Exits 1 if the data needs attention."""
import sys

from freshness import validate
from recommender import load_data

issues = validate(load_data())
print("\n".join(issues) if issues else "data OK")
sys.exit(1 if issues else 0)
