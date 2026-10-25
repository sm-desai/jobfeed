"""Lever: GET /v0/postings/{token}?mode=json
No company name in the API -> fall back to the CSV `company` column.
(0 lever boards in the current CSV, but the adapter is here for harvest.)"""
from __future__ import annotations

from typing import List, Optional

from .. import filters
from ..models import Job
from ..normalize import derive_location, strip_html, to_iso_date

URL = "https://api.lever.co/v0/postings/{token}?mode=json"


async def fetch_board(ctx, row) -> Optional[List[Job]]:
    token = (row.get("token") or "").strip()
    r = await ctx.get(URL.format(token=token))
    if r is None:
        return None
    try:
        data = r.json()
    except Exception:
        return None
    if not isinstance(data, list):
        return []

    company = row.get("company") or token
    out: List[Job] = []
    for j in data:
        title = j.get("text", "") or ""
        if not filters.title_ok(ctx.cfg, title):
            continue
        loc = (j.get("categories") or {}).get("location", "") or ""
        force_remote = (j.get("workplaceType") or "").lower() == "remote"
        state, remote, reject = derive_location(loc, ctx.cfg, force_remote=force_remote)
        desc = j.get("descriptionPlain") or strip_html(j.get("description", ""))
        out.append(Job(
            company=company, title=title, location=loc, state=state,
            remote_flag=remote, url=j.get("hostedUrl", ""),
            posted_at=to_iso_date(j.get("createdAt")),
            source="lever", description=desc, reject=reject,
        ))
    return out
