"""Remotive: remote jobs. Optionally scoped by config query.remotive_category
(a Remotive category slug); otherwise all categories, filtered by your titles."""
from __future__ import annotations

from typing import List

from .. import filters
from ..models import Job
from ..normalize import derive_location, strip_html, to_iso_date

BASE = "https://remotive.com/api/remote-jobs"
_US_HINTS = ("usa", "united states", "u.s", "worldwide", "anywhere", "remote")


async def fetch_feed(ctx) -> List[Job]:
    cat = ctx.cfg.remotive_category
    url = f"{BASE}?category={cat}" if cat else BASE
    r = await ctx.get(url)
    if r is None:
        return []
    try:
        jobs = r.json().get("jobs", [])
    except Exception:
        return []

    out: List[Job] = []
    for j in jobs:
        title = j.get("title", "") or ""
        if not filters.title_ok(ctx.cfg, title):
            continue
        loc = j.get("candidate_required_location", "") or ""
        force_remote = any(h in loc.lower() for h in _US_HINTS)
        state, remote, reject = derive_location(loc, ctx.cfg, force_remote=force_remote)
        out.append(Job(
            company=j.get("company_name", "") or "", title=title, location=loc,
            state=state, remote_flag=remote, url=j.get("url", ""),
            posted_at=to_iso_date(j.get("publication_date")), source="remotive",
            description=strip_html(j.get("description", "")), reject=reject))
    return out
