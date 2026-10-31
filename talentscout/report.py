"""Markdown rendering of match reports (full report + concise chat summary)."""

from __future__ import annotations

from datetime import datetime

from .config import MODEL_NAME, ROUND1_SHORTLIST, ROUND1_WEIGHTS
from .tools.agent_tools import requirements_brief, skill_label

BADGE = {"HIRE": "🟢 HIRE", "BORDERLINE": "🟡 BORDERLINE", "NO_HIRE": "🔴 NO HIRE"}


def _skill_status(m: dict) -> str:
    if m["status"] == "demonstrated":
        need = f" / need {m['min_years']:g}y" if m.get("min_years") else ""
        via = f" via {m['matched']}" if m.get("matched") else ""
        return f"✅ {m['skill']} ({m['years']:g}y{need}{via})"
    if m["status"] == "listed_only":
        return f"⚠️ {m['skill']} (listed only)"
    return f"❌ {m['skill']}"


def _must_summary(entry: dict) -> str:
    must = entry.get("must_have", [])
    got = sum(1 for m in must if m["status"] == "demonstrated" and (not m.get("min_years") or m["years"] >= m["min_years"]))
    return f"{got}/{len(must)}"


def ranking_table(final_ranking: list[dict], compact: bool = False) -> str:
    if compact:  # narrow version for the chat column; full detail lives in the report and the Shortlist tab
        rows = ["| # | Candidate | Final | Must-haves | Decision |", "|---|---|---|---|---|"]
        rows += [f"| {e['rank']} | {e['name']} | **{e['final_score']}** | {_must_summary(e)} | "
                 f"{BADGE.get(e.get('recommendation'), '—')} |" for e in final_ranking]
        return "\n".join(rows)
    rows = ["| # | Candidate | Final | R1 | Deep fit | Exp | Must-haves met | Recommendation |",
            "|---|---|---|---|---|---|---|---|"]
    for e in final_ranking:
        rows.append(f"| {e['rank']} | {e['name']} ({e['candidate_id']}) | **{e['final_score']}** | {e['round1_score']} | "
                    f"{e['deep_fit']} | {e['total_years']}y | {_must_summary(e)} | {BADGE.get(e.get('recommendation'), '—')} |")
    return "\n".join(rows)


def changes_section(state: dict) -> str:
    changes = state.get("ranking_changes") or []
    req_changes = state.get("requirement_changes") or []
    if not changes and not req_changes:
        return ""
    out = ["#### 🔄 What changed after your refinement"]
    out += [f"- {c}" for c in req_changes]
    if changes:
        out += ["", "| Candidate | Before | Now | Move | Why |", "|---|---|---|---|---|"]
        for c in changes:
            out.append(f"| {c['name']} ({c['candidate_id']}) | {c['old_rank'] or '—'} | {c['new_rank'] or 'out'} | "
                       f"{c['movement']} | {c['reason']} |")
    else:
        out.append("- The shortlist order did not change.")
    return "\n".join(out)


def funnel_line(state: dict) -> str:
    r1 = state.get("round1", [])
    fr = state.get("final_ranking", [])
    counts = {k: sum(1 for e in fr if e.get("recommendation") == k) for k in BADGE}
    cutoff = r1[min(ROUND1_SHORTLIST, len(r1)) - 1]["round1_score"] if r1 else 0
    return (f"**Funnel:** Round 1 screened **{len(r1)}** resumes → top **{len(fr)}** (cut-off score {cutoff}) → "
            f"Round 2 deep review of {len(fr)} → Round 3: {counts['HIRE']} hire · {counts['BORDERLINE']} borderline · "
            f"{counts['NO_HIRE']} no-hire")


def chat_summary(state: dict, report_path: str = "") -> str:
    req = state["requirements"]
    parts = [f"### {req.get('role_title', 'Role')} — shortlist",
             f"**Requirements (v{len(state.get('requirements_history', []))}):** {requirements_brief(req)}",
             funnel_line(state)]
    ch = changes_section(state)
    if ch:
        parts.append(ch)
    parts += [ranking_table(state["final_ranking"], compact=True), f"**Summary:** {state.get('overall_summary', '')}"]
    top = state["final_ranking"][:3]
    deep = state.get("deep_analysis", {})
    for e in top:
        d = deep.get(e["candidate_id"], {})
        strengths = "; ".join(s["point"].rstrip(".") for s in d.get("strengths", [])[:2])
        gaps = "; ".join(g.rstrip(".") for g in d.get("gaps", [])[:2]) or "none significant"
        parts.append(f"**{e['rank']}. {e['name']}** — {BADGE.get(e.get('recommendation'), '')} · "
                     f"✔ {strengths} · ✖ {gaps}")
    if report_path:
        parts.append(f"📄 Full match report saved to `{report_path}`.")
    parts.append("_Try: “Compare the top 3 side by side” · “Why did #1 rank higher than #2?” · "
                 "“Make AWS a must-have” · “Interview questions for #1”_")
    return "\n\n".join(parts)


def full_report(state: dict) -> str:
    req = state["requirements"]
    deep = state.get("deep_analysis", {})
    decisions = state.get("decisions", {})
    jd = state.get("jd_profile", {})
    w = ROUND1_WEIGHTS
    lines = [f"# Candidate Match Report — {req.get('role_title', 'Role')}",
             f"_Generated {datetime.now():%Y-%m-%d %H:%M} · TalentScout (LangGraph) · model `{MODEL_NAME}`_", "",
             "## Role understanding",
             f"- **Seniority:** {jd.get('seniority', 'n/a')} · **Domain:** {jd.get('domain') or 'n/a'}",
             f"- **Summary:** {jd.get('summary', '')}",
             f"- **Must-have:** " + (", ".join(skill_label(r) + (f" ({r['min_years']:g}+y)" if r.get('min_years') else "")
                                              for r in req.get("must_have", [])) or "—"),
             f"- **Nice-to-have:** " + (", ".join(skill_label(r) for r in req.get("nice_to_have", [])) or "—"),
             f"- **Min total experience:** " + (f"{req['min_years_experience']:g} years" if req.get("min_years_experience")
                                                else "not specified"),
             f"- **Other:** {'; '.join(req.get('other_requirements', [])) or '—'}", ""]
    ch = changes_section(state)
    if ch:
        lines += [ch, ""]
    lines += ["## Screening funnel", funnel_line(state), "", "## Executive summary", state.get("overall_summary", ""), "",
              "## Final ranking", ranking_table(state["final_ranking"]), "", "## Candidate details"]
    for e in state["final_ranking"]:
        cid = e["candidate_id"]
        d, dec = deep.get(cid, {}), decisions.get(cid, {})
        c = e["components"]
        lines += [f"### {e['rank']}. {e['name']} ({cid}) — {BADGE.get(e.get('recommendation'), '')} "
                  f"(confidence: {dec.get('confidence', 'n/a')}) — final {e['final_score']}",
                  f"*{e['headline']} · {e['total_years']} yrs total · {d.get('seniority_assessment', '')}*", "",
                  f"- **Score breakdown:** must-have {c['must_have']} ×{w['must_have']} · nice {c['nice_to_have']} ×{w['nice_to_have']} · "
                  f"experience {c['experience']} ×{w['experience']} · semantic {c['semantic']} ×{w['semantic']} → "
                  f"**Round 1 {e['round1_score']}** (rank #{e['round1_rank']}); deep fit **{e['deep_fit']}** → **final {e['final_score']}**",
                  "- **Must-haves:** " + " · ".join(_skill_status(m) for m in e.get("must_have", [])),
                  "- **Nice-to-haves:** " + (" · ".join(_skill_status(m) for m in e.get("nice_to_have", [])) or "—")]
        if d.get("strengths"):
            lines.append("- **Strengths:**")
            lines += [f"  - {s['point']} — _{s['evidence']}_" for s in d["strengths"]]
        if d.get("gaps"):
            lines.append("- **Gaps:** " + "; ".join(d["gaps"]))
        if d.get("risks"):
            lines.append("- **Risks:** " + "; ".join(d["risks"]))
        if dec.get("rationale"):
            lines.append(f"- **Decision rationale:** {dec['rationale']}")
        if dec.get("improvement_suggestions"):
            label = "Improvement suggestions (borderline)" if e.get("recommendation") == "BORDERLINE" else "Improvement suggestions"
            lines.append(f"- **{label}:**")
            lines += [f"  - {s}" for s in dec["improvement_suggestions"]]
        lines.append("")
    near = state.get("round1", [])[ROUND1_SHORTLIST:ROUND1_SHORTLIST + 5]
    if near:
        lines += ["## Near misses (Round 1 ranks just below the cut-off)",
                  "| R1 # | Candidate | R1 score | Why not shortlisted |", "|---|---|---|---|"]
        lines += [f"| {n['round1_rank']} | {n['name']} ({n['candidate_id']}) | {n['round1_score']} | "
                  f"{'; '.join(n['flags'][:3]) or 'lower semantic/nice-to-have scores'} |" for n in near]
        lines.append("")
    lines += ["## Methodology",
              f"1. **Round 1 (all resumes):** deterministic score = {int(w['must_have']*100)}% must-have coverage + "
              f"{int(w['nice_to_have']*100)}% nice-to-have + {int(w['experience']*100)}% experience fit + "
              f"{int(w['semantic']*100)}% semantic relevance (MiniLM embeddings + FAISS). Skills used in a described role "
              "get full credit (scaled by years when the JD asks for N+ years); skills only listed get 40%.",
              f"2. **Round 2 (top {ROUND1_SHORTLIST}):** LLM deep review of the full resume → fit score, evidence, strengths, gaps, risks. "
              "Final score = 40% Round 1 + 60% deep fit.",
              "3. **Round 3:** hiring-committee recommendation (HIRE / BORDERLINE / NO HIRE) with guardrails "
              "(a candidate missing a must-have can never be HIRE) and improvement suggestions for borderline candidates."]
    return "\n".join(lines)
