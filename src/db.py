import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent.parent / "data" / "jobs.sqlite"


@contextmanager
def _conn():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT,
            title TEXT,
            location TEXT,
            url TEXT,
            source TEXT DEFAULT 'manual',
            raw_description TEXT,
            extracted_requirements_json TEXT,
            fit_score REAL,
            fit_explanation TEXT,
            status TEXT DEFAULT 'found',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER REFERENCES jobs(id),
            selected_cv_angle TEXT,
            cv_draft_markdown TEXT,
            linkedin_message_draft TEXT,
            recruiter_email_draft TEXT,
            talking_points TEXT,
            notes TEXT,
            status TEXT DEFAULT 'found',
            last_action_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)


def insert_job(data: dict) -> int:
    with _conn() as conn:
        cur = conn.execute(
            """INSERT INTO jobs (company, title, location, url, source, raw_description, status)
               VALUES (:company, :title, :location, :url, :source, :raw_description, :status)""",
            {
                "company": data.get("company", ""),
                "title": data.get("title", ""),
                "location": data.get("location", ""),
                "url": data.get("url", ""),
                "source": data.get("source", "manual"),
                "raw_description": data.get("raw_description", ""),
                "status": data.get("status", "found"),
            },
        )
        return cur.lastrowid


def update_job(job_id: int, **kwargs) -> None:
    kwargs["updated_at"] = datetime.now().isoformat()
    kwargs["id"] = job_id
    set_clause = ", ".join(f"{k} = :{k}" for k in kwargs if k != "id")
    with _conn() as conn:
        conn.execute(f"UPDATE jobs SET {set_clause} WHERE id = :id", kwargs)


def get_job(job_id: int) -> Optional[dict]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None


def get_job_by_url(url: str) -> Optional[dict]:
    if not url:
        return None
    with _conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE url = ?", (url,)).fetchone()
        return dict(row) if row else None


def get_all_jobs(status_filter: Optional[str] = None) -> list[dict]:
    with _conn() as conn:
        if status_filter:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC",
                (status_filter,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY fit_score DESC, created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]


def upsert_application(data: dict) -> int:
    with _conn() as conn:
        existing = conn.execute(
            "SELECT id FROM applications WHERE job_id = ?", (data["job_id"],)
        ).fetchone()
        data["last_action_date"] = datetime.now().isoformat()
        if existing:
            app_id = existing["id"]
            data["id"] = app_id
            set_clause = ", ".join(
                f"{k} = :{k}" for k in data if k not in ("id", "job_id")
            )
            conn.execute(
                f"UPDATE applications SET {set_clause} WHERE id = :id", data
            )
            return app_id
        else:
            cur = conn.execute(
                """INSERT INTO applications
                   (job_id, selected_cv_angle, cv_draft_markdown, linkedin_message_draft,
                    recruiter_email_draft, talking_points, notes, status, last_action_date)
                   VALUES (:job_id, :selected_cv_angle, :cv_draft_markdown, :linkedin_message_draft,
                    :recruiter_email_draft, :talking_points, :notes, :status, :last_action_date)""",
                {
                    "job_id": data.get("job_id"),
                    "selected_cv_angle": data.get("selected_cv_angle", ""),
                    "cv_draft_markdown": data.get("cv_draft_markdown", ""),
                    "linkedin_message_draft": data.get("linkedin_message_draft", ""),
                    "recruiter_email_draft": data.get("recruiter_email_draft", ""),
                    "talking_points": data.get("talking_points", "[]"),
                    "notes": data.get("notes", ""),
                    "status": data.get("status", "found"),
                    "last_action_date": data["last_action_date"],
                },
            )
            return cur.lastrowid


def get_application(job_id: int) -> Optional[dict]:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM applications WHERE job_id = ?", (job_id,)
        ).fetchone()
        return dict(row) if row else None


def get_all_applications() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            """SELECT a.*, j.company, j.title, j.location, j.fit_score, j.url
               FROM applications a
               JOIN jobs j ON a.job_id = j.id
               ORDER BY a.last_action_date DESC"""
        ).fetchall()
        return [dict(r) for r in rows]
