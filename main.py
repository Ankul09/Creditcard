"""CLI: describe a purchase, get the best credit card.

    python3 main.py "Rs 5000 petrol at HPCL"            -> best card name only
    python3 main.py --explain "Rs 5000 petrol at HPCL"  -> full answer with alternatives and caveats
"""
import sys

from freshness import validate
from info import lookup
from parser import parse
from present import to_text
from recommender import load_data, recommend

DATA = None


def show(text: str, explain: bool) -> None:
    global DATA
    DATA = DATA or load_data()
    info = lookup(text, DATA["cards"])
    if info:
        print(info)
        return
    try:
        p = parse(text)
    except ValueError as e:
        print(e)
        return
    rec = recommend(p, DATA)
    if explain:
        print(to_text(rec))
    else:
        print(rec.primary.card["name"] if rec.primary else "No reliable recommendation for this purchase.")


def main() -> None:
    args = sys.argv[1:]
    explain = "--explain" in args
    args = [a for a in args if a != "--explain"]
    issues = validate(load_data())
    if issues:
        print(f"warning: {len(issues)} data issue(s); run `python3 check_data.py`", file=sys.stderr)
    if args:
        show(" ".join(args), explain)
        return
    print("Describe a purchase (e.g. 'Rs 5000 on Swiggy'). Ctrl-D to quit.")
    for line in sys.stdin:
        if line.strip():
            show(line, explain)


if __name__ == "__main__":
    main()
