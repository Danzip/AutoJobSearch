#!/usr/bin/env python3
"""
Analyze skill gaps across top-scored jobs stored in SQLite.
Usage: python gap_analysis.py [--top-n 20]
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def aggregate_skills(jobs: list[dict]) -> dict[str, int]:
    """Count how many jobs require each skill (lowercased)."""
    counts: dict[str, int] = {}
    for job in jobs:
        raw = job.get("extracted_requirements_json") or "{}"
        try:
            reqs = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        for skill in reqs.get("required_skills", []):
            key = skill.lower().strip()
            if key:
                counts[key] = counts.get(key, 0) + 1
    return counts


def classify_gaps(
    counts: dict[str, int],
    total_jobs: int,
    candidate_skills: set[str],
) -> dict[str, list[dict]]:
    """
    Classify skills the candidate lacks into tiers by frequency across top jobs.
    Thresholds: Critical >70%, High 50-70%, Medium 30-50%, Low <30%.
    """
    gaps: dict[str, list[dict]] = {"critical": [], "high": [], "medium": [], "low": []}
    if total_jobs == 0:
        return gaps
    for skill, count in sorted(counts.items(), key=lambda x: -x[1]):
        # Skip if candidate already has this skill (substring match)
        if any(cs in skill or skill in cs for cs in candidate_skills):
            continue
        pct = count / total_jobs
        entry = {"skill": skill, "count": count, "pct": round(pct * 100, 1)}
        if pct > 0.70:
            gaps["critical"].append(entry)
        elif pct > 0.50:
            gaps["high"].append(entry)
        elif pct > 0.30:
            gaps["medium"].append(entry)
        else:
            gaps["low"].append(entry)
    return gaps


def _candidate_skill_set(profile: dict) -> set[str]:
    """Flatten all skills from profile into a lowercase set."""
    skills_section = profile.get("skills", {})
    flat: set[str] = set()
    for category_skills in skills_section.values():
        if isinstance(category_skills, list):
            for s in category_skills:
                flat.add(str(s).lower().strip())
    return flat


def _print_gaps(gaps: dict, keywords_dict: dict[str, list[str]] = None):
    tiers = [("CRITICAL (>70% of roles)", "critical"),
             ("HIGH (50-70%)", "high"),
             ("MEDIUM (30-50%)", "medium"),
             ("LOW (<30%)", "low")]
    for label, key in tiers:
        items = gaps[key]
        if not items:
            continue
        print(f"\n{label}:")
        for g in items:
            resources = ""
            if keywords_dict and g["skill"] in keywords_dict:
                resources = " → " + " | ".join(keywords_dict[g["skill"]])
            print(f"  {g['pct']:5.1f}%  {g['skill']}{resources}")


def main(top_n: int = 20):
    from dotenv import load_dotenv
    load_dotenv()

    import src.db as db
    from src.utils import load_profile

    db.init_db()
    profile = load_profile()

    all_jobs = db.get_all_jobs()
    top_jobs = sorted(
        [j for j in all_jobs if j.get("fit_score") is not None],
        key=lambda j: j["fit_score"],
        reverse=True,
    )[:top_n]

    if not top_jobs:
        print("No analyzed jobs in database. Run batch_search.py first.")
        return

    print(f"\nAnalyzing skill gaps across top {len(top_jobs)} jobs "
          f"(scores {top_jobs[-1]['fit_score']:.0f}-{top_jobs[0]['fit_score']:.0f})\n")

    counts = aggregate_skills(top_jobs)
    candidate_skills = _candidate_skill_set(profile)
    gaps = classify_gaps(counts, total_jobs=len(top_jobs), candidate_skills=candidate_skills)

    total_gaps = sum(len(v) for v in gaps.values())
    print(f"Skills required across these roles: {len(counts)}")
    print(f"Skills candidate already has: {sum(1 for s in counts if any(cs in s or s in cs for cs in candidate_skills))}")
    print(f"Skill gaps identified: {total_gaps}")

    _print_gaps(gaps)

    # Write to file
    out = Path("outputs") / "gap_analysis.md"
    out.parent.mkdir(exist_ok=True)
    lines = [f"# Skill Gap Analysis — top {len(top_jobs)} jobs\n"]
    for label, key in [("CRITICAL", "critical"), ("HIGH", "high"),
                        ("MEDIUM", "medium"), ("LOW", "low")]:
        if gaps[key]:
            lines.append(f"\n## {label}\n")
            for g in gaps[key]:
                lines.append(f"- {g['skill']} ({g['pct']}% of top roles, {g['count']} jobs)")
    out.write_text("\n".join(lines))
    print(f"\nWritten to {out}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--top-n", type=int, default=20)
    args = parser.parse_args()
    main(top_n=args.top_n)
