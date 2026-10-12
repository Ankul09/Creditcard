"""CLI: describe a purchase, get the best credit card.

    python3 main.py "Rs 5000 petrol at HPCL"            -> best card name only
    python3 main.py --explain "Rs 5000 petrol at HPCL"  -> full answer with alternatives and caveats
"""
import sys

from freshness import validate
from answer import handle, render
from session import Session, reply
from recommender import load_data

DATA = None


SESSION = Session()


def show(text: str, explain: bool) -> None:
    global DATA
    DATA = DATA or load_data()
    if explain:  # one-shot detailed answer, no conversation
        print(render(handle(text, DATA), True))
    else:
        print(reply(SESSION, text, DATA))


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
            print()


if __name__ == "__main__":
    main()
