"""Grid search on the TUNE set only. Never reads the holdout set.

Search: ask threshold {35,40,45} x pause threshold {55,60,65,70}
        x weight shifts of S1, S4, S7 in {-5, 0, +5}  (324 candidates).
Objective: max recall (with question) subject to
        any-intervention FPR <= 5% and pause FPR <= 1%.
If no candidate satisfies both constraints, pick the one with the smallest
constraint violation and say so in the report.

v2 (2026-11-23): `python tasks.py tune --v2` tunes engine/rules.v2.start.yaml on the
TUNE2 set only and writes engine/rules.v2.tuned.yaml and reports/tuning_v2.md.
"""
from __future__ import annotations

import itertools
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))

from engine import load_rules  # noqa: E402
from engine.scoring import with_overrides  # noqa: E402
from evaluate import metrics, replay, load  # noqa: E402


def main(argv=()):
    v2 = "--v2" in argv
    base = load_rules(ROOT / "engine" / "rules.v2.start.yaml") if v2 else load_rules()
    split = "tune2" if v2 else "tune"
    scenarios = load(split)           # no holdout is ever loaded here
    rows = []
    for ask, pause, d1, d4, d7 in itertools.product((35, 40, 45), (55, 60, 65, 70),
                                                    (-5, 0, 5), (-5, 0, 5), (-5, 0, 5)):
        if pause <= ask:
            continue
        r = with_overrides(base,
                           weights={"S1": base["weights"]["S1"] + d1,
                                    "S4": base["weights"]["S4"] + d4,
                                    "S7": base["weights"]["S7"] + d7},
                           thresholds={"ask": ask, "pause": pause})
        m = metrics([replay(sc, r) for sc in scenarios])
        viol = max(0, m["fpr_any"] - 0.05) + max(0, m["fpr_pause"] - 0.01)
        rows.append((ask, pause, d1, d4, d7, m["recall"], m["recall_noq"], m["fpr_any"],
                     m["fpr_pause"], viol, r))
    feasible = [x for x in rows if x[9] == 0]
    pool = feasible or sorted(rows, key=lambda x: (x[9], -x[5]))[:1]
    best = max(pool, key=lambda x: (x[5], x[6], -x[7])) if feasible else pool[0]
    note = ("feasible set found" if feasible else
            "NO candidate met both false-alarm limits; chose the smallest violation")

    # Stage 2: coordinate descent over more weights, still on the TUNE set only.
    def score_rules(r):
        m = metrics([replay(sc, r) for sc in scenarios])
        viol = max(0, m["fpr_any"] - 0.05) + max(0, m["fpr_pause"] - 0.01)
        return (viol == 0, m["recall"], m["recall_noq"], -m["fpr_any"]), m

    cur = best[10]
    cur_key, cur_m = score_rules(cur)
    steps = []
    improved = True
    while improved:
        improved = False
        names = ("S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S11") + (("S12", "S13", "S14") if v2 else ())
        for kind, name in [("w", s) for s in names] + \
                          [("t", "ask"), ("t", "pause")]:
            for delta in (-5, 5):
                if kind == "w":
                    cand = with_overrides(cur, weights={name: cur["weights"][name] + delta})
                else:
                    th = {name: cur["thresholds"][name] + delta}
                    cand = with_overrides(cur, thresholds=th)
                    if cand["thresholds"]["pause"] <= cand["thresholds"]["ask"] or \
                            cand["thresholds"]["pause"] < 45:
                        continue
                if any(v < 0 for k, v in cand["weights"].items() if k not in ("S9",)):
                    continue
                key, m = score_rules(cand)
                if key > cur_key:
                    cur, cur_key, cur_m = cand, key, m
                    steps.append(f"{kind}:{name}{delta:+d} -> recall {m['recall']:.1%}, FPR {m['fpr_any']:.1%}")
                    improved = True
    best = (cur["thresholds"]["ask"], cur["thresholds"]["pause"], 0, 0, 0, cur_m["recall"],
            cur_m["recall_noq"], cur_m["fpr_any"], cur_m["fpr_pause"], 0, cur)

    n_f = sum(sc["label"] == "fraud" for sc in scenarios)
    out = [f"# Tuning report ({split.upper()} set only, {len(scenarios) - n_f} normal + {n_f} fraud)", "",
           f"Candidates evaluated: {len(rows)}. Feasible (FPR<=5%, false pause<=1%): {len(feasible)}. {note}.", "",
           "## Top 10 candidates", "",
           "| ask | pause | dS1 | dS4 | dS7 | recall | recall no-question | FPR any | FPR pause |",
           "|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    top = sorted(rows, key=lambda x: (x[9] > 0, -x[5], x[7]))[:10]
    for x in top:
        out.append(f"| {x[0]} | {x[1]} | {x[2]:+d} | {x[3]:+d} | {x[4]:+d} | {x[5]:.1%} | {x[6]:.1%} | {x[7]:.1%} | {x[8]:.1%} |")
    out += ["", "## Stage 2: coordinate descent (tune set only)", ""] + [f"- {s}" for s in steps]
    out += ["", f"## Chosen: ask={best[0]}, pause={best[1]}, weights={best[10]['weights']}",
            f"recall {best[5]:.1%}, recall without question {best[6]:.1%}, FPR any {best[7]:.1%}, FPR pause {best[8]:.1%}",
            "", f"Overfitting warning: {len(scenarios)} scenarios written by the same team, "
            f"{len(names) + 2} free parameters. "
            "Only the single holdout measurement says whether this generalizes.", ""]
    (ROOT / "reports" / ("tuning_v2.md" if v2 else "tuning.md")).write_text("\n".join(out), encoding="utf-8")

    cfg = dict(best[10])
    cfg["version"] = "v2-tuned-candidate" if v2 else "tuned-candidate"
    out_file = ROOT / "engine" / ("rules.v2.tuned.yaml" if v2 else "rules.tuned.yaml")
    with open(out_file, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True)
    sys.stdout.reconfigure(encoding="utf-8")
    print("\n".join(out))
    print(f"Wrote {out_file.relative_to(ROOT)}.")


if __name__ == "__main__":
    main(sys.argv[1:])
