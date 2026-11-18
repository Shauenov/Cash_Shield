"""Scoring: sums signal weights, maps the score to a decision, explains why."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from . import signals as sg
from .signals import Customer, Events, Executed, Operation  # noqa: F401

DEFAULT_RULES = Path(__file__).with_name("rules.yaml")

SEVERITY = {"allow": 0, "ask": 1, "pause": 2, "hold": 3}


def load_rules(path: Optional[Path] = None) -> dict:
    with open(path or DEFAULT_RULES, encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass
class Decision:
    decision: str                # allow | ask | pause | hold
    score: int
    reasons: list = field(default_factory=list)  # [{signal, contribution, text_ru}]
    rules_version: str = ""


def _signal_list(rules: dict):
    fns = [
        sg.s1_loan_recent, sg.s2_balance_drain, sg.s3_large_cash, sg.s4_series,
        sg.s5_new_payee, sg.s6_deposit_closed, sg.s8_report, sg.s9_legal_payee,
        sg.s11_escalation,
    ]
    if rules.get("camera_enabled", True):
        fns.append(sg.s10_phone_at_ear)
    return fns


def band(score: int, th: dict) -> str:
    if score >= th["hold"]:
        return "hold"
    if score >= th["pause"]:
        return "pause"
    if score >= th["ask"]:
        return "ask"
    return "allow"


def decide(op: Operation, cust: Customer, events: Events,
           history: list[Executed], rules: dict) -> Decision:
    p, w = rules["params"], rules["weights"]
    hits = {}
    for fn in _signal_list(rules):
        hit = fn(op, cust, events, history, p)
        if hit:
            hits[hit[0]] = (hit[1], hit[2])
    # S7 is a combination of S5 and S6
    if "S5" in hits and "S6" in hits:
        hits["S7"] = ("Связка: депозит закрыт и перевод новому получателю", "Combination: deposit closed and transfer to a new recipient")

    reasons = [
        {"signal": code, "contribution": w[code], "text_ru": ru, "text_en": en}
        for code, (ru, en) in hits.items()
    ]
    reasons.sort(key=lambda r: -abs(r["contribution"]))
    score = max(0, min(100, sum(r["contribution"] for r in reasons)))
    decision = band(score, rules["thresholds"])
    # explainability contract: any non-allow decision must carry reasons
    assert decision == "allow" or reasons, "decision without reasons"
    return Decision(decision, score, reasons, str(rules.get("version", "")))


def with_overrides(rules: dict, weights: dict | None = None,
                   thresholds: dict | None = None, **top) -> dict:
    r = copy.deepcopy(rules)
    if weights:
        r["weights"].update(weights)
    if thresholds:
        r["thresholds"].update(thresholds)
    r.update(top)
    return r
