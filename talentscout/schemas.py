"""Pydantic schemas used for structured LLM outputs and agent data."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


# ---------- JD understanding ----------
class JDProfile(BaseModel):
    """Output of the Parse JD step."""

    is_hiring_request: bool = Field(description="True if the text is a job description or a request to find candidates.")
    input_type: Literal["full_jd", "search_query", "other"] = Field(
        description="full_jd = a pasted job description; search_query = a short natural-language candidate search.")
    role_title: str = Field(description="Normalised role title, e.g. 'Senior Frontend Engineer'. Use 'Software Engineer' if unclear.")
    seniority: Literal["intern", "junior", "mid", "senior", "lead", "unspecified"]
    domain: str = Field(description="Business/technical domain, e.g. 'fintech web apps'. Empty string if unknown.")
    key_responsibilities: list[str] = Field(description="Up to 5 short responsibilities. Empty for search queries.")
    summary: str = Field(description="One-sentence summary of who the recruiter is looking for.")


class SkillRequirement(BaseModel):
    skill: str = Field(description="Single skill/technology, e.g. 'React', 'AWS', 'Kubernetes'. One skill per item.")
    alternatives: list[str] = Field(default_factory=list, description=(
        "Other skills that equally satisfy this requirement when the JD says 'X or Y' / 'X (or similar)'. Empty otherwise."))
    min_years: Optional[float] = Field(default=None, description="Minimum years with THIS skill if explicitly stated, else null.")
    rationale: str = Field(default="", description="Short quote or reason from the JD.")


class JobRequirements(BaseModel):
    """Output of extract_requirements(jd): must-have vs nice-to-have."""

    role_title: str
    must_have: list[SkillRequirement] = Field(description="Non-negotiable skills (required / must / mandatory / strong X).")
    nice_to_have: list[SkillRequirement] = Field(description="Preferred / bonus / plus / good-to-have skills.")
    min_years_experience: Optional[float] = Field(default=None, description="Minimum TOTAL professional years, if stated.")
    education: Optional[str] = Field(default=None, description="Education requirement if stated, else null.")
    other_requirements: list[str] = Field(default_factory=list, description="Non-skill requirements (location, domain, leadership...).")
    search_query: str = Field(description="A dense one-paragraph semantic search query describing the ideal candidate's resume.")


class RequirementUpdate(BaseModel):
    """Output of the refine step: the full updated requirement set plus what changed."""

    updated: JobRequirements
    change_summary: str = Field(description="One or two sentences describing exactly what changed and why.")


# ---------- Conversation routing ----------
Intent = Literal["refine_requirements", "new_search", "compare", "explain_ranking",
                 "interview_questions", "question", "end"]


class RouterDecision(BaseModel):
    intent: Intent = Field(description=(
        "refine_requirements: change/add/remove criteria of the CURRENT search (e.g. 'make AWS mandatory', 'need 5+ years'). "
        "new_search: a completely new role or new set of criteria / new JD. "
        "compare: side-by-side comparison of specific candidates. "
        "explain_ranking: why someone ranked higher/lower or why someone is (not) shortlisted. "
        "interview_questions: generate screening/interview questions for a candidate. "
        "question: any other question about candidates, resumes, reports, or the process (answered with tools). "
        "end: user is done / says bye / exit."))
    candidate_ids: list[str] = Field(default_factory=list, description="Candidate IDs (e.g. C017) the user refers to, in the order mentioned. Resolve 'top 3', '#2', names using the ranking provided.")
    instruction: str = Field(description="The user's request restated precisely and self-contained.")
    reasoning: str = Field(description="One short sentence on why this intent was chosen.")


# ---------- Round 2: deep analysis ----------
class SkillEvidence(BaseModel):
    skill: str
    status: Literal["demonstrated", "mentioned_only", "missing"] = Field(
        description="demonstrated = used in a described role/project; mentioned_only = only listed; missing = absent.")
    evidence: str = Field(description="Short quote/paraphrase from the resume, or 'Not found'.")


class Strength(BaseModel):
    point: str
    evidence: str = Field(description="Concrete resume evidence (company, metric, project).")


class DeepAnalysis(BaseModel):
    fit_score: int = Field(ge=0, le=100, description="Holistic fit for THIS role, 0-100. 85+ exceptional, 70-84 strong, 55-69 borderline, <55 weak.")
    seniority_assessment: str = Field(description="E.g. 'Senior — has led design system work across 7 teams'.")
    must_have_evidence: list[SkillEvidence]
    strengths: list[Strength] = Field(description="2-4 strongest points relative to the JD.")
    gaps: list[str] = Field(description="1-4 concrete gaps relative to the JD (empty only if truly none).")
    risks: list[str] = Field(default_factory=list, description="Hiring risks, e.g. job hopping, keyword stuffing, recency of skill use.")
    summary: str = Field(description="Two-sentence assessment.")


# ---------- Round 3: decision ----------
class CandidateDecision(BaseModel):
    candidate_id: str
    recommendation: Literal["HIRE", "BORDERLINE", "NO_HIRE"]
    confidence: Literal["low", "medium", "high"]
    rationale: str = Field(description="One or two sentences grounded in scores, strengths and gaps.")
    improvement_suggestions: list[str] = Field(
        default_factory=list,
        description="For BORDERLINE (and optionally NO_HIRE): what the candidate could do/show to become a hire, or what to verify in interview.")


class FinalDecisions(BaseModel):
    decisions: list[CandidateDecision]
    overall_summary: str = Field(description="3-4 sentence summary of the shortlist for the hiring manager.")


# ---------- Tool outputs ----------
class InterviewQuestion(BaseModel):
    category: Literal["Skill verification", "Gap probe", "System design / depth", "Behavioural"]
    question: str
    what_good_looks_like: str
    targets: str = Field(description="Which requirement, strength or gap this question tests.")


class InterviewKit(BaseModel):
    questions: list[InterviewQuestion] = Field(description="6-8 questions tailored to the candidate's resume and gaps.")
    red_flags: list[str] = Field(description="2-3 answers/behaviours that should worry the interviewer.")
