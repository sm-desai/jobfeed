"""Greenhouse: GET /v1/boards/{token}/jobs?content=true
Company name comes from the API's per-job `company_name`."""
from __future__ import annotations

from typing import List, Optional

from .. import filters
from ..models import Job
from ..normalize import derive_location, strip_html, to_iso_date

URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"


async def fetch_board(ctx, row) -> Optional[List[Job]]:
    token = (row.get("token") or "").strip()
    r = await ctx.get(URL.format(token=token))
    if r is None:
        return None
    try:
        data = r.json()
    except Exception:
        return None

    out: List[Job] = []
    for j in data.get("jobs", []):
        title = j.get("title", "") or ""
        if not filters.title_ok(ctx.cfg, title):
            continue
        company = j.get("company_name") or row.get("company") or token
        loc = ((j.get("location") or {}).get("name")) or ""
        state, remote, reject = derive_location(loc, ctx.cfg)
        posted = to_iso_date(j.get("updated_at") or j.get("first_published"))
        out.append(Job(
            company=company, title=title, location=loc, state=state,
            remote_flag=remote, url=j.get("absolute_url", ""), posted_at=posted,
            source="greenhouse", description=strip_html(j.get("content", "")),
            reject=reject,
        ))
    return out
