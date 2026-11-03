#!/usr/bin/env bash
# Rebuild the public-frame submissions R0 (= CH-rrf --no-p1, 0af2e5ca...0d83) and P-D250-doconly (2_D250doconly.zip, e26e38e9...26d0),
# and, with the P1 chunk texts of CH-rrf, try CH-rrf itself (3_CHrrf.zip, b12b8591...08c8). CPU only, about 1 h.
#
#   scripts/reproduce_public.sh <root> [p1_chunks_chrrf.parquet]
#
# <root>: checkout where the hand-off packages were extracted (data/ and out/runs/ of DATA.md). Writes below
# <root>/out/runs/s49-public (or $S49_PUBLIC_OUT) only, plus the C-max chunk rows of step 5 when they are missing. The S45 scripts read RUNS_DIR = <root>/out/runs (S45_RESTORE / R2AI_OUT_DIR = <root>/out).
set -euo pipefail
ROOT=${1:?root}; P1C=${2:-}
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/.." && pwd)
PY=${PY:-python}
export R2AI_DATA_DIR=${R2AI_DATA_DIR:-$ROOT/data} R2AI_OLD_ROOT=${R2AI_OLD_ROOT:-$ROOT/.no-old-root}
export R2AI_OUT_DIR=$ROOT/out S45_RESTORE=$ROOT/out R2AI_ROOT=$ROOT S45_CHRRF_ZIP=${S45_CHRRF_ZIP:-$ROOT/submissions/3_CHrrf.zip}
export PYTHONIOENCODING=utf-8 PYTHONPATH=$REPO/src
W=${S49_PUBLIC_OUT:-$ROOT/out/runs/s49-public}; mkdir -p "$W"
check() { test "$(sha256sum "$1" | cut -d' ' -f1)" = "$2" && echo "OK  $2  $1" || { echo "DIFF $1 (expected $2)"; return 1; }; }

# 1. exact cosine order of the public queries (S29 query vectors = the S26 q_dense / q_ids, SHA checked inside)
$PY "$REPO/scripts/s45/exact_top.py" "$ROOT/out/runs/s26_query_vectors" "$W/exact"
# 2. doc selection and carriers with the frozen private config (R0) and the depth-250 pool (P-D250)
$PY "$REPO/scripts/s45/public_rebuild.py" --top "$W/exact/top300.parquet" --out "$W/pub" --name R0
$PY "$REPO/scripts/s45/public_rebuild.py" --top "$W/exact/top300.parquet" --out "$W/pub" --name P-D250 --depth 250
A=$W/pub/apply; C=$W/compose
# 3. chunks: whole body + 768 window, canonical / 120ask / Pharmacity text only (--no-p1). R0 (29/10) was composed after S44 had
#    deleted the C-max chunk rows (s37/cmax*/pool/shards), so its 120ask windows come from the cosine top chunk: R2AI_CMAX_CHUNK_SCORES=none.
#    CH-rrf (27/10) and 120A were composed with those rows (rebuilt by scripts/reproduce_120a.sh step cmax-shards).
R2AI_CMAX_CHUNK_SCORES=none $PY -m r2ai.s38.compose run --name R0-full+w768 --docsel "$A/docsel-R0.parquet" --rule full+w768 --carriers "$A/carriers-R0.parquet" \
    --fit-carriers --rounds 10 --no-p1 --out "$C"
check "$C/R0-full+w768-t1536.zip" 0af2e5ca6196a3132710f6c779deaea4dc34b24bb5a57ba78813ab93204d0d83
# 4. P-D250-doconly: relevant_docs = docsel D250 + the R0 carriers it lacks; relevant_chunks byte for byte from R0
$PY "$REPO/scripts/s45/doc_only.py" "$C/R0-full+w768-t1536.zip" "$A/docsel-P-D250.parquet" "$C/P-D250-doconly.zip" \
    "$ROOT/out/runs/s27-pharmacity/handoff/cc-s27-pharmacity" "$C/R0-full+w768-t1536.validator-extra"
check "$C/P-D250-doconly.zip" e26e38e98fe9be1ae7a30fc59c6684c5bef405eed8cc473cc467a64e4a1c26d0
# 5. optional: CH-rrf with the P1 chunk texts; needs the C-max chunk rows (run scripts/reproduce_120a.sh first, step cmax-shards) (same stand-in as scripts/reproduce_120a; K_q is not used on this path)
if [ -n "$P1C" ]; then
  test -e "$ROOT/out/runs/s37/cmax/pool/shards/pool-93001.parquet" || $PY "$REPO/scripts/reproduce_120a/run.py" cmax-shards
  export S49_KQ=$ROOT/out/runs/s49-120a/inputs/kq_counts.parquet S49_P1_CHUNKS=$P1C
  $PY "$REPO/scripts/reproduce_120a/run.py" compose --docsel "$A/docsel-R0.parquet" --carriers "$A/carriers-R0.parquet" \
      --name CH-rrf-full+w768 --out "$W/chrrf"
  check "$W/chrrf/CH-rrf-full+w768-t1536.zip" b12b85912ba03ec45062fb817b806583c0182633a89feaa2ae4f1372767908c8
fi
