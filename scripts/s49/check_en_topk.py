"""S49: checks of an EN-hedge ZIP with ``--chunk-top K`` against its base and the K-doc hedge (streaming, one row at a time).

  check_en_topk.py <base.zip> <ref-hedge.zip> <new.zip> <K> [--limit 101000000]

* base prefix: per query, ``relevant_docs`` and ``relevant_chunks`` of the base are an exact prefix of the new row;
* the first K appended docs and their chunks equal the appended part of the reference hedge (e.g. 4_120A-en3);
* appended docs beyond K carry no chunk; every chunk's doc is in ``relevant_docs``;
* per-query distribution of appended docs and chunks; ZIP size against the limit.
"""
import argparse
import json
import zipfile
from collections import Counter
from pathlib import Path


def rows_of(zp):
    with zipfile.ZipFile(zp) as z, z.open(z.namelist()[0]) as f:
        for line in f:
            line = line.strip().rstrip(b",")
            if line.startswith(b"{"):
                yield json.loads(line)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("base", type=Path); ap.add_argument("ref", type=Path); ap.add_argument("new", type=Path); ap.add_argument("k", type=int)
    ap.add_argument("--limit", type=int, default=101_000_000)
    a = ap.parse_args()
    bad = Counter()
    docs_added, chunks_added = Counter(), Counter()
    n = 0
    for b, r, x in zip(rows_of(a.base), rows_of(a.ref), rows_of(a.new)):
        n += 1
        if not (b["id"] == r["id"] == x["id"]):
            bad["id_order"] += 1
            continue
        bd, bc = b["relevant_docs"], b["relevant_chunks"]
        if x["relevant_docs"][:len(bd)] != bd:
            bad["base_docs_prefix"] += 1
        if x["relevant_chunks"][:len(bc)] != bc:
            bad["base_chunks_prefix"] += 1
        tail_d, tail_c = x["relevant_docs"][len(bd):], x["relevant_chunks"][len(bc):]
        ref_d, ref_c = r["relevant_docs"][len(bd):], r["relevant_chunks"][len(bc):]
        if tail_d[:a.k] != ref_d[:a.k] or len(ref_d) > a.k:
            bad["first_k_docs_vs_ref"] += 1
        if tail_c != ref_c:
            bad["en_chunks_vs_ref"] += 1
        if any(c["doc_id"] not in set(tail_d[:a.k]) for c in tail_c):
            bad["chunk_beyond_k"] += 1
        docs = set(x["relevant_docs"])
        if any(c["doc_id"] not in docs for c in x["relevant_chunks"]):
            bad["chunk_not_in_docs"] += 1
        if len(set(x["relevant_docs"])) != len(x["relevant_docs"]):
            bad["duplicate_docs"] += 1
        docs_added[len(tail_d)] += 1
        chunks_added[len(tail_c)] += 1
    size = a.new.stat().st_size
    report = {"queries": n, "violations": dict(bad), "en_docs_per_query": dict(sorted(docs_added.items())),
              "en_docs_mean": round(sum(k * v for k, v in docs_added.items()) / n, 3),
              "en_chunks_per_query": dict(sorted(chunks_added.items())), "zip_bytes": size, "under_limit": size <= a.limit,
              "ok": not bad and n == 1200 and size <= a.limit}
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
