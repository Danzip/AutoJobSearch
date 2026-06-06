import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from gap_analysis import aggregate_skills, classify_gaps


def test_aggregate_skills_counts():
    jobs = [
        {"extracted_requirements_json": '{"required_skills": ["PyTorch", "ONNX"]}'},
        {"extracted_requirements_json": '{"required_skills": ["PyTorch", "OpenCV"]}'},
        {"extracted_requirements_json": '{"required_skills": ["OpenCV"]}'},
    ]
    counts = aggregate_skills(jobs)
    assert counts["pytorch"] == 2
    assert counts["onnx"] == 1
    assert counts["opencv"] == 2


def test_aggregate_skills_empty_jobs():
    assert aggregate_skills([]) == {}


def test_aggregate_skills_missing_field():
    jobs = [{"extracted_requirements_json": "{}"}]
    assert aggregate_skills(jobs) == {}


def test_aggregate_skills_null_json():
    jobs = [{"extracted_requirements_json": None}]
    assert aggregate_skills(jobs) == {}


def test_classify_gap_critical():
    counts = {"pytorch": 8}  # 8/10 = 80% → critical
    gaps = classify_gaps(counts, total_jobs=10, candidate_skills=set())
    assert any(g["skill"] == "pytorch" for g in gaps["critical"])


def test_classify_gap_high():
    counts = {"onnx": 6}  # 6/10 = 60% → high
    gaps = classify_gaps(counts, total_jobs=10, candidate_skills=set())
    assert any(g["skill"] == "onnx" for g in gaps["high"])


def test_classify_gap_medium():
    counts = {"triton": 4}  # 4/10 = 40% → medium
    gaps = classify_gaps(counts, total_jobs=10, candidate_skills=set())
    assert any(g["skill"] == "triton" for g in gaps["medium"])


def test_classify_gap_low():
    counts = {"matlab": 2}  # 2/10 = 20% → low
    gaps = classify_gaps(counts, total_jobs=10, candidate_skills=set())
    assert any(g["skill"] == "matlab" for g in gaps["low"])


def test_classify_excludes_candidate_skills():
    counts = {"pytorch": 10, "opencv": 5}
    gaps = classify_gaps(counts, total_jobs=10, candidate_skills={"pytorch"})
    all_skills = [g["skill"] for tier in gaps.values() for g in tier]
    assert "pytorch" not in all_skills
    assert "opencv" in all_skills


def test_classify_gap_pct_field():
    counts = {"tensorrt": 8}  # 80% → critical (>70%)
    gaps = classify_gaps(counts, total_jobs=10, candidate_skills=set())
    critical = gaps["critical"]
    assert len(critical) == 1
    assert critical[0]["pct"] == 80.0
    assert critical[0]["count"] == 8


def test_classify_boundary_exactly_70pct():
    counts = {"skill_x": 7}  # exactly 70% → high (> not >=)
    gaps = classify_gaps(counts, total_jobs=10, candidate_skills=set())
    assert any(g["skill"] == "skill_x" for g in gaps["high"])
