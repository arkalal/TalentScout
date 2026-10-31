"""Live conversation-flow tests (call the LLM through OpenRouter).

    pytest -m llm -v

Two sessions are shared across tests to keep cost low (~$0.05 per full run).
"""

from pathlib import Path

import pytest

from matching_agent import MatchingAgent

pytestmark = pytest.mark.llm
ROOT = Path(__file__).resolve().parents[1]


def last_route(agent):
    return agent.state["route"]


@pytest.fixture(scope="module")
def jd_session():
    agent = MatchingAgent(thread_id="test-jd")
    replies = agent.send((ROOT / "data/jds/senior_frontend_engineer.md").read_text())
    return agent, replies


@pytest.fixture(scope="module")
def query_session():
    return MatchingAgent(thread_id="test-query")


# Flow 1 — JD → requirements → search → 3-round ranking → report → waiting for human feedback
def test_flow1_full_pipeline_and_multi_round(jd_session):
    agent, replies = jd_session
    s = agent.state
    must = {r["skill"] for r in s["requirements"]["must_have"]}
    assert {"React", "TypeScript"} <= must
    assert len(s["round1"]) == 100                          # round 1 scored all resumes
    assert len(s["final_ranking"]) == 10                    # top 10 to round 2
    assert set(s["deep_analysis"]) >= set(s["shortlist"])  # deep analysis of all 10
    assert all(e["recommendation"] in {"HIRE", "BORDERLINE", "NO_HIRE"} for e in s["final_ranking"])
    assert s["final_ranking"][0]["candidate_id"] == "C017"  # John Carter is the planted best fit
    assert (ROOT / s["report_path"]).exists() and "## Candidate details" in s["report"]
    assert "shortlist" in replies[-1] and agent.waiting_for_user
    # explainability: every borderline candidate gets improvement suggestions
    for e in s["final_ranking"]:
        if e["recommendation"] == "BORDERLINE":
            assert s["decisions"][e["candidate_id"]]["improvement_suggestions"]


# Flow 2 — "Compare the top 3 matches side by side"
def test_flow2_compare_top3(jd_session):
    agent, _ = jd_session
    reply = agent.send("Compare the top 3 matches side by side")[-1]
    top3 = [e["candidate_id"] for e in agent.state["final_ranking"][:3]]
    assert last_route(agent)["intent"] == "compare"
    assert last_route(agent)["candidate_ids"] == top3
    assert "Head-to-head" in reply and all(cid in reply for cid in top3)


# Flow 3 — "Why did John rank higher than Jane?" (Jane is outside the shortlist)
def test_flow3_explain_john_vs_jane(jd_session):
    agent, _ = jd_session
    reply = agent.send("Why did John rank higher than Jane?")[-1]
    assert last_route(agent)["intent"] == "explain_ranking"
    assert last_route(agent)["candidate_ids"][:2] == ["C017", "C042"]
    assert "John" in reply and "Jane" in reply and "must-have" in reply.lower()


# Flow 4 — iterative refinement: adjust requirements mid-conversation, re-rank, explain changes
def test_flow4_refine_and_rerank(jd_session):
    agent, _ = jd_session
    before = [e["candidate_id"] for e in agent.state["final_ranking"]]
    reply = agent.send("Make AWS a must-have and drop the Jest requirement")[-1]
    s = agent.state
    must = {r["skill"] for r in s["requirements"]["must_have"]}
    assert "AWS" in must and "Jest" not in must
    assert len(s["requirements_history"]) == 2
    assert s["ranking_changes"], "re-ranking should move candidates"
    assert [e["candidate_id"] for e in s["final_ranking"]] != before
    assert "What changed" in reply


# Flow 5 — interview questions + tool-using Q&A over resumes
def test_flow5_interview_questions_and_tool_qa(jd_session):
    agent, _ = jd_session
    reply = agent.send("Generate interview questions for Meera")[-1]
    assert last_route(agent)["intent"] == "interview_questions" and "Meera Iyer" in reply
    reply = agent.send("Which shortlisted candidates have mentored engineers? Check the resumes.")[-1]
    qa_trace = [t for t in agent.state["trace"] if t["node"] == "answer_question"][-1]
    assert qa_trace["details"]["tool_calls"], "Q&A should use tools"
    assert "C0" in reply or "C1" in reply


# Flow 6 — natural-language search from scratch, non-hiring input, new search and ending
def test_flow6_nl_query_new_search_and_end(query_session):
    agent = query_session
    reply = agent.send("hello there")[-1]
    assert "job description" in reply.lower() and agent.waiting_for_user
    agent.send("Find me candidates with React and 3+ years experience")
    s = agent.state
    react = next(r for r in s["requirements"]["must_have"] if r["skill"] == "React")
    assert react["min_years"] == 3
    for e in s["final_ranking"]:
        m = next(m for m in e["must_have"] if m["skill"] == "React")
        assert m["status"] == "demonstrated"
    agent.send("Now find me data engineers with Spark and Airflow instead")
    assert last_route(agent)["intent"] == "new_search"
    assert {"Spark", "Airflow"} <= {r["skill"] for r in agent.state["requirements"]["must_have"]}
    reply = agent.send("That's all, thanks!")[-1]
    assert last_route(agent)["intent"] == "end" and not agent.waiting_for_user and "Session closed" in reply
