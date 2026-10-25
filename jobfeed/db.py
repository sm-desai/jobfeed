"""SQLite storage at jobs.db. The upsert protects human-touched rows: a row
whose status != 'new' only ever has last_seen bumped and is rescored."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from typing import List, Optional

from .models import Job

DB_PATH = "jobs.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id            TEXT PRIMARY KEY,
    company       TEXT NOT NULL,
    title         TEXT NOT NULL,
    location      TEXT,
    state         TEXT,
    remote_flag   INTEGER NOT NULL,
    url           TEXT NOT NULL,
    posted_at     TEXT,
    source        TEXT NOT NULL,
    salary_min    INTEGER,
    salary_max    INTEGER,
    description   TEXT,
    score         INTEGER NOT NULL,
    score_reasons TEXT,
    status        TEXT NOT NULL DEFAULT 'new',
    applied_date  TEXT,
    notes         TEXT,
    first_seen    TEXT NOT NULL,
    last_seen     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_status_score ON jobs(status, score DESC);
"""


def _norm(s: str) -> str:
    return " ".join((s or "").lower().split())


def job_id(company: str, title: str, url: str) -> str:
    return hashlib.sha256(
        (_norm(company) + _norm(title) + (url or "")).encode("utf-8")
    ).hexdigest()


def connect(path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def upsert(conn: sqlite3.Connection, job: Job) -> str:
    """Returns 'inserted' | 'updated' | 'kept'."""
    jid = job_id(job.company, job.title, job.url)
    now = _now()
    reasons = json.dumps(job.score_reasons)
    row = conn.execute("SELECT status FROM jobs WHERE id = ?", (jid,)).fetchone()

    if row is None:
        conn.execute(
            """INSERT INTO jobs (id, company, title, location, state, remote_flag,
                   url, posted_at, source, salary_min, salary_max, description,
                   score, score_reasons, status, applied_date, notes,
                   first_seen, last_seen)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,'new',NULL,NULL,?,?)""",
            (jid, job.company, job.title, job.location, job.state,
             int(job.remote_flag), job.url, job.posted_at, job.source,
             job.salary_min, job.salary_max, job.description, job.score,
             reasons, now, now),
        )
        return "inserted"

    if row["status"] == "new":
        conn.execute(
            """UPDATE jobs SET last_seen=?, score=?, score_reasons=?,
                   salary_min=?, salary_max=?, description=?, posted_at=?,
                   location=?, state=?, remote_flag=?, company=?
               WHERE id=?""",
            (now, job.score, reasons, job.salary_min, job.salary_max,
             job.description, job.posted_at, job.location, job.state,
             int(job.remote_flag), job.company, jid),
        )
        return "updated"

    conn.execute(
        "UPDATE jobs SET last_seen=?, score=?, score_reasons=? WHERE id=?",
        (now, job.score, reasons, jid),
    )
    return "kept"


# ── queries ─────────────────────────────────────────────────────────────

def resolve_id(conn: sqlite3.Connection, prefix: str) -> str:
    rows = conn.execute("SELECT id FROM jobs WHERE id LIKE ?", (prefix + "%",)).fetchall()
    if not rows:
        raise KeyError(f"no job id starting with {prefix!r}")
    if len(rows) > 1:
        raise KeyError(f"{prefix!r} is ambiguous ({len(rows)} matches)")
    return rows[0]["id"]


def query_top(conn, top_n: int, min_score: int) -> List[sqlite3.Row]:
    return conn.execute(
        """SELECT * FROM jobs WHERE status='new' AND score >= ?
           ORDER BY score DESC, COALESCE(posted_at, last_seen) DESC LIMIT ?""",
        (min_score, top_n),
    ).fetchall()


def query_new_all(conn) -> List[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM jobs WHERE status='new' ORDER BY COALESCE(posted_at, last_seen) DESC"
    ).fetchall()


def set_status(conn, prefix: str, status: str, applied_date=None, notes=None) -> sqlite3.Row:
    jid = resolve_id(conn, prefix)
    if applied_date is not None:
        conn.execute("UPDATE jobs SET status=?, applied_date=? WHERE id=?",
                     (status, applied_date, jid))
    elif notes is not None:
        conn.execute("UPDATE jobs SET status=?, notes=? WHERE id=?", (status, notes, jid))
    else:
        conn.execute("UPDATE jobs SET status=? WHERE id=?", (status, jid))
    conn.commit()
    return conn.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone()


def set_status_by_id(conn, jid: str, status: str, applied_date=None) -> None:
    conn.execute("UPDATE jobs SET status=?, applied_date=? WHERE id=?",
                 (status, applied_date, jid))
    conn.commit()


def update_notes(conn, jid: str, notes: str) -> None:
    conn.execute("UPDATE jobs SET notes=? WHERE id=?", (notes, jid))
    conn.commit()


def status_counts(conn) -> dict:
    rows = conn.execute("SELECT status, COUNT(*) c FROM jobs GROUP BY status").fetchall()
    return {r["status"]: r["c"] for r in rows}


def applies_in_range(conn, start_iso: str, end_iso: str) -> int:
    row = conn.execute(
        """SELECT COUNT(*) c FROM jobs WHERE status='applied'
           AND applied_date IS NOT NULL AND applied_date >= ? AND applied_date <= ?""",
        (start_iso, end_iso),
    ).fetchone()
    return row["c"] if row else 0


def distinct_states(conn) -> List[str]:
    return [r["state"] for r in conn.execute(
        "SELECT DISTINCT state FROM jobs WHERE state IS NOT NULL ORDER BY state")]


def distinct_sources(conn) -> List[str]:
    return [r["source"] for r in conn.execute(
        "SELECT DISTINCT source FROM jobs ORDER BY source")]


def all_rows(conn) -> List[sqlite3.Row]:
    return conn.execute("SELECT * FROM jobs ORDER BY score DESC").fetchall()
