"""All filtering, driven entirely by config.yaml. A job is never silently
dropped for missing comp or an unresolvable location ('?')."""
from __future__ import annotations

from .config import Config
from .models import Job


def title_ok(cfg: Config, title: str) -> bool:
    title = title or ""
    if not any(rx.search(title) for rx in cfg.titles_include):
        return False
    if any(rx.search(title) for rx in cfg.titles_exclude):
        return False
    return True


def location_ok(cfg: Config, job: Job) -> bool:
    """reject_hints override everything. Otherwise accept remote-US, an
    accepted state, or an unresolved '?' (kept, surfaced in `digest --all`)."""
    if job.reject:
        return False
    if job.remote_flag and cfg.accept_remote_us:
        return True
    if not cfg.states:          # empty states = accept any US location
        return True
    if job.state in cfg.states:
        return True
    if job.state == "?":
        return True
    return False


def comp_ok(cfg: Config, job: Job) -> bool:
    """Never drops null-comp rows. Only a *known* salary below an explicit
    drop_below is filtered; drop_below is null by default."""
    if cfg.comp_drop_below is None:
        return True
    salary = job.salary_max or job.salary_min
    if salary is None:
        return True
    return salary >= cfg.comp_drop_below
