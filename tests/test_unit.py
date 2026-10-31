"""Offline tests (no LLM calls): parsing, skills, scoring, explanations, routing and graph structure."""

from matching_agent import _TOP_N, _WHY_RANK, INTENT_TO_NODE, build_graph, merge_trace
from talentscout.resume_store import load_profiles, resolve_candidate
from talentscout.scoring import (pairwise_breakdown, rank_round1, ranking_changes, requirements_diff,
                                 score_candidate, skill_match)
from talentscout.skills import find_skills, normalize_skill

REQ = {"role_title": "Senior Frontend Engineer", "min_years_experience": 5,
       "must_have": [{"skill": "React", "min_years": 3}, {"skill": "TypeScript", "min_years": None}],
       "nice_to_have": [{"skill": "AWS", "min_years": None}], "search_query": "react typescript"}


def test_skill_aliases_and_boundaries():
    assert find_skills("ReactJS, Golang, k8s, Postgres") >= {"React", "Go", "Kubernetes", "PostgreSQL"}
    assert "Java" not in find_skills("JavaScript only")
    assert "React" not in find_skills("React Native apps")
    assert normalize_skill("reactjs") == "React" and normalize_skill("K8s") == "Kubernetes"


def test_resume_pool_and_parsing():
    profiles = load_profiles()
    assert len(profiles) == 100
    john = profiles["C017"]
    assert john.name == "John Carter" and john.total_years >= 8
    assert john.skill_years["React"] > 7 and len(john.roles) == 3


def test_candidate_resolution():
    assert resolve_candidate("john").candidate_id == "C017"
    assert resolve_candidate("Jane Fernandes").candidate_id == "C042"
    assert resolve_candidate("c063").name == "Meera Iyer"


def test_skill_credit_listed_vs_demonstrated():
    profiles = load_profiles()
    vikram = profiles["C088"]  # lists React but never used it in a role
    m = skill_match(vikram, {"skill": "React", "min_years": 3})
    assert m["status"] == "listed_only" and m["credit"] == 0.4
    meera = profiles["C063"]  # React 1.7y < 3y
    m = skill_match(meera, {"skill": "React", "min_years": 3})
    assert m["status"] == "demonstrated" and 0.5 < m["credit"] < 1.0


def test_round1_ranking_is_explainable():
    profiles = load_profiles()
    semantic = {cid: 0.5 for cid in profiles}
    ranked = rank_round1(profiles, REQ, semantic)
    assert len(ranked) == 100 and ranked[0]["round1_rank"] == 1
    john = next(e for e in ranked if e["candidate_id"] == "C017")
    jane = next(e for e in ranked if e["candidate_id"] == "C042")
    assert john["round1_score"] > jane["round1_score"]
    assert any("TypeScript" in f for f in jane["flags"])
    rows = pairwise_breakdown(john, jane)
    assert rows[0]["component"] == "must-have coverage" and rows[0]["delta"] > 0


def test_requirements_diff_detects_moves():
    new = {**REQ, "must_have": REQ["must_have"] + [{"skill": "AWS", "min_years": None}], "nice_to_have": []}
    assert requirements_diff(REQ, new) == ["Moved AWS: nice-to-have → must-have"]


def test_ranking_changes():
    prev = [{"candidate_id": "A", "name": "A", "rank": 1, "components": {}}, {"candidate_id": "B", "name": "B", "rank": 2, "components": {}}]
    curr = [{"candidate_id": "B", "name": "B", "rank": 1}, {"candidate_id": "C", "name": "C", "rank": 2}]
    r1 = [{"candidate_id": x, "must_have": [], "components": {}, "round1_rank": i, "round1_score": 50}
          for i, x in enumerate("ABC", 1)]
    moves = {c["candidate_id"]: c["movement"] for c in ranking_changes(prev, curr, r1)}
    assert moves == {"B": "▲1", "C": "NEW", "A": "DROPPED"}


def test_router_regex_safety_nets():
    assert _WHY_RANK.search("Why did John rank higher than Jane?")
    assert _WHY_RANK.search("why isn't Priya shortlisted")
    assert _TOP_N.search("Compare the top 3 matches").group(1) == "3"


def test_trace_reducer_dedupes():
    a = [{"id": "1"}]
    assert merge_trace(a, [{"id": "1"}, {"id": "2"}]) == [{"id": "1"}, {"id": "2"}]


def test_graph_structure_matches_brief():
    g = build_graph().get_graph(xray=1)
    nodes = set(g.nodes)
    for n in ["parse_jd", "extract_requirements", "search_resumes", "generate_report", "human_feedback",
              "understand_request", "refine_requirements", "compare_candidates", "explain_ranking",
              "interview_questions", "answer_question", "finish"]:
        assert n in nodes, n
    assert any("round1_screen" in n for n in nodes) and any("round3_final_decision" in n for n in nodes)
    edges = {(e.source, e.target) for e in g.edges}
    assert ("__start__", "parse_jd") in edges and ("finish", "__end__") in edges
    assert ("refine_requirements", "search_resumes") in edges  # re-rank loop
    assert set(INTENT_TO_NODE.values()) <= nodes


def test_score_candidate_components_sum():
    p = load_profiles()["C017"]
    s = score_candidate(p, REQ, 1.0)
    assert s["components"]["must_have"] == 100.0 and 0 <= s["round1_score"] <= 100


def test_either_or_alternatives_take_best_match():
    from talentscout.scoring import skill_match
    john = load_profiles()["C017"]  # React, no Vue in roles
    m = skill_match(john, {"skill": "Vue.js", "alternatives": ["React"], "min_years": None})
    assert m["status"] == "demonstrated" and m["matched"] == "React" and m["skill"] == "Vue.js / React"


def test_generic_skills_become_experience_requirement():
    from talentscout.schemas import JobRequirements
    from talentscout.tools.agent_tools import _normalise_requirements
    req = JobRequirements(role_title="SRE", search_query="q", nice_to_have=[],
                          must_have=[{"skill": "DevOps", "min_years": 4}, {"skill": "AWS"},
                                     {"skill": "Django", "alternatives": ["fastapi"]}])
    d = _normalise_requirements(req)
    assert [m["skill"] for m in d["must_have"]] == ["AWS", "Django"]
    assert d["must_have"][1]["alternatives"] == ["FastAPI"] and d["min_years_experience"] == 4


def test_iac_matches_terraform():
    assert "Infrastructure as Code" in find_skills("Provisioned infra with Terraform")


def test_cross_category_alternatives_are_split():
    from talentscout.schemas import JobRequirements
    from talentscout.tools.agent_tools import _normalise_requirements
    req = JobRequirements(role_title="x", search_query="q", nice_to_have=[{"skill": "Kafka", "alternatives": ["message broker"]}],
                          must_have=[{"skill": "Python", "alternatives": ["Django", "FastAPI"]}])
    d = _normalise_requirements(req)
    assert [(m["skill"], m["alternatives"]) for m in d["must_have"]] == [("Python", []), ("Django", ["FastAPI"])]
    assert d["nice_to_have"][0]["alternatives"] == []


def test_pronoun_neutralizer():
    from talentscout.tools.agent_tools import neutralize_pronouns
    assert neutralize_pronouns("She has strong React; boosting his score") == "They have strong React; boosting their score"


def test_pronoun_neutralizer_verb_agreement():
    from talentscout.tools.agent_tools import neutralize_pronouns
    assert neutralize_pronouns("because she lacks AWS") == "because they lack AWS"
    assert neutralize_pronouns("He also leads; she can mentor") == "They also lead; they can mentor"


def test_pronoun_neutralizer_object_vs_possessive():
    from talentscout.tools.agent_tools import neutralize_pronouns
    assert neutralize_pronouns("caused her to fall; her React work") == "caused them to fall; their React work"
