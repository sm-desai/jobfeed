"""Turn a raw location string into (state, remote_flag, reject), plus small
text helpers. State is always derived from the job's own location — never
from the CSV target row. See PLAN.md sec 3."""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from html import unescape
from typing import Optional, Tuple

from .config import Config

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_MAX_DESC = 8000


def strip_html(s: Optional[str]) -> str:
    if not s:
        return ""
    # unescape FIRST — ATS feeds entity-encode their HTML (&lt;h2&gt;), so the
    # tags only become strippable after unescaping.
    text = _TAG.sub(" ", unescape(s))
    text = _WS.sub(" ", text).strip()
    return text[:_MAX_DESC]


def derive_location(
    raw: Optional[str], cfg: Config, force_remote: bool = False
) -> Tuple[str, bool, bool]:
    """Returns (state, remote_flag, reject). Order matters:
    reject_hints override everything, then remote, then city hints, then '?'."""
    raw = raw or ""
    low = raw.lower()

    for hint in cfg.reject_hints:
        if hint.lower() in low:
            return ("?", False, True)

    if force_remote or any(h.lower() in low for h in cfg.remote_hints):
        return ("REMOTE", True, False)

    for state, hints in cfg.city_hints.items():
        for hint in hints:
            if hint.lower() in low:
                return (state, False, False)

    return ("?", False, False)


def to_iso_date(value) -> Optional[str]:
    """Best-effort parse of assorted date shapes into YYYY-MM-DD."""
    if value is None or value == "":
        return None
    # epoch millis (Lever createdAt) or seconds
    if isinstance(value, (int, float)):
        secs = value / 1000 if value > 1e11 else value
        try:
            return datetime.fromtimestamp(secs, tz=timezone.utc).date().isoformat()
        except (OverflowError, OSError, ValueError):
            return None
    s = str(value).strip()
    if not s:
        return None
    # take the leading YYYY-MM-DD if present
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        try:
            datetime.strptime(s[:10], "%Y-%m-%d")
            return s[:10]
        except ValueError:
            return None
    return None


def days_since(iso_date: Optional[str]) -> Optional[int]:
    if not iso_date:
        return None
    try:
        d = datetime.strptime(iso_date[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
    return (date.today() - d).days
