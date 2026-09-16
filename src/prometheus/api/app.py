"""
FastAPI application exposing Prometheus RAG query and ingestion endpoints.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware

from prometheus.rag.models import RagQueryRequest, RagResult
from prometheus.rag.pipeline import query_rag
from prometheus.retrieval.ingestion import ingest_document
from prometheus.retrieval.parsers import SUPPORTED_EXTENSIONS

app = FastAPI(
    title="Prometheus RAG API",
    description="Minimal REST API for grounded research and document question-answering in Prometheus",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/rag/health")
def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "prometheus-rag"}


@app.post("/api/rag/query", response_model=RagResult)
def rag_query_endpoint(request: RagQueryRequest) -> RagResult:
    """Query the RAG pipeline with a user question and optional document filter."""
    try:
        result = query_rag(
            question=request.question,
            document_id=request.document_id,
            top_k=request.top_k,
            include_academic_evidence=request.include_academic_evidence,
            openalex_max_results=request.openalex_max_results,
        )
        return result
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        ) from val_err
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RAG query processing failed: {exc}",
        ) from exc


@app.post("/api/rag/ingest")
async def ingest_file_endpoint(
    file: UploadFile = File(...),  # noqa: B008
    document_id: str | None = Form(None),
) -> dict:
    """Upload and ingest a document file (.pdf, .docx, .pptx, .txt) into the RAG knowledge store."""
    filename = file.filename or "uploaded_doc"
    ext = Path(filename).suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Supported formats: {sorted(SUPPORTED_EXTENSIONS)}",
        )

    # Save to a temporary file for parser processing
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        doc_id = ingest_document(
            path=str(tmp_path),
            document_id=document_id,
            metadata={"original_filename": filename},
        )
        return {
            "status": "success",
            "document_id": doc_id,
            "filename": filename,
            "file_type": ext.lstrip("."),
        }
    finally:
        if tmp_path.exists():
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
