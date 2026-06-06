# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Active development plan:** See `PLAN.md` for the full task list and next steps.

## Commands

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then add ANTHROPIC_API_KEY

# Run the app
streamlit run app.py   # opens localhost:8501

# Run tests (no API key needed)
pytest tests/ -v

# Run a single test
pytest tests/test_scorer.py::test_high_cv_role_scores_above_75 -v
```

> **⚠️ IMPORTANT — HOW THE PIPELINE WORKS:**
>
> **Running through Claude Code (this terminal) = ZERO API cost.**
> Claude Code itself acts as the LLM for all Analyze and Generate steps.
> API tokens are ONLY needed when `batch_search.py` runs unattended (outside this terminal).
>
> **Standard workflow (no API cost):**
> 1. `python batch_search.py --dry-run --skip-config-sync` — search + scrape → `data/all_scraped.json`
> 2. Tell Claude Code: *"Analyze and generate CVs from data/all_scraped.json"*
> 3. Claude Code analyzes each job, scores them, generates CVs for score ≥60, saves to DB + outputs/

## Architecture

Single-file Streamlit app (`app.py`) with page routing via `st.session_state.page`. All pages are functions in that file. Backend is SQLite via `src/db.py`.

**Data flow for a job:**
1. Add (scrape URL or paste description) → `src/scrapers/` → `src/db.py`
2. Analyze (button) → `src/analyzer.py` (LLM) → extracts JSON requirements → `src/scorer.py` (deterministic) → score + angle stored in DB
3. Generate (button) → `src/generator.py` (LLM) → CV draft / LinkedIn / email / talking points stored in `applications` table
4. User edits generated text in the UI and saves manually

**No action is ever taken automatically** - every LLM call requires an explicit button click.

## Key Files

| File | Role |
|---|---|
| `app.py` | All Streamlit pages and routing |
| `src/db.py` | SQLite CRUD; `jobs` and `applications` tables |
| `src/scorer.py` | Deterministic scorer (weights sum to 100); no LLM |
| `src/analyzer.py` | LLM call to extract requirements JSON |
| `src/generator.py` | LLM call to generate CV draft, LinkedIn, email, talking points |
| `src/llm.py` | `LLMProvider` ABC; Anthropic (with prompt caching) + OpenAI impls |
| `src/prompts.py` | All prompt templates - edit here to tune LLM behavior |
| `src/scrapers/` | One scraper per job board; `base.py` dispatches by URL |
| `src/job_search.py` | DuckDuckGo site: queries for job discovery |
| `profile/candidate_profile.yaml` | Source of truth - stories with tags, skills, hard limits, key metrics |
| `profile/notes.md` | App-managed profile notes (appended from Settings page) |

## Profile Structure

`profile/candidate_profile.yaml` has tagged stories that the LLM uses to generate tailored content. Each story has `id`, `tags`, `headline`, and `body`. The `hard_limits` section lists skills that must never be claimed. The `key_metrics` section has exact numbers to use verbatim.

**Never modify the scoring weights without updating tests.** The weights in `src/scorer.py` are designed to sum to 100 at maximum; changing one changes the scale.

## Batch Pipeline

```bash
# Full automated run (search → scrape → analyze → score → generate top 10 CVs)
source .venv/bin/activate
python batch_search.py

# Custom keywords or boards
python batch_search.py --keywords "perception engineer israel" --top-n 5
python batch_search.py --boards Comeet Greenhouse --max-per-board 15
```

Output goes to `outputs/YYYY-MM-DD_HHmm_batch/`:
- `SUMMARY.md` - stats + ranked table of all analyzed jobs
- `NN_Company_Title/description.md` - full job description + original URL
- `NN_Company_Title/cv.md` - tailored CV draft, LinkedIn message, recruiter email, talking points
- `NN_Company_Title/summary.md` - score breakdown, match reasons, concerns, clarifying questions

All top-N jobs are also saved to SQLite so they appear in the Streamlit UI.

## Clarifying Questions Workflow

Each `summary.md` ends with clarifying questions the LLM generated. When the user answers them:

1. Read the user's answers
2. Update `profile/candidate_profile.yaml` - either add a new story entry under `stories:` or append to an existing story's `body`
3. If the answer reveals a genuinely new capability or framing, add it as a new story with appropriate tags
4. **After updating the profile**, run the config sync so scoring dimensions stay aligned:
   ```bash
   python -c "from src.config_updater import sync_scoring_config; sync_scoring_config()"
   ```
5. Confirm to the user what was updated

**Never** modify the original reference doc in `input/` - it is read-only.  
The editable profile is `profile/candidate_profile.yaml`.

## Scoring Config Auto-Sync

`config.yaml`'s `scoring` section (dimensions, excluded_domains, primary_keys, candidate_degree) is
auto-generated from `profile/candidate_profile.yaml` by the LLM. It runs automatically at the
start of `batch_search.py`. You can also trigger it manually:

```bash
python -c "from src.config_updater import sync_scoring_config; sync_scoring_config()"
```

This means:
- A PhD candidate gets no degree penalty (candidate_degree=phd)
- A biomedical engineer gets biomedical-specific scoring dimensions instead of CV/edge-AI ones
- Excluded domains derive from the profile's `hard_limits` and story content
- Skip the sync with `--skip-config-sync` flag if you want to lock the current config

## Token Cost Mitigation

All techniques are active. Estimated cost per 24-job batch: **~$0.07**.

| Technique | Where | Saving |
|---|---|---|
| **Anthropic Batch API** | `batch_analyze()` in `analyzer.py` | 50% off all analysis tokens |
| **Haiku for analysis** | `get_analyze_llm()` in `llm.py` | ~10x cheaper than Sonnet |
| **Prompt caching** | `cache_control` on system block in both providers | ~90% off repeated system tokens |
| **Story selection** | `_select_stories()` in `generator.py` | Sends 6 of 18 stories → ~60% fewer prompt tokens |
| **Description truncation** | `_truncate()` in `analyzer.py` | Caps at `max_description_chars` (default 4000) |

Tune in `config.yaml`:
```yaml
llm:
  analyze_model: claude-haiku-4-5-20251001   # change to sonnet for higher accuracy
  generate_model: claude-sonnet-4-6
  max_description_chars: 4000
  max_stories_in_prompt: 6
```

Token usage is logged to `data/token_usage.jsonl` and visible in Settings > Token Usage tab.

**Do NOT add streaming** - it does not reduce token cost, only improves latency.

## Scraping Performance

Comeet (Angular SPA) requires Playwright. The bottleneck is per-page load time (~4-6s each).

| Technique | Where | Saving |
|---|---|---|
| **Parallel job URL scraping** | `scrape_batch()` in `src/scrapers/comeet.py` | ~4.5× faster (6 browsers in parallel) |
| **Parallel company page discovery** | `search_comeet_companies()` in `src/job_search_comeet.py` | ~6× faster (14 pages → 6 parallel) |

Tune workers in `config.yaml` (each worker = one Chromium instance, ~150 MB RAM):
```yaml
scraping:
  comeet_workers: 6
```

**Key Comeet scraper details:**
- Uses `wait_until="domcontentloaded"` + 4000ms explicit wait (not `networkidle` — Angular makes continuous requests)
- `page.inner_text("body")` for full description (not a CSS selector — avoids partial div capture)
- Company name extracted from URL slug, not DOM (DOM shows "All Jobs" navigation noise)
- Closed/redirect jobs detected by `len(description) < 200` (not by DOM element presence)

## CV Writing Rules (enforced in every generated CV)

These live in `src/prompts.py` GENERATOR_SYSTEM and are injected into every LLM generation call:

1. **No em dashes** - use commas, colons, or plain hyphens. Never the "—" character.
2. **One page in spirit** - max 5-6 tight bullet points. No preamble sentence, no padding.
3. **Mirror JD buzzwords** - use the job description's exact terminology where it accurately describes the candidate's experience (e.g. "real-time inference", "edge deployment", "model compression", "perception pipeline"). Do not paraphrase away from JD language.
4. **Exact metrics** - 0.321 AP50:95, 20 FPS, 80 MB, 100x speedup. Never rounded or changed.
5. **Stories only** - every bullet must trace to a story in `profile/candidate_profile.yaml`. No invented claims.

## Hard Rules - Never Violate

These apply to ALL generated content (CVs, messages, emails, talking points):

- **Never claim** any skill in `hard_limits` section of `candidate_profile.yaml` (SLAM, VIO, ROS2, RL, LiDAR, PyTorch Lightning, end-to-end driving, foundation model pretraining, ISO 26262)
- **Never auto-send** anything - no emails, no LinkedIn messages, no applications
- **Use exact metrics** - 0.321 AP50:95 (not 0.30), 20 FPS, 80 MB, 100× speedup
- **Head pose = DMS only** - not full body, not CMS (different team)
- **IMU work = coordinate sync** - not VIO, not SLAM
- **Razor Labs = Axon Vision** - same company, same team, different legal entity

## Scoring Weights (sum to 100 at max)

Dimensions are defined in `config.yaml` under `scoring.dimensions` and auto-synced from the
candidate profile. Seniority always contributes up to 15 pts; all other dimensions sum to 85 max.
Penalties (domain mismatch, zero-signal, management, degree gap) can reduce score by up to -55 pts.

**Never modify scoring weights without updating tests.** The math in `src/scorer.py` assumes
`max_pts` across all dimensions sums to 85.
