"""S48: S26 validator with --no-p1 (the P1-vi+10.zip verbatim source is not on disk any more) through ``compose.run_validator``.

  validate_nop1.py <zip> <out_dir> <label> [extra_lot_dir ...]

Used as a differential: the same call on the base ZIP (120A) and on base + EN-hedge must report the same errors, so the en part adds none.
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from r2ai.s38 import compose  # noqa: E402

zp, out, label, extra = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], [Path(x) for x in sys.argv[4:]]
rows = []
import zipfile
with zipfile.ZipFile(zp) as z, z.open(z.namelist()[0]) as f:
    ids = set()
    for line in f:
        line = line.strip().rstrip(b',')
        if line.startswith(b'{'):
            ids.update(int(d) for d in json.loads(line)['relevant_docs'])
compose.NO_P1 = True
out.mkdir(parents=True, exist_ok=True)
res = compose.run_validator(out, label, 'full+w768', zp, ids, extra)
print(json.dumps(res, indent=1, default=str)[:3000])
