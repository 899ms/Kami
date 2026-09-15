"""Marp and Mermaid diagram tests."""
from __future__ import annotations

from support import REPO_ROOT, SKILL_ROOT, check, write_temp_html

import json
import re
import subprocess
import sys
import tempfile
from lint import scan_file
from pathlib import Path
from shared import TEMPLATES
from tokens import _mermaid_theme_drift


def test_marp_themes_token_synced() -> None:
    """Marp theme CSS keeps its :root tokens in sync with tokens.json.

    Locks the invariant AGENTS.md documents (tokens.py globs marp/*.css), so the
    Marp decks cannot silently drift even if that glob is later refactored away.
    """
    from shared import TOKENS_FILE
    from tokens import CSS_VAR, ROOT_BLOCK

    canonical = {k.lstrip("-"): v.strip().lower()
                 for k, v in json.loads(TOKENS_FILE.read_text(encoding="utf-8")).items()}
    marp_files = sorted((TEMPLATES / "marp").glob("*.css"))
    check("marp theme CSS present", len(marp_files) >= 1, f"found {len(marp_files)} file(s)")

    drift: list[str] = []
    checked = 0
    for path in marp_files:
        block = ROOT_BLOCK.search(path.read_text(encoding="utf-8", errors="replace"))
        if not block:
            continue
        checked += 1
        found = {m.group(1): m.group(2).strip().lower()
                 for m in CSS_VAR.finditer(block.group(1))}
        for name, expected in canonical.items():
            actual = found.get(name)
            if actual is not None and actual != expected:
                drift.append(f"{path.name}: --{name} expected {expected}, got {actual}")
    check("marp theme :root tokens match tokens.json",
          checked >= 1 and not drift,
          "; ".join(drift) if drift else f"checked {checked}, no :root block found")


def test_mermaid_theme_matches_tokens() -> None:
    from shared import TOKENS_FILE
    canonical = json.loads(TOKENS_FILE.read_text(encoding="utf-8"))
    issues = _mermaid_theme_drift(canonical)
    check("mermaid theme colors and role docs match tokens.json",
          issues == [],
          f"issues: {issues}")


def test_mermaid_theme_drift_flags_token_mismatch() -> None:
    from shared import TOKENS_FILE
    canonical = json.loads(TOKENS_FILE.read_text(encoding="utf-8"))
    canonical["--brand"] = "#000000"
    issues = _mermaid_theme_drift(canonical)
    check("mermaid theme drift flags accent token mismatch",
          any("accent" in issue and "--brand" in issue for issue in issues),
          f"issues: {issues}")


def test_mermaid_normalize_defaults_match_theme() -> None:
    import mermaid_normalize as mermaid_mod
    theme = json.loads((SKILL_ROOT / "references" / "mermaid-theme.json").read_text(encoding="utf-8"))
    expected_colors = {f"--{key}": value for key, value in theme["colors"].items()}
    check("mermaid normalizer fallback colors mirror mermaid-theme.json",
          mermaid_mod._DEFAULT_COLORS == expected_colors,
          f"default={mermaid_mod._DEFAULT_COLORS}, theme={expected_colors}")
    check("mermaid normalizer fallback font mirrors mermaid-theme.json",
          mermaid_mod._DEFAULT_FONT_STACK == theme["cssFontStack"],
          f"default={mermaid_mod._DEFAULT_FONT_STACK}, theme={theme['cssFontStack']}")


def test_mermaid_color_mix_srgb_single_pct() -> None:
    from mermaid_normalize import _Resolver
    r = _Resolver({"--fg": "#141413", "--bg": "#f5f4ed"})
    # color-mix(in srgb, fg 12%, bg) == 0.12*fg + 0.88*bg
    got = r.hex_of("color-mix(in srgb, var(--fg) 12%, var(--bg))")
    check("color-mix(in srgb, fg 12%, bg) resolves to warm gray",
          got == "#dad9d3", f"got {got}")


def test_mermaid_color_mix_both_pct() -> None:
    from mermaid_normalize import _Resolver
    r = _Resolver({"--bg": "#ffffff", "--c": "#000000"})
    got = r.hex_of("color-mix(in srgb, var(--bg) 75%, var(--c) 25%)")
    check("color-mix honors both explicit percentages", got == "#bfbfbf", f"got {got}")


def test_mermaid_normalize_strips_unsafe_features() -> None:
    from mermaid_normalize import normalize
    # Root carries a deliberately NON-Kami theme (red accent, white bg) to prove
    # the normalizer re-themes to the Kami palette regardless of source theme.
    raw = (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'style="--bg:#ffffff;--fg:#000000;--accent:#ff0000;background:var(--bg)">'
        "<style>@import url('https://fonts.googleapis.com/css2?family=Charter');\n"
        "  text { font-family: 'Charter', system-ui, sans-serif; }\n"
        "  svg { --_t: color-mix(in srgb, var(--fg) 25%, var(--bg)); }</style>"
        '<rect fill="var(--accent)" stroke="var(--fg)"/></svg>'
    )
    out = normalize(raw)
    check("normalize removes color-mix()", "color-mix(" not in out, out)
    check("normalize removes var()", "var(" not in out, out)
    check("normalize removes google-fonts import", "googleapis" not in out, out)
    check("normalize drops the quoted single-family bug", "'Charter'" not in out, out)
    check("normalize keeps the Kami CJK serif stack", "TsangerJinKai02" in out, out)
    check("normalize resolves fill to a static hex", 'fill="#' in out, out)
    check("normalize re-themes accent to Kami ink-blue",
          "#1b365d" in out.lower(), out)
    check("normalize drops the source theme's red accent",
          "#ff0000" not in out.lower(), out)


def test_mermaid_lint_flags_unnormalized_svg() -> None:
    body = '<svg><rect fill="color-mix(in srgb, #000000 50%, #ffffff)"/></svg>'
    path = write_temp_html(body, suffix=".html")  # not a screen-template name
    try:
        rules = {f.rule for f in scan_file(path)}
        check("scan_file flags un-normalized mermaid color-mix",
              "mermaid-color-mix" in rules, f"rules={rules}")
    finally:
        path.unlink(missing_ok=True)


def test_mermaid_diagram_templates_normalized() -> None:
    for name in ("sequence.html", "class.html", "er.html"):
        path = SKILL_ROOT / "assets" / "diagrams" / name
        check(f"diagram {name} exists", path.exists(), f"missing {path}")
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        check(f"{name} carries no color-mix()", "color-mix(" not in text)
        check(f"{name} carries no <foreignObject>", "<foreignObject" not in text)
        check(f"{name} carries no runtime web-font import", "googleapis" not in text)


def test_mermaid_diagrams_match_their_mmd_sources() -> None:
    """The committed diagram HTML must still carry every node/participant/entity
    label from its .mmd source. No Node regenerates these, so this guards against
    a .mmd edit that silently leaves the committed SVG stale."""
    src_dir = SKILL_ROOT / "assets" / "diagrams" / "src"
    sources = sorted(src_dir.glob("*.mmd"))
    check("diagram .mmd sources present", len(sources) >= 1, f"found {len(sources)}")
    for mmd in sources:
        html_path = SKILL_ROOT / "assets" / "diagrams" / f"{mmd.stem}.html"
        check(f"{mmd.stem}.html exists for {mmd.name}", html_path.exists())
        if not html_path.exists():
            continue
        labels: set[str] = set()
        for line in mmd.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            m = re.match(r"participant\s+\S+\s+as\s+(.+)", line)
            if m:
                labels.add(m.group(1).strip())
            m = re.match(r"class\s+(\w+)", line)
            if m:
                labels.add(m.group(1))
            labels.update(re.findall(r"\b([A-Z][A-Z_]{2,})\b", line))  # ER entities
        body = html_path.read_text(encoding="utf-8")
        missing = sorted(label for label in labels if label not in body)
        check(f"{mmd.stem}.html carries all {mmd.name} labels",
              not missing, f"missing labels (regenerate the diagram): {missing}")


def test_mermaid_normalize_rejects_non_beautiful_mermaid() -> None:
    """A non-beautiful-mermaid SVG (no --bg/--fg roles) must raise, not silently
    emit unresolved colors."""
    from mermaid_normalize import normalize
    raised = False
    try:
        normalize('<svg xmlns="http://www.w3.org/2000/svg"><rect fill="#000"/></svg>')
    except ValueError:
        raised = True
    check("normalize rejects input lacking --bg/--fg color roles", raised)


def test_mermaid_normalize_cli_accepts_output_before_input() -> None:
    """CLI parsing should accept both `input -o out` and `-o out input`."""
    script = SKILL_ROOT / "scripts" / "mermaid_normalize.py"
    raw = (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'style="--bg:#ffffff;--fg:#000000;--accent:#ff0000">'
        '<rect fill="var(--accent)" /></svg>'
    )
    with tempfile.TemporaryDirectory() as d:
        dp = Path(d)
        src = dp / "raw.svg"
        out = dp / "clean.svg"
        src.write_text(raw, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(script), "-o", str(out), str(src)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        body = out.read_text(encoding="utf-8") if out.exists() else ""
        check("mermaid_normalize CLI supports -o before input",
              result.returncode == 0 and out.exists() and "color-mix(" not in body and "var(" not in body,
              (result.stdout + result.stderr).strip())


def test_mermaid_normalize_cli_reports_missing_input() -> None:
    """Missing input should be a concise ERROR, not a Python traceback."""
    script = SKILL_ROOT / "scripts" / "mermaid_normalize.py"
    with tempfile.TemporaryDirectory() as d:
        result = subprocess.run(
            [sys.executable, str(script), str(Path(d) / "missing.svg")],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        combined = result.stdout + result.stderr
        check("mermaid_normalize CLI reports missing input without traceback",
              result.returncode == 1 and "ERROR:" in combined and "Traceback" not in combined,
              combined.strip())


def test_architecture_geometry_contract() -> None:
    from diagram_geometry import scan_geometry
    base = '''<svg><rect data-node="a" x="0" y="0" width="40" height="40"/>
    <rect data-node="b" x="120" y="0" width="40" height="40"/>
    <line data-edge="ab" data-from="a" data-to="b" x1="44" y1="20" x2="116" y2="20"/>
    <rect data-label-for="ab" x="60" y="10" width="40" height="10"/>
    <text x="65" y="18">任务入队</text></svg>'''
    check("geometry accepts a Chinese label and 4px connector standoff", not scan_geometry(base))
    cases = [
        (base.replace('data-to="b"', 'data-to="missing"'), "missing node"),
        (base.replace('x="120"', 'x="20"'), "overlap"),
        (base.replace('x1="44"', 'x1="90"'), "attach outward"),
        (base.replace('x1="44"', 'x1="38"'), "attach outward"),
        (base.replace('x2="116"', 'x2="44"'), "zero-length"),
        (base.replace('x1="44"', 'x1="NaN"'), "numeric"),
        (base.replace('x1="44"', 'x1'), "requires a numeric value"),
        (base.replace('x1="44"', 'x1="1e999"'), "finite"),
        (base.replace('width="40"', 'width="-40"', 1), "positive"),
        (base.replace('data-node="b"', 'data-node="a"'), "duplicate"),
        (base.replace('data-label-for="ab"', 'data-label-for="none"'), "matching edge"),
        (base.replace('x="60"', 'x="30"'), "overlaps node"),
        (base.replace('<svg>', '<svg><g transform="translate(10)">').replace('</svg>', '</g></svg>'), "direct coordinates"),
        (base.replace('data-edge="ab"', ''), "require data-edge"),
        (base.replace('</svg>', '<rect data-node="c" x="70" y="15" width="10" height="20"/></svg>'), "crosses node 'c'"),
        (base.replace('</svg>', '<rect data-label-for="other" x="70" y="5" width="20" height="10"/></svg>'), "label masks"),
    ]
    for html, expected in cases:
        findings = scan_geometry(html)
        check(f"geometry rejects {expected}", any(expected in message for _, message in findings), str(findings))
    check("unannotated Mermaid endpoints remain outside the contract", not scan_geometry('<svg><line data-from="a" data-to="b"/></svg>'))
    branch = base.replace('</svg>', '<rect x="110" y="-10" width="60" height="160" fill="none"/>'
                          '<rect data-node="c" x="120" y="100" width="40" height="40"/>'
                          '<polyline data-edge="ac" data-from="a" data-to="c" points="44,30 105,30 105,120 116,120"/></svg>')
    check("branches may cross an unmarked system boundary", not scan_geometry(branch), str(scan_geometry(branch)))
    crossing = base.replace('</svg>', '<rect data-label-for="other" x="70" y="18" width="20" height="8"/></svg>')
    check("edges cannot cross another label mask", any("crosses label mask" in m for _, m in scan_geometry(crossing)))
    check("independent SVGs may reuse semantic IDs", not scan_geometry(base + base))
    check("unmarked diagrams and comments are not interpreted as topology", not scan_geometry('<svg><!--'+base+'--></svg>'))
    polyline = base.replace('<line data-edge="ab" data-from="a" data-to="b" x1="44" y1="20" x2="116" y2="20"/>',
                            '<polyline data-edge="ab" data-from="a" data-to="b" points="44,20 60,20 116,20"/>')
    check("geometry accepts multi-segment paths", not scan_geometry(polyline))
    check("bare polyline points report an error", any("requires a numeric value" in m for _, m in scan_geometry(polyline.replace('points="44,20 60,20 116,20"', "points"))))
    for points, expected in [('44,20 60', 'complete points'), ('44,20 20,20 116,20', 'attach outward')]:
        bad = polyline.replace('44,20 60,20 116,20', points)
        check(f"geometry rejects polyline {expected}", any(expected in m for _, m in scan_geometry(bad)))
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'filled.html'
        path.write_text(base.replace('data-to="b"', 'data-to="missing"'))
        check("normal lint consumes diagram geometry", any(f.rule == 'diagram-geometry' for f in scan_file(path)))
    for name, nodes, edges in [('architecture', 5, 4), ('architecture-board', 6, 5)]:
        source = SKILL_ROOT / 'assets' / 'diagrams' / f'{name}.html'
        html = source.read_text()
        check(f"{name} keeps the annotated topology", html.count('data-node=') == nodes and html.count('data-edge=') == edges)
        check(f"{name} geometry is valid", not scan_geometry(html), str(scan_geometry(html)))
