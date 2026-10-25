"""The one normalized Job record every source is mapped into."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Job:
    company: str
    title: str
    location: str
    state: str            # two-letter, 'REMOTE', or '?'
    remote_flag: bool
    url: str
    posted_at: Optional[str]   # ISO date (YYYY-MM-DD) or None
    source: str
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    description: str = ""
    # set for rows a reject_hint matched; filters drop these, normalize never does
    reject: bool = False
    # populated by scoring
    score: int = 0
    score_reasons: List[str] = field(default_factory=list)
