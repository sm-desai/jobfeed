"""Adzuna: paged US search, keyed to your profession (config query.adzuna_what).
Keys come from .env (free tier at developer.adzuna.com)."""
from __future__ import annotations

import os
from typing import List

from .. import filters
from ..models import Job
from ..normalize import derive_location, strip_html, to_iso_date

BASE = "https://api.adzuna.com/v1/api/jobs/us/search/{page}"
MAX_PAGES = 5
PER_PAGE = 50


def _int(v):
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return None


async def fetch_feed(ctx) -> List[Job]:
    app_id = os.environ.get("ADZUNA_APP_ID")
    app_key = os.environ.get("ADZUNA_APP_KEY")
    if not (app_id and app_key):
        ctx.log.warning("adzuna: ADZUNA_APP_ID/KEY not set, skipping")
        return []

    what = ctx.cfg.adzuna_what or ctx.cfg.profession
    out: List[Job] = []
    for page in range(1, MAX_PAGES + 1):
        params = {"app_id": app_id, "app_key": app_key, "what": what,
                  "results_per_page": PER_PAGE, "content-type": "application/json"}
        r = await ctx.get(BASE.format(page=page), params=params)
        if r is None:
            break
        try:
            results = r.json().get("results", [])
        except Exception:
            break
        if not results:
            break
        for j in results:
            title = strip_html(j.get("title", "") or "")
            if not filters.title_ok(ctx.cfg, title):
                continue
            company = (j.get("company") or {}).get("display_name", "") or ""
            loc = (j.get("location") or {}).get("display_name", "") or ""
            state, remote, reject = derive_location(loc, ctx.cfg)
            out.append(Job(
                company=company, title=title, location=loc, state=state,
                remote_flag=remote, url=j.get("redirect_url", ""),
                posted_at=to_iso_date(j.get("created")), source="adzuna",
                salary_min=_int(j.get("salary_min")), salary_max=_int(j.get("salary_max")),
                description=strip_html(j.get("description", "")), reject=reject))
        if len(results) < PER_PAGE:
            break
    return out
