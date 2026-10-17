from app.schemas.schemas import ModelAnalysis
from app.services.matching_engine import calculate_analysis


def model(requirements):
    return ModelAnalysis.model_validate({"requirements": requirements})


def test_all_matching_gives_full_score_and_normalizes_active_weights():
    result = calculate_analysis(model([
        {"name": "JavaScript", "category": "required_skills", "status": "matched", "evidence": "Built JavaScript apps"},
        {"name": "3 years experience", "category": "relevant_experience", "status": "matched", "evidence": "3 years experience"},
    ]), "Built JavaScript apps with 3 years experience")
    assert result["score"] == 100
    assert result["score_breakdown"]["required_skills"]["weight"] == .6667
    assert result["score_breakdown"]["preferred_skills"]["match_percentage"] is None


def test_partial_missing_and_uncertain_are_distinct():
    result = calculate_analysis(model([
        {"name": "Python", "category": "required_skills", "status": "partial", "evidence": "Python projects"},
        {"name": "Kubernetes", "category": "required_skills", "status": "missing"},
        {"name": "Terraform", "category": "required_skills", "status": "uncertain", "evidence": "Terraform adjacent"},
    ]), "Python projects and Terraform adjacent")
    assert result["score"] == 25
    assert result["missing_evidence"] == ["Kubernetes"]
    assert result["uncertain_matches"] == ["Terraform"]


def test_duplicate_aliases_are_not_double_counted_and_unverified_quotes_do_not_score():
    result = calculate_analysis(model([
        {"name": "JavaScript", "category": "required_skills", "status": "matched", "evidence": "javascript experience"},
        {"name": "JS", "category": "required_skills", "status": "missing"},
        {"name": "Go", "category": "required_skills", "status": "matched", "evidence": "I know Go"},
        {"name": "SQL", "category": "required_skills", "status": "missing"},
    ]), "javascript experience")
    assert result["score"] == 50
    assert len(result["score_breakdown"]["required_skills"]["requirements"]) == 3
    assert "Go" in result["uncertain_matches"]
