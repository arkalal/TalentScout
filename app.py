"""TalentScout — Streamlit chat interface for the LangGraph matching agent.

    streamlit run app.py
"""

from __future__ import annotations

import html
from pathlib import Path

import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage

from matching_agent import MatchingAgent, build_graph
from talentscout.config import JD_DIR, MODEL_NAME, ROOT
from talentscout.rag import get_index
from talentscout.resume_store import load_profiles
from talentscout.tools.agent_tools import skill_label

st.set_page_config(page_title="TalentScout · Matching Agent", page_icon="🎯", layout="wide")

st.markdown("""
<style>
  :root { --ts-accent: #818cf8; --ts-accent-bg: rgba(99,102,241,.16); --ts-border: rgba(148,163,184,.22);
          --ts-muted: #94a3b8; }
  .block-container {padding-top: 4.2rem; padding-bottom: 6rem; max-width: 1500px;}  /* clears the fixed top header */
  /* columns must be allowed to shrink, otherwise wide content spills into the neighbour column */
  div[data-testid="stColumn"] {min-width: 0;}
  /* right panel stays visible while the chat scrolls */
  div[data-testid="stHorizontalBlock"]:has(.stTabs) {align-items: flex-start;}
  div[data-testid="stColumn"]:has(.stTabs) {position: sticky; top: 4rem; max-height: calc(100vh - 10rem);
      overflow-y: auto; overflow-x: hidden; padding: 0 6px 0 2px;}
  /* hide the anchor-link icons Streamlit adds to markdown headings */
  [data-testid="stHeaderActionElements"] {display: none;}
  /* Streamlit's built-in 'install skills' promo toast — not part of the product */
  [data-testid="stSkillsNudgeAnchor"] {display: none !important;}
  /* chat typography: compact headings, readable body, tables that scroll instead of overflowing */
  [data-testid="stChatMessage"] {padding: .6rem .2rem;}
  [data-testid="stChatMessage"] h1, [data-testid="stChatMessage"] h2, [data-testid="stChatMessage"] h3
      {font-size: 1.22rem !important; line-height: 1.35; padding: .1rem 0 .35rem 0;}
  [data-testid="stChatMessage"] h4 {font-size: 1.02rem !important; padding: .4rem 0 .2rem 0;}
  [data-testid="stChatMessage"] p, [data-testid="stChatMessage"] li {font-size: .95rem; line-height: 1.55;}
  [data-testid="stMarkdownContainer"] table {display: block; max-width: 100%; overflow-x: auto;
      font-size: .86rem; border-collapse: collapse;}
  [data-testid="stMarkdownContainer"] th {white-space: nowrap; font-weight: 600;}
  [data-testid="stMarkdownContainer"] th, [data-testid="stMarkdownContainer"] td {padding: .35rem .6rem;
      vertical-align: top;}
  /* report / panel markdown: compact heading scale for the narrow side column */
  div[data-testid="stColumn"]:has(.stTabs) [data-testid="stMarkdownContainer"] h1 {font-size: 1.35rem !important; line-height: 1.3; padding: .4rem 0 .3rem 0;}
  div[data-testid="stColumn"]:has(.stTabs) [data-testid="stMarkdownContainer"] h2 {font-size: 1.12rem !important; padding: .9rem 0 .3rem 0;}
  div[data-testid="stColumn"]:has(.stTabs) [data-testid="stMarkdownContainer"] h3 {font-size: 1rem !important; padding: .7rem 0 .2rem 0;}
  div[data-testid="stColumn"]:has(.stTabs) [data-testid="stMarkdownContainer"] p,
  div[data-testid="stColumn"]:has(.stTabs) [data-testid="stMarkdownContainer"] li {font-size: .9rem; line-height: 1.5;}
  /* requirement chips */
  .ts-chips {display: flex; flex-wrap: wrap; gap: 6px; margin: .25rem 0 .8rem 0;}
  .ts-chip {white-space: nowrap; padding: 2px 9px; border-radius: 999px; font-size: .8rem;
      background: var(--ts-accent-bg); color: #c7d2fe; border: 1px solid rgba(129,140,248,.35);}
  .ts-chip.nice {background: rgba(148,163,184,.12); color: #cbd5e1; border-color: var(--ts-border);}
  .ts-label {font-size: .78rem; text-transform: uppercase; letter-spacing: .06em; color: var(--ts-muted);
      margin-top: .4rem;}
  /* reasoning step cards */
  .ts-step {border: 1px solid var(--ts-border); border-radius: 10px; padding: .55rem .75rem; margin: 0 0 .5rem 0;}
  .ts-step-head {display: flex; align-items: center; gap: 8px; margin-bottom: .25rem;}
  .ts-pill {font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .76rem; padding: 1px 8px;
      border-radius: 6px; background: var(--ts-accent-bg); color: #c7d2fe;}
  .ts-time {margin-left: auto; font-size: .74rem; color: var(--ts-muted);}
  .ts-step-body {font-size: .88rem; line-height: 1.45; overflow-wrap: anywhere;}
  .ts-turn {font-size: .78rem; text-transform: uppercase; letter-spacing: .08em; color: var(--ts-muted);
      margin: .8rem 0 .4rem 0;}
  .ts-muted {color: var(--ts-muted); font-size: .85rem;}
  /* button labels wrap instead of being clipped on narrow windows */
  .stButton button {height: auto; min-height: 2.6rem;}
  .stButton button p {white-space: normal !important; overflow: visible; text-overflow: clip; line-height: 1.3;}
  /* shortlist table in the side panel */
  table.ts-rank {display: table !important; width: 100%; font-size: .84rem; margin-bottom: .8rem;}
  table.ts-rank th, table.ts-rank td {padding: .35rem .45rem !important;}
  table.ts-rank td {vertical-align: middle;}
  table.ts-rank td.ts-dec {white-space: nowrap;}
  .ts-sub {font-size: .74rem; color: var(--ts-muted);}
  .ts-bar {height: 4px; background: rgba(148,163,184,.2); border-radius: 4px; margin: 3px 0; width: 64px;}
  .ts-bar span {display: block; height: 4px; border-radius: 4px; background: var(--ts-accent);}
  /* JSON / code in the panel wraps instead of being cut off */
  div[data-testid="stColumn"]:has(.stTabs) pre, div[data-testid="stColumn"]:has(.stTabs) code
      {white-space: pre-wrap !important; word-break: break-word;}
</style>
""", unsafe_allow_html=True)

NODE_ICONS = {"parse_jd": "📝", "extract_requirements": "🧩", "search_resumes": "🔎", "round1_screen": "1️⃣",
              "round2_deep_analysis": "2️⃣", "round3_final_decision": "3️⃣", "generate_report": "📄",
              "understand_request": "🧭", "refine_requirements": "🔧", "compare_candidates": "⚖️",
              "explain_ranking": "💡", "interview_questions": "🎤", "answer_question": "🛠️", "finish": "🏁"}
REC = {"HIRE": "🟢 HIRE", "BORDERLINE": "🟡 BORDERLINE", "NO_HIRE": "🔴 NO HIRE"}
USER_AVATAR, AGENT_AVATAR = "👤", "🎯"


@st.cache_resource(show_spinner="Loading resumes, embeddings and the agent graph…")
def shared_graph():
    load_profiles()
    get_index()  # warm the FAISS index + embedding model
    return build_graph()


def new_session() -> None:
    st.session_state.agent = MatchingAgent(graph=shared_graph())
    st.session_state.pending = None


def step_card(t: dict) -> str:
    return (f"<div class='ts-step'><div class='ts-step-head'><span>{NODE_ICONS.get(t['node'], '•')}</span>"
            f"<span class='ts-pill'>{html.escape(t['node'])}</span><span class='ts-time'>{t.get('time', '')}</span></div>"
            f"<div class='ts-step-body'>{html.escape(t['summary'])}</div></div>")


def chips(items: list[str], kind: str = "") -> str:
    if not items:
        return "<div class='ts-chips'><span class='ts-muted'>—</span></div>"
    return "<div class='ts-chips'>" + "".join(f"<span class='ts-chip {kind}'>{html.escape(i)}</span>" for i in items) + "</div>"


if "agent" not in st.session_state:
    new_session()
agent: MatchingAgent = st.session_state.agent

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.title("🎯 TalentScout")
    st.caption(f"LangGraph resume ⇄ JD matching agent · {len(load_profiles())} resumes · `{MODEL_NAME}`")
    if st.button("➕ New conversation", use_container_width=True):
        new_session()
        st.rerun()

    st.subheader("Start with a sample JD")
    jds = sorted(JD_DIR.glob("*.md"))
    default = next((i for i, p in enumerate(jds) if p.stem == "senior_frontend_engineer"), 0)
    choice = st.selectbox("Job description", jds, index=default, format_func=lambda p: p.stem.replace("_", " ").title().replace("Ml ", "ML ").replace("Sre", "SRE"))
    if choice:
        with st.expander("Preview JD"):
            st.markdown(choice.read_text())
        if st.button("Screen candidates for this JD", type="primary", use_container_width=True):
            st.session_state.pending = choice.read_text()
            st.rerun()

    state = agent.state
    req = state.get("requirements")
    if req:
        st.subheader(f"Requirements · v{len(state.get('requirements_history', []))}")
        must = [skill_label(r) + (f" · {r['min_years']:g}+y" if r.get("min_years") else "") for r in req.get("must_have", [])]
        st.markdown("<div class='ts-label'>Must-have</div>" + chips(must), unsafe_allow_html=True)
        st.markdown("<div class='ts-label'>Nice-to-have</div>" +
                    chips([skill_label(r) for r in req.get("nice_to_have", [])], "nice"), unsafe_allow_html=True)
        if req.get("min_years_experience"):
            st.markdown(f"**Min experience:** {req['min_years_experience']:g} years")
        with st.expander("Requirement history"):
            for h in state.get("requirements_history", []):
                st.markdown(f"**v{h['version']}** — {h['change']}")

    st.divider()
    st.caption("Graph: START → Parse JD → Extract Requirements → Search Resumes → Rank (3 rounds) → "
               "Report → Human Feedback ⟲ → END")

# ------------------------------------------------------------------ layout
chat_col, side_col = st.columns([7, 5], gap="medium")


def render_messages() -> None:
    for m in agent.state.get("messages", []):
        if isinstance(m, HumanMessage):
            with st.chat_message("user", avatar=USER_AVATAR):
                text = m.content
                if len(text) > 400:
                    st.markdown(f"**Job description submitted** · {len(text.split())} words")
                    with st.expander("Show JD"):
                        st.markdown(text)
                else:
                    st.markdown(text)
        elif isinstance(m, AIMessage):
            with st.chat_message("assistant", avatar=AGENT_AVATAR):
                st.markdown(m.content)


def run_turn(text: str) -> None:
    """Called inside the chat column: echo the message, stream the agent's reasoning live, then refresh."""
    with st.chat_message("user", avatar=USER_AVATAR):
        st.markdown(text if len(text) <= 400 else f"**Job description submitted** · {len(text.split())} words")
    with st.chat_message("assistant", avatar=AGENT_AVATAR):
        with st.status("Agent is reasoning…", expanded=True) as status:
            def on_event(node: str, update: dict) -> None:
                for t in (update.get("trace") or [])[-1:]:
                    if t["node"] == node:
                        st.markdown(step_card(t), unsafe_allow_html=True)
            try:
                agent.send(text, on_event=on_event)
                status.update(label="Done", state="complete", expanded=False)
            except Exception as exc:  # show the error instead of a blank screen
                status.update(label="Something went wrong", state="error")
                st.exception(exc)
                st.stop()
    st.rerun()


prompt = st.chat_input("Ask anything — e.g. “Make AWS a must-have”, “Why did John rank higher than Jane?”")
if prompt:
    st.session_state.pending = prompt

with chat_col:
    if not agent.state.get("messages") and not st.session_state.pending:
        st.markdown("### 👋 Hi! I'm TalentScout.")
        st.markdown("Paste a job description, pick a sample JD in the sidebar, or try a quick search:")
    render_messages()
    if not agent.state.get("final_ranking") and not st.session_state.pending:  # examples until a search exists
        cols = st.columns(2)
        for i, q in enumerate(["Find me candidates with React and 3+ years experience",
                               "Find Python backend engineers with Django or FastAPI, PostgreSQL and Docker, 4+ years",
                               "I need an ML engineer with PyTorch and LLM experience",
                               "Find DevOps engineers strong in AWS, Kubernetes and Terraform"]):
            if cols[i % 2].button(q, key=f"ex{i}", use_container_width=True):
                st.session_state.pending = q
                st.rerun()
    if st.session_state.pending:  # run the turn right under the conversation (live reasoning shows here)
        text, st.session_state.pending = st.session_state.pending, None
        run_turn(text)
    if agent.state.get("final_ranking") and agent.waiting_for_user:
        st.markdown("<div class='ts-label'>Quick actions</div>", unsafe_allow_html=True)
        qa = st.columns(2) * 2
        actions = ["Compare the top 3 matches side by side", "Why did #1 rank higher than #2?",
                   "Generate interview questions for #1", "Who should we hire? How can borderline candidates improve?"]
        for i, (c, a) in enumerate(zip(qa, actions)):
            if c.button(a, key=f"qa{i}", use_container_width=True):
                st.session_state.pending = a
                st.rerun()
    elif agent.state.get("messages") and not agent.waiting_for_user and agent.state.get("final_ranking"):
        st.info("Conversation ended. Send a new JD or query to start another search, or click **New conversation**.")


# ------------------------------------------------------------------ right panel
with side_col:
    state = agent.state
    tab_rank, tab_trace, tab_report, tab_graph = st.tabs(["🏆 Shortlist", "🧠 Reasoning", "📄 Report", "🗺️ Graph"])

    with tab_rank:
        fr = state.get("final_ranking") or []
        if not fr:
            st.caption("The ranked shortlist appears here after the first screening.")
        else:
            rows = "".join(
                f"<tr><td><span class='ts-sub'>#{e['rank']}</span><br>{html.escape(e['name'])}<div class='ts-sub'>{e['candidate_id']} · "
                f"{e['total_years']}y</div></td><td><b>{e['final_score']}</b><div class='ts-bar'><span style='width:"
                f"{max(0, min(100, e['final_score']))}%'></span></div><div class='ts-sub'>R1 {e['round1_score']} · deep "
                f"{e['deep_fit']}</div></td><td class='ts-dec'>{REC.get(e.get('recommendation'), '—')}</td></tr>"
                for e in fr)
            st.markdown("<table class='ts-rank'><thead><tr><th>Candidate</th><th>Score</th><th>Decision</th>"
                        f"</tr></thead><tbody>{rows}</tbody></table>", unsafe_allow_html=True)
            deep, decisions = state.get("deep_analysis", {}), state.get("decisions", {})
            for e in fr:
                d, dec = deep.get(e["candidate_id"], {}), decisions.get(e["candidate_id"], {})
                with st.expander(f"{e['rank']}. {e['name']} ({e['candidate_id']}) — {REC.get(e.get('recommendation'), '')} · {e['final_score']}"):
                    c = e["components"]
                    st.markdown(f"**Round 1 (0-100):** must {c['must_have']} · nice {c['nice_to_have']} · "
                                f"exp {c['experience']} · semantic {c['semantic']} → **{e['round1_score']}**  \n"
                                f"**Deep fit:** {e['deep_fit']} → **final {e['final_score']}**")
                    st.markdown("**Must-haves:** " + " · ".join(
                        ("✅" if m["status"] == "demonstrated" else "⚠️" if m["status"] == "listed_only" else "❌") +
                        f" {m['skill']} {m['years']:g}y" for m in e["must_have"]))
                    if d.get("strengths"):
                        st.markdown("**Strengths**\n" + "\n".join(f"- {s['point']} — _{s['evidence']}_" for s in d["strengths"]))
                    if d.get("gaps"):
                        st.markdown("**Gaps**\n" + "\n".join(f"- {g}" for g in d["gaps"]))
                    if dec.get("rationale"):
                        st.markdown(f"**Decision:** {dec['rationale']}")
                    if dec.get("improvement_suggestions"):
                        st.markdown("**Improvement suggestions**\n" + "\n".join(f"- {s}" for s in dec["improvement_suggestions"]))

    with tab_trace:
        trace = state.get("trace") or []
        if not trace:
            st.caption("Every node the agent runs is logged here with its reasoning.")
        for turn in sorted({t["turn"] for t in trace}, reverse=True):
            st.markdown(f"<div class='ts-turn'>Turn {turn}</div>", unsafe_allow_html=True)
            for t in [x for x in trace if x["turn"] == turn]:
                st.markdown(step_card(t), unsafe_allow_html=True)
                if t.get("details"):
                    with st.expander("details"):
                        st.json(t["details"], expanded=True)

    with tab_report:
        if state.get("report"):
            st.download_button("⬇️ Download report (.md)", state["report"], file_name=Path(state["report_path"]).name,
                               use_container_width=True)
            st.markdown(state["report"])
        else:
            st.caption("The full match report (strengths, gaps, suggestions per candidate) appears here.")

    with tab_graph:
        st.caption("Hover a diagram and click ⛶ to view it full screen.")
        for name, caption in (("architecture.png", "Conceptual view"),
                              ("state_machine.png", "Generated from the compiled LangGraph")):
            png = ROOT / "docs" / name
            if png.exists():
                st.image(str(png), caption=caption, use_container_width=True)
