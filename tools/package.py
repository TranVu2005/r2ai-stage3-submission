"""Build the upload packages of tools/packages.json (S49 hand-off). Nothing is uploaded.

  python tools/package.py --root <checkout with data/ and out/> --out <dir> [--only name ...] [--dry-run]

For each package ``<name>``:
* ``<name>.tar`` (uncompressed: parquet / npz / zip are already compressed), or a byte copy of the ``copy`` source.
* ``<name>.SHA256SUMS``: ``sha256  path-inside-the-package`` for every file. The same list is stored inside the tar as
  ``SHA256SUMS-<name>.txt``. A copied tar gets the list of its members.

``<out>/SHA256SUMS`` lists the package files themselves. ``<out>/data-manifest.csv`` has one row per file:
package, path, bytes, sha256. Sources are only read; the script refuses to write into an existing package file.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import shutil
import sys
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
BLOCK = 1 << 20


def resolve(src: str, root: Path) -> Path:
    if src.startswith("repo:"):
        return root / src[5:]
    if src.startswith("abs:"):
        return Path(src[4:])
    raise ValueError(f"source must start with repo: or abs: ({src})")


def files_of(spec: dict, root: Path) -> list[tuple[Path, str]]:
    out = []
    for inc in spec["include"]:
        src = resolve(inc["src"], root)
        if src.is_file():
            out.append((src, inc["as"]))
        elif src.is_dir():
            for f in sorted(p for p in src.rglob("*") if p.is_file()):
                out.append((f, f"{inc['as']}/{f.relative_to(src).as_posix()}"))
        else:
            raise FileNotFoundError(src)
    names = [a for _, a in out]
    if len(set(names)) != len(names):
        raise ValueError(f"{spec['name']}: duplicate paths inside the package")
    return out


class Hashing(io.RawIOBase):
    """Read-through file object that hashes what tarfile reads."""

    def __init__(self, f):
        self.f, self.h = f, hashlib.sha256()

    def readable(self):
        return True

    def readinto(self, b):
        n = self.f.readinto(b)
        if n:
            self.h.update(memoryview(b)[:n])
        return n


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(BLOCK), b""):
            h.update(block)
    return h.hexdigest()


def tar_members(path: Path) -> list[tuple[str, int, str]]:
    rows = []
    with tarfile.open(path) as t:
        for m in t:
            if m.isfile():
                h = hashlib.sha256()
                f = t.extractfile(m)
                for block in iter(lambda: f.read(BLOCK), b""):
                    h.update(block)
                rows.append((m.name, m.size, h.hexdigest()))
    return rows


def build(spec: dict, root: Path, out: Path, dry: bool) -> list[tuple[str, str, int, str]]:
    name = spec["name"]
    if "from_tar" in spec:                                   # members of an existing tar under the given prefixes
        src = resolve(spec["from_tar"], root)
        target = out / f"{name}.tar"
        if dry:
            print(f"{name}: members of {src} under {len(spec['prefixes'])} prefixes")
            return []
        if target.exists():
            raise SystemExit(f"{target} exists")
        rows = []
        with tarfile.open(src) as s, tarfile.open(target, "w", format=tarfile.PAX_FORMAT) as t:
            for m in s:
                if m.isfile() and m.name.startswith(tuple(spec["prefixes"])):
                    data = s.extractfile(m).read()
                    t.addfile(m, io.BytesIO(data))
                    rows.append((m.name, m.size, hashlib.sha256(data).hexdigest()))
            listing = "".join(f"{h}  {a}\n" for a, _, h in rows).encode("utf-8")
            info = tarfile.TarInfo(f"SHA256SUMS-{name}.txt")
            info.size = len(listing)
            t.addfile(info, io.BytesIO(listing))
        (out / f"{name}.SHA256SUMS").write_text("".join(f"{h}  {a}\n" for a, _, h in rows), encoding="utf-8", newline="\n")
        return [(name, a, s_, h) for a, s_, h in rows]
    if "copy" in spec:
        src = resolve(spec["copy"], root)
        target = out / (name + "".join(src.suffixes))
        if dry:
            print(f"{name}: copy {src} ({src.stat().st_size:,} B)")
            return []
        if target.exists():
            raise SystemExit(f"{target} exists")
        shutil.copyfile(src, target)
        rows = tar_members(target)
    else:
        items = files_of(spec, root)
        total = sum(f.stat().st_size for f, _ in items)
        print(f"{name}: {len(items):,} files, {total:,} B", flush=True)
        if dry:
            return [(name, a, f.stat().st_size, "") for f, a in items]
        target = out / f"{name}.tar"
        if target.exists():
            raise SystemExit(f"{target} exists")
        rows = []
        with tarfile.open(target, "w", format=tarfile.PAX_FORMAT) as t:
            for f, arc in items:
                info = t.gettarinfo(str(f), arcname=arc)
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                with open(f, "rb") as raw:
                    wrapped = Hashing(raw)
                    t.addfile(info, io.BufferedReader(wrapped, BLOCK))
                rows.append((arc, info.size, wrapped.h.hexdigest()))
            listing = "".join(f"{h}  {a}\n" for a, _, h in rows).encode("utf-8")
            info = tarfile.TarInfo(f"SHA256SUMS-{name}.txt")
            info.size = len(listing)
            t.addfile(info, io.BytesIO(listing))
    (out / f"{name}.SHA256SUMS").write_text("".join(f"{h}  {a}\n" for a, _, h in rows), encoding="utf-8", newline="\n")
    return [(name, a, s, h) for a, s, h in rows]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    specs = json.loads((HERE / "packages.json").read_text(encoding="utf-8"))["packages"]
    if a.only:
        specs = [s for s in specs if s["name"] in a.only]
    a.out.mkdir(parents=True, exist_ok=True)
    manifest = []
    for spec in specs:
        manifest += build(spec, a.root, a.out, a.dry_run)
    if a.dry_run:
        return 0
    with open(a.out / "data-manifest.csv", "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if f.tell() == 0:
            w.writerow(["package", "path", "bytes", "sha256"])
        w.writerows(manifest)
    sums = sorted(p for p in a.out.iterdir() if p.is_file() and p.name.startswith("r2ai-") and not p.name.endswith(".SHA256SUMS"))
    (a.out / "SHA256SUMS").write_text("".join(f"{sha256(p)}  {p.name}\n" for p in sums), encoding="utf-8", newline="\n")   # LF: sha256sum -c reads CR as part of the name
    print((a.out / "SHA256SUMS").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
