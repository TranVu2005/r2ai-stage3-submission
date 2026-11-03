"""Rebuild the private submissions from the shared data packages and check every output ZIP against its SHA256.

    python -m r2ai.reproduce --list
    python -m r2ai.reproduce [--root DIR] <target> [<target> ...]
    python -m r2ai.reproduce [--root DIR] --all          # the 5 submitted files (SUBMISSIONS)

``--root`` (default: ``$R2AI_ROOT``, else the repository) is the directory the packages were extracted into: it holds ``data/``,
``out/runs/`` and ``submissions/`` (DATA.md). Each target belongs to one group, and a group is one run of an existing script:

    group   script                      targets
    public  scripts/reproduce_public.sh ch-rrf, d250-doconly            (R0, the CH-rrf build without P1 text, is checked inside)
    120a    scripts/reproduce_120a.sh   120a, 120a-en3, 120a-en10, 120a-nop1

``--all`` builds the 5 submitted files; ``120a-nop1`` is an extra check, run by name.
A group runs at most once, even when several of its targets are asked for. The scripts stop at the first SHA256 mismatch; this module then
checks each requested ZIP again: PASS only when the ZIP was written by this run and its SHA256 is the expected one. A table and a JSON
report (``<root>/out/runs/reproduce/report-<time>.json``) close the run; the script output goes to ``<root>/out/runs/reproduce/*.log``.
Exit code 0 only when every requested target passes.

Environment: ``R2AI_BASH`` (bash to run the scripts; on Windows Git Bash, not WSL), ``HF_HOME`` (BGE-M3 / Qwen3 tokenizers). ``HF_HUB_OFFLINE`` defaults to 1. CPU only; at most one group runs at a time (RAM).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"
INPUTS_120A = "out/runs/s49-120a/inputs"


@dataclass(frozen=True)
class Target:
    name: str
    group: str
    sha256: str
    zip: str          # output ZIP; {work} = the 120a work dir; relative to the root otherwise
    desc: str


TARGETS = {t.name: t for t in (
    Target("ch-rrf", "public", "b12b85912ba03ec45062fb817b806583c0182633a89feaa2ae4f1372767908c8",
           "out/runs/s49-public/chrrf/CH-rrf-full+w768-t1536.zip", "3_CHrrf.zip (CH-rrf)"),
    Target("d250-doconly", "public", "e26e38e98fe9be1ae7a30fc59c6684c5bef405eed8cc473cc467a64e4a1c26d0",
           "out/runs/s49-public/compose/P-D250-doconly.zip", "2_D250doconly.zip (D250-doconly)"),
    Target("120a", "120a", "34d235f6f37704d11b803e83e9eddeabbf4c6100a38497c2728b56cb614937e2",
           "out/runs/s49-120a/3c/120A-p4b-v3-full+w768-t1536.zip", "1_120A.zip (120A)"),
    Target("120a-en3", "120a", "e6c6384e00214a9b67da4a35945be294d668fe4987cf748d5388b446e4fca954",
           "{work}/en3/120A-p4b-v3-en3.zip", "4_120A-en3.zip (120A + 3 en docs)"),
    Target("120a-en10", "120a", "09e3b019f02bbb9eecdd9062f46e3d5f261fee481061f9ae4c9a73910471b571",
           "{work}/en10/120A-p4b-v3-en10.zip", "5_120A-en10.zip (120A + 10 en docs)"),
    Target("120a-nop1", "120a", "c76e2d3ee5d572163145775013d9e1ae0626c38b0f3145d94f1db6f7c0a85ecc",
           "out/runs/s49-120a/3b/120A-p4b-v3-full+w768-t1536.zip", "120A built from the canonical corpus only (reference)"),
)}
GROUP_ORDER = ("120a", "public")
SUBMISSIONS = ("120a", "d250-doconly", "ch-rrf", "120a-en3", "120a-en10")      # 1_ .. 5_ in submissions/
# inputs each group reads first; a missing one stops before the script starts
BTC_FILES = ["data/raw/query.parquet", "data/raw/links_corpus_vi_en_zh.parquet"]   # dataset AIGuruTinix/ViBioMIR, read by the validator
REQUIRED = {
    "public": ["data/canonical-20261018", "out/runs/s26_query_vectors", "out/runs/s27-pharmacity/handoff/cc-s27-pharmacity",
               "submissions/3_CHrrf.zip"],    # docsel gate of scripts/s45/public_rebuild.py: compared with, never read as input
    "120a": ["data/canonical-20261018", "data/s37_120ask", f"{INPUTS_120A}/P1-vi+10.approval.json", "out/runs/s26_query_vectors"],
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def posix(p: Path | str) -> str:
    return str(p).replace("\\", "/")


def find_bash() -> str:
    if os.environ.get("R2AI_BASH"):
        return os.environ["R2AI_BASH"]
    found = shutil.which("bash")
    if os.name == "nt":
        for cand in (r"C:\Program Files\Git\bin\bash.exe", r"C:\Program Files\Git\usr\bin\bash.exe"):
            if Path(cand).is_file() and (found is None or "system32" in found.lower() or "windowsapps" in found.lower()):
                return cand
    if found is None:
        raise SystemExit("bash not found: install Git Bash (Windows) or set R2AI_BASH")
    return found


def group_command(group: str, root: Path, targets: list[Target], work: Path) -> list[str]:
    if group == "public":
        cmd = [posix(SCRIPTS / "reproduce_public.sh"), posix(root)]
        if any(t.name == "ch-rrf" for t in targets):
            cmd.append(posix(root / INPUTS_120A / "p1_chunks_chrrf.parquet"))
        return cmd
    if group == "120a":
        only_nop1 = all(t.name == "120a-nop1" for t in targets)
        p1 = "none" if only_nop1 else posix(root / INPUTS_120A / "p1_chunks.parquet")
        return [posix(SCRIPTS / "reproduce_120a.sh"), posix(work), posix(root / "out"),
                posix(root / INPUTS_120A / "P1-vi+10.approval.json"), p1]
    raise ValueError(group)


def run_group(bash: str, cmd: list[str], log: Path, env: dict) -> int:
    log.parent.mkdir(parents=True, exist_ok=True)
    print(f"$ bash {' '.join(cmd)}\n  log: {log}", flush=True)
    with log.open("w", encoding="utf-8") as f, subprocess.Popen([bash, *cmd], cwd=REPO, env=env, stdout=subprocess.PIPE,
                                                                 stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                                                 errors="replace") as p:
        for line in p.stdout:
            sys.stdout.write(line)
            f.write(line)
        return p.wait()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m r2ai.reproduce", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("targets", nargs="*", metavar="target", help=", ".join(TARGETS))
    ap.add_argument("--all", action="store_true", help="the 5 submitted files: " + ", ".join(SUBMISSIONS))
    ap.add_argument("--list", action="store_true", help="print the targets and their SHA256, run nothing")
    ap.add_argument("--root", type=Path, default=Path(os.environ.get("R2AI_ROOT", REPO)),
                    help="directory the data packages were extracted into (default $R2AI_ROOT, else the repository)")
    ap.add_argument("--dry-run", action="store_true", help="print the commands only")
    a = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):      # script output is UTF-8 (progress bars, Vietnamese); a cp1252 console must not stop the run
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")

    if a.list:
        for t in TARGETS.values():
            print(f"{t.name:13s} {t.group:7s} {'submission' if t.name in SUBMISSIONS else 'check':10s} {t.desc}")
        return 0
    names = list(SUBMISSIONS) + a.targets if a.all else a.targets
    unknown = [n for n in names if n not in TARGETS]
    if not names or unknown:
        ap.error(f"unknown target(s) {unknown}" if unknown else "give a target, --all or --list")
    wanted = [TARGETS[n] for n in dict.fromkeys(names)]
    root = a.root.resolve()
    if not (root / "out/runs").is_dir():
        raise SystemExit(f"{root}/out/runs not found: extract the data packages (DATA.md) into --root / $R2AI_ROOT")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    work = root / "out/runs/s49-120a" / f"work-{stamp}"
    logs = root / "out/runs/reproduce"
    py = posix(sys.executable)
    if " " in py:
        raise SystemExit(f"the scripts call $PY unquoted: use a Python whose path has no space ({py})")
    env = dict(os.environ, PY=py, PYTHONIOENCODING="utf-8")
    env.setdefault("HF_HUB_OFFLINE", "1")
    bash = find_bash()

    results = []
    for group in GROUP_ORDER:
        targets = [t for t in wanted if t.group == group]
        if not targets:
            continue
        missing = [p for p in REQUIRED[group] + BTC_FILES if not (root / p).exists()]
        cmd = group_command(group, root, targets, work)
        started, rc, seconds = time.time(), None, 0.0
        if missing:
            print(f"[{group}] missing inputs below {root}: {missing} (extract the packages of DATA.md there)", flush=True)
        elif a.dry_run:
            print(f"$ bash {' '.join(cmd)}")
        else:
            print(f"\n[{group}] {time.strftime('%H:%M:%S')} start", flush=True)
            rc = run_group(bash, cmd, logs / f"{group}-{stamp}.log", env)
            seconds = time.time() - started
            print(f"[{group}] {time.strftime('%H:%M:%S')} exit {rc} after {seconds / 60:.1f} min", flush=True)
        for t in targets:
            z = root / t.zip.format(work=work.relative_to(root).as_posix())
            got = sha256(z) if z.is_file() and z.stat().st_mtime >= started and rc is not None else None
            status = "DRY-RUN" if a.dry_run and not missing else ("PASS" if got == t.sha256 else "FAIL")
            results.append({"target": t.name, "group": group, "status": status, "desc": t.desc, "expected": t.sha256, "sha256": got,
                            "zip": posix(z), "exit_code": rc, "missing_inputs": missing, "minutes": round(seconds / 60, 1)})

    print(f"\n{'target':13s} {'status':8s} {'submission':38s} zip")      # PASS = byte-equal to the submitted file
    for r in results:
        print(f"{r['target']:13s} {r['status']:8s} {r['desc']:38s} {r['zip']}")
    if not a.dry_run:
        logs.mkdir(parents=True, exist_ok=True)
        report = logs / f"report-{stamp}.json"
        report.write_text(json.dumps({"root": posix(root), "repo": posix(REPO), "python": py, "results": results}, indent=1) + "\n",
                          encoding="utf-8")
        print(f"report: {report}")
    return 0 if all(r["status"] in ("PASS", "DRY-RUN") for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
