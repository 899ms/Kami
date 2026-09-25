#!/usr/bin/env python3
"""Deterministic scoring for a `claude plugin eval` run of the Kami suite.

The eval harness grades what it can see (skill fired, files created, an LLM
read of the HTML). It cannot run Kami's own gates on the rendered PDF, so this
script walks each kept run workspace and applies them: page contract, atomic
fact survival in the PDF text, font family, density, Markdown residue, and
template style drift.

Run the suite with --keep-temp, then:
    python3 evals/score.py                     # newest results dir
    python3 evals/score.py evals/results/<ts>  # a specific run
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import re
import stat
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "skills" / "kami" / "scripts"))

from checks import check_density, check_markdown_residue, check_placeholders, check_resume_balance  # noqa: E402
from lint import check_style  # noqa: E402
from verify import check_fonts  # noqa: E402

# case -> (min pages, max pages or 0 for none, atomic facts that must appear in the PDF text)
CONTRACTS: dict[str, tuple[int, int, list[str]]] = {
    "resume-cn": (2, 2, ["林予安", "140", "900", "3.8", "1.6", "11%", "0.9%", "0.2%", "Sail UI", "1.8k"]),
    "one-pager-en": (1, 1, ["$1.2M", "$310K", "38", "214", "14%", "6%", "$6M", "Leeds"]),
    "equity-report-cn": (1, 3, ["18.4", "26.9", "35.2", "42.6", "21.3%", "增持", "128"]),
    "slides-en": (7, 12, ["400", "37", "41%", "88%", "23", "11 months"]),
    "letter-ko": (1, 1, ["박서연", "김도윤", "90초", "Kafka", "Flink", "18"]),
    "long-doc-cn": (3, 0, ["350", "18.5", "4.2", "12.1", "2.3", "94%", "81%", "97%"]),
}


def _quiet(fn, argv: list[str]) -> tuple[int, str]:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        try:
            code = fn(argv)
        except Exception as exc:  # a crashing gate is a failed gate, not a crashed scorer
            print(f"ERROR: {exc}")
            code = 2
    return code, buffer.getvalue().strip()


def _workspace(trace_path: str) -> Path | None:
    sealed = Path(trace_path).parent.parent / "sealed"
    if not sealed.exists():
        return None
    # The harness seals the run tree with mode 000; the scorer runs as its owner.
    sealed.chmod(sealed.stat().st_mode | stat.S_IRUSR | stat.S_IXUSR)
    cwd = sealed / "home" / "cwd"
    return cwd if cwd.exists() else None


def _deliverable(ws: Path) -> tuple[Path | None, Path | None]:
    pdfs = [p for p in ws.rglob("*.pdf") if not any(part.endswith("-visual") for part in p.parts)]
    if not pdfs:
        return None, None
    pdf = max(pdfs, key=lambda p: p.stat().st_mtime)
    html = pdf.with_suffix(".html")
    if not html.exists():
        htmls = list(ws.rglob("*.html"))
        html = max(htmls, key=lambda p: p.stat().st_mtime) if htmls else None
    return pdf, html


def _pdf_text(pdf: Path) -> tuple[int, str]:
    import fitz  # PyMuPDF, already a Kami check dependency

    with fitz.open(str(pdf)) as doc:
        return len(doc), "".join(page.get_text() for page in doc)


def score_run(case: str, run: dict) -> dict:
    row: dict = {
        "case": case,
        "cost": run.get("costUsd") or 0.0,
        "turns": run.get("turns"),
        "secs": run.get("durationSeconds"),
        "harness": run.get("score"),
        "error": run.get("error"),
    }
    ws = _workspace(run.get("tracePath") or "")
    if ws is None:
        row["note"] = "workspace not kept (run with --keep-temp)"
        return row
    pdf, html = _deliverable(ws)
    if pdf is None:
        row["note"] = "no PDF delivered"
        return row
    lo, hi, facts = CONTRACTS[case]
    pages, text = _pdf_text(pdf)
    flat = re.sub(r"\s+", "", text)
    found = [f for f in facts if re.sub(r"\s+", "", f) in flat]
    row.update({
        "pdf": str(pdf.relative_to(ws)),
        "pages": pages,
        "contract": lo <= pages and (hi == 0 or pages <= hi),
        "facts": f"{len(found)}/{len(facts)}",
        "missing": [f for f in facts if f not in found],
        "fonts": _quiet(check_fonts, [str(pdf)])[0] == 0,
        "density": _quiet(check_density, [str(pdf)])[0] == 0,
        "residue": _quiet(check_markdown_residue, [str(pdf)])[0] == 0,
    })
    if case == "resume-cn":
        row["balance"] = _quiet(check_resume_balance, [str(pdf)])[0] == 0
    if html is not None:
        row["placeholders"] = _quiet(check_placeholders, [str(html)])[0] == 0
        row["style"] = _quiet(check_style, [str(html)])[0] == 0
    return row


def gate_score(row: dict) -> float | None:
    """Share of deterministic gates passed, facts weighted as one gate."""
    if "pages" not in row:
        return 0.0 if row.get("note") == "no PDF delivered" else None
    gates = [row["contract"], row["fonts"], row["density"], row["residue"]]
    gates += [row[k] for k in ("balance", "placeholders", "style") if k in row]
    got, total = (int(x) for x in row["facts"].split("/"))
    return (sum(gates) + got / total) / (len(gates) + 1)


def main(argv: list[str]) -> int:
    results = HERE / "results"
    if len(argv) > 1:
        target = Path(argv[1])
    else:
        dirs = sorted(p for p in results.iterdir() if (p / "aggregate-result.json").exists())
        if not dirs:
            print("ERROR: no results found; run claude plugin eval . --keep-temp first")
            return 2
        target = dirs[-1]
    data = json.loads((target / "aggregate-result.json").read_text())
    rows = []
    for case in data["cases"]:
        name = case["name"]
        if name not in CONTRACTS:
            continue
        for run in case["arms"].get("with", []):
            rows.append(score_run(name, run))

    cols = ["case", "harness", "gates", "pages", "contract", "facts", "fonts", "density",
            "residue", "style", "placeholders", "balance", "turns", "secs", "cost"]
    print("\t".join(cols))
    total_cost = 0.0
    for row in rows:
        row["gates"] = gate_score(row)
        total_cost += row["cost"]
        cells = []
        for col in cols:
            value = row.get(col, "")
            if isinstance(value, bool):
                value = "ok" if value else "FAIL"
            elif isinstance(value, float):
                value = f"{value:.2f}"
            cells.append(str(value))
        print("\t".join(cells))
        for key in ("note", "error"):
            if row.get(key):
                print(f"  {row['case']}: {key}: {row[key]}")
        if row.get("missing"):
            print(f"  {row['case']}: missing facts: {', '.join(row['missing'])}")
    scored = [r["gates"] for r in rows if r["gates"] is not None]
    if scored:
        print(f"mean gate score {sum(scored) / len(scored):.2f} over {len(scored)} run(s); agent cost ${total_cost:.2f}")
    (target / "gate-scores.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
