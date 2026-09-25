"""Delivery gate: caller-relative inputs, template detection, one verdict."""
from __future__ import annotations

from support import SITE_ROOT, check, run_build_args, skip

import contextlib
import io
import os
import shutil
import tempfile
from pathlib import Path

from checks import check_placeholders
from deliver import detect_template, family
from optional_deps import MissingDepError, require_pymupdf, require_weasyprint_html
from shared import HTML_TEMPLATES, SCREEN_TEMPLATES, TEMPLATES


def test_relative_inputs_resolve_from_the_callers_directory() -> None:
    # Agents run the checks from the folder holding their document. Before
    # resolve_input, a relative path was joined onto the skill root and the
    # check reported "file not found" instead of checking the file.
    previous = Path.cwd()
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "doc.html").write_text("<p>{{TITLE}}</p>", encoding="utf-8")
        os.chdir(tmp)
        try:
            caller_relative = _captured(check_placeholders, ["doc.html"])
            skill_relative = _captured(check_placeholders, ["assets/templates/resume.html"])
        finally:
            os.chdir(previous)
    check("relative input resolves from the caller's directory",
          "unfilled placeholder(s): {{TITLE}}" in caller_relative, caller_relative)
    check("skill-relative input still resolves as the fallback",
          "unfilled placeholder" in skill_relative and "not found" not in skill_relative,
          skill_relative)


def test_author_meta_placeholder_is_left_for_the_renderer() -> None:
    # SKILL.md tells non-personal documents to leave the author placeholder so
    # render.py can stamp /Author; the placeholder gate must not then fail them.
    with tempfile.TemporaryDirectory() as tmp:
        left = Path(tmp, "left.html")
        left.write_text('<head><meta name="author" content="{{AUTHOR}}"></head><p>ok</p>', encoding="utf-8")
        missed = Path(tmp, "missed.html")
        missed.write_text('<head><meta name="author" content="{{AUTHOR}}"></head><h1>{{TITLE}}</h1>', encoding="utf-8")
        left_out = _captured(check_placeholders, [str(left)])
        missed_out = _captured(check_placeholders, [str(missed)])
    check("author meta placeholder is left for the renderer", "no placeholders" in left_out, left_out)
    check("other placeholders still fail beside it",
          "{{TITLE}}" in missed_out and "{{AUTHOR}}" not in missed_out, missed_out)


def _captured(fn, argv: list[str]) -> str:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        fn(argv)
    return buffer.getvalue()


def test_detect_template_recognizes_every_registered_template() -> None:
    sources = {name: spec.source for name, spec in HTML_TEMPLATES.items()}
    sources.update(SCREEN_TEMPLATES)
    misses = []
    for name, source in sources.items():
        detected, score = detect_template((TEMPLATES / source).read_text(encoding="utf-8"))
        if detected is None or family(detected) != family(name):
            misses.append(f"{name} -> {detected} ({score:.2f})")
    check("deliver detects the template family of every registered template", not misses,
          "; ".join(misses))
    check("deliver does not guess a template for bare HTML",
          detect_template("<html><body><p>hi</p></body></html>")[0] is None)


def test_deliver_reports_one_verdict_and_blocks_on_errors() -> None:
    try:
        require_weasyprint_html()
        require_pymupdf()
    except MissingDepError as exc:
        skip("deliver verdict", str(exc), ci_required=True)
        return
    demo = SITE_ROOT / "assets" / "demos" / "demo-letter.html"
    with tempfile.TemporaryDirectory() as tmp:
        clean = Path(tmp) / "letter.html"
        shutil.copy(demo, clean)
        rc_clean, out_clean = run_build_args(["--deliver", str(clean)])
        broken = Path(tmp) / "broken.html"
        broken.write_text(
            demo.read_text(encoding="utf-8").replace(
                "</body>", "<p>{{TODO}} [DATA NEEDED: signature date]</p></body>"),
            encoding="utf-8",
        )
        rc_broken, out_broken = run_build_args(["--deliver", str(broken)])
        rendered = (Path(tmp) / "letter.pdf").exists()
        images = sorted((Path(tmp) / "letter-visual").glob("page-*.png"))

    check("deliver recognizes the letter family", "template: letter" in out_clean, out_clean[:300])
    check("deliver renders the PDF next to the HTML", rendered)
    check("deliver exports page images for the perceptual pass", len(images) == 1, str(images))
    fonts_ok = "OK:    fonts" in out_clean
    if fonts_ok:
        check("clean filled letter is READY", rc_clean == 0 and "READY:" in out_clean, out_clean)
    check("unfilled placeholder blocks delivery",
          rc_broken == 1 and "NOT READY" in out_broken and "ERROR: placeholders" in out_broken,
          out_broken)
    check("data gaps are listed for the closing message",
          "GAP:   [DATA NEEDED: signature date]" in out_broken, out_broken)
