"""S48: structural check of base + EN-hedge. check_hedge_zip.py <base.zip> <hedge.zip> [--limit 101000000]

Row by row (streamed): same ids in the same order; base relevant_docs / relevant_chunks are an exact prefix of the hedge row (vi/zh part 100% equal);
the tail is en lane docs only, each with one chunk; chunk doc_id subset of relevant_docs; 1,200 rows; ZIP bytes <= limit; SHA256.
"""
import argparse, hashlib, json, sys, zipfile
from pathlib import Path
import numpy as np


def rows_of(zp):
    with zipfile.ZipFile(zp) as z, z.open(z.namelist()[0]) as f:
        for line in f:
            line = line.strip().rstrip(b',')
            if line.startswith(b'{'):
                yield json.loads(line)


ap = argparse.ArgumentParser(); ap.add_argument('base', type=Path); ap.add_argument('hedge', type=Path); ap.add_argument('--limit', type=int, default=101_000_000)
a = ap.parse_args()
with np.load('data/s37_en/seg37900-en-pubmed/vectors.npz') as z:
    en = set(z['doc_ids'].astype(np.int64).tolist())
n = bad_prefix = bad_chunk_subset = tail_not_en = tail_chunk_mismatch = base_has_en = 0
per_q = []
for b, h in zip(rows_of(a.base), rows_of(a.hedge)):
    n += 1
    if b['id'] != h['id']:
        sys.exit(f'row {n}: id order differs')
    kd, kc = len(b['relevant_docs']), len(b['relevant_chunks'])
    bad_prefix += not (h['relevant_docs'][:kd] == b['relevant_docs'] and h['relevant_chunks'][:kc] == b['relevant_chunks'])
    base_has_en += sum(d in en for d in b['relevant_docs'])
    td, tc = h['relevant_docs'][kd:], h['relevant_chunks'][kc:]
    per_q.append(len(td)); tail_not_en += sum(d not in en for d in td)
    tail_chunk_mismatch += [c['doc_id'] for c in tc] != td
    bad_chunk_subset += not {c['doc_id'] for c in h['relevant_chunks']} <= set(h['relevant_docs'])
size = a.hedge.stat().st_size
rep = {'rows': n, 'base_prefix_violations': bad_prefix, 'base_docs_already_en': base_has_en, 'tail_docs_not_en': tail_not_en, 'tail_chunks_not_matching_tail_docs': tail_chunk_mismatch,
       'chunk_not_subset_of_docs_rows': bad_chunk_subset, 'en_per_query_mean': round(float(np.mean(per_q)), 3), 'en_per_query_dist': {int(k): int(v) for k, v in zip(*np.unique(per_q, return_counts=True))},
       'zip_bytes': size, 'limit': a.limit, 'under_limit': size <= a.limit, 'sha256': hashlib.sha256(a.hedge.read_bytes()).hexdigest()}
print(json.dumps(rep, indent=1))
sys.exit(0 if (n == 1200 and not bad_prefix and not tail_not_en and not tail_chunk_mismatch and not bad_chunk_subset and size <= a.limit) else 1)
