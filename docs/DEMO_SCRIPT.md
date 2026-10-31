# Demo video script (5–6 minutes)

**Setup before recording**

- `source .venv/bin/activate && streamlit run app.py` → open http://localhost:8501. Click **New conversation**.
- Warm up once: run any search and then click **New conversation**, so the embedding model is already loaded.
- Have `docs/architecture.png` and `matching_agent.py` open in your editor.
- Screen-record at 1080p with the browser at about 90% zoom so the chat and the right panel both fit.

---

### 0:00 – 0:40 · Intro and architecture

**Show:** `docs/architecture.png`

> "This is TalentScout, a resume-matching agent built with LangGraph. The graph follows the brief: Parse JD,
> Extract Requirements, Search Resumes, Rank Candidates, Generate Report, then a human feedback loop.
> Rank Candidates is a subgraph with three screening rounds: a deterministic screen of all 100 resumes,
> an LLM deep review of the top 10, and a final hire / borderline / no-hire decision.
> After the report the graph pauses with LangGraph's `interrupt()`. A router node reads my message and decides whether
> to refine requirements and re-rank, compare, explain, generate interview questions, or answer with tools."

**Optional (10 s):** scroll `matching_agent.py` to `class AgentState` and `build_graph()`.

### 0:40 – 1:50 · Full JD → multi-round screening

**Do:** sidebar → choose **Senior Frontend Engineer** → **Screen candidates for this JD**.

> "I'll paste a real-looking JD. Watch the status box. Each line is a graph node reporting its reasoning."

Point at the live steps: parse_jd → extract_requirements (must-have React 3+ years, TypeScript, Jest) →
search_resumes (RAG over 762 chunks) → Round 1 (100 → 10, cut-off score) → Round 2 deep review → Round 3 decisions.

> "The chat shows the funnel, the ranked table with Round-1, deep-fit and final scores, and the decision for each candidate.
> John Carter is the clear hire. Several candidates are borderline."

**Do:** open the **🏆 Shortlist** tab and expand a BORDERLINE candidate (e.g. Meera Iyer).

> "Every candidate has a score breakdown, must-have evidence with years, strengths with resume quotes, gaps, and
> improvement suggestions for borderline candidates. Meera has strong TypeScript but only 1.7 years of React against the 3 required."

**Do:** open the **📄 Report** tab and scroll briefly. Mention the download button and that the report is saved under `reports/`.

### 1:50 – 2:40 · Compare side by side

**Do:** type `Compare the top 3 matches side by side`.

> "The router recognised a comparison and resolved 'top 3' to candidate IDs. The table is computed from the data:
> years per must-have, nice-to-haves, scores. The LLM only writes the verdict and a 'choose X if' line for each candidate."

### 2:40 – 3:30 · "Why did John rank higher than Jane?"

**Do:** type `Why did John rank higher than Jane?`

> "Jane isn't even in the top 10, but the agent scored all 100 resumes, so it can explain. The table shows the weighted
> points: John gets 45 of 45 on must-haves, Jane 15, because she has no TypeScript or Jest in any role.
> The explanation quotes those numbers rather than guessing."

**Do:** open the **🧠 Reasoning** tab and show `understand_request → explain_ranking` for this turn.

### 3:30 – 4:30 · Iterative refinement and re-ranking

**Do:** type `Make AWS a must-have and drop the Jest requirement`.

> "Now I change requirements mid-conversation. The agent updates the requirements (version 2 in the sidebar), loops
> back to Search Resumes and re-runs all three rounds."

Point at **"What changed after your refinement"**: the requirement diff (AWS moved from nice-to-have to must-have, Jest removed) and the
movement table (▲/▼/NEW/DROPPED, with a reason for each move, e.g. "missing must-have AWS").

### 4:30 – 5:10 · Interview questions and tool use

**Do:** type `Generate interview questions for Meera`.

> "The questions are tailored: they verify her Adobe migration work and probe her React-years gap, and each question
> includes what a good answer looks like."

**Do:** type `Which shortlisted candidates have mentored engineers? Check the resumes.`

> "This one goes to a ReAct node that uses the file-system and RAG tools. The reasoning tab lists the tool calls."

### 5:10 – 5:45 · Wrap-up

**Do:** type `done`.

> "The graph reaches END and summarises the recommended hires. Behind this there are 16 offline unit tests, 6 live
> conversation-flow tests, and 6 scenario transcripts in docs/test_scenarios. Thanks for watching."

**Optional cut-in (10 s):** a terminal running `pytest -m llm -v` showing 6 passed.

---

**Backup lines if something is slow:** "Round 2 runs ten LLM reviews in parallel, so a full screening takes about 20 seconds."
