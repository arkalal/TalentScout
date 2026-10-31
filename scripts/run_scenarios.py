"""Run the 6 documented conversation flows end-to-end and save transcripts.

    python scripts/run_scenarios.py            # all scenarios
    python scripts/run_scenarios.py 2 4        # selected scenarios

Writes docs/test_scenarios/<n>_<name>.md with every user turn, the agent's reasoning
trace (graph nodes visited) and the agent's replies.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from matching_agent import MatchingAgent  # noqa: E402

JD = {p.stem: p.read_text() for p in (ROOT / "data" / "jds").glob("*.md")}

SCENARIOS = [
    ("full_jd_multi_round_screening",
     "Paste a full JD → requirement extraction → RAG search over 100 resumes → 3-round screening → report → hire decision.",
     [JD["senior_frontend_engineer"],
      "Run the final round summary: who should we hire, who is borderline and what would borderline candidates need to improve?",
      "done"]),
    ("natural_language_query_compare_and_why",
     "Natural-language search, side-by-side comparison and a 'why did X rank higher than Y' explanation.",
     ["Find me candidates with React and 3+ years experience",
      "Compare the top 3 matches side by side",
      "Why did John rank higher than Jane?"]),
    ("iterative_refinement_reranking",
     "Requirements adjusted mid-conversation; the agent re-ranks and explains how and why the ranking changed.",
     [JD["backend_python_engineer"],
      "Make Kafka a must-have",
      "Actually relax the minimum experience to 2+ years and treat Docker as nice-to-have",
      "Why did the top candidate change?"]),
    ("explainability_borderline_interview",
     "Explainability: strengths/gaps, a non-shortlisted candidate explained, interview questions for a borderline candidate.",
     [JD["ml_engineer"],
      "Which candidates are borderline and what would they need to improve?",
      "Why isn't Vikram Malhotra shortlisted?",
      "Generate interview questions for the highest-ranked borderline candidate"]),
    ("tool_use_file_system_and_rag",
     "Free-form questions answered with file-system tools, RAG search and saved reports.",
     [JD["devops_sre"],
      "Which candidates in the whole pool hold a Kubernetes or Terraform certification? Check the resumes.",
      "Use semantic search: who has experience reducing alert noise or improving monitoring?",
      "Save a short summary of the top 3 candidates to a file called devops_top3"]),
    ("edge_cases_new_search_and_exit",
     "Non-hiring input, switching to a completely new search mid-conversation, and ending the session.",
     ["hello! what can you do?",
      "Find me data engineers with Spark and Airflow",
      "Now find me mobile developers with React Native instead",
      "Thanks, that's all"]),
]


def run(idx: int, name: str, description: str, turns: list[str]) -> Path:
    agent = MatchingAgent(thread_id=f"scenario-{idx}")
    out = [f"# Scenario {idx}: {name.replace('_', ' ').title()}", "", f"_{description}_", ""]
    for t_no, text in enumerate(turns, 1):
        shown = text if len(text) < 300 else f"(pasted job description — {len(text.split())} words)\n\n" + \
            "\n".join("> " + ln for ln in text.strip().splitlines())
        out += [f"## Turn {t_no}", "", f"**👤 Recruiter:** {shown}", ""]
        steps: list[str] = []

        def on_event(node: str, update: dict) -> None:
            for tr in (update.get("trace") or [])[-1:]:
                if tr["node"] == node:
                    steps.append(f"- `{node}` — {tr['summary']}")

        t0 = time.time()
        replies = agent.send(text, on_event=on_event)
        out += ["<details><summary>🧠 Agent reasoning trace (graph nodes)</summary>", "", *steps, "", "</details>", ""]
        for r in replies:
            out += ["**🎯 TalentScout:**", "", r, ""]
        out.append(f"_⏱ {time.time() - t0:.1f}s_\n")
        print(f"  turn {t_no}: {len(steps)} steps, {time.time() - t0:.1f}s")
    path = ROOT / "docs" / "test_scenarios" / f"{idx}_{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out), encoding="utf-8")
    return path


if __name__ == "__main__":
    wanted = {int(a) for a in sys.argv[1:]} or set(range(1, len(SCENARIOS) + 1))
    for i, (name, desc, turns) in enumerate(SCENARIOS, 1):
        if i in wanted:
            print(f"Scenario {i}: {name}")
            print(f"  -> {run(i, name, desc, turns).relative_to(ROOT)}")
