"""Local Streamlit UI for jobfeed. Launched by `jf ui`."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import streamlit as st

from jobfeed import db
from jobfeed.config import ROOT, get_config
from jobfeed.normalize import days_since


@st.cache_resource
def _cfg():
    return get_config()


def _conn():
    conn = db.connect(str(ROOT / "jobs.db"))
    db.init_schema(conn)
    return conn


def _salary(lo, hi) -> str:
    def k(n):
        return f"${n/1000:.0f}k" if pd.notna(n) and n else None
    lo_s, hi_s = k(lo), k(hi)
    if lo_s and hi_s:
        return f"{lo_s}–{hi_s}"
    return lo_s or hi_s or "—"


def _write_status(jid: str, status: str):
    conn = _conn()
    applied = date.today().isoformat() if status == "applied" else None
    db.set_status_by_id(conn, jid, status, applied_date=applied)
    conn.close()
    st.toast(f"Marked {status}")


def _save_notes(jid: str, key: str):
    conn = _conn()
    db.update_notes(conn, jid, st.session_state.get(key, ""))
    conn.close()
    st.toast("Notes saved")


def _skip_many(jids):
    conn = _conn()
    for jid in jids:
        db.set_status_by_id(conn, jid, "skipped")
    conn.close()
    st.toast(f"Skipped {len(jids)} listings")


def _fetch_now():
    proc = subprocess.Popen([sys.executable, "jf.py", "fetch"], cwd=str(ROOT),
                            stdout=open(ROOT / "fetch_stdout.log", "a"),
                            stderr=subprocess.STDOUT)
    st.session_state["fetch_pid"] = proc.pid
    st.toast(f"jf fetch started (pid {proc.pid}) — refresh to see new rows")


def main():
    st.set_page_config(page_title="jobfeed", layout="wide")
    cfg = _cfg()
    conn = _conn()

    with st.sidebar:
        st.header("Filters")
        search = st.text_input("Search company / title", "")
        f_status = st.multiselect("Status", ["new", "interested", "applied", "skipped"],
                                  default=["new", "interested"])
        f_states = st.multiselect("State", db.distinct_states(conn), default=[])
        remote_only = st.checkbox("Remote only", value=False)
        min_score = st.slider("Min score", -50, 120, int(cfg.digest_min_score))
        min_salary = st.number_input("Min salary ($)", min_value=0, value=0, step=10000)
        f_sources = st.multiselect("Source", db.distinct_sources(conn), default=[])
        posted_within = st.slider("Posted within N days (0 = any)", 0, 60, 0)

    left, right = st.columns([0.75, 0.25])
    left.title(f"jobfeed · {cfg.profession}")
    if right.button("🔄 Fetch now", width="stretch"):
        _fetch_now()

    counts = db.status_counts(conn)
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    this_week = db.applies_in_range(conn, monday.isoformat(), today.isoformat())
    prev_mon, prev_sun = monday - timedelta(days=7), monday - timedelta(days=1)
    last_week = db.applies_in_range(conn, prev_mon.isoformat(), prev_sun.isoformat())
    m = st.columns(6)
    for col, label, val in zip(m, ["New", "Interested", "Applied", "Skipped",
                                   "Applied this week", "Applied last week"],
                               [counts.get("new", 0), counts.get("interested", 0),
                                counts.get("applied", 0), counts.get("skipped", 0),
                                this_week, last_week]):
        col.metric(label, val)
    st.divider()

    rows = [dict(r) for r in db.all_rows(conn)]
    conn.close()
    if not rows:
        st.info("No jobs yet. Run `jf fetch` (or Fetch now) to populate jobs.db.")
        return

    df = pd.DataFrame(rows)
    df["age"] = df["posted_at"].apply(lambda p: days_since(p) if p else None)
    df["salary"] = df.apply(lambda r: _salary(r["salary_min"], r["salary_max"]), axis=1)

    if f_status:
        df = df[df["status"].isin(f_status)]
    if f_states:
        df = df[df["state"].isin(f_states)]
    if remote_only:
        df = df[df["remote_flag"] == 1]
    df = df[df["score"] >= min_score]
    if min_salary > 0:
        known = df["salary_max"].fillna(df["salary_min"])
        df = df[known >= min_salary]
    if f_sources:
        df = df[df["source"].isin(f_sources)]
    if posted_within > 0:
        df = df[df["age"].notna() & (df["age"] <= posted_within)]
    if search.strip():
        s = search.strip().lower()
        df = df[df["company"].str.lower().str.contains(s, na=False)
                | df["title"].str.lower().str.contains(s, na=False)]

    df = df.sort_values("score", ascending=False).reset_index(drop=True)
    st.caption(f"{len(df)} jobs match")
    if df.empty:
        st.info("No jobs match the current filters.")
        return

    event = st.dataframe(
        df, width="stretch", hide_index=True, height=460,
        on_select="rerun", selection_mode="multi-row",
        column_order=["score", "company", "title", "location", "salary",
                      "posted_at", "source", "age"],
        column_config={
            "score": st.column_config.NumberColumn("Score", width="small"),
            "company": st.column_config.TextColumn("Company"),
            "title": st.column_config.TextColumn("Title", width="large"),
            "location": st.column_config.TextColumn("Location"),
            "salary": st.column_config.TextColumn("Salary"),
            "posted_at": st.column_config.TextColumn("Posted"),
            "source": st.column_config.TextColumn("Source", width="small"),
            "age": st.column_config.NumberColumn("Age (d)", width="small"),
        },
    )

    sel = event.selection.rows if event and event.selection else []
    if not sel:
        st.info("Tick one or more rows to see a summary of each below — then pass in "
                "bulk, or apply / mark interested individually.")
        return

    selected = [df.iloc[i].to_dict() for i in sel]
    st.divider()
    head, action = st.columns([0.6, 0.4])
    head.subheader(f"Selected — {len(selected)} listing{'s' if len(selected) != 1 else ''}")
    action.button(f"🚫 Pass on all {len(selected)} selected", key="bulk_skip",
                  on_click=_skip_many, args=([j["id"] for j in selected],), width="stretch")
    for job in selected:
        _summary_card(cfg, job)


def _summary_card(cfg, job):
    jid = job["id"]
    with st.container(border=True):
        flag = ""
        known = job["salary_max"] or job["salary_min"]
        if cfg.comp_flag_below and known and known < cfg.comp_flag_below:
            flag = " ⚠low"
        remote = "Remote" if job["remote_flag"] else job["state"]
        st.markdown(f"**{job['title']} — {job['company']}**  ·  score {job['score']}")
        st.caption(f"{remote} · {job['location']} · "
                   f"{_salary(job['salary_min'], job['salary_max'])}{flag} · "
                   f"{job['source']} · posted {job['posted_at'] or '?'} · "
                   f"status: **{job['status']}**")
        b = st.columns([1, 1, 1, 2])
        b[0].button("✅ Applied", key=f"a_{jid}", on_click=_write_status,
                    args=(jid, "applied"), width="stretch")
        b[1].button("⭐ Interested", key=f"i_{jid}", on_click=_write_status,
                    args=(jid, "interested"), width="stretch")
        b[2].button("🚫 Skip", key=f"s_{jid}", on_click=_write_status,
                    args=(jid, "skipped"), width="stretch")
        if job["url"]:
            b[3].link_button("↗ Apply / view", job["url"], width="stretch")
        with st.expander("description, score breakdown & notes"):
            try:
                reasons = json.loads(job.get("score_reasons") or "[]")
            except Exception:
                reasons = []
            if reasons:
                st.markdown("**Why this score:** " + ", ".join(f"`{r}`" for r in reasons))
            notes_key = f"notes_{jid}"
            st.text_area("Notes (saved on blur)", value=job.get("notes") or "",
                         key=notes_key, on_change=_save_notes, args=(jid, notes_key))
            st.markdown("**Description**")
            st.write(job.get("description") or "_(no description)_")


if __name__ == "__main__":
    main()
