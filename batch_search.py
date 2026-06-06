#!/usr/bin/env python3
"""
Automated batch: search → scrape → analyze → score → generate CVs for top N.
Usage:
  python batch_search.py
  python batch_search.py --keywords "perception engineer israel" --top-n 5
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

import src.db as db
from src.analyzer import analyze_job, batch_analyze
from src.generator import generate_application_content
from src.job_search import search_jobs, ALL_BOARDS
from src.job_search_workday import search_workday_companies
from src.llm import get_analyze_llm, get_generate_llm, get_review_llm
from src.referral_search import find_referral_targets, write_referral_targets_md
from src.scorer import score_requirements
from src.scrapers.base import ScraperError, scrape_url
from src.token_tracker import print_summary as print_token_summary
from src.utils import load_profile, load_profile_notes, save_profile_notes


def slugify(text: str, max_len: int = 35) -> str:
    text = re.sub(r"[^\w\s-]", "", str(text))
    text = re.sub(r"[\s/-]+", "_", text)
    return text[:max_len].strip("_")


# ─── Main pipeline ─────────────────────────────────────────────────────────────

def run_batch(
    keywords: str = "computer vision engineer israel",
    boards: list = None,
    max_per_board: int = 10,
    top_n: int = 10,
    skip_config_sync: bool = False,
) -> Path:
    db.init_db()

    if not skip_config_sync:
        from src.config_updater import sync_scoring_config
        sync_scoring_config(llm=get_analyze_llm())

    profile = load_profile()
    analyze_llm  = get_analyze_llm()   # Haiku — cheap extraction
    generate_llm = get_generate_llm()  # Sonnet — quality writing
    review_llm   = get_review_llm()    # Haiku — reviewer pass

    if boards is None:
        boards = ALL_BOARDS

    out_dir = Path("outputs") / datetime.now().strftime("%Y-%m-%d_%H%M_batch")
    out_dir.mkdir(parents=True, exist_ok=True)

    _banner("AUTOJOBAPPLY BATCH RUN")
    print(f"Keywords : {keywords}")
    print(f"Boards   : {', '.join(boards)}")
    print(f"Output   : {out_dir}/\n")

    # ── 1. Search ──────────────────────────────────────────────────────────────
    _step(1, 4, "Searching job boards")
    raw = search_jobs(keywords, boards, max_results=max_per_board)
    urls = [r for r in raw if r.get("url")]
    print(f"  DuckDuckGo: {len(urls)} URLs found")

    print("  Direct Workday company search:")
    workday_direct = search_workday_companies(keywords, max_per_company=max_per_board)
    print(f"  → {len(urls)} DDG URLs + {len(workday_direct)} Workday direct\n")

    # ── 2. Scrape ──────────────────────────────────────────────────────────────
    _step(2, 4, "Fetching job descriptions")
    scraped = []

    # Workday direct results already have descriptions — add them immediately
    seen_urls = set()
    for wd in workday_direct:
        if wd["url"] in seen_urls:
            continue
        seen_urls.add(wd["url"])
        from src.scrapers.base import ScrapedJob
        scraped.append({
            "url": wd["url"],
            "board": wd["board"],
            "scraped": ScrapedJob(
                title=wd["title"],
                company=wd["company"],
                description=wd["description"],
                source="workday_api",
            ),
        })
        print(f"  OK    {wd['title'][:55]}  [{wd['company']}]")

    for r in urls:
        if r["url"] in seen_urls:
            continue
        seen_urls.add(r["url"])
        try:
            job = scrape_url(r["url"])
            if len(job.description.strip()) < 80:
                print(f"  SKIP  (too short)  {r['url'][:70]}")
                continue
            scraped.append({
                "url": r["url"],
                "board": r["board"],
                "scraped": job,
            })
            title = (job.title or r["title"])[:55]
            print(f"  OK    {title}")
        except (ScraperError, Exception) as exc:
            print(f"  FAIL  {r['url'][:60]}  —  {exc}")
        time.sleep(0.4)
    print(f"\n  → {len(scraped)} jobs with real descriptions\n")

    # ── 3. Analyze + score (Batch API — 50% discount) ────────────────────────
    _step(3, 4, f"Analyzing and scoring {len(scraped)} jobs")
    descriptions = [item["scraped"].description for item in scraped]
    try:
        all_reqs = batch_analyze(descriptions)
    except Exception as exc:
        print(f"  Batch API failed ({exc}), falling back to sequential...")
        all_reqs = []
        for item in scraped:
            try:
                all_reqs.append(analyze_job(item["scraped"].description, analyze_llm))
            except Exception as e:
                print(f"  ERROR {item['url'][:60]}: {e}")
                from src.analyzer import _DEFAULTS
                all_reqs.append(_DEFAULTS.copy())
            time.sleep(0.4)

    analyzed = []
    for item, reqs in zip(scraped, all_reqs):
        s = item["scraped"]
        try:
            score, explanation, angle = score_requirements(reqs)
            company = reqs.get("company") or s.company or item["board"]
            title   = reqs.get("title")   or s.title   or "Unknown"
            analyzed.append({
                "url":         item["url"],
                "board":       item["board"],
                "company":     company,
                "title":       title,
                "location":    s.location or "",
                "description": s.description,
                "reqs":        reqs,
                "score":       score,
                "explanation": explanation,
                "angle":       angle,
            })
            bar = "█" * int(score // 10) + "░" * (10 - int(score // 10))
            print(f"  {bar}  {score:5.0f}/100  {company[:22]:<22} {title[:40]}")
        except Exception as exc:
            print(f"  ERROR scoring {item['url'][:60]}: {exc}")

    if not analyzed:
        print("No jobs analyzed successfully. Exiting.")
        return out_dir

    analyzed.sort(key=lambda x: x["score"], reverse=True)
    top = analyzed[:top_n]

    avg_all = sum(j["score"] for j in analyzed) / len(analyzed)
    avg_top = sum(j["score"] for j in top) / len(top)

    print(f"\n{'─'*60}")
    print(f"  Jobs found:            {len(urls)}")
    print(f"  Successfully analyzed: {len(analyzed)}")
    print(f"  Best match score:      {analyzed[0]['score']:.0f}/100")
    print(f"  Average score:         {avg_all:.0f}/100")
    print(f"  Top {len(top)} average:        {avg_top:.0f}/100")
    print(f"{'─'*60}\n")

    # ── 4. Generate CVs for top N ─────────────────────────────────────────────
    _step(4, 5, f"Generating CVs for top {len(top)} matches")
    for rank, job in enumerate(top, 1):
        dir_name = f"{rank:02d}_{slugify(job['company'])}_{slugify(job['title'])}"
        job_dir = out_dir / dir_name
        job_dir.mkdir(exist_ok=True)

        # Persist to DB so the Streamlit app shows these too
        job_id = _save_to_db(job)

        try:
            content = generate_application_content(
                job, job["reqs"], profile, job["angle"], generate_llm, reviewer_llm=review_llm
            )
        except Exception as exc:
            print(f"  FAIL generating CV for {job['company']}: {exc}")
            content = {
                "cv_draft_markdown": f"[Generation failed: {exc}]",
                "linkedin_message": "",
                "recruiter_email": "",
                "talking_points": [],
            }

        db.upsert_application({
            "job_id": job_id,
            "selected_cv_angle": job["angle"],
            "cv_draft_markdown": content["cv_draft_markdown"],
            "linkedin_message_draft": content["linkedin_message"],
            "recruiter_email_draft": content["recruiter_email"],
            "talking_points": json.dumps(content.get("talking_points", [])),
            "notes": "",
            "status": "cv_generated",
        })
        db.update_job(job_id, status="cv_generated")

        # Write files
        _write_description(job_dir, job)
        _write_cv(job_dir, job, content)
        _write_summary(job_dir, rank, job, content, generate_llm)

        print(f"  [{rank:2d}] {job['score']:.0f}/100  {job['company']} — {job['title'][:45]}")
        time.sleep(0.5)

    # ── 5. Referral search for top N ──────────────────────────────────────────
    _step(5, 5, f"Searching referral targets for top {len(top)} matches")
    for rank, job in enumerate(top, 1):
        dir_name = f"{rank:02d}_{slugify(job['company'])}_{slugify(job['title'])}"
        job_dir = out_dir / dir_name
        targets = find_referral_targets(job["company"])
        write_referral_targets_md(job_dir, job, targets)
        n = len(targets)
        print(f"  [{rank:2d}] {n} target{'s' if n != 1 else ''} found  {job['company']}")
        time.sleep(1.0)  # be polite to DuckDuckGo

    # Overall summary
    _write_overall_summary(out_dir, keywords, boards, len(urls), analyzed, top)

    # Generate PDFs for all top-N CVs
    print("Generating PDFs...")
    from src.pdf_generator import batch_dir_to_pdf
    batch_dir_to_pdf(out_dir, profile)

    _banner("DONE")
    print(f"Output directory : {out_dir}/")
    print(f"Files per job    : description.md  cv.md  cover_letter.md  cv.pdf  summary.md  referral_targets.md")
    print(f"Streamlit        : http://localhost:8501  (Job Inbox shows all analyzed jobs)")
    print_token_summary()
    return out_dir


# ─── File writers ──────────────────────────────────────────────────────────────

def _write_description(job_dir: Path, job: dict):
    r = job["reqs"]
    (job_dir / "description.md").write_text(f"""# {job['company']} — {job['title']}

**URL:** {job['url']}
**Location:** {job['location'] or 'Not specified'}
**Source board:** {job['board']}
**Seniority:** {r.get('seniority', 'unknown')}
**Domains:** {', '.join(r.get('domains', []))}
**Required skills:** {', '.join(r.get('required_skills', [])) or '—'}
**Nice to have:** {', '.join(r.get('nice_to_have_skills', [])) or '—'}

---

{job['description']}
""")


def _write_cv(job_dir: Path, job: dict, content: dict):
    tps = content.get("talking_points", [])
    tp_text = "\n".join(f"{i}. {p}" for i, p in enumerate(tps, 1))

    (job_dir / "cv.md").write_text(f"""# CV Draft — {job['company']} / {job['title']}

**Angle:** {job['angle']}
**Score:** {job['score']:.0f}/100

---

{content['cv_draft_markdown']}

---

## LinkedIn Message

{content['linkedin_message']}

---

## Recruiter Email

{content['recruiter_email']}

---

## Interview Talking Points

{tp_text}
""")

    if content.get("cover_letter"):
        (job_dir / "cover_letter.md").write_text(f"""# Cover Letter — {job['company']} / {job['title']}

{content['cover_letter']}
""")


def _write_summary(job_dir: Path, rank: int, job: dict, content: dict, llm):
    r = job["reqs"]
    reasons  = r.get("reasons_to_apply", [])
    concerns = r.get("concerns", [])

    cq_prompt = (
        f"Job: {job['company']} — {job['title']}\n"
        f"Required: {', '.join(r.get('required_skills', []))}\n"
        f"Concerns: {'; '.join(concerns)}\n"
        f"Score: {job['score']:.0f}/100\n\n"
        "Generate 2-3 specific clarifying questions whose answers would improve this candidate's "
        "CV fit for this role — focus on experience that may exist but isn't documented, or skills "
        "that could be framed more precisely. Numbered list only, no preamble."
    )
    try:
        cq_text = llm.complete(cq_prompt).strip()
    except Exception:
        cq_text = "1. [Could not generate — add manually]"

    reasons_md  = "\n".join(f"- {x}" for x in reasons)  or "- See score breakdown"
    concerns_md = "\n".join(f"- {x}" for x in concerns) or "- None identified"

    (job_dir / "summary.md").write_text(f"""# Summary — {job['company']} / {job['title']}

**Rank:** #{rank}
**Score:** {job['score']:.0f}/100
**CV Angle:** {job['angle']}
**URL:** {job['url']}

---

## Score Breakdown

```
{job['explanation']}
```

## Why This is a Match

{reasons_md}

## Concerns / Gaps

{concerns_md}

---

## Clarifying Questions

*Answer these below. When you reply, the reference profile will be updated.*

{cq_text}

---

**Your answers:**

*(paste answers here)*
""")


def _write_overall_summary(out_dir, keywords, boards, n_found, all_scored, top):
    top_rows = "\n".join(
        f"| {i+1} | {j['company']} | {j['title'][:38]} | **{j['score']:.0f}** | {j['angle'][:35]} |"
        for i, j in enumerate(top)
    )
    all_rows = "\n".join(
        f"| {j['score']:.0f} | {j['company'][:25]} | {j['title'][:38]} | {j['location'] or '—'} |"
        for j in all_scored
    )
    avg_all = sum(j["score"] for j in all_scored) / len(all_scored)
    avg_top = sum(j["score"] for j in top) / len(top)

    (out_dir / "SUMMARY.md").write_text(f"""# AutoJobApply Batch — {datetime.now().strftime('%Y-%m-%d %H:%M')}

**Keywords:** {keywords}
**Boards:** {', '.join(boards)}

## Statistics

| Metric | Value |
|---|---|
| Jobs found | {n_found} |
| Successfully analyzed | {len(all_scored)} |
| Best match score | {all_scored[0]['score']:.0f} / 100 |
| Average score | {avg_all:.0f} / 100 |
| Top {len(top)} average | {avg_top:.0f} / 100 |

---

## Top {len(top)} Matches

| Rank | Company | Title | Score | CV Angle |
|---|---|---|---|---|
{top_rows}

---

## All Analyzed Jobs

| Score | Company | Title | Location |
|---|---|---|---|
{all_rows}
""")
    print(f"\n  SUMMARY.md written to {out_dir}/")


# ─── DB helper ─────────────────────────────────────────────────────────────────

def _save_to_db(job: dict) -> int:
    existing = db.get_job_by_url(job["url"])
    if existing:
        job_id = existing["id"]
        db.update_job(
            job_id,
            company=job["company"],
            title=job["title"],
            location=job["location"],
            extracted_requirements_json=json.dumps(job["reqs"]),
            fit_score=job["score"],
            fit_explanation=job["explanation"],
            status="analyzed",
        )
    else:
        job_id = db.insert_job({
            "company": job["company"],
            "title": job["title"],
            "location": job["location"],
            "url": job["url"],
            "source": job["board"].lower(),
            "raw_description": job["description"],
            "status": "analyzed",
        })
        db.update_job(
            job_id,
            extracted_requirements_json=json.dumps(job["reqs"]),
            fit_score=job["score"],
            fit_explanation=job["explanation"],
        )
    return job_id


# ─── Formatting ────────────────────────────────────────────────────────────────

def _banner(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")


def _step(n, total, label):
    print(f"Step {n}/{total} — {label}")


# ─── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AutoJobApply batch pipeline")
    parser.add_argument("--keywords", default="computer vision engineer israel",
                        help="Search keywords")
    parser.add_argument("--boards", nargs="*", default=ALL_BOARDS,
                        choices=ALL_BOARDS, help="Boards to search")
    parser.add_argument("--max-per-board", type=int, default=10,
                        help="Max results per board")
    parser.add_argument("--top-n", type=int, default=10,
                        help="Number of CVs to generate")
    parser.add_argument("--dry-run", action="store_true",
                        help="Search + scrape only; save to data/scraped_jobs.json for agentic mode")
    parser.add_argument("--skip-config-sync", action="store_true",
                        help="Skip auto-update of scoring config from candidate profile")
    args = parser.parse_args()

    if args.dry_run:
        import json as _json
        db.init_db()
        _banner("DRY RUN — search + scrape only")
        raw = search_jobs(args.keywords, args.boards, max_results=args.max_per_board)
        urls = [r for r in raw if r.get("url")]
        print(f"  DDG: {len(urls)} URLs found")

        print("  Direct Workday company search:")
        workday_direct = search_workday_companies(args.keywords, max_per_company=args.max_per_board)

        scraped = []
        seen_urls = set()

        for wd in workday_direct:
            if wd["url"] in seen_urls:
                continue
            seen_urls.add(wd["url"])
            scraped.append({"url": wd["url"], "board": wd["board"],
                            "title": wd["title"], "company": wd["company"],
                            "description": wd["description"]})
            print(f"  OK  {wd['title'][:60]}  [{wd['company']}]")

        for r in urls:
            if r["url"] in seen_urls:
                continue
            seen_urls.add(r["url"])
            try:
                job = scrape_url(r["url"])
                if len(job.description.strip()) < 80:
                    continue
                scraped.append({"url": r["url"], "board": r["board"],
                                "title": job.title or r["title"],
                                "company": job.company or "",
                                "description": job.description})
                print(f"  OK  {(job.title or r['title'])[:60]}")
            except Exception as exc:
                print(f"  FAIL  {r['url'][:60]}  —  {exc}")
        out = Path("data") / "scraped_jobs.json"
        out.parent.mkdir(exist_ok=True)
        out.write_text(_json.dumps(scraped, indent=2, ensure_ascii=False))
        print(f"\n{len(scraped)} jobs saved to {out}")
        print("Now tell Claude Code: 'Analyze and generate CVs from data/scraped_jobs.json'")
    else:
        run_batch(
            keywords=args.keywords,
            boards=args.boards,
            max_per_board=args.max_per_board,
            top_n=args.top_n,
            skip_config_sync=args.skip_config_sync,
        )
