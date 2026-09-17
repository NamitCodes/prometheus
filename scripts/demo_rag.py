"""
End-to-end verification, interactive testing, and user document Q&A for Prometheus RAG.

Supports:
1. User Document Testing:
   python scripts/demo_rag.py --live --file "C:\\path\\to\\my.pdf"
   python scripts/demo_rag.py --live --file doc1.pdf doc2.pdf --question "What is the key finding?"
2. Automated Synthetic Demonstration (when no --file is given):
   python scripts/demo_rag.py --live
   python scripts/demo_rag.py --mock
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import pymupdf

from prometheus.config import settings
from prometheus.llm.base import BaseLLMClient
from prometheus.llm.mock import MockLLMClient
from prometheus.llm.openrouter import OpenRouterClient
from prometheus.rag.pipeline import query_rag
from prometheus.retrieval.ingestion import ingest_document


def mask_key(key: str) -> str:
    if not key:
        return "<NOT SET>"
    prefix = key[:6] if len(key) >= 6 else key[:2]
    return f"{prefix}...[HIDDEN, length={len(key)}]"


def _setup_llm_client(force_live: bool, force_mock: bool) -> tuple[BaseLLMClient, str, bool]:
    """Resolve and instantiate the LLM client according to flags and environment."""
    api_key = os.getenv("OPENROUTER_API_KEY") or settings.openrouter_api_key
    model = os.getenv("OPENROUTER_MODEL") or settings.openrouter_model

    if force_mock:
        use_live_llm = False
    elif force_live:
        if not api_key:
            print("\n[ERROR] --live flag specified but OPENROUTER_API_KEY is not set in .env!")
            sys.exit(1)
        use_live_llm = True
    else:
        use_live_llm = bool(api_key)

    if use_live_llm:
        client: BaseLLMClient = OpenRouterClient(api_key=api_key, model=model)
    else:
        client = MockLLMClient(
            default_response=(
                "The Surface Code is currently the leading quantum error-correcting code [1]. "
                "It requires approximately 1,000 physical qubits to construct one fault-tolerant "
                "logical qubit [1]."
            )
        )

    return client, model, use_live_llm


def display_rag_results(rag_result, document_scope: str | None = None) -> None:
    """Pretty-print generated answer, citation mappings, and raw retrieved chunks."""
    print("\n" + "=" * 60)
    print("1. GENERATED ANSWER")
    print("=" * 60)
    print(rag_result.answer.strip())

    print("\n" + "=" * 60)
    print(f"2. CITATION MAPPING ({len(rag_result.sources)} citations)")
    print("=" * 60)
    if not rag_result.sources:
        print("  (No citations returned - context was insufficient or query unmatched)")
    for src in rag_result.sources:
        score_str = f"{src.score:.4f}" if src.score is not None else "N/A"
        loc_str = f"Page {src.page_number}" if src.page_number else (f"Slide {src.slide_number}" if src.slide_number else "N/A")
        print(f"  [{src.citation_index}] -> Source: {src.filename} ({loc_str})")
        print(f"       Document ID : {src.document_id}")
        print(f"       Chunk ID    : {src.chunk_id}")
        print(f"       Rerank Score: {score_str}")
        print(f"       Evidence    : {src.text_snippet[:140].strip()}...")

    if rag_result.academic_sources:
        print("\n" + "=" * 60)
        print(f"2b. EXTERNAL ACADEMIC EVIDENCE ({len(rag_result.academic_sources)} papers from OpenAlex)")
        print("=" * 60)
        for acad in rag_result.academic_sources:
            authors_str = ", ".join(acad.authors) if acad.authors else "Unknown"
            year_str = str(acad.year) if acad.year is not None else "n.d."
            doi_url = acad.doi or acad.url or "N/A"
            abstract_snippet = (
                (acad.abstract[:140].strip() + "...")
                if acad.abstract
                else "No abstract available."
            )
            print(f"  [{acad.citation_label}] -> Paper: \"{acad.title}\"")
            print(f"       Authors     : {authors_str} ({year_str})")
            print(f"       DOI / Link  : {doi_url}")
            print(f"       OpenAlex ID : {acad.source_id}")
            print(f"       Abstract    : {abstract_snippet}")

    print("\n" + "=" * 60)
    print(f"3. RETRIEVED CHUNKS ({len(rag_result.retrieved_chunks)} candidate passages)")
    print("=" * 60)
    for rank, chunk in enumerate(rag_result.retrieved_chunks, start=1):
        meta = chunk.get("metadata", {})
        score = chunk.get("final_score", chunk.get("rerank_score", chunk.get("score")))
        score_fmt = f"{score:.4f}" if score is not None else "N/A"
        loc = f"Page {meta.get('page_number')}" if meta.get('page_number') else (f"Slide {meta.get('slide_number')}" if meta.get('slide_number') else "N/A")
        print(f"  Rank #{rank} [Score: {score_fmt}] [Chunk: {chunk.get('id')}]:")
        print(f"    Origin     : {meta.get('filename')} ({loc}) [Doc: {meta.get('document_id')}]")
        print(f"    Text       : {chunk.get('text', '').strip()[:140]}...")


def run_user_documents_qa(
    file_paths: list[str],
    question: str | None = None,
    doc_id_filter: str | None = None,
    top_k: int = 5,
    force_live: bool = False,
    force_mock: bool = False,
    include_academic: bool = False,
) -> int:
    """Ingest user-supplied files (.pdf, .docx, .pptx, .txt) and answer questions."""
    print("=" * 72)
    print("PROMETHEUS RAG -- USER DOCUMENT TESTING WORKFLOW")
    print("=" * 72)

    api_key = os.getenv("OPENROUTER_API_KEY") or settings.openrouter_api_key
    llm_client, model, is_live = _setup_llm_client(force_live, force_mock)

    print(f"Target Model       : {model}")
    print(f"API Key Status     : {mask_key(api_key)}")
    print(f"Active LLM Backend : {'Live OpenRouter (' + model + ')' if is_live else 'Deterministic MockLLMClient'}")
    print(f"Academic Literature: {'Enabled (OpenAlex)' if include_academic else 'Disabled (Local PDF evidence only)'}")

    # Ingest each provided file
    ingested_docs: list[dict[str, str]] = []
    print("\n[Ingestion Phase] Processing user documents...")

    for fpath in file_paths:
        p = Path(fpath).resolve()
        if not p.exists():
            print(f"  [ERROR] File not found: {p}")
            return 1

        # Generate a clean, human-readable document_id incorporating the filename
        clean_stem = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in p.stem)[:24]
        doc_id = f"doc-{clean_stem}-{uuid.uuid4().hex[:6]}"

        print(f"\n  Parsing and ingesting: '{p.name}'")
        try:
            assigned_id = ingest_document(
                path=str(p),
                document_id=doc_id,
                metadata={"original_path": str(p)},
            )
            print("    -> Ingestion successful!")
            print(f"    -> Assigned Document ID : '{assigned_id}'")
            print(f"    -> Format               : {p.suffix.lower()}")
            ingested_docs.append({"document_id": assigned_id, "filename": p.name, "path": str(p)})
        except Exception as exc:  # noqa: BLE001
            print(f"    -> Ingestion failed for {p.name}: {exc}")
            return 1

    print("\n" + "-" * 72)
    print(f"All {len(ingested_docs)} document(s) successfully indexed into ChromaDB and BM25.")
    for d in ingested_docs:
        print(f"  * {d['filename']} => Document ID: {d['document_id']}")
    print("-" * 72)

    # -----------------------------------------------------------------------
    # Determine effective query scope
    # -----------------------------------------------------------------------
    # Priority: explicit --doc-id > auto-scope (single file) > global search
    if doc_id_filter:
        # User explicitly requested a specific document scope.
        effective_doc_id: str | None = doc_id_filter
        scope_label = f"Explicit --doc-id scope: '{effective_doc_id}'"
    elif len(ingested_docs) == 1:
        # Single-file workflow: automatically scope to the ingested document
        # so the user doesn't have to supply --doc-id manually.
        effective_doc_id = ingested_docs[0]["document_id"]
        scope_label = (
            f"Auto-scoped to '{ingested_docs[0]['filename']}' "
            f"(document_id='{effective_doc_id}')"
        )
    else:
        # Multiple files ingested without an explicit doc-id: search everything.
        effective_doc_id = None
        scope_label = f"Searching across all {len(ingested_docs)} indexed documents (top_k={top_k})"

    print(f"\n[Query Scope] {scope_label}")

    def execute_query(q_text: str, override_academic: bool | None = None) -> None:
        use_academic = include_academic if override_academic is None else override_academic
        print(f"\nQuestion: '{q_text}'")
        if use_academic:
            print("Mode: Combining local document evidence + external OpenAlex academic literature...")
        else:
            print("Mode: Local document evidence only (academic evidence disabled)...")
        print("Retrieving candidates, reranking, and generating grounded response...")

        result = query_rag(
            question=q_text,
            document_id=effective_doc_id,
            top_k=top_k,
            llm_client=llm_client,
            include_academic_evidence=use_academic,
        )
        display_rag_results(result, document_scope=effective_doc_id)

    # If single question passed from command-line
    if question:
        execute_query(question)
        return 0

    # Otherwise enter interactive Q&A loop
    print("\nEntering Interactive Question-Answering mode.")
    print("Type your question and press Enter. Prefix with '/academic <q>' for academic evidence.")
    print("Type 'q', 'exit', or 'quit' to exit.")

    while True:
        try:
            user_input = input("\n[Prometheus Question] > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting interactive session.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("q", "exit", "quit"):
            print("Session ended.")
            break

        acad_override = None
        actual_q = user_input
        if user_input.startswith("/academic "):
            acad_override = True
            actual_q = user_input[len("/academic "):].strip()

        execute_query(actual_q, override_academic=acad_override)

    return 0


def run_e2e_demo(force_live: bool = False, force_mock: bool = False) -> int:
    """Run the synthetic 3-page scientific demonstration (fallback when no --file given)."""
    print("=" * 72)
    print("PROMETHEUS RAG GENERATION LAYER -- AUTOMATED DEMONSTRATION")
    print("=" * 72)

    api_key = os.getenv("OPENROUTER_API_KEY") or settings.openrouter_api_key
    llm_client, model, is_live = _setup_llm_client(force_live, force_mock)

    print(f"Target Model       : {model}")
    print(f"API Key Status     : {mask_key(api_key)}")
    print(f"Active LLM Backend : {'Live OpenRouter Client (' + model + ')' if is_live else 'Deterministic MockLLMClient (offline mode)'}")

    # 1. Prepare temporary directory for isolated demo data
    temp_dir = Path(tempfile.mkdtemp(prefix="prometheus_demo_"))
    pdf_path = temp_dir / "quantum_computing_primer.pdf"

    try:
        # 2. Generate a 3-page scientific PDF
        print("\n[Step 1] Generating multi-page scientific test PDF...")
        doc = pymupdf.open()

        page1 = doc.new_page()
        page1.insert_text(
            (50, 50),
            "Chapter 1: Principles of Quantum Computation\n\n"
            "Quantum computers process information using quantum bits or qubits. "
            "Unlike classical bits which are strictly 0 or 1, qubits can exist in a "
            "state of superposition, described mathematically by linear combinations "
            "of basis states |0> and |1>.\n\n"
            "This superposition principle enables quantum parallel processing of mathematical "
            "evaluations simultaneously across exponentially large state spaces."
        )

        page2 = doc.new_page()
        page2.insert_text(
            (50, 50),
            "Chapter 2: Quantum Entanglement and Teleportation\n\n"
            "Quantum entanglement is a phenomenon where pairs or groups of particles "
            "interact such that the quantum state of each particle cannot be described "
            "independently of the state of the others, even when separated by large distances.\n\n"
            "Bell state measurements allow quantum teleportation of qubit states without "
            "transmitting the physical particle itself across the communication channel."
        )

        page3 = doc.new_page()
        page3.insert_text(
            (50, 50),
            "Chapter 3: Quantum Error Correction and Decoherence\n\n"
            "A major challenge in physical quantum hardware is environmental decoherence. "
            "Thermal fluctuations and electromagnetic noise cause quantum states to collapse.\n\n"
            "The Surface Code is currently the leading quantum error-correcting code, requiring "
            "approximately 1,000 physical qubits to construct one fault-tolerant logical qubit."
        )

        doc.save(str(pdf_path))
        doc.close()
        print(f"  Created: {pdf_path.name} (3 pages, authentic page structure)")

        # 3. Ingest PDF
        print("\n[Step 2] Ingesting document into vector store and BM25 index...")
        doc_id = "doc-quantum-primer-v1"
        ingested_id = ingest_document(
            path=str(pdf_path),
            document_id=doc_id,
            metadata={"domain": "quantum-physics", "author": "Prometheus Research Team"},
        )
        print(f"  Document ingested successfully. Assigned document_id: '{ingested_id}'")

        # 4. Ingest a second distinct document to verify document isolation
        bio_path = temp_dir / "cellular_biology.txt"
        bio_path.write_text(
            "Mitochondria are double-membrane-bound organelles found in most eukaryotic organisms. "
            "They generate most of the chemical energy needed to power biochemical reactions, "
            "stored in adenosine triphosphate (ATP).",
            encoding="utf-8",
        )
        bio_id = "doc-biology-primer-v1"
        ingest_document(str(bio_path), document_id=bio_id)
        print(f"  Second document ingested for isolation testing. Assigned document_id: '{bio_id}'")

        # 5. Query 1: Targeted question against quantum primer
        question = "What is the Surface Code and how many physical qubits does it require?"
        print("\n[Step 3] Querying RAG pipeline:")
        print(f"  User Question  : '{question}'")
        print(f"  Document Scope : '{doc_id}'")

        rag_result = query_rag(
            question=question,
            document_id=doc_id,
            top_k=3,
            llm_client=llm_client,
        )

        display_rag_results(rag_result, document_scope=doc_id)

        # 6. Verification checks
        print("\n" + "=" * 60)
        print("4. GROUNDING & ISOLATION VERIFICATION")
        print("=" * 60)

        lower_ans = rag_result.answer.lower()
        surface_code_mentioned = "surface code" in lower_ans
        qubits_mentioned = "1,000" in lower_ans or "1000" in lower_ans or "thousand" in lower_ans

        if surface_code_mentioned and qubits_mentioned:
            print("  [GROUNDING CHECK] PASSED: Answer contains key factual evidence from Page 3.")
        else:
            print("  [GROUNDING CHECK] WARNING: Answer may be missing expected keywords.")

        citation_present = any(f"[{i}]" in rag_result.answer for i in range(1, len(rag_result.sources) + 1))
        if citation_present:
            print("  [CITATION CHECK] PASSED: Answer includes bracketed citation references.")
        else:
            print("  [CITATION CHECK] NOTE: No explicit bracketed references found in response text.")

        page_3_sources = [s for s in rag_result.sources if s.page_number == 3]
        if page_3_sources:
            print("  [PAGE ACCURACY CHECK] PASSED: Top retrieved evidence is authentically attributed to Page 3.")
        else:
            print("  [PAGE ACCURACY CHECK] WARNING: Page 3 not found in top sources.")

        print("\n  Testing Document Isolation:")
        cross_result = query_rag(
            question="What do mitochondria generate?",
            document_id=doc_id,  # Scoped strictly to quantum document
            top_k=3,
            llm_client=llm_client,
        )
        leaked = [s for s in cross_result.sources if s.document_id == bio_id]
        if not leaked:
            print("  [ISOLATION CHECK] PASSED: Zero chunks leaked from cellular biology into quantum scope.")
        else:
            print(f"  [ISOLATION CHECK] FAILED: Leak detected from {bio_id}")
            return 2

        print("\n" + "=" * 72)
        print("AUTOMATED DEMONSTRATION COMPLETED SUCCESSFULLY!")
        print("=" * 72)
        return 0

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prometheus RAG -- Interactive and Automated Testing Workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  # Ingest your own PDF and ask interactively:
  python scripts/demo_rag.py --live --file "C:\\path\\to\\paper.pdf"

  # Ingest multiple files and ask a single question:
  python scripts/demo_rag.py --live --file paper1.pdf doc2.docx -q "What methodology is used?"

  # Run the automated 3-page synthetic demonstration:
  python scripts/demo_rag.py --live
  python scripts/demo_rag.py --mock
""",
    )
    parser.add_argument(
        "--file", "-f",
        nargs="+",
        dest="files",
        help="Path to one or more PDF, DOCX, PPTX, or TXT documents to ingest and test.",
    )
    parser.add_argument(
        "--question", "-q",
        type=str,
        default=None,
        help="Question to ask against the document(s). If omitted, opens interactive prompt.",
    )
    parser.add_argument(
        "--doc-id",
        type=str,
        default=None,
        help="Optional document_id to isolate search strictly to a single document.",
    )
    parser.add_argument(
        "--top-k", "-k",
        type=int,
        default=5,
        help="Number of candidate evidence chunks to consider (default: 5).",
    )
    parser.add_argument(
        "--academic",
        action="store_true",
        help="Include lightweight external academic evidence from OpenAlex.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Force live OpenRouter Gemini generation.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Force offline deterministic Mock LLM generation.",
    )

    args = parser.parse_args()

    if args.files:
        return run_user_documents_qa(
            file_paths=args.files,
            question=args.question,
            doc_id_filter=args.doc_id,
            top_k=args.top_k,
            force_live=args.live,
            force_mock=args.mock,
            include_academic=args.academic,
        )
    else:
        return run_e2e_demo(force_live=args.live, force_mock=args.mock)


if __name__ == "__main__":
    sys.exit(main())
