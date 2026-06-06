from src.models import CV_ANGLES
from src.utils import load_config

_DEGREE_LEVEL = {"bsc": 1, "bs": 1, "msc": 2, "ms": 2, "masters": 2, "phd": 3, "ph.d": 3}

_MANAGEMENT_SIGNALS = (
    "team lead", "team leader", "tech lead", "engineering manager",
    "r&d lead", "r&d manager", "group lead", "group manager",
    "director", "vp of", "head of",
)


def _load_dims() -> list[dict]:
    """Return scoring dimensions from config."""
    cfg = load_config()
    return cfg.get("scoring", {}).get("dimensions", [])


def _scoring_cfg() -> dict:
    return load_config().get("scoring", {})


def degree_penalty(requirements: dict, candidate_degree: str = "bsc") -> float:
    required = requirements.get("degree_required", "none").lower().strip()
    candidate_level = _DEGREE_LEVEL.get(candidate_degree.lower(), 1)
    required_level = _DEGREE_LEVEL.get(required, 0)
    if required_level <= candidate_level:
        return 0.0
    gap = required_level - candidate_level
    return -10.0 * gap


def is_management_role(title: str, seniority: str) -> bool:
    combined = (title + " " + seniority).lower()
    return any(sig in combined for sig in _MANAGEMENT_SIGNALS)


def _seniority_score(seniority: str) -> float:
    if any(s in seniority for s in ("senior", "lead", "principal", "staff", "vp", "head")):
        return 15.0
    if any(s in seniority for s in ("mid", " ii", "level 2", "2+")):
        return 10.0
    if any(s in seniority for s in ("junior", "entry", "jr", " i,")):
        return 2.0
    return 8.0


def score_requirements(requirements: dict) -> tuple[float, str, str]:
    """Returns (score 0-100, explanation, cv_angle)."""
    cfg = _scoring_cfg()
    dims = cfg.get("dimensions", [])

    dim_scores: dict[str, tuple[float, float, str, int]] = {}  # key -> (val, pts, label, max_pts)
    total = 0.0
    for dim in dims:
        val = float(requirements.get(dim["key"], 0))
        pts = val / 10.0 * dim["max_pts"]
        dim_scores[dim["key"]] = (val, pts, dim["label"], dim["max_pts"])
        total += pts

    seniority = requirements.get("seniority", "").lower()
    title     = requirements.get("title", "").lower()
    sen_score = _seniority_score(seniority)
    total += sen_score

    # Domain mismatch penalty
    domains  = {d.lower().replace(" ", "_").replace("-", "_") for d in requirements.get("domains", [])}
    excluded = {d.lower() for d in cfg.get("excluded_domains", [])}
    domain_penalty = domains & excluded

    # Zero primary-signal penalty
    primary_keys = cfg.get("primary_keys", [])
    zero_signal = bool(primary_keys) and all(
        float(requirements.get(k, 0)) == 0 for k in primary_keys
    )

    candidate_degree = cfg.get("candidate_degree", "bsc")
    mgmt_penalty = is_management_role(title, seniority)
    deg_penalty  = degree_penalty(requirements, candidate_degree)

    if domain_penalty:
        total -= 20.0
    if zero_signal:
        total -= 10.0
    if mgmt_penalty:
        total -= 25.0
    total += deg_penalty  # value is negative

    score = round(max(0.0, min(100.0, total)), 1)
    angle = _determine_angle(requirements)
    explanation = _build_explanation(
        score, requirements, dim_scores, sen_score,
        domain_penalty=bool(domain_penalty),
        zero_signal=zero_signal,
        management_penalty=mgmt_penalty,
        deg_penalty=deg_penalty,
        degree_required=requirements.get("degree_required", "none"),
        candidate_degree=candidate_degree,
    )
    return score, explanation, angle


def _determine_angle(requirements: dict) -> str:
    edge  = float(requirements.get("edge_ai_relevance", 0))
    rt    = float(requirements.get("realtime_relevance", 0))
    track = float(requirements.get("tracking_relevance", 0))
    geom  = float(requirements.get("geometry_relevance", 0))
    rob   = float(requirements.get("robotics_relevance", 0))
    prod  = float(requirements.get("production_relevance", 0))

    ranked = {
        "Edge AI / real-time deployment":         edge * 1.5 + rt,
        "Production CV pipeline owner":           prod * 1.5 + rt * 0.5,
        "Object detection / perception":          track * 1.5,
        "Image registration / visual inspection": geom * 2.0,
        "Robotics / tracking / geometry":         rob * 1.5 + geom * 0.5,
        "General senior CV/DL engineer":          4.0,
    }
    return max(ranked, key=lambda k: ranked[k])


def _build_explanation(
    score: float,
    requirements: dict,
    dim_scores: dict,
    seniority_score: float,
    domain_penalty: bool = False,
    zero_signal: bool = False,
    management_penalty: bool = False,
    deg_penalty: float = 0.0,
    degree_required: str = "none",
    candidate_degree: str = "bsc",
) -> str:
    lines = [f"Score: {score:.0f}/100"]

    for key, (val, pts, label, max_pts) in dim_scores.items():
        if val > 0:
            lines.append(f"{label}: {val:.0f}/10 = {pts:.1f}pts (max {max_pts})")

    lines.append(f"Seniority '{requirements.get('seniority', 'unknown')}': {seniority_score:.0f}pts")

    reasons  = requirements.get("reasons_to_apply", [])
    if reasons:
        lines.append("Reasons: " + "; ".join(str(r) for r in reasons[:3]))
    concerns = requirements.get("concerns", [])
    if concerns:
        lines.append("Concerns: " + "; ".join(str(c) for c in concerns[:3]))

    if domain_penalty:
        lines.append("PENALTY: Domain outside candidate expertise (-20pts)")
    if zero_signal:
        lines.append("PENALTY: Zero primary-domain signal (-10pts)")
    if management_penalty:
        lines.append("PENALTY: People management / team lead role (-25pts) - no management experience")
    if deg_penalty < 0:
        lines.append(
            f"PENALTY: {degree_required.upper()} required, candidate has {candidate_degree.upper()} ({deg_penalty:.0f}pts)"
        )

    return "\n".join(lines)
