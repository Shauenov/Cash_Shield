"""Scores the pause-screen usability test (metric 15) from reports/usability_data.csv.

Pass rule, fixed in docs/usability-test.md before the test:
  correct = column `correct` is Y AND `seconds` <= 20
  target 8 of 10, minimum 7 of 10, and at least 3 of the participants over 50.
Never invents data: an empty CSV only gives a "no data yet" message.

Run: python tasks.py usability [path/to/data.csv]
"""
import csv
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIMIT_S = 20
TARGET, MINIMUM, MIN_OLDER = 8, 7, 3


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - m) / d, (c + m) / d


def read(path):
    rows = []
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if (r.get("correct") or "").strip() == "" and (r.get("age_group") or "").strip() == "":
                continue  # an untouched template row
            rows.append(r)
    return rows


def main(argv):
    path = Path(argv[0]) if argv else ROOT / "reports" / "usability_data.csv"
    rows = read(path)
    if not rows:
        print("No data yet: fill reports/usability_data.csv after the test (see docs/usability-test.md).")
        return 2

    problems = []
    n = len(rows)
    if n < 10:
        problems.append(f"only {n} participants (10 planned): the result is not comparable with the pass rule")
    scored = []
    for r in rows:
        ans = (r.get("correct") or "").strip().upper()
        if ans not in ("Y", "N"):
            problems.append(f"participant {r.get('id')}: `correct` must be Y or N")
            continue
        try:
            secs = float(r.get("seconds") or "")
        except ValueError:
            secs = None
        ok = ans == "Y" and secs is not None and secs <= LIMIT_S
        if ans == "Y" and (secs is None or secs > LIMIT_S):
            problems.append(f"participant {r.get('id')}: marked Y but time is {secs}: counted as NOT correct")
        scored.append((r, ok))

    n = len(scored)
    k = sum(1 for _, ok in scored if ok)
    older = [r for r, _ in scored if (r.get("age_group") or "").strip().lower() in ("over 50", "50+", ">50")]
    older_ok = sum(1 for r, ok in scored if ok and r in older)
    if len(older) < MIN_OLDER:
        problems.append(f"only {len(older)} participants over 50 (need {MIN_OLDER}): the result is INVALID for the pass rule")

    lo, hi = wilson(k, n)
    if len(older) < MIN_OLDER or n < 10:
        verdict = "INVALID (see problems)"
    elif k >= TARGET:
        verdict = "PASS (target met)"
    elif k >= MINIMUM:
        verdict = "PASS (minimum met, target missed)"
    else:
        verdict = "FAIL (below minimum): rewrite the text and test 5 new people"

    langs = {}
    for r, ok in scored:
        l = (r.get("language") or "?").strip() or "?"
        a, b = langs.get(l, (0, 0))
        langs[l] = (a + (1 if ok else 0), b + 1)
    words = [((r.get("unclear_words") or "").strip(), (r.get("language") or "?").strip()) for r, _ in scored]
    words = [(w, l) for w, l in words if w]
    secs_ok = sorted(float(r["seconds"]) for r, ok in scored if ok)

    out = ["# Usability test: pause screen (metric 15)", "",
           f"**Result: {k} of {n} correct within {LIMIT_S} s. Verdict: {verdict}.**", "",
           f"- Rule: target {TARGET} of 10, minimum {MINIMUM} of 10, at least {MIN_OLDER} participants over 50.",
           f"- Over 50: {len(older)} participants, {older_ok} correct.",
           f"- 95% Wilson interval for the share correct: {lo:.0%} to {hi:.0%}."]
    if secs_ok:
        out.append(f"- Time of the correct answers: median {secs_ok[len(secs_ok) // 2]:.0f} s, slowest {secs_ok[-1]:.0f} s.")
    out += ["- By language: " + ", ".join(f"{l} {a}/{b}" for l, (a, b) in sorted(langs.items())) + ".", ""]
    if problems:
        out += ["## Problems with the data", ""] + [f"- {p}" for p in problems] + [""]
    if words:
        out += ["## Words or lines people did not understand", ""] + [f"- ({l}) {w}" for w, l in words] + [""]
    out += ["Limits: quiet room, no real phone pressure, 10 people, texts not reviewed by a native-speaker editor.", ""]
    text = "\n".join(out)
    (path.parent / "usability.md").write_text(text, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
