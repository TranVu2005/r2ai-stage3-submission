"""S49: stand-ins for the two lost hand-off ZIPs of the 120A-p4b-v3 build (P1-vi+10.zip, P-A4-K90-ph.zip).

The build reads them through ``r2ai.s29.qwen_judge._load_submission`` for three things only:

* ``cal.Frame.base_k``: ``len(relevant_docs)`` of each K90-ph row  -> ``K90`` of ``kq_counts.parquet``;
* ``s38.compose.s29_chunk_texts``: the P1 chunk text of a carrier (``p1_row``: same query, ``p1_any``: first P1 chunk of the doc)
  -> the rows of ``p1_chunks.parquet`` (3c) or nothing (3b, ``--no-p1``);
* the pool13 size ``round(1.3 * K_q)`` with ``K_q = len(relevant_docs)`` of P1-vi+10 -> ``K_q`` of ``kq_counts.parquet``
  (used by ``pool13.py`` / ``pool_npz.py``, not through this loader).

``install()`` replaces the loader for exactly these two paths; every other submission still goes through the original. The doc
IDs of the stand-in rows are negative placeholders: nothing on these code paths reads them, only their count.
Environment: ``S49_KQ`` (kq_counts.parquet, required), ``S49_P1_CHUNKS`` (p1_chunks.parquet, optional).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pandas as pd

P1_NAME, BASELINE_NAME = "P1-vi+10.zip", "P-A4-K90-ph.zip"


def _rows(kind: str) -> list[dict[str, Any]]:
    kq = pd.read_parquet(os.environ["S49_KQ"]).sort_values("query_id")
    column = "K_q" if kind == "p1" else "K90"
    chunks: dict[int, list[dict[str, Any]]] = {}
    if kind == "p1" and os.environ.get("S49_P1_CHUNKS"):
        frame = pd.read_parquet(os.environ["S49_P1_CHUNKS"]).sort_values(["query_id", "chunk_order"])
        for q, d, t in zip(frame.query_id.astype(int), frame.doc_id.astype(int), frame.chunk_text):
            chunks.setdefault(q, []).append({"doc_id": d, "chunk_text": t})
    return [{"id": int(q), "relevant_docs": [-(i + 1) for i in range(int(k))], "relevant_chunks": chunks.get(int(q), [])}
            for q, k in zip(kq.query_id, kq[column])]


def install() -> None:
    from r2ai.s29 import qwen_judge
    from r2ai.s36 import cal

    original = qwen_judge._load_submission

    def load(path: Path, with_chunks: bool = False) -> list[dict[str, Any]]:
        name = Path(path).name
        if name == P1_NAME:
            return _rows("p1")
        if name == BASELINE_NAME:
            return _rows("baseline")
        return original(path, with_chunks)

    qwen_judge._load_submission = load
    cal._load_submission = load
