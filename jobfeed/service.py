"""Fetch logic shared by the CLI."""
from __future__ import annotations

import asyncio
from logging import Logger
from typing import List, Optional

from . import db, filters, scoring
from .config import ROOT, Config
from .fetching import fetch_all

DB_FILE = str(ROOT / "jobs.db")


def run_fetch(cfg: Config, log: Logger, targets: str = "targets.csv",
              limit: Optional[int] = None) -> dict:
    """Poll the enabled sources, filter/score/upsert into jobs.db."""
    enabled = [name for name, on in cfg.sources_enabled.items() if on]
    conn = db.connect(DB_FILE)
    db.init_schema(conn)
    results = asyncio.run(fetch_all(cfg, log, targets, limit=limit, only=enabled))

    sources, ins, upd, kept_h = [], 0, 0, 0
    for res in results:
        kept = 0
        for job in res.jobs:
            if not filters.location_ok(cfg, job):
                continue
            if not filters.comp_ok(cfg, job):
                continue
            scoring.score_job(cfg, job)
            outcome = db.upsert(conn, job)
            kept += 1
            ins += outcome == "inserted"
            upd += outcome == "updated"
            kept_h += outcome == "kept"
        conn.commit()
        log.info("%s: title-matches=%d kept=%d boards=%d failed=%d",
                 res.name, len(res.jobs), kept, res.boards_total, res.boards_failed)
        sources.append({"source": res.name, "matches": len(res.jobs), "kept": kept,
                        "boards": res.boards_total, "failed": res.boards_failed})
    conn.close()
    return {"sources": sources, "inserted": ins, "updated": upd, "unchanged": kept_h}
