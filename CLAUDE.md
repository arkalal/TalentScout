# CLAUDE.md — TalentScout: LangGraph Resume–JD Matching Agent (Airtribe project)

Single source of truth for building this project. Keep the checklist and progress log current.

## Brief → deliverable map (all must be ✅ before submission)

| Brief item | Where it lives | Status |
|---|---|---|
| A. `matching_agent.py` using LangGraph | `matching_agent.py` | ✅ |
| A. State: conversation history | `AgentState.messages` (add_messages reducer) | ✅ |
| A. State: job requirements understanding | `AgentState.jd_profile`, `requirements`, `requirements_history` | ✅ |
| A. State: shortlist + reasoning | `round1`, `shortlist`, `deep_analysis`, `final_ranking`, `trace` | ✅ |
| A. Graph: START→Parse JD→Extract Req→Search→Rank→Report→Human Feedback→END | `build_graph()` in `matching_agent.py` | ✅ |
| A. File system tools (Milestone 1, rebuilt) | `talentscout/tools/fs_tools.py` | ✅ |
| A. RAG search tool (Milestone 2, rebuilt) | `talentscout/rag.py`, `rag_search` tool | ✅ |
| A. `extract_requirements(jd)` | `talentscout/tools/agent_tools.py` | ✅ |
| A. `compare_candidates(candidate_ids)` | `talentscout/tools/agent_tools.py` | ✅ |
| A. `generate_interview_questions(candidate_id)` | `talentscout/tools/agent_tools.py` | ✅ |
| B. Natural-language queries (find / compare / why) | `understand_request` router + action nodes | ✅ |
| B. Iterative refinement + re-rank + explain changes | `refine_requirements` → re-run pipeline, `ranking_changes` | ✅ |
| C. Multi-round screening (100→10→deep→hire/no-hire) | `rank_candidates` subgraph (3 round nodes) | ✅ |
| C. Explainability: reports, strengths/gaps, borderline suggestions | `generate_report`, `report.py` | ✅ |
| Submission: state machine diagram | `docs/state_machine.png` + `.mmd` (generated from compiled graph) | ✅ |
| Submission: chat interface | `app.py` (Streamlit) + `cli.py` | ✅ |
| Submission: 5+ conversation flow tests | `tests/test_flows.py` + `scripts/run_scenarios.py` → `docs/test_scenarios/` | ✅ |
| Submission: demo video (user records) | `docs/DEMO_SCRIPT.md` | ✅ |

## Key decisions
- LLM: OpenRouter via `langchain_openai.ChatOpenAI(base_url="https://openrouter.ai/api/v1")` (same pattern as the course notebooks). Default model `openai/gpt-4.1-mini` (env `TALENTSCOUT_MODEL`). Key has a **$3 limit** → keep calls lean, temperature 0.
- Embeddings: local `sentence-transformers/all-MiniLM-L6-v2` + FAISS, reranked by `cross-encoder/ms-marco-MiniLM-L-6-v2` (mirrors course Milestone-2 RAG notebook). No extra API key.
- Data: 100 synthetic resumes generated deterministically (`scripts/generate_resumes.py`, seed 42) — no LLM cost. Planted personas: John Carter vs Jane Fernandes for the "why did John rank higher than Jane?" demo.
- Scoring is hybrid and *numeric* so explanations are grounded: Round 1 = 45% must-have + 15% nice-to-have + 20% experience + 20% semantic (RAG). Round 2 LLM deep fit; final = 40% R1 + 60% deep fit. Round 3 = hire / borderline / no-hire.
- Human-in-the-loop via `langgraph.types.interrupt()` + `InMemorySaver`; resume with `Command(resume=text)`. `interrupt()` re-runs the node on resume → human_feedback node contains only the interrupt; routing LLM call lives in `understand_request`.
- Python 3.10 (only version on this machine). Venv at `.venv`.
- User does all git/GitHub operations — never run git commands.

## Commands
```bash
source .venv/bin/activate
python scripts/generate_resumes.py      # writes data/resumes/*.md (100)
python scripts/build_index.py           # builds vector_store/ (FAISS)
streamlit run app.py                    # chat UI
python cli.py                           # CLI chat
python scripts/draw_graph.py            # docs/state_machine.{png,mmd}
pytest -q                               # unit + offline tests
pytest -q -m llm                        # live conversation-flow tests (uses OpenRouter credit)
python scripts/run_scenarios.py         # writes transcripts to docs/test_scenarios/
```

## Progress log
- 2026-10-31: Plan approved. Course notebooks checked (no Milestone 1/2 code; they show the OpenRouter+LangGraph and MiniLM+FAISS+cross-encoder stack). Building from scratch.
- 2026-10-31: All code built: resumes (100), parser, RAG index (762 chunks), scoring, tools, graph (13 nodes + 3-node rank subgraph), report, Streamlit UI, CLI, diagrams, README, DEMO_SCRIPT.
- 2026-10-31: Hardening from live runs:
  - Router: deterministic override — any "why … rank/shortlist" → explain_ranking (LLM once sent it to Q&A, which confused Jane with Meera). Q&A prompt now carries the ID=name directory.
  - Extraction: generic "skills" (Software Engineering, DevOps, SRE…) are converted to min_years_experience / other_requirements; "X or Y" is ONE requirement with `alternatives` (Django / FastAPI), scored by best option. Added "Infrastructure as Code" to the taxonomy.
  - Round 3 guardrail (missing must-have ≠ HIRE) is now mentioned in the overall summary so the summary never contradicts the table.
  - Explainer receives weighted points as "earned / max" plus Round-3 rationale and suggestions; with no IDs it covers the whole shortlist.
  - pytest pinned <9 (9.2 INTERNALERROR with the langsmith plugin).
  - UI: sticky right panel, default JD = Senior Frontend Engineer, toolbar hidden (.streamlit/config.toml).

- 2026-10-31: UI pass after user screenshots: compact chat table (full table in report/Shortlist), columns min-width:0 +
  scrollable tables (no overlap), scaled chat headings, reasoning steps as cards, wrapping JSON, non-breaking requirement
  chips, HTML shortlist table (st.dataframe clipped columns), turns run in place under the conversation, wrapping buttons.
  Verified at 1440 and 1280 px: 0 px overflow in both columns.
- 2026-10-31: Fairness: FAIRNESS rule in every candidate-facing prompt + deterministic `neutralize_pronouns` safety net.
- 2026-10-31: UI pass 2: top padding 4.2rem (first message was hidden under the fixed header), Streamlit skills-promo
  toast hidden, example searches stay until a search exists, report headings scaled in side panel, summary-style
  questions get whole-shortlist answers (pairwise table only for "why X vs Y"), pronoun safety net handles verb
  agreement + her→them/their. Full end-to-end click-through at 1440 and 1280 px: 0 px overflow, nothing cut off.
- Final state: 18 offline tests + 6 live flow tests pass; 6 scenario transcripts in docs/test_scenarios/.

## Gotchas
- `interrupt()` re-runs its node on resume → keep human_feedback minimal.
- Subgraph returns the full inherited state → `trace` uses the id-deduplicating `merge_trace` reducer, not operator.add.
- numpy matmul on macOS Accelerate emits spurious RuntimeWarnings → wrapped in np.errstate.
- Streamlit only re-reads `.streamlit/config.toml` on restart, and `st.cache_resource` keeps the compiled graph → restart the server after changing agent code.
