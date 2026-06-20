# AutoJobApply

A local, human-in-the-loop job application assistant. Searches job boards, scores roles against your profile, and generates tailored CV drafts. Nothing is sent automatically.

---

## Changelog

### v1.3.0 — Two-pass CV generation + PDF style overhaul (2026-06-20)

#### CV PDF styling (`src/pdf_generator.py`)
- Name heading increased from 16pt to 22pt (scales down to 18pt under shrink overrides).
- Added separate subtitle line (`h1 + p`) at 10pt, centered, `#444` — renders the role/positioning title on its own line.
- Contact line (`h1 + p + p`) styled at 8.5pt centered with `·` separators.
- Section headers (`h2`) recolored to dark navy `#1a3055` with a 1.5px solid underline (was light `#ccc` hairline).
- `strong` weight raised from 600 → 700 so `**Role · Company**` format pops visibly.
- Added `h3` fallback (9.7pt bold) for any older `cv.md` files using `###` for role headers.

#### Two-pass CV generation (`src/generator.py`, `src/prompts.py`, `GENERATOR_PROMPT.md`)
- **Pass 1 — comprehensive draft:** sends the full story pool (all ~18 stories) with a 4–6 bullet-per-role instruction and no page limit, producing a 1.5–2 page dump of every relevant story.
- **Pass 2 — compress and package:** takes the comprehensive draft and compresses it to one dense page, simultaneously generating all application materials (LinkedIn message, recruiter email, talking points).
- Both passes share the same cached system prompt, so the docx story reference (~6,300 tokens) is written only once per batch.
- Removed `_select_stories()` pre-filtering — story selection now happens inside the LLM reasoning rather than a simple tag-overlap heuristic.

#### DB: `folder_name` column (`src/db.py`, `batch_search.py`)
- Added `folder_name TEXT` column to `jobs` table — stored at insert time, eliminating the need for fuzzy company/title matching when syncing a DB row to its output folder.
- Auto-migration: `ALTER TABLE jobs ADD COLUMN folder_name TEXT` runs on init so existing DBs upgrade seamlessly.
- `batch_search.py` now passes `folder_name` through `_save_to_db()`.

#### `write_cv.py` helper (new file)
- `write_job_cv(folder, angle, score, cv_md, ...)` — writes `cv.md` with the standard header block and immediately renders `cv.pdf` via `src/pdf_generator.py`.
- Used by batch regeneration scripts and by any manual CV writing workflow.

---

### v1.2.0 — Employer-completeness guard + docx story caching (2026-06-18)

- Added employer-completeness guard: before finalising any CV, checks each JD requirement against the available story pool. If a requirement is not covered, leaves it out and prompts the user to answer rather than hedging in the document.
- Cached docx story reference in the generator system prompt: the full `input/*.docx` narrative (~6,300 tokens) is appended to the cached system block instead of the per-job user prompt — billed once per batch rather than on every generation call.
- `cv.pdf` extraction now correctly handles older `cv.md` files where content started on the same line as `# Daniel Ziv`.
- Added manual job-list audit utility and CV PDF rendering utility.

---

### v1.1.0 — ATS prompt rewrite + output status folders (2026-06-15)

- Rewrote CV generation prompt for ATS coverage and one-page strictness.
- Changed output layout from per-run batch folders (`outputs/YYYY-MM-DD_batch/`) to three persistent status folders (`outputs/scraped/`, `outputs/interesting/`, `outputs/applied/`).
- `jobs.folder_name` added as the canonical link between a DB row and its output folder.
- Loosened job filtering to reduce false-negative scraping misses.
- Added Machine Learning Israel (machinelearning.co.il) as a discoverable job board.
- Added JobSpy-based LinkedIn job discovery as a second parallel search path.

---

---

## Quick Start

```bash
source .venv/bin/activate       # activate virtualenv
streamlit run app.py            # open http://localhost:8501
```

Or run the fully automated batch pipeline:

```bash
source .venv/bin/activate
python batch_search.py          # search → scrape → analyze → score → generate top 10 CVs
```

---

## Setup (first time)

```bash
# 1. Create virtualenv and install packages
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Add your API key
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY=sk-ant-...
# (Or set OPENAI_API_KEY if using OpenAI)

# 3. Add your personal details
cp profile/personal.yaml.example profile/personal.yaml
# Edit profile/personal.yaml with your name, email, phone, LinkedIn, location

# 4. Build your candidate profile (one-time, takes ~5 minutes)
# Drop your CV, resume, or any document describing your experience into input/
# Then open Claude Code in this terminal and say:
#   "Build my candidate profile from input/<your-file>"
# Claude Code will ask you clarifying questions and write profile/candidate_profile.yaml

# 5. Run the app
streamlit run app.py
```

**No API key?** You can still use Job Search and Add Job without a key. Analyze and Generate require an API key. Claude Code itself (this terminal) can also run the full pipeline for free - see "Running without API credits" below.

---

## Your Profile

The tool personalizes every CV and message to your specific experience. Before running searches, you need a profile.

**Step 1 — Personal details:** Copy `profile/personal.yaml.example` to `profile/personal.yaml` and fill in your name, email, phone, LinkedIn URL, and location. This file is gitignored and never committed.

**Step 2 — Experience profile:** Drop your CV, portfolio, or a detailed notes doc into `input/`. Then tell Claude Code:
```
Build my candidate profile from input/<your-file>
```
Claude Code will read your document, ask clarifying questions to understand your stories and domain strengths, and write `profile/candidate_profile.yaml`. This file contains:
- `personal` - contact and education details
- `key_metrics` - exact numbers to use verbatim in CVs
- `hard_limits` - skills you must NEVER claim (things you don't actually know)
- `stories` - tagged experience stories the generator selects from per-job
- `skills` - categorized technical skills

**Updating your profile:** Answer the clarifying questions at the end of each `summary.md`, then tell Claude Code "update profile from my answers in outputs/[batch]/". It will expand existing stories or add new ones.

**Profile notes:** Edit `profile/notes.md` directly, or use the Settings page in the Streamlit UI. Notes are included in every future generation prompt.

---

## What It Does

```
Search → Scrape → Analyze → Score → Generate → Review
  (free)   (free)   (LLM)    (free)   (LLM)     (you)
```

> **No API credits needed when running through Claude Code.**
> Claude Code (this terminal) acts as the LLM for Analyze and Generate steps — using your Claude subscription, not API credits.
> API credits are only required when running `batch_search.py` directly (unattended, outside this terminal).
>
> **Recommended flow:**
> 1. `python batch_search.py --dry-run` — search + scrape (free, no LLM)
> 2. Tell Claude Code: *"Analyze and generate CVs from data/all_scraped.json"*
> 3. Claude Code scores all jobs, generates CVs for ≥60 scorers, saves everything to the app

1. **Search** - queries Greenhouse, Workable, Comeet, and Workday via DuckDuckGo `site:` operators
2. **Scrape** - fetches job descriptions (Greenhouse uses their public JSON API; others use BeautifulSoup)
3. **Analyze** - sends the description to the LLM, extracts structured requirements (skills, domains, relevance scores 0-10)
4. **Score** - deterministic formula maps relevance scores to 0-100 (no LLM, instant)
5. **Generate** - LLM writes a tailored CV draft, LinkedIn message, recruiter email, and 5 talking points
6. **Review** - everything is editable in the UI before you use it

---

## Streamlit UI Pages

| Page | What it does |
|---|---|
| **Job Search** | Enter keywords, pick boards, get a list of URLs to add to inbox |
| **Job Inbox** | Table of all jobs sorted by score. Click a row to open Job Detail. |
| **Job Detail** | See job description, analysis, score, generated CV, cover letter, and messages. Analyze / Generate / Mark Applied / Skip buttons. |
| **Application Tracker** | All jobs grouped by status (interesting → applied → interview → offer) |
| **Settings / Profile** | API key status, config, token usage, profile notes editor |

### Adding a single job

**Via the UI (saves to database):** Open the app, go to Add Job, paste the URL or description. The job is scraped, saved to SQLite, and appears in your inbox immediately. Click Analyze → Generate to score it and produce a CV.

**Via Claude Code terminal (paste URL here):** Paste a job URL directly in this terminal. Claude Code will scrape it, analyze it, score it, and show you the result. It does **not** auto-save to the database — say "save it" and Claude Code will insert it into SQLite so it appears in the UI too. This is the fastest path for one-off jobs you find on LinkedIn or a company careers page.

---

## Batch Pipeline

`batch_search.py` runs the full pipeline automatically. Two modes are supported:

### Mode 1 — API key (fully automated)

Requires `ANTHROPIC_API_KEY` with credits in `.env`. Everything runs unattended.

```bash
python batch_search.py
# Default: "computer vision engineer israel", all boards, top 10 CVs

python batch_search.py --keywords "perception engineer israel" --top-n 5
python batch_search.py --boards Comeet Greenhouse --max-per-board 15
```

### Mode 2 — Claude Code / agentic terminal (zero API cost)

No API credits needed. Claude Code (this terminal) acts as the LLM for all analyze and generate steps, using your existing Claude subscription.

```bash
# Step 1: search + scrape only (free, no LLM)
python batch_search.py --dry-run

# Step 2: tell Claude Code in this terminal:
# "Analyze and generate CVs from data/scraped_jobs.json, top 10, write all output files"
# Claude Code reads the scraped descriptions, scores them, writes cv.md / summary.md /
# referral_targets.md / cv.pdf for each job — same output as Mode 1.
```

Both modes produce identical output. Mode 2 is free; Mode 1 costs ~$0.09/batch and runs without supervision.

**Output goes to** `outputs/YYYY-MM-DD_HHmm_batch/`:

```
SUMMARY.md              ← stats + ranked table of all analyzed jobs
01_Company_Role/
  description.md        ← full job description + original URL
  cv.md                 ← CV draft, LinkedIn message, recruiter email, talking points
  cover_letter.md       ← 4-paragraph ~280-word cover letter tailored to the role
  cv.pdf                ← 1-page formatted PDF, verified to fit
  summary.md            ← score breakdown, match reasons, concerns, clarifying questions
  referral_targets.md   ← 3-5 LinkedIn employee contacts + connection message template
02_Company_Role/
  ...
```

All top-N jobs are also saved to SQLite so they appear in the Streamlit UI.

---

## Referral Targeting

93% of Israeli companies have employee referral programs ("חבר מביא חבר"). Any employee can refer — even a junior dev — and gets compensated if you're hired. Referrals skip the initial filter and reach the hiring manager faster.

After generating CVs, the pipeline automatically searches LinkedIn for employees at each company via DuckDuckGo (`site:linkedin.com/in`). No login required.

**`referral_targets.md`** per job contains:
- 3-5 employee names, roles, and LinkedIn profile URLs
- A connection message template pre-filled with the company and role

**You send manually.** Edit the message with the person's name and any personal detail before sending. Never send automatically.

---

## Scoring System

Fully deterministic - no LLM involved, runs instantly.

| Component | Max pts | What it measures |
|---|---|---|
| CV + DL relevance | 30 | `cv_relevance` + `dl_relevance` from analyzer (0-10 each) |
| Real-time + Edge AI | 20 | `realtime_relevance` + `edge_ai_relevance` |
| Tracking / detection / seg | 15 | `tracking_relevance` |
| Seniority match | 15 | string match on seniority field |
| Production deployment | 10 | `production_relevance` |
| Geometry / robotics | 10 | `geometry_relevance` + `robotics_relevance` |
| **Penalties** | up to -30 | backend/NLP/fullstack domains: -20; zero CV signal: -10 |

Score threshold (default 60): jobs below this get a warning in the UI suggesting you skip.

Change threshold in `config.yaml`:
```yaml
scoring:
  threshold: 60
```

---

## CV Angles

The system picks one of six positioning angles per job based on which relevance signals are strongest:

| Angle | Best for |
|---|---|
| Edge AI / real-time deployment | Embedded, ADAS, edge hardware roles |
| Production CV pipeline owner | End-to-end pipeline, team lead adjacent roles |
| Object detection / perception | Detection/tracking/segmentation focused roles |
| Image registration / visual inspection | Inspection, metrology, registration roles |
| Robotics / tracking / geometry | Robotics, geometric CV, 3D vision roles |
| General senior CV/DL engineer | Catch-all for mixed or unclear roles |

---

## Token Cost Mitigation

All of these are active by default:

| Technique | Where | Saving |
|---|---|---|
| **Anthropic Batch API** | `batch_analyze()` in `analyzer.py` | **50% off** all analysis tokens - 24 jobs submitted in one batch instead of 24 sequential calls |
| **Haiku for analysis** | `get_analyze_llm()` → `config.yaml: analyze_model` | ~**10x cheaper** than Sonnet for JSON extraction |
| **Prompt caching** | `cache_control` on system block in `llm.py` | ~**90% off** system block tokens from call 2 onwards |
| **Story selection** | `_select_stories()` in `generator.py` | Sends **6 of 18 stories** matched by tag - ~60% fewer generator input tokens |
| **Description truncation** | `_truncate()` in `analyzer.py` | Caps job descriptions at `max_description_chars` (default 4000 chars) |

**Estimated cost per full batch** (40 URLs → 24 scraped → 24 analyzed → 10 CVs generated):
- Analysis: ~$0.015 (Haiku batch pricing)
- Generation: ~$0.075 (Sonnet, 10 CVs with story selection)
- **Total: ~$0.09 per run**

Configure in `config.yaml`:
```yaml
llm:
  analyze_model: claude-haiku-4-5-20251001   # change to sonnet for higher accuracy
  generate_model: claude-sonnet-4-6
  max_description_chars: 4000                # truncate descriptions beyond this
  max_stories_in_prompt: 6                   # max stories sent to generator
```

Token usage is logged to `data/token_usage.jsonl` and visible in Settings > Token Usage tab.

---

## Running Without API Credits

See **Mode 2** in the Batch Pipeline section above. Run `batch_search.py --dry-run` to search and scrape, then hand the results to Claude Code in this terminal to analyze, score, and write all output files. Zero cost — uses your Claude subscription, not API credits.

---

## Clarifying Questions Workflow

Each `summary.md` in the output batch ends with clarifying questions. When you answer them:

1. Paste your answers into the `**Your answers:**` section of the summary file
2. Tell Claude Code "update profile from my answers in [batch directory]"
3. Claude Code will update `profile/candidate_profile.yaml` - either expanding an existing story's `body` or adding a new story
4. Claude Code runs config sync so scoring dimensions stay aligned with your updated profile:
   ```bash
   python -c "from src.config_updater import sync_scoring_config; sync_scoring_config()"
   ```
   This step is also automatic at the start of every `batch_search.py` run.

The original reference doc in `input/` is **never modified** - it is the read-only source.

---

## Hard Rules (Never Violated in Any Output)

The generator never invents experience. Every CV bullet must trace to a story in `profile/candidate_profile.yaml`.

Rules enforced on every generation:
- **Never claim** any skill listed in `hard_limits` in your profile - things you don't actually know
- **Always use exact metrics** from `key_metrics` verbatim - never round or approximate numbers
- **Never auto-send** anything - no emails, no LinkedIn messages, no job applications
- **Stories only** - every bullet traces to a real experience in your profile; no invented claims

Add your own `hard_limits` when building your profile - anything you'd be embarrassed to be asked about in an interview.

---

## File Structure

```
AutoJobApply/
├── app.py                  ← Streamlit UI (all pages)
├── batch_search.py         ← Automated batch pipeline
├── requirements.txt
├── config.yaml             ← LLM models, score threshold, token settings
├── .env                    ← API keys (never commit)
├── input/
│   └── <your_reference_doc>               ← original reference, read-only
├── profile/
│   ├── candidate_profile.yaml             ← structured profile (stories, skills, hard limits)
│   ├── personal.yaml                      ← personal details (gitignored, fill in your own)
│   ├── personal.yaml.example              ← template for personal.yaml
│   └── notes.md                           ← app-managed profile notes
├── data/
│   └── jobs.sqlite         ← SQLite database
├── outputs/
│   └── YYYY-MM-DD_batch/   ← batch run outputs (description, cv, summary per job)
├── src/
│   ├── db.py               ← SQLite CRUD
│   ├── llm.py              ← LLM providers (Anthropic + OpenAI) with token logging
│   ├── analyzer.py         ← LLM job analysis + batch API
│   ├── scorer.py           ← deterministic scoring (no LLM)
│   ├── generator.py        ← CV/message generation with story selection
│   ├── job_search.py       ← DuckDuckGo site: queries
│   ├── token_tracker.py    ← token usage logging and cost calculation
│   ├── prompts.py          ← all LLM prompt templates
│   ├── utils.py            ← config/profile loading, JSON extraction
│   └── scrapers/           ← per-board scrapers (Greenhouse API, BS4 HTML)
└── tests/
    ├── test_scorer.py      ← 9 deterministic scorer tests
    └── test_analyzer.py    ← 7 analyzer + JSON extraction tests
```

---

## Running Tests

```bash
source .venv/bin/activate
pytest tests/ -v              # 65 tests, no API key needed
pytest tests/test_scorer.py   # scorer only
```
