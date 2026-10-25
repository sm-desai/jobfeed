"""Async fetch engine: one shared client, one global rate limiter (so every
source together respects fetch.max_requests_per_second), retry-once, and a
dead token logs a WARNING but never kills the run."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from logging import Logger
from typing import List, Optional

import httpx

from .config import Config
from .models import Job

CONCURRENCY = 24  # in-flight cap; the real throttle is the rate limiter


class RateLimiter:
    """Spaces request *starts* 1/rps apart across all coroutines."""

    def __init__(self, rps: float):
        self.min_interval = 1.0 / rps if rps > 0 else 0.0
        self._lock = asyncio.Lock()
        self._next = 0.0

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            gap = self._next - now
            if gap > 0:
                await asyncio.sleep(gap)
                now = time.monotonic()
            self._next = now + self.min_interval


@dataclass
class Ctx:
    client: httpx.AsyncClient
    limiter: RateLimiter
    cfg: Config
    log: Logger
    sem: asyncio.Semaphore

    async def get(self, url: str, params: Optional[dict] = None) -> Optional[httpx.Response]:
        """GET with the global rate limit + retry. Returns None on a dead
        token (4xx) or exhausted retries; never raises."""
        for attempt in range(self.cfg.retries + 1):
            await self.limiter.wait()
            try:
                r = await self.client.get(url, params=params)
            except Exception as exc:  # network/timeout
                if attempt >= self.cfg.retries:
                    self.log.warning("GET failed %s: %s", url, exc)
                continue
            if r.status_code == 200:
                return r
            if 400 <= r.status_code < 500 and r.status_code != 429:
                return None  # dead token — don't waste a retry
            if attempt >= self.cfg.retries:
                self.log.warning("GET %s -> HTTP %s", url, r.status_code)
        return None


@dataclass
class SourceResult:
    name: str
    jobs: List[Job] = field(default_factory=list)
    boards_total: int = 0
    boards_failed: int = 0


async def run_boards(ctx: Ctx, name: str, rows: list, fetch_board) -> SourceResult:
    """Fan out one ATS across its board rows, logging progress."""
    res = SourceResult(name=name, boards_total=len(rows))
    done = 0

    async def one(row):
        nonlocal done
        async with ctx.sem:
            board_jobs = await fetch_board(ctx, row)
        done += 1
        if board_jobs is None:
            res.boards_failed += 1
        else:
            res.jobs.extend(board_jobs)
        if done % 500 == 0 or done == res.boards_total:
            ctx.log.info(
                "%s progress: %d/%d boards, %d title-matches, %d failed",
                name, done, res.boards_total, len(res.jobs), res.boards_failed,
            )

    if rows:
        await asyncio.gather(*[one(r) for r in rows])
    return res


async def fetch_all(cfg: Config, log: Logger, targets: str, limit: Optional[int] = None,
                    only: Optional[List[str]] = None) -> List[SourceResult]:
    from . import sources

    grouped = sources.read_targets(targets, limit=limit)
    limiter = RateLimiter(cfg.max_rps)
    sem = asyncio.Semaphore(CONCURRENCY)
    results: List[SourceResult] = []

    headers = {"User-Agent": "job-tracker/1.0 (+stage2)"}
    async with httpx.AsyncClient(
        timeout=cfg.timeout, follow_redirects=True, headers=headers
    ) as client:
        ctx = Ctx(client=client, limiter=limiter, cfg=cfg, log=log, sem=sem)

        for name, module in sources.ATS_SOURCES.items():
            if only and name not in only:
                continue
            rows = grouped.get(name, [])
            log.info("%s: starting %d boards", name, len(rows))
            results.append(await run_boards(ctx, name, rows, module.fetch_board))

        for name, module in sources.FEED_SOURCES.items():
            if only and name not in only:
                continue
            log.info("%s: starting feed", name)
            jobs = await module.fetch_feed(ctx)
            results.append(SourceResult(name=name, jobs=jobs, boards_total=1,
                                        boards_failed=0))

    return results
