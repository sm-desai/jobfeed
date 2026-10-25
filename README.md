# jobfeed

A tiny, local-first **job tracker for any profession**. Tell it what you do,
and it pulls matching openings from public job APIs, scores them, and gives you
a clean CLI + web UI to triage and track applications — all in a local SQLite
file. No scraping, no account, nothing leaves your machine except the API calls.

```
python jf.py init "registered nurse"
python jf.py fetch
python jf.py ui
```

---

## What it does

- **One command to start:** `jf init "<profession>"` generates your config.
- **Pulls from universal job sources** keyed to your profession: **Adzuna**,
  **Remotive**, **RemoteOK** (and optionally company **Greenhouse/Ashby/Lever**
  boards if you have a list).
- **Filters** by title rules you control, keeps US + remote roles, and never
  silently drops a role with unknown location or pay.
- **Scores & ranks** by keywords, freshness, remote, and location — and shows
  *why* each role ranked where it did.
- **Tracks your funnel:** mark roles Applied / Interested / Skipped, add notes,
  see weekly application counts.
- **Web UI** (Streamlit): sortable table, multi-select, bulk-pass, per-role
  actions, and a direct apply link.

## Quickstart

Requires Python 3.9+.

```bash
# 1. clone + enter
git clone https://github.com/<you>/jobfeed.git && cd jobfeed

# 2. install
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. get a free Adzuna key at https://developer.adzuna.com, then:
cp .env.example .env         # and paste your ADZUNA_APP_ID / ADZUNA_APP_KEY

# 4. pick your profession
python jf.py init "data scientist"

# 5. pull jobs, then read them
python jf.py fetch
python jf.py digest          # top 25 in your terminal
python jf.py ui              # or the web UI at http://localhost:8501
```

## Commands

| Command | What it does |
|---|---|
| `jf init "<profession>"` | generate `config.yaml` for that profession |
| `jf fetch` | poll the enabled sources, dedupe, store |
| `jf digest` / `--all` | top-N by score (markdown) / everything new |
| `jf ui` | launch the web UI on localhost:8501 |
| `jf apply <id>` | mark applied (id = the short code in the digest) |
| `jf skip <id> --why "…"` | mark skipped with a note |
| `jf status` | funnel counts |
| `jf export --out jobs.csv` | dump everything to CSV |

## Tuning (`config.yaml`)

`jf init` writes a commented `config.yaml` — everything is editable, nothing is
hardcoded in the code:

- **`titles.include` / `exclude`** — regexes a title must / must not match. The
  base phrase also matches seniority variants ("Senior …", "Lead …").
- **`query.adzuna_what`** — your Adzuna search string.
- **`locations`** — `states: []` accepts any US location; set e.g. `[CA, NY, TX]`
  to narrow. `reject_hints` drop non-US noise.
- **`scoring`** — `keyword_boosts` / `keyword_penalties` (regex → points),
  `state_boosts`, `remote_boost`, and `freshness`. See `config.example.yaml`.
- **`sources`** — toggle each source on/off.

Re-run `jf fetch` after editing. Human-touched rows (applied/skipped) are never
overwritten — only re-scored.

## Daily automation (optional)

Run it every morning with `cron` (macOS/Linux). `crontab -e` and add:

```
0 7 * * *  cd /path/to/jobfeed && .venv/bin/python jf.py fetch >> cron.log 2>&1
```

## Advanced: company ATS boards

`Adzuna + Remotive + RemoteOK` need no company list. To also poll specific
company boards, set `greenhouse`/`ashby`/`lever` to `true` in `config.yaml` and
drop a `targets.csv` next to `jf.py`:

```csv
company,ats,token
Acme,greenhouse,acme
Globex,ashby,globex
```

The `token` is the board slug (e.g. `boards.greenhouse.io/<token>`).

## Data & privacy

Everything lives in local files (`jobs.db`, `config.yaml`, `.env`) — all
gitignored. The only network calls are to the public job APIs you enabled.

## License

MIT — see [LICENSE](LICENSE).
