"""Validated API contracts for resume analysis."""
from typing import Literal
from pydantic import BaseModel, Field

Category = Literal["required_skills", "relevant_experience", "explicit_qualifications", "preferred_skills"]


class Requirement(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    category: Category
    status: Literal["matched", "partial", "missing", "uncertain"]
    evidence: str | None = Field(default=None, max_length=500)


class ModelAnalysis(BaseModel):
    requirements: list[Requirement] = Field(max_length=80)
    experience_observations: str = Field(default="", max_length=1200)
    qualification_observations: str = Field(default="", max_length=1200)
    improvement_suggestions: list[str] = Field(default_factory=list, max_length=8)
    warnings: list[str] = Field(default_factory=list, max_length=8)


class CategoryScore(BaseModel):
    base_weight: float
    weight: float
    match_percentage: float | None
    category_score: float
    requirements: list[Requirement]


class AnalysisResponse(BaseModel):
    score: float = Field(ge=0, le=100)
    score_breakdown: dict[str, CategoryScore]
    matched_skills: list[dict[str, str]]
    missing_evidence: list[str]
    uncertain_matches: list[str]
    experience_observations: str
    qualification_observations: str
    improvement_suggestions: list[str]
    warnings: list[str]
