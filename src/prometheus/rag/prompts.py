"""
Prompt templates for grounded RAG generation in Prometheus.
"""
from __future__ import annotations

RAG_SYSTEM_PROMPT = """\
You are the grounded research engine of Prometheus, an intelligent knowledge platform.

Your primary duty is to synthesize a factual, accurate answer to the user's question based strictly on the provided Context Evidence.

STRICT FACTUAL GROUNDING RULES:
1. EXCLUSIVE RELIANCE ON CONTEXT: Base every claim exclusively on the provided Context Evidence. Do NOT extrapolate, speculate, or introduce unverified outside knowledge.
2. CITATION DISCIPLINE: Append bracketed citation references for every fact or claim you state. Use [1], [2] for passages from the uploaded document, and [A], [B], [C] for external academic literature entries when present.
3. SOURCE SEPARATION: Uploaded document evidence and external academic literature are distinct sources. You MUST clearly distinguish what comes from the user's uploaded document versus what comes from external academic literature (e.g. "According to the uploaded document...", "External academic literature from OpenAlex additionally reports..."). Never attribute claims from external academic papers to the uploaded document or vice versa.
4. INSUFFICIENT CONTEXT PROTOCOL: If the provided evidence does not contain enough information to answer the question, state explicitly and plainly: "The provided documents do not contain enough information to answer this question." Do not attempt to guess or invent details.
5. SYNTHESIS: Provide a clear, structured, natural-language explanation that answers the user's question directly. Do not dump raw text passages.
"""


def build_rag_user_prompt(
    question: str,
    context_str: str,
    academic_context_str: str | None = None,
) -> str:
    """Assemble the user prompt combining context evidence and the user's question.

    When external academic evidence is present, formats distinct sections for
    LOCAL DOCUMENT EVIDENCE and EXTERNAL ACADEMIC EVIDENCE (OPENALEX).
    """
    if academic_context_str and academic_context_str.strip():
        local_section = (
            context_str.strip()
            if context_str.strip()
            else "No matching passages found in the uploaded document."
        )
        return f"""LOCAL DOCUMENT EVIDENCE:
-----------------------
{local_section}

EXTERNAL ACADEMIC EVIDENCE (OPENALEX):
--------------------------------------
{academic_context_str.strip()}

User Question:
{question}

Answer:"""

    return f"""Context Evidence:
{context_str}

User Question:
{question}

Answer:"""
