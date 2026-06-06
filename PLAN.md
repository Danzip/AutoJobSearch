# AutoJobApply — Active Development Plan

Last updated: 2026-06-06

---

## All planned work is complete.

Nothing is pending. Next improvements would be driven by real batch results.

---

## What was built (this session)

| Area | File(s) | What |
|---|---|---|
| Public repo prep | `.gitignore`, `profile/personal.yaml`, `profile/personal.yaml.example` | Gitignored personal details; generic template committed |
| Public repo prep | `profile/candidate_profile.yaml` | Renamed from `daniel_profile.yaml` |
| Public repo prep | `input/` | Renamed from `imput/` (typo fixed) |
| Referral targeting | `src/referral_search.py` | DuckDuckGo LinkedIn search, writes `referral_targets.md` per job |
| Referral targeting | `batch_search.py` | Step 5 added: referral search after CV generation |
| Referral targeting | `app.py` | "Referral Targets" tab in Job Detail page |
| Scoring | `src/scorer.py` | PhD required → -20pts, MSc required → -10pts |
| Scoring | `src/analyzer.py` + `src/prompts.py` | `degree_required` field added to extraction |
| Reviewer pass | `src/reviewer.py` | Haiku second-pass after generation |
| Reviewer pass | `src/generator.py` | Optional `reviewer_llm` parameter |
| Reviewer pass | `batch_search.py` | Reviewer wired in |
| Gap analysis | `gap_analysis.py` | Standalone script; Critical/High/Medium/Low tiers; writes `outputs/gap_analysis.md` |
| PDF quality | `src/pdf_generator.py` | `_score_bullet`, `_cut_weakest_bullet`, `_CSS_SHRINK_OVERRIDES`, `generate_cv_pdf_verified` |
| CV tightening | `outputs/2026-06-05_batch/*/cv.md` | All 10 bullets rewritten to single tight lines |
| PDFs | `outputs/2026-06-05_batch/*/cv.pdf` | All 10 regenerated, all 1 page verified |
| Tests | `tests/` | 65 tests, all passing |
