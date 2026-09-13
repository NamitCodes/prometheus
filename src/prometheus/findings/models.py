"""
SQLAlchemy models for the Findings DB: past research reports and the full
reasoning chain behind each, written by the system and reused as context
in later investigations (per proposal, Section 2).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    question: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    status: Mapped[str] = mapped_column(String, default="draft")  # draft | approved | rejected
    summary: Mapped[str] = mapped_column(Text, default="")

    claims: Mapped[list[Claim]] = relationship(back_populates="report", cascade="all, delete-orphan")
    reasoning_steps: Mapped[list[ReasoningStep]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )
    objections: Mapped[list[Objection]] = relationship(back_populates="report", cascade="all, delete-orphan")


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.id"))
    statement: Mapped[str] = mapped_column(Text)
    confidence_level: Mapped[float] = mapped_column(Float, default=0.0)
    supporting_evidence_ids: Mapped[str] = mapped_column(Text, default="")  # comma-separated ids

    report: Mapped[Report] = relationship(back_populates="claims")


class ReasoningStep(Base):
    __tablename__ = "reasoning_steps"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.id"))
    agent_role: Mapped[str] = mapped_column(String)  # planner | researcher | retriever | critic | synthesizer
    input: Mapped[str] = mapped_column(Text)
    output: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    report: Mapped[Report] = relationship(back_populates="reasoning_steps")


class Objection(Base):
    __tablename__ = "objections"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.id"))
    claim_id: Mapped[str | None] = mapped_column(ForeignKey("claims.id"), nullable=True)
    issue_type: Mapped[str] = mapped_column(String)  # unsupported | confound | small-n
    explanation: Mapped[str] = mapped_column(Text)
    resolved: Mapped[bool] = mapped_column(default=False)

    report: Mapped[Report] = relationship(back_populates="objections")
