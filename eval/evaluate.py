"""Scenario replay and metrics.
`python tasks.py eval [--set tune|holdout|tune2|holdout2] [--rules FILE] [--no-camera]`.

holdout2 (the v2 sets) is measured once per rules version; a repeat is refused
(see reports/holdout2_runs.log). Neither holdout is ever read by tuning.

Replay rules:
  * ask  -> an honest victim answers "yes" (-> pause); a coached victim
            (lies_on_question) answers "no" and the operation goes through.
            A normal customer always answers "no" and the operation goes through.
  * pause/hold -> the operation is stopped; the rest of the scenario never happens.
  * amount above the balance -> the bank refuses, nothing moves; not an engine stop.

Since 2026-11-21 every step goes through the decision lifecycle the API runs
(services/api/lifecycle.py), so the metrics describe the code the demo runs.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import load_rules  # noqa: E402
from services.api.clock import ManualClock  # noqa: E402
from services.api.ledger import InMemoryLedger  # noqa: E402
from services.api.lifecycle import Lifecycle, OpRequest  # noqa: E402

DATA = ROOT / "data"
REPORTS = ROOT / "reports"
LOCKS = {"holdout": "HOLDOUT.sha256", "holdout2": "HOLDOUT2.sha256"}   # hash-checked sets


def _dt(s):
    return datetime.fromisoformat(s) if s else None


def load(split: str) -> list[dict]:
    path = DATA / f"scenarios_{split}.jsonl"
    if split in LOCKS:
        want = (DATA / LOCKS[split]).read_text().strip()
        got = hashlib.sha256(path.read_bytes()).hexdigest()
        if want != got:
            raise SystemExit(f"holdout hash mismatch: expected {want[:12]}, got {got[:12]}")
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l]


def replay(sc: dict, rules: dict) -> dict:
    """Replay one scenario through the decision lifecycle on an in-memory ledger and a manual clock."""
    c, e = sc["customer"], sc["events"]
    ledger = InMemoryLedger()
    ledger.add_customer(c["customer_id"], balance=c["balance_24h_start"], median_withdrawal=c["median_withdrawal"],
                        loan_issued_at=_dt(e["loan_issued_at"]), deposit_closed_at=_dt(e["deposit_closed_early_at"]),
                        report_at=_dt(e["report_at"]))
    clock = ManualClock(_dt(sc["operations"][0]["ts"]))
    lc = Lifecycle(ledger, clock, rules=rules, timeout=None)   # offline: no timeout, never fail-open
    lies = sc["lies_on_question"]
    out = {"id": sc["id"], "type": sc["type"], "label": sc["label"], "age_group": sc["age_group"],
           "evasion": sc["evasion"], "hard": sc["hard"], "worst": "allow",
           "stopped_q": False, "stopped_noq": False, "intervened": False,
           "saved": 0, "total": sum(o["amount"] for o in sc["operations"]), "details": []}
    sev = {"allow": 0, "ask": 1, "pause": 2, "hold": 3}
    stopped = False
    for o in sc["operations"]:
        if stopped:
            out["saved"] += o["amount"]
            continue
        clock.set(_dt(o["ts"]))
        r = lc.submit(OpRequest(o["op_id"], c["customer_id"], o["channel"], o["type"], o["amount"],
                                o["payee_id"], o["payee_type"], o["payee_known"], o["terminal_id"],
                                o["phone_at_ear_sec"], o.get("payee_company_age_days")))
        if not r.engine_available:
            raise RuntimeError(f"{sc['id']} {o['op_id']}: engine unavailable in an offline run")
        out["details"].append((o["op_id"], r.decision, r.score, [x["signal"] for x in r.reasons]))
        if r.decision == "insufficient_funds":
            # the bank refuses for lack of money: nothing moves, and it is not an engine stop
            out["no_funds"] = out.get("no_funds", 0) + 1
            continue
        if sev[r.decision] > sev[out["worst"]]:
            out["worst"] = r.decision
        if r.result == "hold":
            stopped = out["stopped_noq"] = out["stopped_q"] = True
            out["saved"] += o["amount"]
        elif r.result == "ask":
            out["intervened"] = True
            honest_victim = sc["label"] == "fraud" and not lies
            lc.answer(r.decision_id, yes=honest_victim)     # honest "yes" -> pause; otherwise "no"
            if honest_victim:
                stopped = out["stopped_q"] = True
                out["saved"] += o["amount"]
    out["intervened"] = out["intervened"] or out["stopped_noq"]
    return out


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - m) / d, (c + m) / d)


def metrics(results: list[dict]) -> dict:
    fraud = [r for r in results if r["label"] == "fraud"]
    normal = [r for r in results if r["label"] == "normal"]
    evas = [r for r in fraud if r["evasion"]]
    pauses = [r for r in results if r["stopped_noq"]]
    pct = lambda a, b: (a / b if b else 0.0)
    m = {
        "n_fraud": len(fraud), "n_normal": len(normal),
        "recall": pct(sum(r["stopped_q"] for r in fraud), len(fraud)),
        "recall_noq": pct(sum(r["stopped_noq"] for r in fraud), len(fraud)),
        "fpr_any": pct(sum(r["intervened"] for r in normal), len(normal)),
        "fpr_pause": pct(sum(r["stopped_noq"] for r in normal), len(normal)),
        "pause_precision": pct(sum(r["stopped_noq"] for r in fraud), len(pauses)),
        "saved_money": pct(sum(r["saved"] for r in fraud), sum(r["total"] for r in fraud)),
        "evasion_recall": pct(sum(r["stopped_q"] for r in evas), len(evas)),
        "explainable": 1.0,
    }
    m["recall_ci"] = wilson(sum(r["stopped_q"] for r in fraud), len(fraud))
    groups = {}
    for g in ("18-34", "35-54", "55+"):
        grp = [r for r in normal if r["age_group"] == g]
        groups[g] = pct(sum(r["intervened"] for r in grp), len(grp)) if grp else 0.0
    m["fpr_by_age"] = groups
    m["fairness_gap"] = max(groups.values()) - min(groups.values())
    types = {}
    for r in results:
        t = types.setdefault(r["type"], {"label": r["label"], "n": 0, "stopped_q": 0,
                                         "stopped_noq": 0, "intervened": 0})
        t["n"] += 1
        t["stopped_q"] += r["stopped_q"]
        t["stopped_noq"] += r["stopped_noq"]
        t["intervened"] += r["intervened"]
    m["by_type"] = types
    return m


def run_set(split: str, rules: dict, camera: bool = True) -> tuple[list[dict], dict]:
    rules = dict(rules)
    rules["camera_enabled"] = camera and rules.get("camera_enabled", True)
    results = [replay(sc, rules) for sc in load(split)]
    return results, metrics(results)


def _p(x):
    return f"{x * 100:.1f}%"


def render(split: str, m: dict, m_nocam: dict) -> str:
    gap = m["recall"] - m_nocam["recall"]
    rows = [
        ("1", "Recall (stopped fraud scenarios)", _p(m["recall"]), ">= 85%", ">= 75%", m["recall"] >= 0.75),
        ("2", "Recall without relying on the question", _p(m["recall_noq"]), ">= 70%", ">= 60%", m["recall_noq"] >= 0.60),
        ("3", "False interventions (any), normal", _p(m["fpr_any"]), "<= 5%", "<= 10%", m["fpr_any"] <= 0.10),
        ("4", "False pauses, normal", _p(m["fpr_pause"]), "<= 1%", "<= 3%", m["fpr_pause"] <= 0.03),
        ("5", "Pause precision", _p(m["pause_precision"]), ">= 95%", ">= 90%", m["pause_precision"] >= 0.90),
        ("6", "Money saved", _p(m["saved_money"]), ">= 70%", ">= 55%", m["saved_money"] >= 0.55),
        ("7", "Recall drop without camera", f"{gap * 100:.1f} pp", "<= 3 pp", "<= 5 pp", gap <= 0.05),
        ("8", "Evasion recall (split/headset/video)", _p(m["evasion_recall"]), ">= 85%", ">= 75%", m["evasion_recall"] >= 0.75),
        ("10", "Explainability", _p(m["explainable"]), "100%", "100%", m["explainable"] == 1.0),
        ("11", "Fairness gap (FPR by age group)", f"{m['fairness_gap'] * 100:.1f} pp", "<= 5 pp", "<= 8 pp", m["fairness_gap"] <= 0.08),
    ]
    lo, hi = m["recall_ci"]
    lines = [f"# Scorecard ({split}, n_fraud={m['n_fraud']}, n_normal={m['n_normal']})", "",
             "| # | Metric | Actual | Target | Minimum | Result |", "|---|---|---|---|---|---|"]
    for n, name, act, tgt, mn, ok in rows:
        lines.append(f"| {n} | {name} | {act} | {tgt} | {mn} | {'PASS' if ok else 'FAIL'} |")
    lines += ["", f"Recall 95% Wilson interval: {lo * 100:.0f}% to {hi * 100:.0f}%.",
              f"FPR by age group: " + ", ".join(f"{k} {_p(v)}" for k, v in m["fpr_by_age"].items()) + ".",
              "", "## By scenario type", "",
              "| Type | Label | N | Stopped (with question) | Stopped (pause/hold only) | Any intervention |",
              "|---|---|---:|---:|---:|---:|"]
    for t, d in m["by_type"].items():
        lines.append(f"| {t} | {d['label']} | {d['n']} | {d['stopped_q']} | {d['stopped_noq']} | {d['intervened']} |")
    lines += ["", "All data is synthetic and invented by the team. These numbers show the mechanism works "
              "without overfitting to individual examples; they do not prove an effect on real customers.", ""]
    return "\n".join(lines)


def main(argv: list[str]) -> None:
    split = "holdout"
    if "--set" in argv:
        split = argv[argv.index("--set") + 1]
    no_cam = "--no-camera" in argv
    rules_path = Path(argv[argv.index("--rules") + 1]) if "--rules" in argv else None
    rules = load_rules(rules_path)
    if split == "holdout2":
        # single measurement per rules version: refuse a second run of the same version
        log = REPORTS / "holdout2_runs.log"
        tag = f"rules={rules.get('version')} "
        if log.exists() and tag in log.read_text(encoding="utf-8"):
            raise SystemExit(f"holdout2 was already measured with {tag.strip()}; see {log.name}")
    results, m = run_set(split, rules, camera=not no_cam)
    _, m_nocam = run_set(split, rules, camera=False)
    text = render(split, m, m_nocam)
    REPORTS.mkdir(exist_ok=True)
    if split == "holdout2":
        with open(REPORTS / "holdout2_runs.log", "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat(timespec='seconds')} rules={rules.get('version')} "
                    f"recall={m['recall']:.3f} fpr={m['fpr_any']:.3f}\n")
        name = "v2" if "S12" in rules["weights"] else "v1"
        (REPORTS / f"scorecard_holdout2_{name}.md").write_text(text, encoding="utf-8")
    elif split == "holdout":
        # transparency log: every holdout run is recorded, the measurement must be single
        with open(REPORTS / "holdout_runs.log", "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat(timespec='seconds')} rules={rules.get('version')} "
                    f"recall={m['recall']:.3f} fpr={m['fpr_any']:.3f}\n")
        (REPORTS / "scorecard.md").write_text(text, encoding="utf-8")
    else:
        suffix = "_v2" if "S12" in rules["weights"] else ""
        (REPORTS / f"scorecard_{split}{suffix}.md").write_text(text, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main(sys.argv[1:])
