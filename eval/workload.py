"""Officer workload estimate: how many pauses and holds a day would officers review?

Run: python tasks.py workload   -> reports/workload.md

Counts decisions per OPERATION (not per scenario) on both synthetic sets, replayed
through the same lifecycle as the metrics, with the frozen rules. Nothing is tuned
and nothing is added to reports/holdout_runs.log: this is a different statistic
read from the same frozen replay.

Only pauses and holds reach an officer. A question is answered by the customer.
Zero pauses on normal operations in a small sample is not zero in reality, so the
estimate uses the 95% upper bound (exact binomial for zero events: 1 - 0.05**(1/n)).
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import load_rules  # noqa: E402
from eval.evaluate import load, replay, wilson  # noqa: E402

REPORTS = ROOT / "reports"
# Illustrative volumes of operations that look like our scenarios (large cash or transfers,
# often after a loan or a closed deposit). The bank's real number is unknown: ask the mentor.
VOLUMES = (1_000, 5_000, 20_000)


def upper95(k: int, n: int) -> float:
    if n == 0:
        return 1.0
    return 1 - 0.05 ** (1 / n) if k == 0 else wilson(k, n)[1]


def count(rules: dict) -> dict:
    out = {}
    for split in ("tune", "holdout"):
        c = Counter()
        for sc in load(split):
            r = replay(sc, dict(rules))
            for _op, dec, _score, _sig in r["details"]:
                if dec != "insufficient_funds":
                    c[(sc["label"], dec)] += 1
        out[split] = c
    return out


def render(counts: dict) -> str:
    def row(split, label):
        c = counts[split]
        n = sum(v for (l, _), v in c.items() if l == label)
        ask = c[(label, "ask")]
        stop = c[(label, "pause")] + c[(label, "hold")]
        return n, ask, stop

    lines = ["# Officer workload estimate", "",
             "All data is synthetic and invented by the team. Counts are per operation, replayed with the frozen rules.", "",
             "| Set | Label | Operations | Question only | Pause or hold (officer) |",
             "|---|---|---:|---:|---:|"]
    tot_n = tot_stop = 0
    for split in ("tune", "holdout"):
        for label in ("normal", "fraud"):
            n, ask, stop = row(split, label)
            lines.append(f"| {split} | {label} | {n} | {ask} ({ask / n:.1%}) | {stop} ({stop / n:.1%}) |")
            if label == "normal":
                tot_n += n
                tot_stop += stop
    ub = upper95(tot_stop, tot_n)
    lines += ["", f"Normal operations, both sets: {tot_stop} of {tot_n} paused or held. "
              f"95% upper bound: {ub:.1%} of such operations.", "",
              "## Reviews a day from honest customers (illustrative)", "",
              "Volume = operations a day that look like our scenarios (large cash or transfers). "
              "Small everyday payments are not in the scenarios and are assumed never to be paused.", "",
              "| Such operations a day | Expected (observed rate) | Worst case (95% upper bound) |",
              "|---:|---:|---:|"]
    rate = tot_stop / tot_n if tot_n else 0.0
    for v in VOLUMES:
        lines.append(f"| {v:,} | {v * rate:.0f} | {v * ub:.0f} |".replace(",", " "))
    lines += ["", "## What this does not say", "",
              "- The bank's real volume of large operations is unknown; the volumes above are placeholders.",
              "- The normal scenarios are deliberately hard (5 of 8 types), so real honest operations are "
              "probably paused less often, but this is not measured.",
              "- Real fraud cases add to the queue; their number per day is unknown.",
              "- Minutes per review (callback, comment) are not measured.", ""]
    return "\n".join(lines)


def main() -> None:
    text = render(count(load_rules()))
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "workload.md").write_text(text, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
