"""CLI: describe a purchase, get the best credit card."""
import sys

from info import lookup
from parser import parse
from freshness import validate
from recommender import load_data, rank


def show(text: str) -> None:
    info = lookup(text, load_data()["cards"])
    if info:
        print(info)
        return
    try:
        p = parse(text)
    except ValueError as e:
        print(e)
        return
    print(rank(p)[0].card["name"])


def main() -> None:
    issues = validate(load_data())
    if issues:
        print(f"warning: {len(issues)} data issue(s); run `python3 check_data.py`", file=sys.stderr)
    if len(sys.argv) > 1:
        show(" ".join(sys.argv[1:]))
        return
    print("Describe a purchase (e.g. 'Rs 5000 on Swiggy'). Ctrl-D to quit.")
    for line in sys.stdin:
        if line.strip():
            show(line)


if __name__ == "__main__":
    main()
