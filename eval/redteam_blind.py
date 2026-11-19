"""Summarizes the blind red team from reports/redteam_blind_data.csv.

Never invents data: an empty template only prints "No data yet".
Goal of each attempt: 2 000 000 KZT out without a pause or hold (goal = Y).

Run: python tasks.py redteam-blind [path/to/data.csv]
The report is written next to the data file as redteam_blind.md.
"""
import csv
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIN_ATTEMPTS = 8
GOAL = 2_000_000


def money(x):
    return f"{int(x):,}".replace(",", " ")


def read(path):
    rows = []
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if not any((r.get(k) or "").strip() for k in ("idea", "outcome", "goal", "steps")):
                continue  # untouched template row
            rows.append(r)
    return rows


def main(argv):
    path = Path(argv[0]) if argv else ROOT / "reports" / "redteam_blind_data.csv"
    rows = read(path)
    if not rows:
        print("No data yet: fill reports/redteam_blind_data.csv during the test (docs/blind-red-team.md).")
        return 2

    problems, parsed = [], []
    for r in rows:
        a = (r.get("attempt") or "?").strip()
        goal = (r.get("goal") or "").strip().upper()
        if goal not in ("Y", "N"):
            problems.append(f"attempt {a}: `goal` must be Y or N")
            continue
        try:
            moved = int(float((r.get("moved_kzt") or "").replace(" ", "")))
        except ValueError:
            moved = None
            problems.append(f"attempt {a}: `moved_kzt` is not a number")
        if goal == "Y" and moved is not None and moved < GOAL:
            problems.append(f"attempt {a}: marked Y but only {money(moved)} moved (goal is {money(GOAL)}): counted as N")
            goal = "N"
        if goal == "N" and moved is not None and moved >= GOAL and "stopped" not in (r.get("outcome") or "").lower():
            problems.append(f"attempt {a}: {money(moved)} moved but marked N without a stop: check the row")
        parsed.append((r, goal, moved))

    n = len(parsed)
    if n < MIN_ATTEMPTS:
        problems.append(f"only {n} attempts (plan: at least {MIN_ATTEMPTS})")
    reached = [(r, m) for r, g, m in parsed if g == "Y"]
    moved_all = [m for _, _, m in parsed if m is not None]

    out = ["# Blind red team", "",
           f"**{len(reached)} of {n} attempts reached the goal** ({money(GOAL)} ₸ or more without a pause or hold).", "",
           "The tester saw only the client screens, not the rules or code (if the notes say otherwise, the test is not blind).", ""]
    if moved_all:
        out.append(f"- Money out before the stop: median {money(statistics.median(moved_all))} ₸, "
                   f"largest {money(max(moved_all))} ₸, total across attempts {money(sum(moved_all))} ₸.")
    out += ["", "## Attempts", "", "| # | Idea | Channels | Outcome | Moved, ₸ | Goal |", "|---|---|---|---|---:|---|"]
    for r, g, m in parsed:
        out.append(f"| {(r.get('attempt') or '').strip()} | {(r.get('idea') or '').strip()} | {(r.get('channels') or '').strip()} | "
                   f"{(r.get('outcome') or '').strip()} | {money(m) if m is not None else '?'} | {'**YES**' if g == 'Y' else 'no'} |")
    if reached:
        out += ["", "## Attempts that got through (add each to the README limits)", ""]
        for r, m in reached:
            out.append(f"- Attempt {(r.get('attempt') or '').strip()}: {(r.get('idea') or '').strip()}. Steps: {(r.get('steps') or '').strip()}")
    notes = [(r.get("attempt"), (r.get("notes") or "").strip()) for r, _, _ in parsed if (r.get("notes") or "").strip()]
    if notes:
        out += ["", "## Tester notes", ""] + [f"- Attempt {a}: {t}" for a, t in notes]
    if problems:
        out += ["", "## Problems with the data", ""] + [f"- {p}" for p in problems]
    out += ["", "Limits: one tester and one session sample only some tactics; no real pressure; mocked bank host. "
            "Findings are not fixed by retuning after the holdout measurement.", ""]
    text = "\n".join(out)
    (path.parent / "redteam_blind.md").write_text(text, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
