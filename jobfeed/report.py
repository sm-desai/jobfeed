"""Render the digest as a markdown string (shared by `jt digest` and the
scheduled email)."""
from __future__ import annotations

import json
from datetime import date
from typing import List

from .config import Config


def fmt_salary(lo, hi) -> str:
    def k(n):
        return f"${n/1000:.0f}k" if n else None
    lo_s, hi_s = k(lo), k(hi)
    if lo_s and hi_s:
        return f"{lo_s}–{hi_s}"
    return lo_s or hi_s or ""


def render_digest(cfg: Config, rows: List, ranked: bool = True) -> str:
    if not rows:
        return "_no matching jobs — run `jf fetch` first_"

    header = (f"## jobfeed digest — top {len(rows)} by score" if ranked
              else f"## jobfeed digest --all — {len(rows)} new roles")
    out = [f"{header}  ({date.today().isoformat()})", ""]

    for i, r in enumerate(rows, 1):
        sid = r["id"][:8]
        sal = fmt_salary(r["salary_min"], r["salary_max"])
        flag = ""
        known = r["salary_max"] or r["salary_min"]
        if cfg.comp_flag_below and known and known < cfg.comp_flag_below:
            flag = " ⚠low"
        remote = "remote" if r["remote_flag"] else r["state"]
        posted = f"posted {r['posted_at']}" if r["posted_at"] else "posted ?"
        score = f"[score {r['score']}]" if ranked else ""
        meta = " · ".join(x for x in [remote, sal + flag if sal else "",
                                      r["source"], posted] if x)
        out.append(f"{i}. **{r['title']}** — {r['company']}  {score}  `{sid}`")
        out.append(f"   {meta}")
        out.append(f"   {r['url']}")
        if ranked and r["score_reasons"]:
            try:
                reasons = ", ".join(json.loads(r["score_reasons"]))
            except Exception:
                reasons = ""
            if reasons:
                out.append(f"   why: {reasons}")
        out.append("")
    return "\n".join(out)
