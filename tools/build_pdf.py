"""THUYET_MINH.md -> THUYET_MINH.html -> THUYET_MINH.pdf (no pandoc / LaTeX on the build machine).

  uv run --with markdown==3.7 python tools/build_pdf.py [--chrome <chrome.exe>] [--values values.json]

``--values``: JSON {"TEN_DOI": "...", "LINK_REPO": "...", ...} fills the ``{{NAME}}`` placeholders (unfilled ones stay visible).
Figures (.svg kept as vectors, .png) are embedded as data URIs, so the HTML is a single file; an SVG figure gets a landscape A4
page of its own. PDF: headless Chrome ``--print-to-pdf``.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[1]
CSS = """
@page { size: A4; margin: 16mm 14mm; }
body { font-family: "Segoe UI", "Noto Sans", Arial, sans-serif; font-size: 10.5pt; line-height: 1.45; color: #111; }
h1 { font-size: 16pt; border-bottom: 2px solid #333; padding-bottom: 3px; margin-top: 22px; }
h2 { font-size: 13pt; margin-top: 16px; }
table { border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 9pt; page-break-inside: auto; }
th, td { border: 1px solid #999; padding: 3px 5px; vertical-align: top; }
th { background: #eee; }
tr { page-break-inside: avoid; }
code { font-family: Consolas, "Courier New", monospace; font-size: 8.5pt; word-break: break-all; }
pre { background: #f5f5f5; padding: 6px; white-space: pre-wrap; font-size: 8.5pt; break-inside: avoid; }
img { max-width: 100%; }
.title { text-align: center; margin-bottom: 18px; }
.title h1 { border: none; font-size: 20pt; }
@page wide { size: A4 landscape; margin: 10mm; }
.fig { page: wide; break-before: page; break-after: page; text-align: center; }
.fig img { width: 100%; max-height: 180mm; object-fit: contain; }
h1, h2 { break-after: avoid; }
"""


ITEM = re.compile(r"^(\s*)([*-]|\d+\.)\s")


def lists_for_python_markdown(text: str) -> str:
    """GitHub-style lists -> python-markdown: a blank line before a list that follows a paragraph line, and nested items
    (2-3 spaces under ``*``, 3 under ``1.``) indented by 4 spaces per level."""
    out, prev, in_code = [], "", False
    for line in text.splitlines():
        if line.startswith("```"):
            in_code = not in_code
        m = None if in_code else ITEM.match(line)
        if m:
            depth = (len(m.group(1)) + 1) // 3 if m.group(1) else 0
            line = " " * (4 * depth) + line.lstrip()
            if prev.strip() and not ITEM.match(prev) and not prev.startswith(" "):
                out.append("")
        out.append(line)
        prev = line
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path, default=ROOT / "docs" / "THUYET_MINH.md")
    ap.add_argument("--chrome", default="C:/Program Files/Google/Chrome/Application/chrome.exe")
    ap.add_argument("--values", type=Path)
    a = ap.parse_args()
    text = a.src.read_text(encoding="utf-8")
    meta = {}
    if text.startswith("---"):
        head, text = text[3:].split("\n---", 1)
        meta = dict(re.findall(r'^(\w+):\s*"?(.*?)"?\s*$', head, flags=re.M))
    values = json.loads(a.values.read_text(encoding="utf-8")) if a.values else {}
    fill = lambda s: re.sub(r"\{\{(\w+)\}\}", lambda m: values.get(m.group(1), m.group(0)), s)
    text, meta = fill(text), {k: fill(v) for k, v in meta.items()}

    def embed(m: re.Match) -> str:
        path = (a.src.parent / m.group(2)).resolve()
        data = base64.b64encode(path.read_bytes()).decode()
        mime = "image/svg+xml" if path.suffix == ".svg" else "image/png"
        return f'![{m.group(1)}](data:{mime};base64,{data})'

    text = re.sub(r"!\[([^\]]*)\]\(([^)]+\.(?:png|svg))\)", embed, text)
    text = lists_for_python_markdown(text)
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])
    body = re.sub(r'<p>(<img [^>]*src="data:image/svg\+xml[^>]*>)</p>', r'<div class="fig">\1</div>', body)
    title = f'<div class="title"><h1>{meta.get("title", "")}</h1><p>{meta.get("subtitle", "")}<br>{meta.get("date", "")}</p></div>'
    html = f'<!doctype html><html lang="vi"><head><meta charset="utf-8"><title>{meta.get("title", "")}</title><style>{CSS}</style></head><body>{title}{body}</body></html>'
    out_html = a.src.with_suffix(".html")
    out_html.write_text(html, encoding="utf-8")
    out_pdf = a.src.with_suffix(".pdf")
    subprocess.run([a.chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={out_pdf}", out_html.as_uri()],
                   check=True, capture_output=True)
    print(out_html, out_pdf, out_pdf.stat().st_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
