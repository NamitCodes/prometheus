from __future__ import annotations

import re as _re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

if len(sys.argv) < 2:
    print("Usage: python scripts/diagnose_pdf.py path/to/paper.pdf"); sys.exit(1)
_pdf = Path(sys.argv[1]).resolve()
if not _pdf.exists():
    print(f"[ERROR] Not found: {_pdf}"); sys.exit(1)

QUERY = "What is the name of the paper?"
SEP = "=" * 72
sep = "-" * 72

from prometheus.retrieval.ingestion import CHUNK_OVERLAP, CHUNK_SIZE, chunk_sections, embed
from prometheus.retrieval.parsers import parse_pdf

# ===== A: Raw parser output =====
print(); print(SEP); print("A. RAW PARSER OUTPUT"); print(SEP)
parsed = parse_pdf(str(_pdf))
print(f"File           : {parsed.filename}")
print(f"PDF title meta : {parsed.title!r}")
print(f"Total sections : {len(parsed.sections)}")
p1s = [s for s in parsed.sections if s.page_number == 1]
print(f"Page-1 sections: {len(p1s)}")
print(); print(sep)
print("Page 1 -- raw extracted text (first 2000 chars, newlines preserved):")
print(sep)
raw1 = "\n\n".join(s.text for s in p1s)
print(raw1[:2000])
if len(raw1) > 2000:
    print(f"\n... [total {len(raw1)} chars on page 1] ...")

all_ln = [ln.strip() for s in p1s for ln in s.text.splitlines() if ln.strip()]
print(); print(sep); print("Longest 5 lines (title candidates):")
for i, ln in enumerate(sorted(all_ln, key=len, reverse=True)[:5], 1):
    print(f"  {i}. [{len(ln):3d} chars] {ln[:120]}")
print("\nAll page-1 section previews:")
for i, s in enumerate(p1s, 1):
    sn = s.text.replace("\n", " ").strip()[:100]
    print(f"  Sec {i:2d} [{len(s.text):4d} chars]: {sn!r}")

# ===== B: Chunking output =====
print(); print(SEP); print("B. CHUNKING OUTPUT (Page 1)")
print(f"   CHUNK_SIZE={CHUNK_SIZE}  CHUNK_OVERLAP={CHUNK_OVERLAP}"); print(SEP)
chunks = chunk_sections(p1s, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
print(f"\nTotal page-1 chunks: {len(chunks)}")
for ci, cd in enumerate(chunks):
    t = cd["text"]
    print(f"\n  [Chunk {ci}]")
    pn_key = "page_number"
    print(f"  page_number : {cd.get(pn_key)}")
    print(f"  chars       : {len(t)}")
    print(f"  words       : {len(t.split())}")
    print(f"  first 100   : {t[:100].replace(chr(10), chr(32))!r}")
    if len(t) > 100:
        print(f"  last  100   : {t[-100:].replace(chr(10), chr(32))!r}")

# ===== C: Structural inspection =====
print(); print(SEP); print("C. STRUCTURAL INSPECTION"); print(SEP)
tl = (parsed.title or "").lower()
print(f"\nC1. Title {parsed.title!r} in page-1 chunks:")
found = False
for ci, cd in enumerate(chunks):
    txt_key = "text"
    if tl and tl in cd[txt_key].lower():
        print(f"   -> Chunk {ci}: {cd[txt_key][:120].replace(chr(10),' ')!r}")
        found = True
if not found:
    print("   [!] Not found. All chunks:")
    for ci, cd in enumerate(chunks):
        print(f"   Chunk {ci}: {cd['text'][:160].replace(chr(10),' ')!r}")

print("\nC2. Fragmentation flags:")
ms = nt = sc2 = la = 0
TERM = frozenset(".!?:'")
for ci, cd in enumerate(chunks):
    t = cd["text"]; fc = t[0] if t else ""; lc = t[-1] if t else ""
    if fc.islower():
        ms += 1; print(f"   [MID-WORD-START] Chunk {ci}: {t[:70].replace(chr(10),' ')!r}")
    if lc not in TERM and len(t) > 50:
        nt += 1
    if len(t) < 80:
        sc2 += 1; print(f"   [SHORT] Chunk {ci} ({len(t)} chars): {t!r}")
    ar = sum(c.isalpha() for c in t) / max(len(t), 1)
    if ar < 0.40:
        la += 1; print(f"   [LOW-ALPHA {ar:.2f}] Chunk {ci}: {t[:80].replace(chr(10),' ')!r}")
print(f"   Totals: mid-word-starts={ms} no-terminator={nt} short={sc2} low-alpha={la}")

print("\nC3. PyMuPDF paragraph boundaries:")
for i, s in enumerate(p1s, 1):
    lns = [ln.strip() for ln in s.text.splitlines() if ln.strip()]
    fl = lns[0][:80] if lns else "(empty)"
    print(f"   Para {i:2d} [{len(s.text):4d} chars]: {fl!r}")

# ===== D: Retrieval trace =====
print(); print(SEP)
print(f"D. RETRIEVAL TRACE: {QUERY!r}")
print("   In-memory page-1 simulation only -- no ChromaDB/BM25 writes"); print(SEP)

import numpy as np
from rank_bm25 import BM25Plus

TOK = _re.compile(r"[a-z0-9]+")
def tok(t): return TOK.findall(t.lower())

texts = [cd["text"] for cd in chunks]
if not texts:
    print("No chunks."); sys.exit(0)

bm = BM25Plus([tok(t) for t in texts])
bm_sc = bm.get_scores(tok(QUERY))
bm_rk = sorted(enumerate(bm_sc), key=lambda x: x[1], reverse=True)
print("\nD1. BM25 top-10:")
for r, (ci, sc) in enumerate(bm_rk[:10], 1):
    print(f"   #{r:2d} [chunk {ci:2d} | bm25={sc:6.3f}]: {texts[ci][:80].replace(chr(10),' ')!r}")

q_emb = np.array(embed([QUERY])[0])
c_embs = np.array(embed(texts))
def cosine(a, b):
    n = float(np.linalg.norm(a)) * float(np.linalg.norm(b))
    return float(np.dot(a, b) / n) if n else 0.0
dn_sc = [cosine(q_emb, ce) for ce in c_embs]
dn_rk = sorted(enumerate(dn_sc), key=lambda x: x[1], reverse=True)
print("\nD2. Dense cosine top-10:")
for r, (ci, sc) in enumerate(dn_rk[:10], 1):
    print(f"   #{r:2d} [chunk {ci:2d} | cos={sc:.4f}]: {texts[ci][:80].replace(chr(10),' ')!r}")

k = 60; rrf: dict[int, float] = {}
for r, (ci, _) in enumerate(bm_rk):
    rrf[ci] = rrf.get(ci, 0.0) + 1.0 / (k + r + 1)
for r, (ci, _) in enumerate(dn_rk):
    rrf[ci] = rrf.get(ci, 0.0) + 1.0 / (k + r + 1)
rrf_rk = sorted(rrf.items(), key=lambda x: x[1], reverse=True)
print("\nD3. RRF merged top-10:")
for r, (ci, sc) in enumerate(rrf_rk[:10], 1):
    print(f"   #{r:2d} [chunk {ci:2d} | rrf={sc:.5f}]: {texts[ci][:80].replace(chr(10),' ')!r}")

from sentence_transformers import CrossEncoder

ce = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
top = [ci for ci, _ in rrf_rk[:10]]
ces = ce.predict([(QUERY, texts[ci]) for ci in top])
ce_rk = sorted(zip(top, ces), key=lambda x: x[1], reverse=True)
print("\nD4. Cross-encoder top-10:")
for r, (ci, sc) in enumerate(ce_rk, 1):
    print(f"   #{r:2d} [chunk {ci:2d} | ce={sc:+7.3f}]: {texts[ci][:80].replace(chr(10),' ')!r}")

print(); print(SEP); print("DIAGNOSIS COMPLETE"); print(SEP)
