"""TalentScout — a LangGraph resume ⇄ job-description matching agent.

Graph (see docs/state_machine.png):

    START → parse_jd → extract_requirements → search_resumes → rank_candidates ─┐
                                   ▲                (subgraph: round1_screen →   │
                                   │                 round2_deep_analysis →      │
                       refine_requirements           round3_final_decision)      │
                                   ▲                                             ▼
                                   │                                     generate_report
                                   │                                             │
          compare_candidates ◄─┐   │                                             ▼
          explain_ranking   ◄──┼── understand_request ◄──────────────── human_feedback (interrupt)
          interview_questions ◄┤      │      │                                   ▲
          answer_question (ReAct) ◄┘  │      └─ new_search → parse_jd            │
                 └──────────────── all action nodes loop back ───────────────────┘
                                      └─ end → finish → END

Run the chat UI with ``streamlit run app.py`` or the CLI with ``python cli.py``.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from typing import Annotated, Any, Callable, Optional

from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Command, interrupt
from typing_extensions import TypedDict

from talentscout import prompts
from talentscout.config import REPORT_DIR, ROUND1_SHORTLIST, get_llm
from talentscout.rag import get_index
from talentscout.report import chat_summary, full_report
from talentscout.resume_store import load_profiles
from talentscout.schemas import JDProfile, RequirementUpdate, RouterDecision
from talentscout.scoring import (
    final_score,
    rank_round1,
    ranking_changes,
    requirements_diff,
)
from talentscout.tools.agent_tools import (
    _normalise_requirements,
    candidate_directory,
    compare_candidates,
    deep_analyze_many,
    explain_ranking,
    extract_requirements,
    final_decisions,
    generate_interview_questions,
    neutralize_pronouns,
    ranking_text,
    requirements_brief,
    resolve_ids,
    skill_label,
    structured,
)
from talentscout.tools.fs_tools import FS_TOOLS, RAG_TOOLS
from talentscout.tools.agent_tools import make_state_tools


# =============================================================== Agent state
def merge_trace(left: list[dict] | None, right: list[dict] | None) -> list[dict]:
    """Append-only reducer that de-duplicates by id (a subgraph returns the full trace it inherited)."""
    left, right = left or [], right or []
    seen = {t["id"] for t in left}
    return left + [t for t in right if t["id"] not in seen]


class AgentState(TypedDict, total=False):
    # conversation history
    messages: Annotated[list[AnyMessage], add_messages]
    turn: int
    # job requirements understanding
    job_description: str
    jd_profile: dict  # Parse JD output (role, seniority, domain, ...)
    requirements: dict  # must-have / nice-to-have / min years / search query
    requirements_history: list[dict]  # every version with the change that produced it
    requirement_changes: list[str]  # diff applied by the latest refinement
    # retrieval + multi-round screening
    search_results: (
        dict  # semantic scores for all resumes, keyword coverage, top RAG hits
    )
    round1: list[dict]  # Round 1: every candidate scored + ranked
    shortlist: list[str]  # Round 1 top-N IDs
    deep_analysis: dict[str, dict]  # Round 2: per-candidate LLM deep review
    decisions: dict[str, dict]  # Round 3: hire / borderline / no-hire
    final_ranking: list[dict]  # shortlist ranked by final score, with reasoning fields
    overall_summary: str
    # refinement / explainability
    previous_ranking: list[dict]
    ranking_changes: list[dict]
    report: str
    report_path: str
    route: dict  # latest router decision
    trace: Annotated[list[dict], merge_trace]  # agent reasoning steps (shown in the UI)


def _trace(state: AgentState, node: str, summary: str, **details: Any) -> list[dict]:
    return [
        {
            "id": uuid.uuid4().hex,
            "turn": state.get("turn", 0),
            "node": node,
            "summary": summary,
            "details": details,
            "time": datetime.now().strftime("%H:%M:%S"),
        }
    ]


def _last_human(state: AgentState) -> str:
    for m in reversed(state.get("messages", [])):
        if isinstance(m, HumanMessage):
            return m.content
    return ""


def _recent_dialogue(
    state: AgentState, n: int = 6, max_chars: int = 1200
) -> list[AnyMessage]:
    out: list[AnyMessage] = []
    for m in state.get("messages", [])[-n:]:
        text = m.content if isinstance(m.content, str) else str(m.content)
        text = text if len(text) <= max_chars else text[:max_chars] + " …[truncated]"
        out.append(
            HumanMessage(text) if isinstance(m, HumanMessage) else AIMessage(text)
        )
    return out


# =============================================================== Pipeline nodes
def parse_jd(state: AgentState) -> dict:
    jd = state.get("job_description") or _last_human(state)
    profile: JDProfile = structured(JDProfile, prompts.PARSE_JD, jd)
    update: dict = {
        "job_description": jd,
        "jd_profile": profile.model_dump(),
        "trace": _trace(
            state,
            "parse_jd",
            f"Parsed input as {profile.input_type}: {profile.role_title} "
            f"({profile.seniority})",
            jd_summary=profile.summary,
        ),
    }
    if not profile.is_hiring_request:
        update["messages"] = [
            AIMessage(
                "I'm TalentScout, a recruiting agent. Paste a job description or ask something like "
                "*“Find me candidates with React and 3+ years experience”* and I'll screen all "
                f"{len(load_profiles())} resumes for you."
            )
        ]
    return update


def after_parse(state: AgentState) -> str:
    return (
        "hiring_request"
        if state["jd_profile"]["is_hiring_request"]
        else "not_a_hiring_request"
    )


def extract_requirements_node(state: AgentState) -> dict:
    req = extract_requirements(state["job_description"])
    generic = {"", "unknown", "n/a", "software engineer", "candidate", "engineer"}
    if req.get("role_title", "").lower() in generic:
        req["role_title"] = state["jd_profile"]["role_title"]
    if req["role_title"].lower() in generic and req.get(
        "must_have"
    ):  # short search: name the role by its skills
        req["role_title"] = (
            " / ".join(r["skill"] for r in req["must_have"][:2]) + " Developer"
        )
    history = [
        {
            "version": 1,
            "requirements": req,
            "change": "Initial extraction from the job description",
        }
    ]
    return {
        "requirements": req,
        "requirements_history": history,
        "requirement_changes": [],
        "previous_ranking": [],
        "ranking_changes": [],
        "trace": _trace(
            state, "extract_requirements", requirements_brief(req), requirements=req
        ),
    }


def search_resumes(state: AgentState) -> dict:
    req = state["requirements"]
    profiles = load_profiles()
    index = get_index()
    semantic = index.candidate_similarity(req["search_query"])
    coverage = {}
    for r in req.get("must_have", []) + req.get("nice_to_have", []):
        opts = [r["skill"]] + list(r.get("alternatives") or [])
        coverage[skill_label(r)] = {
            "demonstrated": sum(
                1 for p in profiles.values() if any(s in p.skill_years for s in opts)
            ),
            "mentioned": sum(
                1 for p in profiles.values() if any(s in p.skills for s in opts)
            ),
        }
    top_hits = [h.to_dict() for h in index.search(req["search_query"], k=5)]
    summary = (
        f"RAG-scored all {len(profiles)} resumes ({len(index.chunks)} chunks). Must-have coverage: "
        + ", ".join(
            f"{s} {c['demonstrated']}"
            for s, c in coverage.items()
            if s in {skill_label(m) for m in req.get("must_have", [])}
        )
    )
    return {
        "search_results": {
            "semantic": semantic,
            "coverage": coverage,
            "top_hits": top_hits,
        },
        "trace": _trace(
            state,
            "search_resumes",
            summary,
            top_rag_hits=[
                f"{h['name']} ({h['candidate_id']}) · {h['section']}" for h in top_hits
            ],
        ),
    }


# ------------------------------------------------------- rank_candidates subgraph (multi-round screening)
def round1_screen(state: AgentState) -> dict:
    ranked = rank_round1(
        load_profiles(), state["requirements"], state["search_results"]["semantic"]
    )
    shortlist = [e["candidate_id"] for e in ranked[:ROUND1_SHORTLIST]]
    knocked = sum(
        1 for e in ranked if any(f.startswith("Missing must-have") for f in e["flags"])
    )
    summary = (
        f"Round 1: scored {len(ranked)} resumes → top {len(shortlist)} "
        f"(cut-off {ranked[len(shortlist) - 1]['round1_score']}); {knocked} miss ≥1 must-have"
    )
    return {
        "round1": ranked,
        "shortlist": shortlist,
        "trace": _trace(
            state,
            "round1_screen",
            summary,
            top10=[
                f"{e['name']} {e['round1_score']}" for e in ranked[:ROUND1_SHORTLIST]
            ],
        ),
    }


def round2_deep_analysis(state: AgentState) -> dict:
    entries = state["round1"][:ROUND1_SHORTLIST]
    deep = deep_analyze_many(entries, state["requirements"])
    final = []
    for e in entries:
        fit = deep[e["candidate_id"]]["fit_score"]
        final.append(
            {**e, "deep_fit": fit, "final_score": final_score(e["round1_score"], fit)}
        )
    final.sort(key=lambda x: (-x["final_score"], x["round1_rank"]))
    for i, e in enumerate(final, 1):
        e["rank"] = i
    moved = [
        f"{e['name']} R1#{e['round1_rank']}→#{e['rank']}"
        for e in final
        if e["round1_rank"] != e["rank"]
    ]
    return {
        "deep_analysis": {**(state.get("deep_analysis") or {}), **deep},
        "final_ranking": final,
        "trace": _trace(
            state,
            "round2_deep_analysis",
            f"Round 2: LLM deep review of {len(final)} resumes; re-ranked by 40% R1 + 60% deep fit",
            reorder=moved or ["order unchanged"],
        ),
    }


def round3_final_decision(state: AgentState) -> dict:
    result = final_decisions(
        state["final_ranking"], state["deep_analysis"], state["requirements"]
    )
    final = [
        {
            **e,
            "recommendation": result["decisions"][e["candidate_id"]]["recommendation"],
        }
        for e in state["final_ranking"]
    ]
    counts = {
        k: sum(1 for e in final if e["recommendation"] == k)
        for k in ("HIRE", "BORDERLINE", "NO_HIRE")
    }
    return {
        "final_ranking": final,
        "decisions": result["decisions"],
        "overall_summary": result["overall_summary"],
        "trace": _trace(
            state,
            "round3_final_decision",
            f"Round 3: {counts['HIRE']} hire · {counts['BORDERLINE']} borderline · {counts['NO_HIRE']} no-hire",
        ),
    }


def build_rank_subgraph():
    g = StateGraph(AgentState)
    g.add_node("round1_screen", round1_screen)
    g.add_node("round2_deep_analysis", round2_deep_analysis)
    g.add_node("round3_final_decision", round3_final_decision)
    g.add_edge(START, "round1_screen")
    g.add_edge("round1_screen", "round2_deep_analysis")
    g.add_edge("round2_deep_analysis", "round3_final_decision")
    g.add_edge("round3_final_decision", END)
    return g.compile()


def generate_report(state: AgentState) -> dict:
    changes = (
        ranking_changes(
            state["previous_ranking"], state["final_ranking"], state["round1"]
        )
        if state.get("previous_ranking")
        else []
    )
    view = {**state, "ranking_changes": changes}
    report = full_report(view)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    slug = re.sub(
        r"[^a-z0-9]+", "_", state["requirements"].get("role_title", "role").lower()
    ).strip("_")
    path = (
        REPORT_DIR
        / f"{slug}_v{len(state.get('requirements_history', []))}_{datetime.now():%Y%m%d_%H%M%S}.md"
    )
    path.write_text(report, encoding="utf-8")
    rel = str(path.relative_to(REPORT_DIR.parent))
    return {
        "report": report,
        "report_path": rel,
        "ranking_changes": changes,
        "previous_ranking": [],
        "messages": [AIMessage(chat_summary(view, rel))],
        "trace": _trace(
            state,
            "generate_report",
            f"Match report generated ({len(changes)} ranking changes)",
            path=rel,
        ),
    }


# =============================================================== Human-in-the-loop
def human_feedback(state: AgentState) -> dict:
    # NOTE: interrupt() re-runs this node on resume, so it contains nothing but the interrupt.
    user_input = interrupt(
        {
            "type": "awaiting_recruiter",
            "prompt": "Refine requirements, compare candidates, ask why, request interview "
            "questions — or say 'done'.",
        }
    )
    return {
        "messages": [HumanMessage(str(user_input))],
        "turn": state.get("turn", 0) + 1,
    }


_TOP_N = re.compile(r"\btop\s*(\d+|three|two|five|four)\b", re.IGNORECASE)
_WHY_RANK = re.compile(
    r"\bwhy\b.*\b(rank|ranked|higher|lower|above|below|ahead|behind|better|shortlist|shortlisted|"
    r"top|first|last|not|over|beat|outrank)",
    re.IGNORECASE,
)
_WORDS = {"two": 2, "three": 3, "four": 4, "five": 5}


def understand_request(state: AgentState) -> dict:
    text = _last_human(state)
    has_ranking = bool(state.get("final_ranking"))
    system = prompts.ROUTER.format(
        role=(state.get("requirements") or {}).get("role_title", "(none yet)"),
        requirements=(
            requirements_brief(state["requirements"])
            if state.get("requirements")
            else "(none yet)"
        ),
        ranking=ranking_text(state) if has_ranking else "(nothing screened yet)",
    )
    system += f"\n\nFull candidate directory: {candidate_directory()}"
    decision: RouterDecision = (
        get_llm()
        .with_structured_output(RouterDecision)
        .invoke(
            [SystemMessage(system)]
            + _recent_dialogue(state, n=4)
            + [HumanMessage(f"LATEST MESSAGE: {text}")]
        )
    )
    route = decision.model_dump()
    route["candidate_ids"] = resolve_ids(route["candidate_ids"])
    # deterministic safety net for "top N"
    m = _TOP_N.search(text)
    if (
        has_ranking
        and m
        and route["intent"] in {"compare", "explain_ranking"}
        and len(route["candidate_ids"]) < 2
    ):
        n = int(m.group(1)) if m.group(1).isdigit() else _WORDS[m.group(1).lower()]
        route["candidate_ids"] = [e["candidate_id"] for e in state["final_ranking"][:n]]
    if (
        has_ranking
        and _WHY_RANK.search(text)
        and route["intent"] in {"question", "compare"}
    ):
        route["intent"] = (
            "explain_ranking"  # 'why did X rank above Y' must use the grounded explainer
        )
    if not has_ranking and route["intent"] not in {"end", "new_search"}:
        route["intent"] = "new_search"
    update: dict = {
        "route": route,
        "trace": _trace(
            state,
            "understand_request",
            f"Intent: {route['intent']} — {route['reasoning']}",
            candidates=route["candidate_ids"],
            instruction=route["instruction"],
        ),
    }
    if route["intent"] == "new_search":
        update["job_description"] = text
    return update


INTENT_TO_NODE = {
    "refine_requirements": "refine_requirements",
    "new_search": "parse_jd",
    "compare": "compare_candidates",
    "explain_ranking": "explain_ranking",
    "interview_questions": "interview_questions",
    "question": "answer_question",
    "end": "finish",
}


def route_request(state: AgentState) -> str:
    return state["route"]["intent"]


# =============================================================== Action nodes
def refine_requirements(state: AgentState) -> dict:
    old = state["requirements"]
    upd: RequirementUpdate = structured(
        RequirementUpdate,
        prompts.REFINE_REQUIREMENTS,
        f"CURRENT REQUIREMENTS:\n{json.dumps(old, indent=1)}\n\nRECRUITER INSTRUCTION: {state['route']['instruction']}"
        f"\n(original message: {_last_human(state)})",
    )
    new = _normalise_requirements(upd.updated)
    new["role_title"] = new.get("role_title") or old.get("role_title")
    diff = requirements_diff(old, new) or [upd.change_summary]
    history = list(state.get("requirements_history", [])) + [
        {
            "version": len(state.get("requirements_history", [])) + 1,
            "requirements": new,
            "change": upd.change_summary,
        }
    ]
    return {
        "requirements": new,
        "requirements_history": history,
        "requirement_changes": diff,
        "previous_ranking": state.get("final_ranking", []),
        "trace": _trace(
            state,
            "refine_requirements",
            "; ".join(diff),
            change_summary=upd.change_summary,
        ),
    }


def compare_candidates_node(state: AgentState) -> dict:
    ids = state["route"]["candidate_ids"] or [
        e["candidate_id"] for e in state["final_ranking"][:3]
    ]
    md, deep = compare_candidates(ids, state)
    return {
        "messages": [AIMessage(md)],
        "deep_analysis": deep or state.get("deep_analysis", {}),
        "trace": _trace(state, "compare_candidates", f"Compared {', '.join(ids)}"),
    }


def explain_ranking_node(state: AgentState) -> dict:
    text = _last_human(state)
    # "why did X rank above Y" -> focused (pairwise) explanation; summary questions -> whole shortlist
    ids = state["route"]["candidate_ids"] if _WHY_RANK.search(text) else []
    md = explain_ranking(ids, text, state)
    return {
        "messages": [AIMessage(md)],
        "trace": _trace(
            state,
            "explain_ranking",
            f"Explained ranking for {', '.join(ids) or 'overall method'}",
        ),
    }


def interview_questions_node(state: AgentState) -> dict:
    ids = state["route"]["candidate_ids"] or [state["final_ranking"][0]["candidate_id"]]
    md, deep = generate_interview_questions(ids[0], state)
    return {
        "messages": [AIMessage(md)],
        "deep_analysis": deep or state.get("deep_analysis", {}),
        "trace": _trace(
            state, "interview_questions", f"Generated screening questions for {ids[0]}"
        ),
    }


def answer_question(state: AgentState) -> dict:
    """Free-form Q&A: a small ReAct loop over file-system, RAG and agent tools."""
    tools = FS_TOOLS + RAG_TOOLS + make_state_tools(state)
    by_name = {t.name: t for t in tools}
    llm = get_llm().bind_tools(tools)
    system = prompts.QA.format(
        role=state["requirements"].get("role_title"),
        requirements=requirements_brief(state["requirements"]),
        ranking=ranking_text(state),
    )
    system += f"\n\nCandidate directory (ID=name) — map names to IDs exactly, never substitute another person:\n{candidate_directory()}"
    msgs: list[AnyMessage] = [SystemMessage(system)] + _recent_dialogue(state)
    calls: list[str] = []
    answer = ""
    for _ in range(6):
        ai = llm.invoke(msgs)
        msgs.append(ai)
        if not ai.tool_calls:
            answer = ai.content
            break
        for call in ai.tool_calls:
            calls.append(f"{call['name']}({json.dumps(call['args'])[:80]})")
            try:
                result = by_name[call["name"]].invoke(call["args"])
            except (
                Exception
            ) as exc:  # surface tool errors to the model instead of crashing the graph
                result = f"Tool error: {exc}"
            content = (
                result if isinstance(result, str) else json.dumps(result, default=str)
            )
            msgs.append(ToolMessage(content=content[:8000], tool_call_id=call["id"]))
    if not answer:
        answer = (
            get_llm()
            .invoke(msgs + [HumanMessage("Answer now using the information gathered.")])
            .content
        )
    return {
        "messages": [AIMessage(neutralize_pronouns(answer))],
        "trace": _trace(
            state,
            "answer_question",
            f"ReAct answer using {len(calls)} tool call(s)",
            tool_calls=calls,
        ),
    }


def finish(state: AgentState) -> dict:
    fr = state.get("final_ranking") or []
    hires = [
        f"{e['name']} ({e['candidate_id']})"
        for e in fr
        if e.get("recommendation") == "HIRE"
    ]
    msg = "Session closed. "
    if fr:
        msg += (
            f"Recommended to advance: {', '.join(hires) or 'none'}. "
            f"The full report is at `{state.get('report_path', '')}`."
        )
    return {
        "messages": [AIMessage(msg + " Good luck with the hiring! 👋")],
        "trace": _trace(state, "finish", "Conversation ended by recruiter"),
    }


# =============================================================== Graph
def build_graph(checkpointer=None):
    g = StateGraph(AgentState)
    g.add_node("parse_jd", parse_jd)
    g.add_node("extract_requirements", extract_requirements_node)
    g.add_node("search_resumes", search_resumes)
    g.add_node("rank_candidates", build_rank_subgraph())
    g.add_node("generate_report", generate_report)
    g.add_node("human_feedback", human_feedback)
    g.add_node("understand_request", understand_request)
    g.add_node("refine_requirements", refine_requirements)
    g.add_node("compare_candidates", compare_candidates_node)
    g.add_node("explain_ranking", explain_ranking_node)
    g.add_node("interview_questions", interview_questions_node)
    g.add_node("answer_question", answer_question)
    g.add_node("finish", finish)

    g.add_edge(START, "parse_jd")
    g.add_conditional_edges(
        "parse_jd",
        after_parse,
        {
            "hiring_request": "extract_requirements",
            "not_a_hiring_request": "human_feedback",
        },
    )
    g.add_edge("extract_requirements", "search_resumes")
    g.add_edge("search_resumes", "rank_candidates")
    g.add_edge("rank_candidates", "generate_report")
    g.add_edge("generate_report", "human_feedback")
    g.add_edge("human_feedback", "understand_request")
    g.add_conditional_edges("understand_request", route_request, INTENT_TO_NODE)
    g.add_edge("refine_requirements", "search_resumes")  # re-rank with the new criteria
    for node in (
        "compare_candidates",
        "explain_ranking",
        "interview_questions",
        "answer_question",
    ):
        g.add_edge(node, "human_feedback")
    g.add_edge("finish", END)
    return g.compile(checkpointer=checkpointer or InMemorySaver())


# =============================================================== Session wrapper (used by UI, CLI, tests)
class MatchingAgent:
    """Thin conversational wrapper: first message starts the graph, later ones resume the interrupt."""

    def __init__(self, thread_id: Optional[str] = None, graph=None):
        self.graph = graph or build_graph()
        self.thread_id = thread_id or uuid.uuid4().hex[:8]
        self.config = {
            "configurable": {"thread_id": self.thread_id},
            "recursion_limit": 60,
        }

    @property
    def state(self) -> dict:
        return self.graph.get_state(self.config).values

    @property
    def waiting_for_user(self) -> bool:
        return bool(self.graph.get_state(self.config).next)

    def send(
        self, text: str, on_event: Callable[[str, dict], None] | None = None
    ) -> list[str]:
        """Send a recruiter message; returns the agent's new reply/replies."""
        before = len(self.state.get("messages", []))
        if self.waiting_for_user:
            payload: Any = Command(resume=text)
        else:  # fresh conversation (or a new one after 'done')
            payload = {
                "messages": [HumanMessage(text)],
                "job_description": text,
                "turn": self.state.get("turn", 0) + 1,
            }
            before += 1
        for namespace, chunk in self.graph.stream(
            payload, self.config, stream_mode="updates", subgraphs=True
        ):
            for node, update in chunk.items():
                if on_event and node != "__interrupt__":
                    on_event(node, update or {})
        msgs = self.state.get("messages", [])[before:]
        return [m.content for m in msgs if isinstance(m, AIMessage)]


if __name__ == "__main__":  # quick smoke run
    agent = MatchingAgent()
    for reply in agent.send(
        "Find me candidates with React and 3+ years experience",
        on_event=lambda n, u: print(
            f"  ▸ {n}: {(u.get('trace') or [{}])[-1].get('summary', '')}"
        ),
    ):
        print(reply)
