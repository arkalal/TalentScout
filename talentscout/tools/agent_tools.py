"""Agent-specific tools: extract_requirements, compare_candidates, generate_interview_questions,
plus the Round-2 / Round-3 analysis functions and ranking explanations.

Core functions take plain data (requirements dict, state dict) so they can be called from graph
nodes directly; ``make_state_tools(state)`` wraps them as LangChain tools for the Q&A agent.
"""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool

from .. import prompts
from ..config import BORDERLINE_THRESHOLD, HIRE_THRESHOLD, ROUND1_SHORTLIST, ROUND1_WEIGHTS, get_llm
from ..resume_store import CandidateProfile, get_profile, resolve_candidate
from ..schemas import DeepAnalysis, FinalDecisions, InterviewKit, JobRequirements
from ..scoring import component_contributions, pairwise_breakdown
from ..skills import SKILL_ALIASES, SKILL_CATEGORIES, normalize_skill


def structured(schema, system: str, user: str):
    return get_llm().with_structured_output(schema).invoke([SystemMessage(system), HumanMessage(user)])


_PRONOUNS = {"him": "them", "his": "their", "her": "their", "hers": "theirs",
             "himself": "themselves", "herself": "themselves"}
_PRONOUN_RE = re.compile(r"\b(" + "|".join(_PRONOUNS) + r")\b", re.IGNORECASE)
_SUBJECT_RE = re.compile(r"\b([Hh]e|[Ss]he)\b((?:\s+(?:also|only|still|clearly|currently|already|then|now|never|"
                         r"often|later|really|primarily|mainly|just|not|always|even|further|likewise))*)\s+([A-Za-z]+(?:['’]t)?)")
_IRREGULAR = {"is": "are", "was": "were", "has": "have", "does": "do", "isn't": "aren't", "wasn't": "weren't",
              "hasn't": "haven't", "doesn't": "don't"}


_OBJECT_FOLLOWERS = {"to", "a", "an", "the", "and", "or", "for", "from", "with", "as", "in", "on", "at", "by", "into",
                     "than", "over", "about", "because", "since", "if", "but", "so", "up", "out", "down", "apart", "ahead"}


def _plural_verb(word: str) -> str:
    low = word.lower().replace("’", "'")
    if low in _IRREGULAR:
        return _IRREGULAR[low]
    if low.endswith("ies") and len(low) > 4:
        return word[:-3] + "y"                      # applies -> apply
    if re.search(r"(sh|ch|x|ss|zz|o)es$", low):
        return word[:-2]                            # pushes -> push, goes -> go
    if low.endswith("s") and not low.endswith("ss") and len(low) > 2:
        return word[:-1]                            # lacks -> lack
    return word                                     # can, will, led, would ... unchanged


def neutralize_pronouns(text: str) -> str:
    """Safety net for the fairness rule: candidate-facing text never infers gender from a name."""
    def subject(m: re.Match) -> str:
        they = "They" if m.group(1)[0].isupper() else "they"
        return f"{they}{m.group(2)} {_plural_verb(m.group(3))}"

    def other(m: re.Match) -> str:
        word = m.group(0)
        new = _PRONOUNS[word.lower()]
        if word.lower() == "her":  # object ("caused her to") vs possessive ("her React work")
            nxt = re.match(r"\s*([A-Za-z]+)?", text[m.end():]).group(1) or ""
            if not nxt or nxt.lower() in _OBJECT_FOLLOWERS:
                new = "them"
        return new.capitalize() if word[0].isupper() else new
    return _PRONOUN_RE.sub(other, _SUBJECT_RE.sub(subject, text))


def text_llm(system: str, user: str) -> str:
    return neutralize_pronouns(get_llm().invoke([SystemMessage(system), HumanMessage(user)]).content)


# ------------------------------------------------------------------ requirement helpers
_GENERIC = re.compile(r"\b(software|engineering|development|developer|experience|programming|coding|frontend|"
                      r"backend|full[- ]?stack|professional|industry|years?|devops|sre|site reliability)\b", re.IGNORECASE)


_VAGUE = re.compile(r"\b(similar|equivalent|other|another|any|etc|related|comparable|frameworks?|tools?|brokers?|"
                    r"platforms?|services?)\b", re.IGNORECASE)
_CATEGORY = {skill: cat for cat, skills in SKILL_CATEGORIES.items() for skill in skills}


def _split_cross_category(items: list[dict]) -> list[dict]:
    """'Python / Django / FastAPI' -> Python + 'Django / FastAPI': alternatives must be the same kind of skill."""
    out = []
    for item in items:
        alts = item.get("alternatives") or []
        cat = _CATEGORY.get(item["skill"])
        other = [a for a in alts if cat and _CATEGORY.get(a) and _CATEGORY[a] != cat]
        if other:
            out.append({**item, "alternatives": [a for a in alts if a not in other]})
            out.append({"skill": other[0], "alternatives": other[1:], "min_years": None, "rationale": item.get("rationale", "")})
        else:
            out.append(item)
    return out


def _is_generic(skill: str) -> bool:
    """'Software Engineering', 'Frontend development', 'Professional experience' are not matchable skills."""
    return skill not in SKILL_ALIASES and bool(_GENERIC.search(skill))


def _normalise_requirements(req: JobRequirements) -> dict:
    data = req.model_dump()
    seen: set[str] = set()
    for key in ("must_have", "nice_to_have"):
        cleaned = []
        for item in _split_cross_category([{**i, "skill": normalize_skill(i["skill"]),
                                            "alternatives": [normalize_skill(a) for a in i.get("alternatives") or []]}
                                           for i in data[key]]):
            item["skill"] = normalize_skill(item["skill"])
            item["alternatives"] = [a for a in dict.fromkeys(normalize_skill(x) for x in item.get("alternatives") or [])
                                    if a != item["skill"] and not _is_generic(a) and not _VAGUE.search(a)]
            if _is_generic(item["skill"]) and item["alternatives"]:  # promote a concrete alternative
                item["skill"] = item["alternatives"].pop(0)
            if _is_generic(item["skill"]):  # generic "skill" with years -> total experience requirement
                if item.get("min_years") and key == "must_have":
                    data["min_years_experience"] = max(data.get("min_years_experience") or 0, item["min_years"])
                data["other_requirements"] = data.get("other_requirements", []) + [f"{item['skill']} (general)"]
                continue
            if item["skill"].lower() in seen:
                continue
            seen.add(item["skill"].lower())
            cleaned.append(item)
        data[key] = cleaned
    return data


def skill_label(req: dict) -> str:
    """'Django' or 'Django / FastAPI' when alternatives are accepted."""
    return " / ".join([req["skill"]] + list(req.get("alternatives") or []))


def extract_requirements(jd: str) -> dict:
    """Tool: parse a JD (or a short search request) into must-have vs nice-to-have requirements."""
    return _normalise_requirements(structured(JobRequirements, prompts.EXTRACT_REQUIREMENTS, jd))


def requirements_brief(req: dict) -> str:
    def fmt(items):
        return ", ".join(skill_label(i) + (f" ({i['min_years']:g}+y)" if i.get("min_years") else "") for i in items) or "—"

    s = f"Must-have: {fmt(req.get('must_have', []))}. Nice-to-have: {fmt(req.get('nice_to_have', []))}."
    if req.get("min_years_experience"):
        s += f" Min total experience: {req['min_years_experience']:g}y."
    if req.get("other_requirements"):
        s += " Other: " + "; ".join(req["other_requirements"]) + "."
    return s


def ranking_text(state: dict, limit: int = 10) -> str:
    rows = state.get("final_ranking") or []
    if not rows:
        return "(no ranking yet)"
    return "\n".join(f"{e['rank']}. {e['candidate_id']} {e['name']} — final {e['final_score']} — "
                     f"{e.get('recommendation', 'n/a')}" for e in rows[:limit])


def candidate_directory() -> str:
    from ..resume_store import load_profiles

    return "; ".join(f"{p.candidate_id}={p.name}" for p in load_profiles().values())


# ------------------------------------------------------------------ Round 2 / Round 3
def _deep_prompt(profile: CandidateProfile, requirements: dict, r1: dict) -> str:
    return (f"ROLE: {requirements.get('role_title')}\nREQUIREMENTS: {requirements_brief(requirements)}\n"
            f"System-parsed facts: total experience {profile.total_years}y; per-skill years from roles "
            f"{json.dumps(profile.skill_years)}; Round-1 flags: {r1.get('flags') or 'none'}\n\n"
            f"RESUME ({profile.candidate_id}):\n{profile.text}")


def deep_analyze_many(entries: list[dict], requirements: dict) -> dict[str, dict]:
    """Round 2: LLM deep review of each shortlisted resume (run concurrently)."""
    profiles = [get_profile(e["candidate_id"]) for e in entries]
    chain = get_llm().with_structured_output(DeepAnalysis)
    inputs = [[SystemMessage(prompts.DEEP_ANALYSIS), HumanMessage(_deep_prompt(p, requirements, e))]
              for p, e in zip(profiles, entries)]
    results = chain.batch(inputs, config={"max_concurrency": 10}, return_exceptions=True)
    out: dict[str, dict] = {}
    for e, res in zip(entries, results):
        if isinstance(res, Exception):  # degrade gracefully: fall back to the Round-1 score
            out[e["candidate_id"]] = {"fit_score": int(e["round1_score"]), "seniority_assessment": "n/a",
                                      "must_have_evidence": [], "strengths": [], "gaps": [], "risks": [],
                                      "summary": f"Deep review unavailable ({type(res).__name__}); using Round-1 score."}
        else:
            out[e["candidate_id"]] = res.model_dump()
    return out


def final_decisions(finalists: list[dict], deep: dict[str, dict], requirements: dict) -> dict:
    """Round 3: hire / borderline / no-hire for each finalist, with improvement suggestions."""
    lines = []
    for e in finalists:
        d = deep.get(e["candidate_id"], {})
        missing = [m["skill"] for m in e.get("must_have", []) if m["status"] == "missing"]
        lines.append(json.dumps({
            "candidate_id": e["candidate_id"], "name": e["name"], "final_score": e["final_score"],
            "round1_score": e["round1_score"], "deep_fit": e["deep_fit"], "total_years": e["total_years"],
            "missing_must_haves": missing, "flags": e.get("flags", []),
            "strengths": [s["point"] for s in d.get("strengths", [])], "gaps": d.get("gaps", []),
            "risks": d.get("risks", []), "summary": d.get("summary", "")}))
    user = (f"ROLE: {requirements.get('role_title')}\nREQUIREMENTS: {requirements_brief(requirements)}\n\n"
            "FINALISTS:\n" + "\n".join(lines))
    system = prompts.FINAL_DECISION.format(hire=HIRE_THRESHOLD, border=BORDERLINE_THRESHOLD)
    result: FinalDecisions = structured(FinalDecisions, system, user)
    by_id = {d.candidate_id: d.model_dump() for d in result.decisions}
    # deterministic guardrails on top of the LLM decision
    adjusted: list[str] = []
    for e in finalists:
        dec = by_id.get(e["candidate_id"])
        if dec is None:
            band = ("HIRE" if e["final_score"] >= HIRE_THRESHOLD else
                    "BORDERLINE" if e["final_score"] >= BORDERLINE_THRESHOLD else "NO_HIRE")
            dec = by_id[e["candidate_id"]] = {"candidate_id": e["candidate_id"], "recommendation": band,
                                              "confidence": "low", "rationale": "Score-band default.",
                                              "improvement_suggestions": []}
        missing = [m["skill"] for m in e.get("must_have", []) if m["status"] == "missing"]
        if dec["recommendation"] == "HIRE" and missing:
            dec["recommendation"] = "BORDERLINE"
            dec["rationale"] += f" (Guardrail: downgraded — missing must-have {', '.join(missing)}.)"
            adjusted.append(e["name"])
            dec["improvement_suggestions"] = dec["improvement_suggestions"] or [f"Demonstrate hands-on {s}" for s in missing]
    summary = result.overall_summary
    if adjusted:
        summary += f" Guardrail: {', '.join(adjusted)} moved from HIRE to BORDERLINE because a must-have is missing."
    return {"decisions": by_id, "overall_summary": summary}


# ------------------------------------------------------------------ lookup helpers
def _round1_entry(state: dict, cid: str) -> dict | None:
    return next((e for e in state.get("round1", []) if e["candidate_id"] == cid), None)


def _final_entry(state: dict, cid: str) -> dict | None:
    return next((e for e in state.get("final_ranking", []) if e["candidate_id"] == cid), None)


def resolve_ids(refs: list[str]) -> list[str]:
    ids = []
    for r in refs:
        p = get_profile(r) or resolve_candidate(r)
        if p and p.candidate_id not in ids:
            ids.append(p.candidate_id)
    return ids


def _ensure_deep(state: dict, ids: list[str]) -> dict[str, dict]:
    """Deep analyses for ids; analyse on demand anyone not in the shortlist."""
    deep = dict(state.get("deep_analysis") or {})
    todo = [_round1_entry(state, cid) for cid in ids if cid not in deep and _round1_entry(state, cid)]
    if todo:
        deep.update(deep_analyze_many(todo, state["requirements"]))
    return deep


def _skill_cell(m: dict) -> str:
    if m["status"] == "demonstrated":
        return f"✅ {m['years']:g}y"
    return "⚠️ listed only" if m["status"] == "listed_only" else "❌"


# ------------------------------------------------------------------ compare_candidates
def compare_candidates(candidate_ids: list[str], state: dict) -> tuple[str, dict[str, dict]]:
    """Tool: head-to-head comparison. Returns (markdown, deep analyses incl. any computed on demand)."""
    ids = resolve_ids(candidate_ids)
    if len(ids) < 2:
        return "Please name at least two candidates to compare (IDs, names or e.g. 'top 3').", {}
    deep = _ensure_deep(state, ids)
    entries = [(_round1_entry(state, cid), _final_entry(state, cid), deep.get(cid, {})) for cid in ids]
    header = "| | " + " | ".join(f"**{r1['name']}** ({r1['candidate_id']})" for r1, _, _ in entries) + " |"
    sep = "|---" * (len(ids) + 1) + "|"
    rows = [
        ("Final rank / score", [f"#{f['rank']} · {f['final_score']}" if f else f"not shortlisted (R1 #{r1['round1_rank']})"
                                for r1, f, _ in entries]),
        ("Recommendation", [(f or {}).get("recommendation", "—").replace("_", " ") for _, f, _ in entries]),
        ("Round 1 score", [f"{r1['round1_score']}" for r1, _, _ in entries]),
        ("Deep-review fit", [str(d.get("fit_score", "—")) for _, _, d in entries]),
        ("Total experience", [f"{r1['total_years']}y" for r1, _, _ in entries]),
    ]
    for i, m in enumerate(entries[0][0]["must_have"]):
        rows.append((f"Must: {m['skill']}" + (f" ({m['min_years']:g}+y)" if m["min_years"] else ""),
                     [_skill_cell(r1["must_have"][i]) for r1, _, _ in entries]))
    for i, m in enumerate(entries[0][0]["nice_to_have"]):
        rows.append((f"Nice: {m['skill']}", [_skill_cell(r1["nice_to_have"][i]) for r1, _, _ in entries]))
    rows.append(("Top strength", [(d.get("strengths") or [{"point": "—"}])[0]["point"] for _, _, d in entries]))
    rows.append(("Main gap", [(d.get("gaps") or ["—"])[0] for _, _, d in entries]))
    table = "\n".join([header, sep] + [f"| {label} | " + " | ".join(str(c).replace("|", "/") for c in cells) + " |"
                                        for label, cells in rows])
    notes = "\n".join(f"{r1['name']} ({r1['candidate_id']}): {d.get('summary', '')} Strengths: "
                      f"{[s['point'] for s in d.get('strengths', [])]}. Gaps: {d.get('gaps', [])}"
                      for r1, _, d in entries)
    verdict = text_llm(prompts.COMPARE, f"ROLE: {state['requirements'].get('role_title')}\n"
                                        f"REQUIREMENTS: {requirements_brief(state['requirements'])}\n\nTABLE:\n{table}\n\nNOTES:\n{notes}")
    md = f"### Head-to-head: {' vs '.join(r1['name'] for r1, _, _ in entries)}\n\n{table}\n\n{verdict}"
    return md, deep


# ------------------------------------------------------------------ explain ranking
def explain_ranking(candidate_ids: list[str], question: str, state: dict) -> str:
    ids = resolve_ids(candidate_ids) or [e["candidate_id"] for e in state.get("final_ranking", [])]
    r1_all = state.get("round1", [])
    cutoff = r1_all[ROUND1_SHORTLIST - 1]["round1_score"] if len(r1_all) >= ROUND1_SHORTLIST else 0
    facts: list[str] = []
    for cid in ids[:3] if len(candidate_ids) else ids[:10]:
        r1, fin = _round1_entry(state, cid), _final_entry(state, cid)
        dec = (state.get("decisions") or {}).get(cid, {})
        if not r1:
            continue
        d = (state.get("deep_analysis") or {}).get(cid, {})
        facts.append(json.dumps({
            "candidate": f"{r1['name']} ({cid})", "final_rank": fin["rank"] if fin else None,
            "final_score": fin["final_score"] if fin else None, "round1_rank": r1["round1_rank"],
            "round1_score": r1["round1_score"],
            "round1_points": {k: f"{v} / {round(ROUND1_WEIGHTS[k] * 100)}" for k, v in component_contributions(r1).items()},
            "must_have": [{k: m[k] for k in ("skill", "status", "years", "min_years")} for m in r1["must_have"]],
            "nice_to_have": [{k: m[k] for k in ("skill", "status")} for m in r1["nice_to_have"]],
            "total_years": r1["total_years"], "flags": r1["flags"], "deep_fit": d.get("fit_score"),
            "deep_strengths": [s["point"] for s in d.get("strengths", [])], "deep_gaps": d.get("gaps", []),
            "recommendation": (fin or {}).get("recommendation"), "decision_rationale": dec.get("rationale"),
            "improvement_suggestions": dec.get("improvement_suggestions")}))
    table = ""
    if len(candidate_ids) >= 2 and len(ids) >= 2:
        a, b = _round1_entry(state, ids[0]), _round1_entry(state, ids[1])
        if a and b:
            rows = pairwise_breakdown(a, b)
            table = (f"| Round-1 component (weighted pts) | {a['name']} | {b['name']} | Δ |\n|---|---|---|---|\n" +
                     "\n".join(f"| {r['component']} | {r['a_points']} | {r['b_points']} | {r['delta']:+} |" for r in rows) +
                     f"\n| **Round-1 total** | **{a['round1_score']}** | **{b['round1_score']}** | "
                     f"**{a['round1_score'] - b['round1_score']:+.1f}** |")
            fa, fb = _final_entry(state, ids[0]), _final_entry(state, ids[1])
            if fa and fb:
                table += (f"\n| Round-2 deep fit | {fa['deep_fit']} | {fb['deep_fit']} | {fa['deep_fit'] - fb['deep_fit']:+} |"
                          f"\n| **Final score** | **{fa['final_score']}** | **{fb['final_score']}** | "
                          f"**{fa['final_score'] - fb['final_score']:+.1f}** |")
    context = (f"QUESTION: {question}\nROLE: {state['requirements'].get('role_title')}\n"
               f"REQUIREMENTS: {requirements_brief(state['requirements'])}\nShortlist cut-off (Round-1 #"
               f"{ROUND1_SHORTLIST} score): {cutoff}\n\nCURRENT RANKING:\n{ranking_text(state)}\n\n"
               f"COMPUTED BREAKDOWN TABLE:\n{table or 'n/a'}\n\nCANDIDATE FACTS:\n" + "\n".join(facts))
    narrative = text_llm(prompts.EXPLAIN.format(k=ROUND1_SHORTLIST), context)
    return (f"{table}\n\n{narrative}" if table else narrative).strip()


# ------------------------------------------------------------------ interview questions
def generate_interview_questions(candidate_id: str, state: dict) -> tuple[str, dict[str, dict]]:
    """Tool: tailored screening questions for one candidate. Returns (markdown, deep analyses)."""
    ids = resolve_ids([candidate_id])
    if not ids:
        return f"I couldn't find a candidate matching '{candidate_id}'.", {}
    cid = ids[0]
    deep = _ensure_deep(state, [cid])
    p, d, r1 = get_profile(cid), deep.get(cid, {}), _round1_entry(state, cid) or {}
    user = (f"ROLE: {state['requirements'].get('role_title')}\nREQUIREMENTS: {requirements_brief(state['requirements'])}\n"
            f"ASSESSMENT: strengths={[s['point'] for s in d.get('strengths', [])]}; gaps={d.get('gaps', [])}; "
            f"risks={d.get('risks', [])}; flags={r1.get('flags', [])}\n\nRESUME:\n{p.text}")
    kit: InterviewKit = structured(InterviewKit, prompts.INTERVIEW, user)
    md = [f"### Screening questions for {p.name} ({cid})"]
    for i, q in enumerate(kit.questions, 1):
        md.append(f"**{i}. [{q.category}]** {q.question}  \n   *Tests:* {q.targets}  \n   *Good answer:* {q.what_good_looks_like}")
    md.append("\n**Red flags to watch for:**\n" + "\n".join(f"- {r}" for r in kit.red_flags))
    return "\n\n".join(md), deep


# ------------------------------------------------------------------ LangChain tool wrappers
def make_state_tools(state: dict) -> list[Any]:
    """Tools bound to the current agent state, for the free-form Q&A node."""

    @tool("extract_requirements")
    def extract_requirements_tool(jd: str) -> dict:
        """Parse a job description into must-have vs nice-to-have requirements (does NOT change the active search)."""
        return extract_requirements(jd)

    @tool("compare_candidates")
    def compare_candidates_tool(candidate_ids: list[str]) -> str:
        """Head-to-head comparison of 2-4 candidates (IDs or names) against the current requirements."""
        return compare_candidates(candidate_ids, state)[0]

    @tool("generate_interview_questions")
    def generate_interview_questions_tool(candidate_id: str) -> str:
        """Create tailored screening/interview questions for one candidate (ID or name)."""
        return generate_interview_questions(candidate_id, state)[0]

    @tool
    def get_current_ranking() -> str:
        """The current final ranking of shortlisted candidates with scores and recommendations."""
        return ranking_text(state)

    @tool
    def get_candidate_assessment(candidate: str) -> dict:
        """Scores, must-have evidence, strengths, gaps, recommendation and improvement suggestions for a candidate."""
        ids = resolve_ids([candidate])
        if not ids:
            return {"error": f"Unknown candidate '{candidate}'"}
        cid = ids[0]
        r1 = _round1_entry(state, cid) or {}
        return {"round1": {k: r1.get(k) for k in ("round1_rank", "round1_score", "components", "must_have",
                                                  "nice_to_have", "flags", "total_years")},
                "final": _final_entry(state, cid), "deep_analysis": (state.get("deep_analysis") or {}).get(cid),
                "decision": (state.get("decisions") or {}).get(cid)}

    return [extract_requirements_tool, compare_candidates_tool, generate_interview_questions_tool,
            get_current_ranking, get_candidate_assessment]
