"""Verify model supplied evidence and calculate an explainable deterministic score."""
from collections import defaultdict
from app.schemas.schemas import ModelAnalysis

WEIGHTS = {
    "required_skills": 0.50,
    "relevant_experience": 0.25,
    "explicit_qualifications": 0.15,
    "preferred_skills": 0.10,
}
ALIASES = {"js": "javascript", "node.js": "nodejs", "node js": "nodejs", "postgres": "postgresql", "py": "python", "ts": "typescript", "c#": "c sharp", "csharp": "c sharp", "cpp": "c plus plus", "c++": "c plus plus", "ci/cd": "continuous integration continuous delivery"}


def normalize(value: str) -> str:
    text = " ".join(value.casefold().replace("&", " and ").split())
    return ALIASES.get(text, text)


def calculate_analysis(model: ModelAnalysis, resume_text: str) -> dict:
    """Count exact/alias matches as 1, partial matches as .5, and ignore uncertain evidence.

    Empty job categories are excluded and remaining configured weights are renormalized,
    so an unstated degree or years-of-experience requirement is never an automatic penalty.
    Model evidence must be a literal excerpt from the extracted resume before being scored.
    """
    normalized_requirements = []
    seen = set()
    resume_folded = " ".join(resume_text.casefold().split())
    for requirement in model.requirements:
        key = (requirement.category, normalize(requirement.name))
        if key in seen:
            continue
        seen.add(key)
        item = requirement.model_copy(deep=True)
        if item.evidence and " ".join(item.evidence.casefold().split()) not in resume_folded:
            item.status = "uncertain"
            item.evidence = None
        if item.status in ("matched", "partial") and not item.evidence:
            item.status = "uncertain"
        normalized_requirements.append(item)

    grouped = defaultdict(list)
    for req in normalized_requirements:
        grouped[req.category].append(req)
    active = [key for key, reqs in grouped.items() if any(req.status != "uncertain" for req in reqs)]
    weight_total = sum(WEIGHTS[key] for key in active)
    breakdown = {}
    total = 0.0
    matches = []
    missing, uncertain = [], []
    for category, weight in WEIGHTS.items():
        reqs = grouped.get(category, [])
        scored = [r for r in reqs if r.status != "uncertain"]
        proportion = (sum(1.0 if r.status == "matched" else 0.5 if r.status == "partial" else 0.0 for r in scored) / len(scored)) if scored else None
        normalized_weight = weight / weight_total if scored and weight_total else 0.0
        contribution = round(100 * normalized_weight * (proportion or 0.0), 2)
        total += contribution
        breakdown[category] = {
            "base_weight": weight,
            "weight": round(normalized_weight, 4),
            "match_percentage": round(proportion, 4) if proportion is not None else None,
            "category_score": contribution,
            "requirements": [r.model_dump() for r in reqs],
        }
        for r in reqs:
            if r.status in ("matched", "partial") and category in ("required_skills", "preferred_skills") and r.evidence:
                matches.append({"resume_skill": r.name, "job_skill": r.name, "match_type": "exact" if r.status == "matched" else "partial", "evidence": r.evidence})
            elif r.status == "missing":
                missing.append(r.name)
            elif r.status == "uncertain":
                uncertain.append(r.name)

    return {"score": round(max(0, min(100, total))), "score_breakdown": breakdown,
            "matched_skills": matches, "missing_evidence": missing, "uncertain_matches": uncertain,
            "experience_observations": model.experience_observations,
            "qualification_observations": model.qualification_observations,
            "improvement_suggestions": model.improvement_suggestions, "warnings": model.warnings}
