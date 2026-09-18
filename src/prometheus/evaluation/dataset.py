"""
Eval cases for new-plan.md Phase 14: known question -> expected routing +
expected answer content, covering document-only, web-only, and no-tool-needed
questions. Distinct from the old-vision `llm_judge.py`/`ragas_eval.py` stubs,
which target hypothesis/synthesis rubric grading -- this evaluates the
Phase 9-13 chat workflow instead.

Document-only cases use a fabricated term/fact (e.g. "Zylorex-9") that
cannot exist in the model's training data -- if the answer is correct, the
model *must* have used knowledge_search, which makes "does it ground its
answer in the document" verifiable without an LLM judge.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EvalCase:
    name: str
    question: str
    expected_keyword: str
    expects_document_tool: bool
    expects_web_tool: bool
    setup_documents: list[tuple[str, str]] = field(default_factory=list)  # [(filename, content)]


EVAL_CASES: list[EvalCase] = [
    EvalCase(
        name="document_only_fabricated_fact",
        question="How many calibration cycles does the Zylorex-9 protocol require before deployment?",
        expected_keyword="42",
        expects_document_tool=True,
        expects_web_tool=False,
        setup_documents=[
            (
                "protocol.txt",
                ("The Zylorex-9 protocol requires exactly 42 calibration cycles "
                "before deployment, per internal engineering review."),
            )
        ],
    ),
    EvalCase(
        name="document_only_second_fact_no_leakage",
        question="What color light does the Quintavane sensor emit during a fault state?",
        expected_keyword="violet",
        expects_document_tool=True,
        expects_web_tool=False,
        setup_documents=[
            (
                "sensor_spec.txt",
                ("During a fault state, the Quintavane sensor emits a violet indicator "
                "light, distinct from its normal green operating light."),
            )
        ],
    ),
    EvalCase(
        name="web_only_real_world_fact",
        question="What year was the transformer architecture introduced in the paper "
        "'Attention Is All You Need'? Search the web if needed.",
        expected_keyword="2017",
        expects_document_tool=False,
        expects_web_tool=True,
    ),
    EvalCase(
        name="general_question_no_tools_needed",
        question="What is 12 plus 30?",
        expected_keyword="42",
        expects_document_tool=False,
        expects_web_tool=False,
    ),
]
