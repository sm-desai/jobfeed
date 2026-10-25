"""RemoteOK: GET /api. The first list element is a legal/metadata notice."""
from __future__ import annotations

from typing import List

from .. import filters
from ..models import Job
from ..normalize import derive_location, strip_html, to_iso_date

URL = "https://remoteok.com/api"
_US_HINTS = ("usa", "united states", "u.s", "worldwide", "anywhere", "remote")


def _int(v):
    try:
        n = int(v)
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None


async def fetch_feed(ctx) -> List[Job]:
    r = await ctx.get(URL)
    if r is None:
        return []
    try:
        data = r.json()
    except Exception:
        return []
    if not isinstance(data, list):
        return []

    out: List[Job] = []
    for j in data[1:]:  # drop metadata element
        if not isinstance(j, dict):
            continue
        title = j.get("position") or j.get("title") or ""
        if not filters.title_ok(ctx.cfg, title):
            continue
        loc = j.get("location") or "Remote"
        force_remote = any(h in str(loc).lower() for h in _US_HINTS) or not loc
        state, remote, reject = derive_location(loc, ctx.cfg, force_remote=force_remote)
        out.append(Job(
            company=j.get("company", "") or "", title=title, location=loc,
            state=state, remote_flag=remote, url=j.get("url", ""),
            posted_at=to_iso_date(j.get("date")),
            source="remoteok",
            salary_min=_int(j.get("salary_min")),
            salary_max=_int(j.get("salary_max")),
            description=strip_html(j.get("description", "")),
            reject=reject,
        ))
    return out
