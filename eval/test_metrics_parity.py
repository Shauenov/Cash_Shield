"""Seam 3: the metrics are measured through the same decision lifecycle the API runs.

Expected numbers are the frozen ones, copied from reports/scorecard.md (holdout, measured
once on 2026-11-18) and reports/FREEZE.md (tune set at freeze). They are not recomputed
here. If this test fails, the metrics no longer describe the code the demo runs.
Calling the functions directly does not append to reports/holdout_runs.log.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine import load_rules  # noqa: E402
import evaluate  # noqa: E402

RULES = load_rules()


def pct(x):
    return round(x * 100, 1)


def test_holdout_scorecard_through_the_lifecycle():
    results = [evaluate.replay(sc, RULES) for sc in evaluate.load("holdout")]
    m = evaluate.metrics(results)
    assert (m["n_fraud"], m["n_normal"]) == (60, 120)
    assert sum(r["stopped_q"] for r in results if r["label"] == "fraud") == 47       # 78.3%
    assert sum(r["stopped_noq"] for r in results if r["label"] == "fraud") == 40     # 66.7%
    assert sum(r["intervened"] for r in results if r["label"] == "normal") == 5      # 4.2%
    assert sum(r["stopped_noq"] for r in results if r["label"] == "normal") == 0     # 0.0%
    assert pct(m["saved_money"]) == 71.5
    assert pct(m["evasion_recall"]) == 78.6
    assert pct(m["fairness_gap"]) == 8.3


def test_holdout_without_camera_drops_one_scenario():
    rules = dict(RULES, camera_enabled=False)
    results = [evaluate.replay(sc, rules) for sc in evaluate.load("holdout")]
    assert sum(r["stopped_q"] for r in results if r["label"] == "fraud") == 46       # 1.7 pp below 47


def test_tune_set_at_freeze_through_the_lifecycle():
    results = [evaluate.replay(sc, RULES) for sc in evaluate.load("tune")]
    assert sum(r["stopped_q"] for r in results if r["label"] == "fraud") == 67       # 74.4% of 90
    assert sum(r["intervened"] for r in results if r["label"] == "normal") == 6      # 3.3% of 180
    assert sum(r["stopped_noq"] for r in results if r["label"] == "normal") == 0     # 0.0%
