from src.models import CV_ANGLES

# Degree gap: candidate holds a BSc. Roles requiring higher degrees are penalized.
_DEGREE_PENALTIES = {"phd": -20.0, "ph.d": -20.0, "msc": -10.0, "ms": -10.0, "masters": -10.0}

# Titles that signal a people-management or team-lead role.
_MANAGEMENT_SIGNALS = (
    "team lead", "team leader", "tech lead", "engineering manager",
    "r&d lead", "r&d manager", "group lead", "group manager",
    "director", "vp of", "head of",
)


def degree_penalty(requirements: dict) -> float:
    degree = requirements.get("degree_required", "none").lower().strip()
    return _DEGREE_PENALTIES.get(degree, 0.0)


def is_management_role(title: str, seniority: str) -> bool:
    combined = (title + " " + seniority).lower()
    return any(sig in combined for sig in _MANAGEMENT_SIGNALS)


def score_requirements(requirements: dict) -> tuple[float, str, str]:
    """Returns (score 0-100, explanation, cv_angle)."""
    cv = float(requirements.get("cv_relevance", 0))
    dl = float(requirements.get("dl_relevance", 0))
    rt = float(requirements.get("realtime_relevance", 0))
    edge = float(requirements.get("edge_ai_relevance", 0))
    track = float(requirements.get("tracking_relevance", 0))
    prod = float(requirements.get("production_relevance", 0))
    geom = float(requirements.get("geometry_relevance", 0))
    rob = float(requirements.get("robotics_relevance", 0))

    # Weighted components — sum to 100 at maximum
    cv_dl_score   = (cv + dl) / 20.0 * 30.0      # max 30
    rt_edge_score = (rt + edge) / 20.0 * 20.0    # max 20
    track_score   = track / 10.0 * 15.0           # max 15
    prod_score    = prod / 10.0 * 10.0            # max 10
    geo_rob_score = (geom + rob) / 20.0 * 10.0   # max 10

    seniority = requirements.get("seniority", "").lower()
    title     = requirements.get("title", "").lower()

    if any(s in seniority for s in ("senior", "lead", "principal", "staff", "vp", "head")):
        seniority_score = 15.0
    elif any(s in seniority for s in ("mid", " ii", "level 2", "2+")):
        seniority_score = 10.0
    elif any(s in seniority for s in ("junior", "entry", "jr", " i,")):
        seniority_score = 2.0
    else:
        seniority_score = 8.0

    score = cv_dl_score + rt_edge_score + track_score + prod_score + geo_rob_score + seniority_score

    # Penalties
    domains = {d.lower().replace(" ", "_").replace("-", "_") for d in requirements.get("domains", [])}
    non_cv  = {"backend", "fullstack", "full_stack", "data_science", "data_engineering", "nlp", "llm"}
    if domains & non_cv:
        score -= 20.0
    if cv == 0 and dl == 0:
        score -= 10.0

    mgmt_penalty = is_management_role(title, seniority)
    if mgmt_penalty:
        score -= 25.0

    deg_penalty = degree_penalty(requirements)
    score += deg_penalty  # value is negative

    score = round(max(0.0, min(100.0, score)), 1)
    angle = _determine_angle(requirements)
    explanation = _build_explanation(
        score, requirements, seniority_score, cv_dl_score, rt_edge_score,
        management_penalty=mgmt_penalty,
        deg_penalty=deg_penalty,
        degree_required=requirements.get("degree_required", "none"),
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
        "Edge AI / real-time deployment":      edge * 1.5 + rt,
        "Production CV pipeline owner":        prod * 1.5 + rt * 0.5,
        "Object detection / perception":       track * 1.5,
        "Image registration / visual inspection": geom * 2.0,
        "Robotics / tracking / geometry":      rob * 1.5 + geom * 0.5,
        "General senior CV/DL engineer":       4.0,
    }
    return max(ranked, key=lambda k: ranked[k])


def _build_explanation(score, requirements, seniority_score, cv_dl_score, rt_edge_score,
                        management_penalty: bool = False,
                        deg_penalty: float = 0.0,
                        degree_required: str = "none") -> str:
    lines = [f"Score: {score:.0f}/100"]
    cv   = requirements.get("cv_relevance", 0)
    dl   = requirements.get("dl_relevance", 0)
    lines.append(f"CV/DL: {cv}/10 + {dl}/10 = {cv_dl_score:.1f}pts (max 30)")
    rt   = requirements.get("realtime_relevance", 0)
    edge = requirements.get("edge_ai_relevance", 0)
    if rt or edge:
        lines.append(f"Real-time/Edge: {rt}/10 + {edge}/10 = {rt_edge_score:.1f}pts (max 20)")
    lines.append(f"Seniority '{requirements.get('seniority', 'unknown')}': {seniority_score:.0f}pts")

    reasons  = requirements.get("reasons_to_apply", [])
    if reasons:
        lines.append("Reasons: " + "; ".join(str(r) for r in reasons[:3]))
    concerns = requirements.get("concerns", [])
    if concerns:
        lines.append("Concerns: " + "; ".join(str(c) for c in concerns[:3]))

    domains = {d.lower().replace(" ", "_").replace("-", "_") for d in requirements.get("domains", [])}
    non_cv  = {"backend", "fullstack", "full_stack", "data_science", "data_engineering", "nlp"}
    if domains & non_cv:
        lines.append("PENALTY: Non-CV domain (-20pts)")
    if float(requirements.get("cv_relevance", 0)) == 0 and float(requirements.get("dl_relevance", 0)) == 0:
        lines.append("PENALTY: Zero CV/DL signal (-10pts)")
    if management_penalty:
        lines.append("PENALTY: People management / team lead role (-25pts) - no management experience")
    if deg_penalty < 0:
        lines.append(
            f"PENALTY: {degree_required.upper()} required, candidate has BSc ({deg_penalty:.0f}pts)"
        )

    return "\n".join(lines)
