"""Deterministic scoring and ranking-diff logic.

Round 1 scores every candidate on four transparent components so that any ranking
can be explained with real numbers:

    round1 = 45% must-have coverage + 15% nice-to-have coverage
           + 20% experience fit      + 20% semantic relevance (RAG)

Skill credit: demonstrated in a role = full credit (scaled by years if the JD asks
for N+ years of that skill), only listed in the skills section = 0.4, missing = 0.
"""

from __future__ import annotations

from .config import FINAL_BLEND, ROUND1_WEIGHTS
from .resume_store import CandidateProfile
from .skills import mentions_skill, normalize_skill

LISTED_ONLY_CREDIT = 0.4


def skill_match(profile: CandidateProfile, req: dict) -> dict:
    """Best match across the skill and its accepted alternatives ('Django or FastAPI')."""
    options = [req["skill"]] + list(req.get("alternatives") or [])
    best = max((_single_match(profile, s, req.get("min_years")) for s in options),
               key=lambda m: (m["credit"], m["years"]))
    if len(options) > 1:
        best = {**best, "matched": best["skill"], "skill": " / ".join(normalize_skill(s) for s in options)}
    return best


def _single_match(profile: CandidateProfile, raw_skill: str, min_years: float | None) -> dict:
    skill = normalize_skill(raw_skill)
    years = profile.skill_years.get(skill, 0.0)
    present = skill in profile.skills or mentions_skill(profile.text, skill)
    if years > 0:
        status = "demonstrated"
        credit = 1.0 if not min_years else 0.5 + 0.5 * min(1.0, years / min_years)
    elif present:
        status, credit = "listed_only", LISTED_ONLY_CREDIT
    else:
        status, credit = "missing", 0.0
    return {"skill": skill, "status": status, "years": years, "min_years": min_years, "credit": round(credit, 3)}


def _coverage(matches: list[dict]) -> float:
    return sum(m["credit"] for m in matches) / len(matches) if matches else 1.0


def experience_fit(total_years: float, min_years: float | None) -> float:
    if not min_years:
        return 1.0
    return min(1.0, total_years / min_years) ** 1.5  # falling short hurts progressively


def score_candidate(profile: CandidateProfile, requirements: dict, semantic_norm: float) -> dict:
    must = [skill_match(profile, r) for r in requirements.get("must_have", [])]
    nice = [skill_match(profile, r) for r in requirements.get("nice_to_have", [])]
    comps = {
        "must_have": _coverage(must),
        "nice_to_have": _coverage(nice),
        "experience": experience_fit(profile.total_years, requirements.get("min_years_experience")),
        "semantic": semantic_norm,
    }
    total = 100 * sum(ROUND1_WEIGHTS[k] * v for k, v in comps.items())
    flags = [f"Missing must-have: {m['skill']}" for m in must if m["status"] == "missing"]
    flags += [f"{m['skill']} only listed, not shown in any role" for m in must if m["status"] == "listed_only"]
    flags += [f"{m['skill']}: {m['years']}y < required {m['min_years']:g}y" for m in must
              if m["status"] == "demonstrated" and m["min_years"] and m["years"] < m["min_years"]]
    min_exp = requirements.get("min_years_experience")
    if min_exp and profile.total_years < min_exp:
        flags.append(f"Total experience {profile.total_years}y < required {min_exp:g}y")
    return {
        "candidate_id": profile.candidate_id,
        "name": profile.name,
        "headline": profile.headline,
        "total_years": profile.total_years,
        "components": {k: round(100 * v, 1) for k, v in comps.items()},
        "round1_score": round(total, 1),
        "must_have": must,
        "nice_to_have": nice,
        "flags": flags,
    }


def rank_round1(profiles: dict[str, CandidateProfile], requirements: dict, semantic: dict[str, float]) -> list[dict]:
    """Score every candidate. Semantic similarity is min-max normalised across the pool."""
    lo, hi = min(semantic.values()), max(semantic.values())
    span = (hi - lo) or 1.0
    scored = [score_candidate(p, requirements, (semantic.get(cid, lo) - lo) / span) for cid, p in profiles.items()]
    scored.sort(key=lambda s: (-s["round1_score"], -s["components"]["semantic"], s["candidate_id"]))
    for i, s in enumerate(scored, 1):
        s["round1_rank"] = i
    return scored


def final_score(round1_score: float, deep_fit: float) -> float:
    return round(FINAL_BLEND["round1"] * round1_score + FINAL_BLEND["deep_fit"] * deep_fit, 1)


# ------------------------------------------------------------------ explanations
COMPONENT_LABELS = {"must_have": "must-have coverage", "nice_to_have": "nice-to-have coverage",
                    "experience": "experience fit", "semantic": "semantic relevance"}


def component_contributions(entry: dict) -> dict[str, float]:
    """Weighted points each component contributes to the Round 1 score."""
    return {k: round(ROUND1_WEIGHTS[k] * v, 1) for k, v in entry["components"].items()}


def pairwise_breakdown(a: dict, b: dict) -> list[dict]:
    """Per-component point difference (a - b), largest first."""
    ca, cb = component_contributions(a), component_contributions(b)
    rows = [{"component": COMPONENT_LABELS[k], "a_points": ca[k], "b_points": cb[k], "delta": round(ca[k] - cb[k], 1)}
            for k in ca]
    return sorted(rows, key=lambda r: -abs(r["delta"]))


def requirements_diff(old: dict | None, new: dict) -> list[str]:
    if not old:
        return []
    changes: list[str] = []

    def skills(reqs: dict, key: str) -> dict[str, float | None]:
        return {normalize_skill(r["skill"]): r.get("min_years") for r in reqs.get(key, [])}

    om, nm, on, nn = skills(old, "must_have"), skills(new, "must_have"), skills(old, "nice_to_have"), skills(new, "nice_to_have")
    moved = {s for s in nm if s in on and s not in om} | {s for s in nn if s in om and s not in on}
    changes += [f"Moved {s}: nice-to-have → must-have" for s in nm if s in moved]
    changes += [f"Moved {s}: must-have → nice-to-have" for s in nn if s in moved]
    for key, label in (("must_have", "must-have"), ("nice_to_have", "nice-to-have")):
        o, n = skills(old, key), skills(new, key)
        changes += [f"Added {label}: {s}" + (f" ({y:g}+ yrs)" if y else "") for s, y in n.items()
                    if s not in o and s not in moved]
        changes += [f"Removed {label}: {s}" for s in o if s not in n and s not in moved]
        changes += [f"Changed {label} {s}: {o[s] or 'any'} → {n[s] or 'any'} yrs" for s in n if s in o and o[s] != n[s]]
    if old.get("min_years_experience") != new.get("min_years_experience"):
        changes.append(f"Minimum total experience: {old.get('min_years_experience') or 'none'} → "
                       f"{new.get('min_years_experience') or 'none'} yrs")
    return changes


def ranking_changes(previous: list[dict], current: list[dict], round1_all: list[dict]) -> list[dict]:
    """Explain how the final shortlist moved after a requirement change."""
    prev = {e["candidate_id"]: e for e in previous}
    curr = {e["candidate_id"]: e for e in current}
    r1 = {e["candidate_id"]: e for e in round1_all}
    out = []
    for cid, e in curr.items():
        old = prev.get(cid)
        if not old:
            out.append({"candidate_id": cid, "name": e["name"], "old_rank": None, "new_rank": e["rank"],
                        "movement": "NEW", "reason": _why_moved(None, r1.get(cid))})
        elif old["rank"] != e["rank"]:
            out.append({"candidate_id": cid, "name": e["name"], "old_rank": old["rank"], "new_rank": e["rank"],
                        "movement": f"{'▲' if e['rank'] < old['rank'] else '▼'}{abs(old['rank'] - e['rank'])}",
                        "reason": _why_moved(old, r1.get(cid))})
    for cid, old in prev.items():
        if cid not in curr:
            out.append({"candidate_id": cid, "name": old["name"], "old_rank": old["rank"], "new_rank": None,
                        "movement": "DROPPED", "reason": _why_moved(old, r1.get(cid), dropped=True)})
    return sorted(out, key=lambda x: (x["new_rank"] is None, x["new_rank"] or 0))


def _why_moved(old: dict | None, now_r1: dict | None, dropped: bool = False) -> str:
    if not now_r1:
        return ""
    bits = []
    missing = [m["skill"] for m in now_r1["must_have"] if m["status"] == "missing"]
    strong = [m["skill"] for m in now_r1["must_have"] if m["status"] == "demonstrated"]
    if dropped and missing:
        bits.append(f"missing must-have {', '.join(missing)}")
    elif not dropped and strong:
        bits.append(f"demonstrates {', '.join(strong[:4])}")
    if old and "components" in old:
        for k, v in now_r1["components"].items():
            d = v - old["components"].get(k, v)
            if abs(d) >= 10:
                bits.append(f"{COMPONENT_LABELS[k]} {'+' if d > 0 else ''}{d:.0f}")
    bits.append(f"Round 1 now #{now_r1['round1_rank']} ({now_r1['round1_score']})")
    return "; ".join(bits)
