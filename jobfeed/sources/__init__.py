"""Source registry + optional target-CSV loader.

FEED_SOURCES (Adzuna/Remotive/RemoteOK) need no company list — they're queried
by your profession. ATS_SOURCES (Greenhouse/Ashby/Lever) poll specific company
boards listed in targets.csv (company,ats,token); if you don't have one, leave
those sources disabled in config.yaml."""
from __future__ import annotations

import csv
import os
from collections import defaultdict
from typing import Dict, List, Optional

from . import adzuna, ashby, greenhouse, lever, remoteok, remotive

ATS_SOURCES = {"greenhouse": greenhouse, "lever": lever, "ashby": ashby}
FEED_SOURCES = {"adzuna": adzuna, "remotive": remotive, "remoteok": remoteok}


def read_targets(path: str, limit: Optional[int] = None) -> Dict[str, List[dict]]:
    """Group target rows by ats. Returns empty if the file is absent."""
    grouped: Dict[str, List[dict]] = defaultdict(list)
    if not os.path.exists(path):
        return grouped
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            ats = (row.get("ats") or "").strip().lower()
            if ats in ATS_SOURCES:
                grouped[ats].append(row)
    if limit:
        grouped = {k: v[:limit] for k, v in grouped.items()}
    return grouped
