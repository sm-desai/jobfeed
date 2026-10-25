"""Additive scoring from config.yaml. Stores which rules fired so a high
rank is always explainable."""
from __future__ import annotations

from typing import List, Tuple

from .config import Config
from .models import Job
from .normalize import days_since


def score_job(cfg: Config, job: Job) -> Tuple[int, List[str]]:
    reasons: List[str] = []
    total = 0
    text = f"{job.title} {job.description}"

    for rx, pts in cfg.keyword_boosts:
        if rx.search(text):
            total += pts
            reasons.append(f"{rx.pattern} +{pts}")

    for rx, pts in cfg.keyword_penalties:
        if rx.search(text):
            total += pts
            reasons.append(f"{rx.pattern} {pts}")

    state_boost = cfg.state_boosts.get(job.state, 0)
    if state_boost:
        total += state_boost
        reasons.append(f"state {job.state} +{state_boost}")

    if job.remote_flag and cfg.remote_boost:
        total += cfg.remote_boost
        reasons.append(f"remote +{cfg.remote_boost}")

    age = days_since(job.posted_at)
    if age is not None:
        fr = cfg.freshness
        if age <= 3 and "posted_within_3_days" in fr:
            total += fr["posted_within_3_days"]
            reasons.append(f"posted_within_3_days +{fr['posted_within_3_days']}")
        elif age <= 7 and "posted_within_7_days" in fr:
            total += fr["posted_within_7_days"]
            reasons.append(f"posted_within_7_days +{fr['posted_within_7_days']}")
        elif age > 30 and "older_than_30_days" in fr:
            total += fr["older_than_30_days"]
            reasons.append(f"older_than_30_days {fr['older_than_30_days']}")

    job.score = total
    job.score_reasons = reasons
    return total, reasons
