"""File-system tools (Milestone 1 rebuilt) and the RAG search tool (Milestone 2) exposed to the agent."""

from __future__ import annotations

import re
from datetime import datetime

from langchain_core.tools import tool

from ..config import REPORT_DIR, RESUME_DIR
from ..rag import get_index
from ..resume_store import get_profile, list_resume_files, load_profiles, resolve_candidate


def _lookup(candidate: str):
    return get_profile(candidate) or resolve_candidate(candidate)


@tool
def list_resumes(skill_filter: str = "") -> list[dict]:
    """List resumes in the resume folder (ID, name, headline, years, file). Optionally filter to candidates with a skill."""
    out = []
    for p in load_profiles().values():
        if skill_filter and not any(skill_filter.lower() == s.lower() for s in p.skills):
            continue
        out.append({"candidate_id": p.candidate_id, "name": p.name, "headline": p.headline,
                    "total_years": p.total_years, "file": p.file_name})
    return out


@tool
def read_resume(candidate: str) -> str:
    """Read the full text of a resume. `candidate` is an ID like C017 or a candidate name."""
    p = _lookup(candidate)
    if not p:
        return f"No resume found for '{candidate}'."
    return f"[{p.candidate_id} | {p.file_name}]\n{p.text}"


@tool
def get_candidate_profile(candidate: str) -> dict:
    """Parsed profile of a candidate: skills, per-skill years, roles, total years, education, certifications."""
    p = _lookup(candidate)
    if not p:
        return {"error": f"No resume found for '{candidate}'."}
    return p.to_dict()


@tool
def search_resumes_by_keyword(keyword: str, max_results: int = 25) -> list[dict]:
    """Exact keyword/regex search across all resume files (like grep). Returns matching candidates and lines."""
    try:
        pat = re.compile(keyword, re.IGNORECASE)
    except re.error:
        pat = re.compile(re.escape(keyword), re.IGNORECASE)
    hits = []
    for p in load_profiles().values():
        lines = [ln.strip() for ln in p.text.splitlines() if pat.search(ln)]
        if lines:
            hits.append({"candidate_id": p.candidate_id, "name": p.name, "matches": lines[:3]})
    return hits[:max_results]


@tool
def save_report(filename: str, content: str) -> str:
    """Save a markdown report/notes to the reports/ folder. Returns the saved path."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", filename).strip("._") or "report"
    if not safe.endswith(".md"):
        safe += ".md"
    path = REPORT_DIR / safe
    path.write_text(content, encoding="utf-8")
    return str(path.relative_to(REPORT_DIR.parent))


@tool
def list_saved_reports() -> list[dict]:
    """List previously saved reports in the reports/ folder."""
    if not REPORT_DIR.exists():
        return []
    return [{"file": f.name, "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(timespec="seconds")}
            for f in sorted(REPORT_DIR.glob("*.md"))]


@tool
def rag_search(query: str, k: int = 6, candidate: str = "") -> list[dict]:
    """Semantic (RAG) search over resume chunks with cross-encoder reranking.
    Use for meaning-based questions ("who has led teams", "experience with payments").
    Optionally restrict to one candidate (ID or name)."""
    cid = ""
    if candidate:
        p = _lookup(candidate)
        if not p:
            return [{"error": f"Unknown candidate '{candidate}'."}]
        cid = p.candidate_id
    return [h.to_dict() for h in get_index().search(query, k=k, candidate_id=cid or None)]


FS_TOOLS = [list_resumes, read_resume, get_candidate_profile, search_resumes_by_keyword, save_report,
            list_saved_reports]
RAG_TOOLS = [rag_search]


def resume_count() -> int:
    return len(list_resume_files(RESUME_DIR))
