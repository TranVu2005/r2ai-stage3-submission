"""S48: EN-hedge on a finished public ZIP (120A-p4b-v3) through ``r2ai.s43.enhedge`` unchanged. Same mechanism and threshold as the
S43 ZIP ``ce0fabc0…8742`` (N 3, X 0.5226, en lane top-N by BGE-M3 cosine, one full-body chunk per en doc, en docs/chunks after the base ones).

  hedge_on_zip.py --zip <120A.zip> --name 120A-en3 --out <dir> [--n 3] [--chunk-top K] [--min-cos 0.5226] [--limit 101000000]
                  [--queries-npz <s29_query_vectors.npz>] [--compare-zip <ce0fabc0.zip>]

Query vectors: S29 ``s29_query_vectors.npz`` (SHA256 eed0e104…edca, checked). ``--limit`` is only checked here (report ``under_limit``); the ZIP is
written either way and the base is never cut. ``--chunk-top K`` (S49): only the first K en docs of a query get their chunk,
the others are doc-only (default: all N, the S48 behaviour). ``--compare-zip``: the en docs per query of that ZIP must equal the hedge computed here.
"""
import argparse, hashlib, json, sys, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
import numpy as np  # noqa: E402
from r2ai import paths  # noqa: E402
from r2ai.s36 import enlane  # noqa: E402
from r2ai.s43 import enhedge  # noqa: E402

QSHA = 'eed0e1046ffce6925987d21fdf832b99d548a7837c592ef21cf75e48cb02edca'


def rows_of(zp):
    with zipfile.ZipFile(zp) as z, z.open(z.namelist()[0]) as f:
        for line in f:
            line = line.strip().rstrip(b',')
            if line.startswith(b'{'):
                yield json.loads(line)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--zip', type=Path, required=True); ap.add_argument('--name', required=True); ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--n', type=int, default=3); ap.add_argument('--chunk-top', type=int, default=None); ap.add_argument('--min-cos', type=float, default=0.5226); ap.add_argument('--limit', type=int, default=101_000_000)
    ap.add_argument('--queries-npz', type=Path, default=Path('<ARCHIVE>/s26_query_vectors/s29_query_vectors.npz'))
    ap.add_argument('--compare-zip', type=Path, default=None)
    a = ap.parse_args()
    sha = hashlib.sha256(a.queries_npz.read_bytes()).hexdigest()
    if sha != QSHA:
        sys.exit(f'{a.queries_npz} is {sha}, not {QSHA}')
    with np.load(a.queries_npz) as z:
        q_ids, q_dense = z['q_ids'].astype(np.int64), np.array(z['q_dense'], copy=True)
    hedge = enhedge.choose(enhedge.lane_pairs(q_ids, q_dense, a.n), a.n, a.min_cos)
    per_q = hedge.groupby('query_id').size().reindex(sorted(int(q) for q in q_ids), fill_value=0)
    out = a.out.resolve()
    rep = enhedge.run(a.zip.resolve(), hedge, out, a.name, None, a.chunk_top)
    rep.pop('under_ceiling', None); rep.pop('limit_bytes', None)
    rep.update({'n': a.n, 'chunk_top': a.chunk_top, 'min_cos': a.min_cos, 'queries_npz_sha256': sha, 'limit': a.limit, 'under_limit': rep['zip_bytes'] <= a.limit,
                'en_per_query_mean': float(per_q.mean()), 'en_per_query_min': int(per_q.min()), 'en_queries_lt_n': int((per_q < a.n).sum())})
    if a.compare_zip:
        lane = set(enlane.load_vectors()[0].tolist())
        ref = {int(r['id']): [d for d in r['relevant_docs'] if d in lane] for r in rows_of(a.compare_zip)}
        mine = {int(r['id']): [d for d in r['relevant_docs'] if d in lane] for r in rows_of(rep['zip'])}
        rep['en_equals_compare_zip'] = ref == mine
    (out / f'{a.name}.hedge-on-zip.json').write_text(json.dumps(rep, indent=1, ensure_ascii=False, default=str), encoding='utf-8')
    keys = ('n', 'chunk_top', 'min_cos', 'en_per_query_mean', 'en_per_query_min', 'en_queries_lt_n', 'en_equals_compare_zip', 'zip', 'zip_bytes', 'zip_sha256', 'limit', 'under_limit', 'docs', 'chunks', 'base_docs_prefix_kept')
    print(json.dumps({k: rep[k] for k in keys if k in rep}, indent=1))
    print('validator:', json.dumps(rep['validator'], default=str)[:600])


if __name__ == '__main__':
    main()
