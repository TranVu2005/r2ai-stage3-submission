"""S49: rebuild the 120A-p4b-v3 submission (34d235f6...37e2) without the two lost hand-off ZIPs.

  run.py kq        --approval <P1-vi+10.approval.json> --out <kq_counts.parquet>
  run.py pool13    --out <dir>                 # s31 pharmacity_ext.prepare (lot-0003 only, as recorded) -> pool13_index.parquet
  run.py pool-npz  --out <pool.npz>            # s37.ingest.build_pool, S29 pool13 size = round(1.3 K_q) of kq_counts
  run.py apply     --config <json> --out <dir> # s36.s37.apply with the stand-ins of shim.py
  run.py compose   --docsel D --carriers C --name N --out <dir under RUNS_DIR> [--no-p1] [--threshold 1536]
  run.py p1-chunks --zip <120A.zip> --nop1-cache <3b base.parquet> --out <p1_chunks.parquet>

Every command reads ``R2AI_OUT_DIR`` (RUNS_DIR = its ``runs``) and ``S49_KQ``; nothing is written outside ``--out``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402



def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def cmd_kq(a: argparse.Namespace) -> dict:
    """K_q = len(relevant_docs) of P1-vi+10 = VI docs after the +10% quota + the preserved zh docs (approval audit, one row per query);
    K90 = len(relevant_docs) of K90-ph = round(0.9 K_q); n13 = round(1.3 K_q) (S29 pool13 size). Python round, as the builders."""
    approval = json.loads(Path(a.approval).read_text(encoding="utf-8"))
    if approval.get("zip_sha256") != "9e83ac7b634aeecfb2cfe91ef522249753b7ac3a845c330cdfbdc1d366221009":
        raise SystemExit("approval does not describe P1-vi+10.zip 9e83ac7b...")
    rows = [(int(r["query_id"]), int(r["vi_docs_after"]) + int(r["zh_docs_preserved"])) for r in approval["audit"]]
    frame = pd.DataFrame(rows, columns=["query_id", "K_q"]).sort_values("query_id").reset_index(drop=True)
    frame["K90"] = [round(0.9 * k) for k in frame.K_q]
    frame["n13"] = [round(1.3 * k) for k in frame.K_q]
    frame["source"] = "P1-vi+10.approval.json audit: vi_docs_after + zh_docs_preserved (json sha256 " + sha256(Path(a.approval)) + ")"
    checks = {"queries": len(frame) == 1200 and frame.query_id.is_unique, "n13_total_281924": int(frame.n13.sum()) == 281924,
              "K90_total_195147": int(frame.K90.sum()) == 195147}
    frame.to_parquet(a.out, index=False)
    return {"out": a.out, "sha256": sha256(Path(a.out)), "approval_sha256": sha256(Path(a.approval)), "K_q_total": int(frame.K_q.sum()),
            "n13_total": int(frame.n13.sum()), "K90_total": int(frame.K90.sum()), "checks": checks, "ok": all(checks.values())}


def cmd_pool13(a: argparse.Namespace) -> dict:
    from r2ai import paths
    from r2ai.s31 import pharmacity_ext

    pool_dir = paths.RUNS_DIR / "s31-strong-judge" / "pool"
    manifest = json.loads((paths.RUNS_DIR / "s31-strong-judge" / "pharmacity-ext" / "manifest.json").read_text(encoding="utf-8"))
    lots = [x["lot"] for x in manifest["new_lots"]]
    pharmacity_ext._new_lots = lambda inputs, m: lots         # the lots of the recorded run (lot-0003), not whatever is there today
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    report = pharmacity_ext.prepare(pool_dir, out)
    got = sha256(out / "pool13_index.parquet")
    return {"lots": lots, "pool13_index_sha256": got, "expected": manifest["pool13_index_sha256"], "ok": got == manifest["pool13_index_sha256"],
            "new_shard_sha256": sha256(out / "shards" / pharmacity_ext.NEW_SHARD), "expected_shard": manifest["new_shard_sha256"],
            "report": {k: report[k] for k in ("new_pairs_in_pool13", "evicted_pairs", "pool13_pairs") if k in report}}


def cmd_pool_npz(a: argparse.Namespace) -> dict:
    from r2ai.s37 import ingest

    kq = pd.read_parquet(os.environ["S49_KQ"])
    size13 = Path(a.out).with_name("s29_pool13_sizes.parquet")      # stand-in for S29 candidate_pool.parquet: its max cosine_rank per query
    pd.DataFrame({"query_id": kq.query_id.astype(np.int64), "cosine_rank": kq.n13.astype(np.int64), "cosine_score": 0.0}).to_parquet(size13, index=False)
    ingest.S29_POOL, ingest.POOL = size13, Path(a.out)
    ingest.build_pool(force=True)
    got = sha256(Path(a.out))
    return {"pool_npz_sha256": got, "expected": "45f69e563d2df74b983bc5441aeccad18251fe9606b5694bea335b2c87c31cdd",
            "ok": got == "45f69e563d2df74b983bc5441aeccad18251fe9606b5694bea335b2c87c31cdd"}


def remap(value):
    from r2ai import paths

    old_runs = paths.PIN_ORIGIN + "/out/runs"          # absolute prefix recorded in the pinned configs
    if isinstance(value, str) and value.replace("\\", "/").startswith(old_runs):
        return str(paths.RUNS_DIR / value.replace("\\", "/")[len(old_runs) + 1:])
    if isinstance(value, list):
        return [remap(v) for v in value]
    if isinstance(value, dict):
        return {k: remap(v) for k, v in value.items()}
    return value


def cmd_apply(a: argparse.Namespace) -> dict:
    import shim

    shim.install()
    from r2ai.s36 import s37

    cfg = remap(json.loads(Path(a.config).read_text(encoding="utf-8")))
    out = Path(a.out)
    s37.apply({**cfg, "out": str(out)})
    name = cfg["name"]
    expected = json.loads((ROOT / "configs" / "s36-handoff-s30-manifest.json").read_text(encoding="utf-8"))["builds"][name]["apply_outputs_sha256"]
    got = {f: sha256(out / f) for f in expected if not f.startswith("missing") and (out / f).exists()}
    differ = sorted(f for f in got if got[f] != expected[f])
    return {"name": name, "outputs": got, "differ": differ, "ok": not differ and len(got) == len([f for f in expected if not f.startswith("missing")])}


def cmd_compose(a: argparse.Namespace) -> dict:
    """``compose prepare`` then ``compose write --threshold T`` in this process (the stand-ins must be in place), like r2ai.release."""
    import shim

    shim.install()
    common = ["--out", a.out] + (["--no-p1"] if a.no_p1 else [])
    for argv in (["prepare", "--name", a.name, "--docsel", a.docsel, "--rule", "full+w768", "--carriers", a.carriers, *common],
                 ["write", "--name", a.name, "--threshold", str(a.threshold), "--drop", "0", *common]):
        sys.argv = ["r2ai.s38.compose", *argv]
        try:
            runpy.run_module("r2ai.s38.compose", run_name="__main__", alter_sys=True)
        except SystemExit as e:
            if e.code not in (0, None):
                raise
    label = f"{a.name}-t{a.threshold}"
    entry = json.loads((Path(a.out) / f"{label}.compose.json").read_text(encoding="utf-8"))
    return {k: entry.get(k) for k in ("zip", "zip_bytes", "zip_sha256", "docs", "chunks", "second_chunks", "under_ceiling", "validator")}


def rows_of(zp: Path):
    import zipfile

    with zipfile.ZipFile(zp) as z, z.open(z.namelist()[0]) as f:
        for line in f:
            line = line.strip().rstrip(b",")
            if line.startswith(b"{"):
                yield json.loads(line)


def cmd_p1_chunks(a: argparse.Namespace) -> dict:
    """The P1 chunk texts the 120A compose took: for every doc whose whole-body chunk in the submitted ZIP differs from the body the
    ``--no-p1`` build gives it (3b cache), every carrier of that doc with the ZIP's whole-body chunk (the first chunk of the doc in its
    row; the second one is the 768 window). A doc with any P1 chunk takes P1 text for all its carriers (S29 rule), so all are listed."""
    nop1 = pd.read_parquet(a.nop1_cache)
    body_col = "body" if "body" in nop1.columns else "chunk_text"
    base = {}
    for q, d, t in zip(nop1.query_id.astype(int), nop1.doc_id.astype(int), nop1[body_col]):
        base.setdefault((q, d), t)
    zipped = {}
    for r in rows_of(Path(a.zip)):
        seen = set()
        for c in r["relevant_chunks"]:
            d = int(c["doc_id"])
            if d not in seen:
                seen.add(d)
                zipped[(int(r["id"]), d)] = c["chunk_text"]
    missing = [(q, d) for (q, d) in zipped if (q, d) not in base]      # no source without P1 (the --no-p1 build skipped the carrier)
    differ_docs = {d for (q, d), t in zipped.items() if (q, d) in base and base[(q, d)] != t} | {d for _, d in missing}
    rows = [(q, d, 0, t) for (q, d), t in sorted(zipped.items()) if d in differ_docs]
    frame = pd.DataFrame(rows, columns=["query_id", "doc_id", "chunk_order", "chunk_text"])
    frame.to_parquet(a.out, index=False)
    return {"out": a.out, "sha256": sha256(Path(a.out)), "rows": len(frame), "docs": len(differ_docs),
            "carriers_differ": sum(1 for (q, d), t in zipped.items() if (q, d) in base and base[(q, d)] != t),
            "zip_carriers": len(zipped), "zip_carriers_not_in_nop1": len(missing)}


CMAX_RUNS = {"cmax": ["b0001", "b0002", "b0003"], **{b: [b] for b in ("b0004", "b0005", "b0006", "b0007", "b0008", "b0009")}}


def cmd_cmax_shards(a: argparse.Namespace) -> dict:
    """The C-max chunk rows (``s37/cmax*/pool/shards/pool-93001.parquet``: pair_id -> query, doc, t256 chunk) that S44 deleted; the
    compose takes the 120ask window chunk from their 0.6B scores. Only the runs scored before the 120A build of 25/10 21:51 (cmax,
    b0004-b0009); d300 (scored 25/10 22:06) and d400 (27/10) stay without rows, as at that build. Checked against the shard SHA256
    of each run's archived pool/manifest.json."""
    from r2ai.s37 import export

    out = {}
    for tag, batches in CMAX_RUNS.items():
        run = export.cmax_names(tag)[0]
        expected = json.loads((run / "pool" / "manifest.json").read_text(encoding="utf-8"))["shard_sha256"]
        export.export_cmax(tag, batches)
        got = sha256(run / "pool" / "shards" / export.SHARD_NAME)
        out[tag] = {"shard_sha256": got, "expected": expected, "ok": got == expected}
    return {"runs": out, "ok": all(v["ok"] for v in out.values())}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("kq"); p.add_argument("--approval", required=True); p.add_argument("--out", required=True)
    p = sub.add_parser("pool13"); p.add_argument("--out", required=True)
    p = sub.add_parser("pool-npz"); p.add_argument("--out", required=True)
    p = sub.add_parser("apply"); p.add_argument("--config", required=True); p.add_argument("--out", required=True)
    p = sub.add_parser("compose")
    for k in ("--docsel", "--carriers", "--name", "--out"):
        p.add_argument(k, required=True)
    p.add_argument("--no-p1", action="store_true"); p.add_argument("--threshold", type=int, default=1536)
    sub.add_parser("cmax-shards")
    p = sub.add_parser("p1-chunks")
    for k in ("--zip", "--nop1-cache", "--out"):
        p.add_argument(k, required=True)
    a = ap.parse_args()
    fn = {"kq": cmd_kq, "pool13": cmd_pool13, "pool-npz": cmd_pool_npz, "apply": cmd_apply, "compose": cmd_compose, "p1-chunks": cmd_p1_chunks,
          "cmax-shards": cmd_cmax_shards}[a.cmd]
    result = fn(a)
    print(json.dumps(result, indent=1, ensure_ascii=False, default=str))
    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
