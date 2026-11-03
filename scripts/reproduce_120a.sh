#!/usr/bin/env bash
# Rebuild the 120A-p4b-v3 submission (1_120A.zip, SHA256 34d235f6...37e2) and its EN-hedge copy (4_120A-en3.zip, e6c6384e...a954)
# without the two hand-off ZIPs lost in S44 (P1-vi+10.zip, P-A4-K90-ph.zip). CPU only, about 1 h 30 for both composes.
#
#   scripts/reproduce_120a.sh <work dir> <runs root> <P1-vi+10.approval.json> <p1_chunks.parquet | none>
#
# <runs root>: a directory whose runs/ holds the public score bundle (judge-public.tar extracted) plus the files listed in
#   DATA.md section 4 (run manifests and cal json from out-runs-meta.tar.xz, s26 full_doc_dense.npz,
#   s27-pharmacity handoff + vectors, s32-chunk-judge, s29 query_vectors.npz, s31 pool-extra/kaggle/judge_score.py).
#   The script writes below <work dir> and <runs root>/runs only: s49-120a/, the rebuilt pool13_index.parquet, pool.npz and
#   the s37/cmax*/pool shards (none of them is in the bundle).
# p1_chunks.parquet: the P1 chunk texts (see run.py p1-chunks); "none" builds only the --no-p1 version 120A-nop1.
#
# Steps (each prints a JSON report; any SHA mismatch stops the script):
#   kq        K_q / K90 / n13 per query from the P1-vi+10 approval audit -> kq_counts.parquet
#   pool13    s31 Pharmacity-extended pool13 index (lot-0003)            -> must be ecf0ea1b...
#   pool-npz  s37 cosine reference pool (not read by the cosine13 apply)  -> 45f69e56... expected, reported only
#   apply     s36.s37.apply 120A-p4b-v3                                  -> docsel 69540d84, carriers e9f543c9, pcal 61bbf036, keep 53b0e7a6
#   cmax-shards  s37 C-max chunk rows (cmax, b0004-b0009; deleted in S44)   -> b0008/b0009 byte-equal, the others content-equal
#   compose   --no-p1 (120A-nop1) and, with p1_chunks, the P1 text build -> 34d235f6...37e2
#   hedge     scripts/s48/hedge_on_zip.py N 3 on the P1 text build        -> e6c6384e...a954 (needs the en lane, data/s37_en)
#             and N 10 --chunk-top 3 (120A-en10)                          -> 09e3b019...b571
set -euo pipefail
WORK=${1:?work dir}; RUNS_ROOT=${2:?runs root}; APPROVAL=${3:?P1-vi+10.approval.json}; P1C=${4:?p1_chunks.parquet or none}
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/.." && pwd)
PY=${PY:-python}
export R2AI_DATA_DIR=${R2AI_DATA_DIR:-$(dirname "$RUNS_ROOT")/data} R2AI_OLD_ROOT=${R2AI_OLD_ROOT:-$(dirname "$RUNS_ROOT")/.no-old-root}   # data/ next to out/ (packages layout)
export R2AI_OUT_DIR=$RUNS_ROOT S49_KQ=$WORK/kq_counts.parquet PYTHONIOENCODING=utf-8 PYTHONPATH=$REPO/src
RUN="$PY $HERE/reproduce_120a/run.py"
OUT=$RUNS_ROOT/runs/s49-120a
mkdir -p "$WORK" "$OUT"

$RUN kq --approval "$APPROVAL" --out "$WORK/kq_counts.parquet"
$RUN pool13 --out "$WORK/pharmacity-ext"
cp "$WORK/pharmacity-ext/pool13_index.parquet" "$RUNS_ROOT/runs/s31-strong-judge/pharmacity-ext/pool13_index.parquet"
$RUN pool-npz --out "$WORK/pool.npz" || echo "pool.npz differs from 45f69e56 (not read by the cosine13 apply; see docs/THUYET_MINH.md)"
cp -n "$WORK/pool.npz" "$RUNS_ROOT/runs/s37/pool.npz" || true
$RUN apply --config "$REPO/configs/s36-handoff-120A-p4b-v3.json" --out "$OUT/apply"

A=$OUT/apply
# C-max chunk rows of the runs scored before the 120A build (pair_id -> t256 chunk); the 120ask window chunk is chosen from them.
# Checked by run.py: rows, and the per-pair max of the 0.6B scores equal the pinned cmax_scores*.parquet (b0008/b0009 also byte-equal).
$RUN cmax-shards || echo "cmax shards differ in bytes from the archived manifests (content checked separately)"
$RUN compose --docsel "$A/docsel-120A-p4b-v3.parquet" --carriers "$A/carriers-120A-p4b-v3.parquet" --name 120A-p4b-v3-full+w768 --out "$OUT/3b" --no-p1
if [ "$P1C" != none ]; then
  export S49_P1_CHUNKS=$P1C     # P1 chunk texts of the build, and the validator's verbatim source for them (also for en3 / en10)
  $RUN compose --docsel "$A/docsel-120A-p4b-v3.parquet" --carriers "$A/carriers-120A-p4b-v3.parquet" --name 120A-p4b-v3-full+w768 --out "$OUT/3c"
  Z=$OUT/3c/120A-p4b-v3-full+w768-t1536.zip
  test "$(sha256sum "$Z" | cut -d' ' -f1)" = 34d235f6f37704d11b803e83e9eddeabbf4c6100a38497c2728b56cb614937e2 || { echo "120A ZIP differs"; exit 1; }
  "$PY" "$REPO/scripts/s48/hedge_on_zip.py" --zip "$Z" --name 120A-p4b-v3-en3 --out "$WORK/en3" \
      --queries-npz "$RUNS_ROOT/runs/s26_query_vectors/s29_query_vectors.npz"
  test "$(sha256sum "$WORK/en3/120A-p4b-v3-en3.zip" | cut -d' ' -f1)" = e6c6384e00214a9b67da4a35945be294d668fe4987cf748d5388b446e4fca954 || { echo "en3 ZIP differs"; exit 1; }
  # 120A-en10 (5_120A-en10.zip): up to 10 en docs per query, chunks for the first 3 only (= the en part of en3)
  "$PY" "$REPO/scripts/s48/hedge_on_zip.py" --zip "$Z" --name 120A-p4b-v3-en10 --out "$WORK/en10" --n 10 --chunk-top 3 --queries-npz "$RUNS_ROOT/runs/s26_query_vectors/s29_query_vectors.npz"
  test "$(sha256sum "$WORK/en10/120A-p4b-v3-en10.zip" | cut -d' ' -f1)" = 09e3b019f02bbb9eecdd9062f46e3d5f261fee481061f9ae4c9a73910471b571 || { echo "en10 ZIP differs"; exit 1; }
  echo "120A, 120A-en3 and 120A-en10 rebuilt byte for byte"
fi
