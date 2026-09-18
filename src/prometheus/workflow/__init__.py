"""The new-plan.md LangGraph workflow: router/agent + knowledge_search tool.

Deliberately separate from `prometheus.agents` / `prometheus.graph`, which
are unimplemented stubs for the older Prometheus vision (a Planner/Critic/
Synthesizer adversarial debate loop, see docs/architecture.md). That
decision is still open (see plan.md) -- this package doesn't touch or
build on those stubs either way.
"""
