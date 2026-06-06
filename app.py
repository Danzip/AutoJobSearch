import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

import src.db as db
from src.job_search import search_jobs, ALL_BOARDS
from src.llm import get_llm
from src.models import CV_ANGLES, JobStatus
from src.scrapers.base import scrape_url, ScraperError
from src.utils import load_config, load_profile, load_profile_notes, save_profile_notes

st.set_page_config(page_title="AutoJobApply", page_icon="💼", layout="wide")
db.init_db()

# ── Session state defaults ────────────────────────────────────────────────────
for key, default in [("page", "inbox"), ("selected_job_id", None)]:
    if key not in st.session_state:
        st.session_state[key] = default


# ── Helpers ───────────────────────────────────────────────────────────────────
def nav(page: str, job_id=None):
    st.session_state.page = page
    st.session_state.selected_job_id = job_id
    st.rerun()


def _score_badge(score) -> str:
    if score is None:
        return "—"
    s = float(score)
    if s >= 75:
        return f"🟢 {s:.0f}"
    if s >= 55:
        return f"🟡 {s:.0f}"
    return f"🔴 {s:.0f}"


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("AutoJobApply")
    st.caption("Human-in-the-loop job tracking")
    st.divider()
    for label, key in [
        ("🔍 Job Search", "search"),
        ("📥 Job Inbox", "inbox"),
        ("➕ Add Job", "add_job"),
        ("📋 Application Tracker", "tracker"),
        ("⚙️ Settings / Profile", "settings"),
    ]:
        if st.button(label, use_container_width=True, key=f"nav_{key}"):
            nav(key)


# ── Page: Job Search ──────────────────────────────────────────────────────────
def page_search():
    st.header("Job Search")
    st.caption("Searches DuckDuckGo with site: operators — results open real job board pages.")

    col1, col2 = st.columns([3, 1])
    with col1:
        keywords = st.text_input(
            "Keywords", placeholder="Computer Vision Engineer Israel"
        )
    with col2:
        max_r = st.number_input("Max per board", min_value=3, max_value=20, value=8)

    boards = st.multiselect("Job boards", ALL_BOARDS, default=ALL_BOARDS)

    if st.button("Search", type="primary", disabled=not keywords or not boards):
        with st.spinner("Searching..."):
            results = search_jobs(keywords, boards, max_results=int(max_r))
            st.session_state["_search_results"] = results

    results = st.session_state.get("_search_results", [])
    if results:
        st.divider()
        st.write(f"**{len(results)} results**")
        for i, r in enumerate(results):
            if not r["url"]:
                continue
            with st.container(border=True):
                c1, c2 = st.columns([6, 1])
                with c1:
                    st.markdown(f"**[{r['title']}]({r['url']})**  `{r['board']}`")
                    if r["snippet"]:
                        st.caption(r["snippet"][:200])
                with c2:
                    if st.button("Add to Inbox", key=f"add_{i}"):
                        existing = db.get_job_by_url(r["url"])
                        if existing:
                            st.warning(f"Already in inbox as job #{existing['id']}")
                        else:
                            job_id = db.insert_job(
                                {
                                    "title": r["title"],
                                    "company": "",
                                    "location": "",
                                    "url": r["url"],
                                    "source": r["board"].lower(),
                                    "raw_description": r["snippet"],
                                    "status": "found",
                                }
                            )
                            st.success(f"Added as job #{job_id}")


# ── Page: Job Inbox ───────────────────────────────────────────────────────────
def page_inbox():
    st.header("Job Inbox")

    statuses = ["All"] + [s.value for s in JobStatus]
    col1, col2 = st.columns([2, 1])
    with col1:
        status_filter = st.selectbox("Filter", statuses, key="inbox_filter")
    with col2:
        st.write("")
        if st.button("Refresh"):
            st.rerun()

    jobs = db.get_all_jobs(
        status_filter=None if status_filter == "All" else status_filter
    )

    if not jobs:
        st.info("No jobs yet. Use 'Job Search' or 'Add Job' to get started.")
        return

    df = pd.DataFrame(
        [
            {
                "ID": j["id"],
                "Company": j["company"] or "—",
                "Title": j["title"] or "—",
                "Location": j["location"] or "—",
                "Score": _score_badge(j["fit_score"]),
                "Status": j["status"],
                "Added": (j["created_at"] or "")[:10],
            }
            for j in jobs
        ]
    )

    event = st.dataframe(
        df,
        hide_index=True,
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row",
    )

    selected_rows = event.selection.rows
    if selected_rows:
        selected_job = jobs[selected_rows[0]]
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("Open Job", type="primary"):
                nav("detail", selected_job["id"])
        with col2:
            st.caption(
                f"Selected: **{selected_job['company']} — {selected_job['title']}**"
            )


# ── Page: Add Job ─────────────────────────────────────────────────────────────
def page_add_job():
    st.header("Add Job")
    tab1, tab2 = st.tabs(["Paste URL (auto-scrape)", "Paste Description (manual)"])

    with tab1:
        url = st.text_input(
            "Job posting URL",
            placeholder="https://boards.greenhouse.io/acme/jobs/123456",
            key="url_input",
        )

        existing = db.get_job_by_url(url) if url else None
        if existing:
            st.warning(
                f"This URL is already in the inbox as job #{existing['id']}. "
            )
            if st.button("Open existing job"):
                nav("detail", existing["id"])
            return

        if st.button("Fetch & Parse", disabled=not url):
            with st.spinner("Fetching..."):
                try:
                    scraped = scrape_url(url)
                    st.session_state["_scraped"] = scraped
                    st.session_state["_scraped_url"] = url
                    st.success("Fetched — review and save below.")
                except ScraperError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"Unexpected error: {e}")

        scraped = st.session_state.get("_scraped")
        if scraped and st.session_state.get("_scraped_url") == url:
            with st.form("scraped_form"):
                company = st.text_input("Company", value=scraped.company)
                title = st.text_input("Title", value=scraped.title)
                location = st.text_input("Location", value=scraped.location)
                description = st.text_area(
                    "Job Description", value=scraped.description, height=350
                )
                if st.form_submit_button("Save Job", type="primary"):
                    job_id = db.insert_job(
                        {
                            "company": company,
                            "title": title,
                            "location": location,
                            "url": url,
                            "source": scraped.source,
                            "raw_description": description,
                            "status": "found",
                        }
                    )
                    st.session_state["_scraped"] = None
                    st.success(f"Saved as job #{job_id}")
                    nav("detail", job_id)

    with tab2:
        with st.form("manual_form"):
            company = st.text_input("Company", key="m_company")
            title = st.text_input("Job Title", key="m_title")
            location = st.text_input("Location", key="m_location")
            url_manual = st.text_input("URL (optional)", key="m_url")
            description = st.text_area("Job Description", height=350, key="m_desc")
            if st.form_submit_button("Save Job", type="primary"):
                if not description.strip():
                    st.error("Description is required.")
                else:
                    job_id = db.insert_job(
                        {
                            "company": company,
                            "title": title,
                            "location": location,
                            "url": url_manual,
                            "source": "manual",
                            "raw_description": description,
                            "status": "found",
                        }
                    )
                    st.success(f"Saved as job #{job_id}")
                    nav("detail", job_id)


# ── Page: Job Detail ──────────────────────────────────────────────────────────
def _run_analysis(job: dict):
    from src.analyzer import analyze_job
    from src.scorer import score_requirements

    with st.spinner("Analyzing with LLM..."):
        try:
            llm = get_llm()
            reqs = analyze_job(job["raw_description"], llm)
            score, explanation, angle = score_requirements(reqs)
            db.update_job(
                job["id"],
                extracted_requirements_json=json.dumps(reqs),
                fit_score=score,
                fit_explanation=explanation,
                status="analyzed",
            )
            st.success(f"Analysis done. Score: {score:.0f}/100 | Angle: {angle}")
            st.rerun()
        except Exception as e:
            st.error(f"Analysis failed: {e}")


def _run_generation(job: dict, reqs: dict, angle: str):
    from src.generator import generate_application_content

    with st.spinner("Generating content with LLM..."):
        try:
            profile = load_profile()
            llm = get_llm()
            content = generate_application_content(job, reqs, profile, angle, llm)
            db.upsert_application(
                {
                    "job_id": job["id"],
                    "selected_cv_angle": angle,
                    "cv_draft_markdown": content["cv_draft_markdown"],
                    "cover_letter_draft": content.get("cover_letter", ""),
                    "linkedin_message_draft": content["linkedin_message"],
                    "recruiter_email_draft": content["recruiter_email"],
                    "talking_points": json.dumps(content["talking_points"]),
                    "notes": "",
                    "status": job["status"],
                }
            )
            db.update_job(job["id"], status="cv_generated")
            st.success("Content generated!")
            st.rerun()
        except Exception as e:
            st.error(f"Generation failed: {e}")


def page_detail():
    job_id = st.session_state.selected_job_id
    if not job_id:
        st.error("No job selected.")
        return

    job = db.get_job(job_id)
    if not job:
        st.error(f"Job #{job_id} not found.")
        return

    if st.button("← Back to Inbox"):
        nav("inbox")

    st.header(f"{job['company'] or 'Unknown Company'} — {job['title'] or 'Unknown Title'}")
    score_text = _score_badge(job["fit_score"])
    st.caption(
        f"Status: **{job['status']}** | Score: {score_text} | "
        f"{job['location'] or ''} | Source: {job['source']}"
    )
    if job["url"]:
        st.markdown(f"[Open original posting]({job['url']})")

    # Action buttons
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        if st.button("Analyze", type="primary"):
            _run_analysis(job)
    with col2:
        if st.button("Mark Interesting"):
            db.update_job(job_id, status="interesting")
            st.rerun()
    with col3:
        if st.button("Mark Applied"):
            db.update_job(job_id, status="applied")
            st.rerun()
    with col4:
        if st.button("Mark Interview"):
            db.update_job(job_id, status="interview")
            st.rerun()
    with col5:
        if st.button("Skip"):
            db.update_job(job_id, status="skipped")
            st.rerun()

    tab1, tab2, tab3, tab4 = st.tabs(["Job Description", "Analysis", "Application Content", "Referral Targets"])

    # ── Tab 1: Description ──
    with tab1:
        st.text_area(
            "Raw description",
            value=job["raw_description"] or "",
            height=500,
            disabled=True,
            label_visibility="collapsed",
        )

    # ── Tab 2: Analysis ──
    with tab2:
        if not job.get("extracted_requirements_json"):
            st.info("Click **Analyze** to extract requirements and compute a fit score.")
        else:
            reqs = json.loads(job["extracted_requirements_json"])
            col_l, col_r = st.columns([1, 2])
            with col_l:
                if job["fit_score"] is not None:
                    st.metric("Fit Score", f"{job['fit_score']:.0f} / 100")
                st.write("**Relevance scores (0-10)**")
                rel_keys = [
                    "cv_relevance", "dl_relevance", "edge_ai_relevance",
                    "realtime_relevance", "tracking_relevance",
                    "production_relevance", "geometry_relevance", "robotics_relevance",
                ]
                for k in rel_keys:
                    val = reqs.get(k, 0)
                    label = k.replace("_relevance", "").replace("_", " ").title()
                    bar = "█" * val + "░" * (10 - val)
                    st.write(f"`{bar}` {label}: {val}")
            with col_r:
                if job.get("fit_explanation"):
                    st.write("**Score breakdown**")
                    st.code(job["fit_explanation"], language=None)
                st.write(f"**Seniority:** {reqs.get('seniority', '—')}")
                if reqs.get("required_skills"):
                    st.write("**Required skills:** " + ", ".join(reqs["required_skills"]))
                if reqs.get("domains"):
                    st.write("**Domains:** " + ", ".join(reqs["domains"]))
                reasons = reqs.get("reasons_to_apply", [])
                if reasons:
                    st.write("**Reasons to apply:**")
                    for r in reasons:
                        st.write(f"- {r}")
                concerns = reqs.get("concerns", [])
                if concerns:
                    st.write("**Concerns:**")
                    for c in concerns:
                        st.write(f"- {c}")

    # ── Tab 3: Application Content ──
    with tab3:
        app = db.get_application(job_id)
        config = load_config()
        threshold = config.get("scoring", {}).get("threshold", 60)

        if job.get("fit_score") is not None and job["fit_score"] < threshold:
            st.warning(
                f"Score {job['fit_score']:.0f} is below threshold ({threshold}). "
                "Consider skipping this role."
            )

        reqs_dict = (
            json.loads(job["extracted_requirements_json"])
            if job.get("extracted_requirements_json")
            else {}
        )

        # Suggest angle from scorer or use saved one
        saved_angle = app["selected_cv_angle"] if app and app.get("selected_cv_angle") else None
        default_idx = CV_ANGLES.index(saved_angle) if saved_angle in CV_ANGLES else 0
        selected_angle = st.selectbox("CV Angle", CV_ANGLES, index=default_idx)

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Generate Application Content", type="primary"):
                _run_generation(job, reqs_dict, selected_angle)
        with col_b:
            if app and st.button("Regenerate"):
                _run_generation(job, reqs_dict, selected_angle)

        if not app:
            st.info("Click **Generate Application Content** to create tailored drafts.")
        else:
            st.divider()
            cv_draft = st.text_area(
                "CV Draft (Markdown)", value=app.get("cv_draft_markdown", ""), height=300
            )
            cover_letter = st.text_area(
                "Cover Letter", value=app.get("cover_letter_draft", ""), height=250
            )
            linkedin_msg = st.text_area(
                "LinkedIn Message", value=app.get("linkedin_message_draft", ""), height=120
            )
            recruiter_email = st.text_area(
                "Recruiter Email", value=app.get("recruiter_email_draft", ""), height=180
            )

            tp_raw = app.get("talking_points", "[]")
            try:
                tp_list = json.loads(tp_raw) if tp_raw else []
            except Exception:
                tp_list = []
            tp_text = st.text_area(
                "Talking Points (one per line)",
                value="\n".join(tp_list),
                height=150,
            )

            notes = st.text_area("Notes", value=app.get("notes", ""), height=80)

            col1, col2 = st.columns(2)
            with col1:
                if st.button("Save Changes", type="primary"):
                    new_tp = [l.strip() for l in tp_text.splitlines() if l.strip()]
                    db.upsert_application(
                        {
                            "job_id": job_id,
                            "selected_cv_angle": selected_angle,
                            "cv_draft_markdown": cv_draft,
                            "cover_letter_draft": cover_letter,
                            "linkedin_message_draft": linkedin_msg,
                            "recruiter_email_draft": recruiter_email,
                            "talking_points": json.dumps(new_tp),
                            "notes": notes,
                            "status": job["status"],
                        }
                    )
                    st.success("Saved.")
            with col2:
                if cv_draft and st.button("Export CV as PDF"):
                    try:
                        from src.pdf_generator import generate_cv_pdf
                        out_dir = Path(__file__).parent / "outputs" / "Cvs"
                        out_dir.mkdir(parents=True, exist_ok=True)
                        safe_name = (
                            f"{job.get('company', 'company')}_{job.get('title', 'role')}"
                            .replace(" ", "_").replace("/", "-")[:60]
                        )
                        # Write a temp cv.md so the generator can read it
                        tmp_md = out_dir / f"{safe_name}.md"
                        tmp_md.write_text(cv_draft)
                        pdf_path = out_dir / f"{safe_name}.pdf"
                        generate_cv_pdf(
                            tmp_md, load_profile(), pdf_path,
                            company=job.get("company", ""),
                        )
                        st.success(f"PDF saved to {pdf_path.relative_to(Path(__file__).parent)}")
                        # Also offer markdown download
                        st.download_button(
                            "Download PDF",
                            data=pdf_path.read_bytes(),
                            file_name=pdf_path.name,
                            mime="application/pdf",
                        )
                    except Exception as e:
                        st.error(f"PDF generation failed: {e}")

    # ── Tab 4: Referral Targets ──
    with tab4:
        from src.referral_search import find_referral_targets, write_referral_targets_md

        company = job.get("company", "")
        st.write(f"Find employees at **{company}** who could refer you.")

        if st.button("Search Referral Targets", type="primary"):
            with st.spinner(f"Searching LinkedIn for {company} employees..."):
                targets = find_referral_targets(company)
            if targets:
                st.success(f"Found {len(targets)} potential contact(s).")
                for t in targets:
                    st.write(f"- [{t['name']}]({t['linkedin_url']}) — {t['role']}")
            else:
                st.warning("No results found. Try searching manually:")
                st.code(f'site:linkedin.com/in "{company}" "Israel"')

        st.divider()
        st.caption(
            "Do NOT send connection requests automatically. "
            "Edit the message template and send manually."
        )
        st.write("**Connection message template:**")
        title = job.get("title", "the role")
        default_msg = (
            f"Hi [Name], I came across the {title} role at {company} and I'd love to connect. "
            f"I'm a senior computer vision engineer with 8+ years of experience and I'm very "
            f"interested in what {company} is building. Would you be open to a quick chat?"
        )
        st.text_area("Edit before sending", value=default_msg, height=120, key="referral_msg")


# ── Page: Application Tracker ─────────────────────────────────────────────────
def page_tracker():
    st.header("Application Tracker")

    apps = db.get_all_applications()
    if not apps:
        st.info("No applications tracked yet.")
        return

    status_order = [
        "interesting", "cv_generated", "contacted", "applied",
        "interview", "offer", "rejected", "skipped",
    ]

    for status in status_order:
        group = [a for a in apps if a.get("status") == status]
        if not group:
            continue
        st.subheader(status.replace("_", " ").title())
        df = pd.DataFrame(
            [
                {
                    "ID": a["job_id"],
                    "Company": a.get("company", "—"),
                    "Title": a.get("title", "—"),
                    "Score": _score_badge(a.get("fit_score")),
                    "Last Action": (a.get("last_action_date") or "")[:10],
                }
                for a in group
            ]
        )
        event = st.dataframe(
            df, hide_index=True, use_container_width=True,
            on_select="rerun", selection_mode="single-row", key=f"tracker_{status}"
        )
        if event.selection.rows:
            selected = group[event.selection.rows[0]]
            if st.button("Open", key=f"open_{status}_{selected['job_id']}"):
                nav("detail", selected["job_id"])


# ── Page: Settings / Profile ──────────────────────────────────────────────────
def page_settings():
    st.header("Settings / Profile")

    tab1, tab2, tab3 = st.tabs(["Configuration", "Profile Notes", "Token Usage"])

    with tab1:
        import os
        from dotenv import load_dotenv
        load_dotenv()

        config = load_config()
        st.subheader("LLM")
        st.write(f"**Provider:** `{config.get('llm', {}).get('provider', 'anthropic')}`")
        st.write(f"**Model:** `{config.get('llm', {}).get('model', 'claude-sonnet-4-6')}`")
        st.caption("Edit `config.yaml` to change provider or model.")

        st.subheader("API Keys")
        ak = os.getenv("ANTHROPIC_API_KEY")
        ok = os.getenv("OPENAI_API_KEY")
        st.write(f"ANTHROPIC_API_KEY: {'set' if ak else 'NOT SET'}")
        st.write(f"OPENAI_API_KEY: {'set' if ok else 'NOT SET'}")
        st.caption("Set keys in `.env` file (copy from `.env.example`).")

        st.subheader("Scoring Threshold")
        st.write(f"**Threshold:** {config.get('scoring', {}).get('threshold', 60)}")
        st.caption("Jobs below this score show a warning. Edit `config.yaml` to change.")

        st.subheader("Profile")
        try:
            profile = load_profile()
            p = profile.get("personal", {})
            st.write(f"**Name:** {p.get('name')}")
            st.write(f"**Experience:** {p.get('years_experience')}+ years")
            st.write(f"**Stories loaded:** {len(profile.get('stories', []))}")
            st.caption(
                "Edit `profile/candidate_profile.yaml` to update stories, skills, and hard limits."
            )
        except Exception as e:
            st.error(f"Could not load profile: {e}")

    with tab3:
        from src.token_tracker import summary as token_summary, read_log
        st.subheader("Token Usage")
        s = token_summary()
        if not s:
            st.info("No usage recorded yet. Run a batch or analyze a job first.")
        else:
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Calls", s["total_calls"])
            col2.metric("Total Tokens", f"{s['total_input_tokens'] + s['total_output_tokens']:,}")
            col3.metric("Total Cost", f"${s['total_cost_usd']:.4f}")
            st.write("**By call type:**")
            for t, info in s["by_type"].items():
                st.write(f"- `{t}`: {info['calls']} calls | {info['tokens']:,} tokens | ${info['cost']:.4f}")
            st.write(f"**Cache hits (input tokens saved):** {s['total_cache_hits']:,}")
            if st.button("Show full log"):
                st.dataframe(read_log(), use_container_width=True)

    with tab2:
        st.subheader("Profile Notes")
        st.caption(
            "Add notes about new angles or positioning discovered during applications. "
            "These are included in all future generation prompts."
        )
        current_notes = load_profile_notes()
        new_notes = st.text_area(
            "Notes (free text, Markdown supported)",
            value=current_notes,
            height=400,
        )
        if st.button("Save Notes", type="primary"):
            save_profile_notes(new_notes)
            st.success("Saved to profile/notes.md")


# ── Router ────────────────────────────────────────────────────────────────────
page = st.session_state.page
if page == "search":
    page_search()
elif page == "inbox":
    page_inbox()
elif page == "add_job":
    page_add_job()
elif page == "detail":
    page_detail()
elif page == "tracker":
    page_tracker()
elif page == "settings":
    page_settings()
else:
    page_inbox()
