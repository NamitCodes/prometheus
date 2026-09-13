"""
Findings DB repository -- read/write access used by:
  - Retriever Agent (query past findings as a data store)
  - Meta-Orchestrator (persist final report + reasoning chain on approval)
  - MCP tools (search_papers / save_report expose a subset of this)

Phase 1 provides basic save/search (plain substring match). Phase 4 upgrades
search_findings to the same BM25 + dense hybrid machinery as
prometheus.retrieval.hybrid_search, once report volume justifies it.
"""
from __future__ import annotations

from sqlalchemy import create_engine, or_
from sqlalchemy.orm import Session

from prometheus.config import settings
from prometheus.findings.models import Base, Claim, Objection, ReasoningStep, Report

_engine = create_engine(settings.database_url)


def init_db() -> None:
    Base.metadata.create_all(_engine)


def save_report(report: dict) -> str:
    """report: {question, summary, status?, claims?: [{statement, confidence_level, supporting_evidence_ids}]}"""
    with Session(_engine) as session:
        row = Report(
            question=report["question"],
            summary=report.get("summary", ""),
            status=report.get("status", "draft"),
        )
        for claim in report.get("claims", []):
            row.claims.append(
                Claim(
                    statement=claim["statement"],
                    confidence_level=claim.get("confidence_level", 0.0),
                    supporting_evidence_ids=",".join(claim.get("supporting_evidence_ids", [])),
                )
            )
        session.add(row)
        session.commit()
        return row.id


def get_report(report_id: str) -> Report | None:
    with Session(_engine) as session:
        return session.get(Report, report_id)


def search_findings(query: str, top_k: int = 10) -> list[Report]:
    like = f"%{query}%"
    with Session(_engine) as session:
        stmt = (
            session.query(Report)
            .filter(or_(Report.question.ilike(like), Report.summary.ilike(like)))
            .order_by(Report.created_at.desc())
            .limit(top_k)
        )
        return list(stmt)


def save_reasoning_chain(report_id: str, steps: list[dict]) -> None:
    """steps: [{agent_role, input, output}]"""
    with Session(_engine) as session:
        for step in steps:
            session.add(
                ReasoningStep(
                    report_id=report_id,
                    agent_role=step["agent_role"],
                    input=step["input"],
                    output=step["output"],
                )
            )
        session.commit()


def save_objection(report_id: str, objection: dict) -> str:
    """objection: {issue_type, explanation, claim_id?, resolved?}"""
    with Session(_engine) as session:
        row = Objection(
            report_id=report_id,
            claim_id=objection.get("claim_id"),
            issue_type=objection["issue_type"],
            explanation=objection["explanation"],
            resolved=objection.get("resolved", False),
        )
        session.add(row)
        session.commit()
        return row.id
