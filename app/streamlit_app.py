"""
Streamlit dashboard (per proposal, Section 4):
  - Shows the agent hierarchy (Meta-Orchestrator -> sub-orchestrators ->
    Planner/Researcher/Retriever/Critic/Synthesizer)
  - Live debate progress (Critic <-> Synthesizer rounds, as they happen)
  - Final report with provenance + confidence metrics
  - Human-in-the-loop approve/redirect controls at each checkpoint

TODO:
  - Input box for the broad question -> calls
    prometheus.graph.meta_orchestrator.run_investigation
  - Sidebar or graph view of the agent hierarchy (st.graphviz_chart or a
    custom component) updating as sub-orchestrators spawn
  - Streaming panel for the debate loop (Critic objections / Synthesizer
    revisions) as they occur (LangGraph streaming events)
  - Final report view: claims + confidence + provenance links + any open
    objections, with Approve / Redirect buttons wired to the graph's
    human-in-the-loop checkpoint
"""
import streamlit as st

st.set_page_config(page_title="Prometheus", layout="wide")
st.title("Prometheus")
st.caption("A multi-agent framework for human-centric research and investigation")

st.info("Scaffold only -- wire this up to prometheus.graph.meta_orchestrator in Phase 6.")

question = st.text_area("Broad research question")
if st.button("Run investigation", disabled=True):
    st.write("TODO: call run_investigation(question) and stream results here")
