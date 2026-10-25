"""Ashby: GET /posting-api/job-board/{token}
The API returns NO company name, so we fall back to the CSV `company`
column (a slug for discovery rows). Location uses the structured address."""
from __future__ import annotations

from typing import List, Optional

from .. import filters
from ..models import Job
from ..normalize import derive_location, strip_html, to_iso_date

URL = "https://api.ashbyhq.com/posting-api/job-board/{token}"


def _location(j) -> str:
    addr = (j.get("address") or {}).get("postalAddress") or {}
    parts = [addr.get("addressLocality"), addr.get("addressRegion"),
             addr.get("addressCountry")]
    joined = ", ".join(p for p in parts if p)
    return joined or (j.get("location") or "")


async def fetch_board(ctx, row) -> Optional[List[Job]]:
    token = (row.get("token") or "").strip()
    r = await ctx.get(URL.format(token=token))
    if r is None:
        return None
    try:
        data = r.json()
    except Exception:
        return None

    company = row.get("company") or token  # no name in the API
    out: List[Job] = []
    for j in data.get("jobs", []):
        title = j.get("title", "") or ""
        if not filters.title_ok(ctx.cfg, title):
            continue
        loc = _location(j)
        state, remote, reject = derive_location(
            loc, ctx.cfg, force_remote=bool(j.get("isRemote"))
        )
        desc = j.get("descriptionPlain") or strip_html(j.get("descriptionHtml", ""))
        out.append(Job(
            company=company, title=title, location=loc, state=state,
            remote_flag=remote,
            url=j.get("jobUrl") or j.get("applyUrl") or "",
            posted_at=to_iso_date(j.get("publishedAt")),
            source="ashby", description=desc, reject=reject,
        ))
    return out
