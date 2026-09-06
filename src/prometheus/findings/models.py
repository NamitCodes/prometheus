"""
SQLAlchemy models for the Findings DB: past research reports and the full
reasoning chain behind each, written by the system and reused as context
in later investigations (per proposal, Section 2).

TODO:
  - Report(id, question, created_at, status, summary)
  - Claim(id, report_id, statement, confidence_level, supporting_evidence_ids)
  - ReasoningStep(id, report_id, agent_role, input, output, timestamp)
    -- this is what the "reasoning chain" reuse depends on
  - Objection(id, report_id, claim_id, issue_type, explanation, resolved: bool)
"""
from __future__ import annotations

# from sqlalchemy.orm import DeclarativeBase
# TODO: define Base, Report, Claim, ReasoningStep, Objection tables
