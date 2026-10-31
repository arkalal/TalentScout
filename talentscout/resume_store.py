"""Resume loading and parsing (Milestone 1 rebuilt).

Reads .md / .txt / .pdf resumes from disk and turns each into a ``CandidateProfile``
with skills, per-role history, total years of experience and *per-skill* years
(how long the skill was used in described roles). Parsing is deterministic so
scores and explanations are reproducible.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

from .config import RESUME_DIR
from .skills import find_skills

TODAY = date(2026, 10, 31)
SUPPORTED = {".md", ".txt", ".pdf"}
_MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_DATE = r"(?:(?P<{p}m>[A-Za-z]{{3}})[a-z]*\.?\s+)?(?P<{p}y>\d{{4}})"
DATE_RANGE = re.compile(
    _DATE.format(p="s") + r"\s*(?:–|-|—|to)\s*(?:(?P<present>present|current|now)|" + _DATE.format(p="e") + ")",
    re.IGNORECASE)


@dataclass
class Role:
    title: str
    company: str
    start: str
    end: str
    months: int
    skills: list[str]
    text: str


@dataclass
class CandidateProfile:
    candidate_id: str
    name: str
    headline: str
    location: str
    file_name: str
    text: str
    skills: list[str]                 # every canonical skill found anywhere
    listed_skills: list[str]          # skills in the Skills section
    demonstrated_skills: list[str]    # skills used in at least one described role
    roles: list[Role]
    total_years: float
    skill_years: dict[str, float]     # skill -> years used across roles
    education: str = ""
    certifications: list[str] = field(default_factory=list)

    def brief(self) -> dict:
        return {"candidate_id": self.candidate_id, "name": self.name, "headline": self.headline,
                "location": self.location, "total_years": self.total_years,
                "skills": self.skills, "file": self.file_name}

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("text")
        for r in d["roles"]:
            r.pop("text")
        return d


# ---------------------------------------------------------------- file reading
def read_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader

        return "\n".join((page.extract_text() or "") for page in PdfReader(str(path)).pages)
    return path.read_text(encoding="utf-8", errors="ignore")


def list_resume_files(directory: Path = RESUME_DIR) -> list[Path]:
    return sorted(p for p in Path(directory).iterdir() if p.suffix.lower() in SUPPORTED and p.is_file())


# ---------------------------------------------------------------- parsing helpers
def _to_month_index(month: str | None, year: str, default_month: int) -> int:
    m = _MONTHS.get((month or "")[:3].lower(), default_month)
    return int(year) * 12 + (m - 1)


def _section(text: str, name: str) -> str:
    m = re.search(rf"^#+\s*{name}\s*$(.*?)(?=^#{{1,2}}\s|\Z)", text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else ""


def _parse_roles(text: str) -> list[Role]:
    exp = _section(text, "Experience") or text
    blocks = re.split(r"^(?=###\s)", exp, flags=re.MULTILINE)
    roles: list[Role] = []
    now_idx = TODAY.year * 12 + TODAY.month - 1
    for block in blocks:
        header = block.strip().splitlines()[0] if block.strip() else ""
        dm = DATE_RANGE.search(header) or DATE_RANGE.search(block[:300])
        if not dm:
            continue
        start = _to_month_index(dm.group("sm"), dm.group("sy"), 1)
        end = now_idx if dm.group("present") else _to_month_index(dm.group("em"), dm.group("ey"), 12)
        cut = header.find(dm.group(0))
        title_part = re.sub(r"^#+\s*", "", header[:cut] if cut > 0 else header).strip().rstrip("(|,").strip()
        title, _, company = title_part.partition("—") if "—" in title_part else title_part.partition(" at ")
        roles.append(Role(title=title.strip(), company=company.strip(),
                          start=f"{dm.group('sm') or ''} {dm.group('sy')}".strip(),
                          end="Present" if dm.group("present") else f"{dm.group('em') or ''} {dm.group('ey')}".strip(),
                          months=max(1, end - start + 1), skills=sorted(find_skills(block)), text=block.strip()))
    return roles


def _merged_years(roles: list[Role], text: str) -> float:
    """Total experience = union of role date ranges (overlaps counted once)."""
    now_idx = TODAY.year * 12 + TODAY.month - 1
    intervals = []
    for m in DATE_RANGE.finditer(_section(text, "Experience") or text):
        s = _to_month_index(m.group("sm"), m.group("sy"), 1)
        e = now_idx if m.group("present") else _to_month_index(m.group("em"), m.group("ey"), 12)
        if e >= s:
            intervals.append((s, e))
    intervals.sort()
    total, cur = 0, None
    for s, e in intervals:
        if cur and s <= cur[1] + 1:
            cur = (cur[0], max(cur[1], e))
        else:
            if cur:
                total += cur[1] - cur[0] + 1
            cur = (s, e)
    if cur:
        total += cur[1] - cur[0] + 1
    return round(total / 12, 1)


def parse_resume(path: Path) -> CandidateProfile:
    text = read_text(path)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    name = re.sub(r"^#+\s*", "", lines[0]) if lines else path.stem
    headline_line = re.sub(r"\*", "", lines[1]) if len(lines) > 1 else ""
    headline, _, location = headline_line.partition("|")
    cid_match = re.match(r"(C\d{3,})", path.stem)
    roles = _parse_roles(text)
    skill_months: dict[str, int] = {}
    for r in roles:
        for s in r.skills:
            skill_months[s] = skill_months.get(s, 0) + r.months
    listed = sorted(find_skills(_section(text, "Skills")))
    certs = [c.lstrip("- ").strip() for c in _section(text, "Certifications").splitlines() if c.strip()]
    return CandidateProfile(
        candidate_id=cid_match.group(1) if cid_match else path.stem,
        name=name,
        headline=headline.strip(),
        location=location.strip(),
        file_name=path.name,
        text=text,
        skills=sorted(find_skills(text)),
        listed_skills=listed,
        demonstrated_skills=sorted(skill_months),
        roles=roles,
        total_years=_merged_years(roles, text),
        skill_years={s: round(m / 12, 1) for s, m in sorted(skill_months.items())},
        education=_section(text, "Education").splitlines()[0] if _section(text, "Education") else "",
        certifications=certs,
    )


# ---------------------------------------------------------------- store
@lru_cache(maxsize=4)
def _load(directory: str, signature: tuple) -> dict[str, CandidateProfile]:
    return {p.candidate_id: p for p in (parse_resume(f) for f in list_resume_files(Path(directory)))}


def load_profiles(directory: Path = RESUME_DIR) -> dict[str, CandidateProfile]:
    """All candidate profiles keyed by ID. Cached; reloads automatically if files change."""
    files = list_resume_files(directory)
    signature = tuple((f.name, f.stat().st_mtime_ns) for f in files)
    return _load(str(directory), signature)


def get_profile(candidate_id: str) -> CandidateProfile | None:
    return load_profiles().get(candidate_id.strip().upper())


def resolve_candidate(ref: str) -> CandidateProfile | None:
    """Resolve an ID ('C017'), a full name or a first name ('John') to a profile."""
    ref = ref.strip()
    profiles = load_profiles()
    if ref.upper() in profiles:
        return profiles[ref.upper()]
    low = ref.lower()
    exact = [p for p in profiles.values() if p.name.lower() == low]
    if exact:
        return exact[0]
    partial = [p for p in profiles.values() if low in p.name.lower().split() or p.name.lower().startswith(low)]
    if len(partial) == 1:
        return partial[0]
    best = max(profiles.values(), key=lambda p: SequenceMatcher(None, low, p.name.lower()).ratio(), default=None)
    if best and SequenceMatcher(None, low, best.name.lower()).ratio() > 0.75:
        return best
    return None
