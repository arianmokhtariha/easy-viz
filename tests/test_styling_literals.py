"""No styling literals in ``src/easy_viz/plots/``.

Colours, fonts and sizes come from the theme or from ``easy_viz.config``, so one
change restyles every chart. The scan reads the source with ``ast``: comments and
docstrings (a string that is a statement on its own) are never inspected.

What counts as a styling literal
--------------------------------
* **hex colour**: a string containing ``#rgb``, ``#rgba``, ``#rrggbb`` or
  ``#rrggbbaa``.
* **colour function**: a string containing ``rgb(``, ``rgba(``, ``hsl(`` or
  ``hsla(``.
* **colour name**: a string literal given to a colour keyword: a name ending in
  ``color`` (``line_color``, ``bgcolor``, ...) but not the bare ``color``,
  because ``color`` is also the column parameter of every plot function; ``colorscale``
  or ``colorway``; or ``color`` inside a ``font``, ``marker`` or ``line`` spec,
  where it is always a colour. A bare ``color="red"`` is therefore not detected.
* **font family**: a string given to ``family`` or ``*_family`` (keyword or dict key),
  a font stack (comma list containing ``sans-serif``, ``serif``, ``monospace`` ...)
  or a ``font-family:`` CSS declaration.
* **pixel size**: a number literal (not 0, not a bool) in one of these places, found
  in call keywords, ``dict(...)`` calls, dict literals and parameter defaults:

  - ``font_size``, ``*font_size``, ``fontsize``, ``marker_size``, ``line_width``,
    ``linewidth``, ``marker_line_width``, ``margin_l/r/t/b/pad``;
  - ``size`` inside a ``font`` or ``marker`` spec (outside them it can be a data
    unit, e.g. histogram ``xbins``);
  - ``width`` inside a ``line`` spec (a bar's own ``width`` is in axis units);
  - ``l``, ``r``, ``t``, ``b``, ``pad`` inside a ``margin`` spec;
  - ``width`` or ``height`` anywhere, but only as an ``int`` above 1: ``0``/``1`` and
    floats such as ``width=0.8`` are axis-unit or sentinel values, not pixels.
  - a string containing a CSS length such as ``12px``.

Not detected (known limits): computed values (``width=2 * 450``), assignments
(``fig.layout.width = 900``), named colours given to a bare ``color``.
"""

import ast
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLOTS = ROOT / "src" / "easy_viz" / "plots"

HEX_COLOUR = re.compile(
    r"(?<![\w&])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})(?!\w)"
)
COLOUR_FUNCTION = re.compile(r"\b(?:rgb|rgba|hsl|hsla)\(", re.IGNORECASE)
CSS_FONT_FAMILY = re.compile(r"font-family\s*:", re.IGNORECASE)
CSS_PIXELS = re.compile(r"(?<![\w.])\d+(?:\.\d+)?px\b")
GENERIC_FAMILIES = frozenset(
    {"serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui"}
)

# Keywords that are always a pixel size, whatever surrounds them.
PIXEL_KEYWORDS = frozenset(
    {"fontsize", "marker_size", "line_width", "linewidth", "marker_line_width"}
    | {f"margin_{side}" for side in ("l", "r", "t", "b", "pad")}
)
MARGIN_KEYS = frozenset({"l", "r", "t", "b", "pad"})
COLOUR_KEYWORDS = frozenset({"colorscale", "colorway"})
# Spec names (the keyword or key that encloses a dict) in which a key means a pixel
# size or a colour. Matched against the end of the enclosing name, lower-cased.
FONT_OR_MARKER = re.compile(r"(?:font|marker)$")
FONT_MARKER_OR_LINE = re.compile(r"(?:font|marker|line)$")
LINE = re.compile(r"line$")
MARGIN = re.compile(r"margin$")


@dataclass(frozen=True)
class Finding:
    """One styling literal: where it is, what kind it is, and its text."""

    line: int
    kind: str
    text: str


def _number(node: ast.expr) -> tuple[float, bool] | None:
    """Return ``(value, is_int)`` for a plain (optionally signed) number literal."""
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub | ast.UAdd):
        inner = _number(node.operand)
        if inner is None:
            return None
        return (-inner[0] if isinstance(node.op, ast.USub) else inner[0]), inner[1]
    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, int | float)
        and not isinstance(node.value, bool)
    ):
        return float(node.value), isinstance(node.value, int)
    return None


def _string_kinds(value: str) -> list[str]:
    """Kinds of styling found inside a string literal, regardless of where it sits."""
    kinds = []
    if HEX_COLOUR.search(value):
        kinds.append("hex colour")
    if COLOUR_FUNCTION.search(value):
        kinds.append("colour function")
    if CSS_FONT_FAMILY.search(value) or _is_font_stack(value):
        kinds.append("font family")
    if CSS_PIXELS.search(value):
        kinds.append("pixel size")
    return kinds


def _is_font_stack(value: str) -> bool:
    tokens = [token.strip(" '\"").lower() for token in value.split(",")]
    return len(tokens) >= 2 and any(token in GENERIC_FAMILIES for token in tokens)


def _is_pixel_pair(name: str, ctx: str, value: float, is_int: bool) -> bool:
    if name in PIXEL_KEYWORDS or name.endswith("font_size"):
        return True
    if name == "size":
        return bool(FONT_OR_MARKER.search(ctx))
    if name in MARGIN_KEYS:
        return bool(MARGIN.search(ctx))
    if name == "width" and LINE.search(ctx):
        return True
    return name in ("width", "height") and is_int and value > 1


class _Scanner(ast.NodeVisitor):
    """Walks a module and collects styling literals.

    ``_ctx`` is the name of the spec being filled in: for
    ``font=dict(size=12)`` it is ``font`` while ``size=12`` is checked; for
    ``go.Font(size=12)`` it is the class name. Plain function calls and
    ``dict(...)`` inherit nothing useful, so their keywords see an empty or the
    enclosing name.
    """

    def __init__(self) -> None:
        self.findings: dict[tuple[int, int, str], Finding] = {}
        self._ctx = ""

    def _add(self, node: ast.expr, kind: str, text: str) -> None:
        key = (node.lineno, node.col_offset, kind)
        self.findings.setdefault(key, Finding(node.lineno, kind, text))

    def _check_pair(self, name: str, value: ast.expr) -> None:
        ctx = self._ctx.lower()
        number = _number(value)
        if number is not None:
            if number[0] != 0 and _is_pixel_pair(name, ctx, *number):
                self._add(value, "pixel size", f"{name}={ast.unparse(value)}")
            return
        if not (isinstance(value, ast.Constant) and isinstance(value.value, str)):
            return
        text = f"{name}={value.value!r}"
        if not value.value.strip():
            return
        if name == "family" or name.endswith("_family"):
            self._add(value, "font family", text)
        elif not _string_kinds(value.value) and (
            (name != "color" and name.endswith("color"))
            or name in COLOUR_KEYWORDS
            or (name == "color" and FONT_MARKER_OR_LINE.search(ctx))
        ):
            self._add(value, "colour name", text)

    def _descend(self, name: str, value: ast.expr) -> None:
        saved, self._ctx = self._ctx, name
        self.visit(value)
        self._ctx = saved

    def visit_Expr(self, node: ast.Expr) -> None:
        # A bare string statement is a docstring or comment-like text: skip it.
        if not (
            isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
        ):
            self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str):
            for kind in _string_kinds(node.value):
                self._add(node, kind, repr(node.value))

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
        saved = self._ctx
        if name != "dict":  # dict(...) keeps the enclosing spec's name
            self._ctx = name
        for keyword in node.keywords:
            if keyword.arg is not None:
                self._check_pair(keyword.arg, keyword.value)
                self._descend(keyword.arg, keyword.value)
            else:
                self.visit(keyword.value)
        self._ctx = saved
        self.visit(func)
        for arg in node.args:
            self.visit(arg)

    def visit_Dict(self, node: ast.Dict) -> None:
        for key, value in zip(node.keys, node.values, strict=True):
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                self._check_pair(key.value, value)
                self._descend(key.value, value)
            else:
                if key is not None:
                    self.visit(key)
                self.visit(value)

    def visit_arguments(self, node: ast.arguments) -> None:
        positional = [*node.posonlyargs, *node.args]
        saved, self._ctx = self._ctx, ""
        for arg, default in zip(positional[::-1], node.defaults[::-1], strict=False):
            self._check_pair(arg.arg, default)
        for arg, default in zip(node.kwonlyargs, node.kw_defaults, strict=True):
            if default is not None:
                self._check_pair(arg.arg, default)
        self._ctx = saved
        self.generic_visit(node)


def detect_styling_literals(source: str) -> list[Finding]:
    """Return every styling literal in ``source``, ordered by line."""
    scanner = _Scanner()
    scanner.visit(ast.parse(source))
    return sorted(scanner.findings.values(), key=lambda f: (f.line, f.kind))


def test_plots_contain_no_styling_literals() -> None:
    messages = [
        f"{path.relative_to(ROOT).as_posix()}:{finding.line}: {finding.kind} "
        f"literal {finding.text}. Take it from the theme (colours, fonts, sizes) "
        f"or from easy_viz.config (default width), or add a Theme field."
        for path in sorted(PLOTS.rglob("*.py"))
        for finding in detect_styling_literals(path.read_text(encoding="utf-8"))
    ]
    assert not messages, "\n" + "\n".join(messages)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        # --- hex colours -------------------------------------------------------
        pytest.param('c = "#fff"', ["hex colour"], id="hex3"),
        pytest.param('c = "#abcd"', ["hex colour"], id="hex4"),
        pytest.param('c = "#1F77B4"', ["hex colour"], id="hex6-upper"),
        pytest.param('c = "#1f77b480"', ["hex colour"], id="hex8"),
        pytest.param('c = f"{x} #abc"', ["hex colour"], id="inside-f-string"),
        pytest.param(
            "html = \"<span style='color:#ff0000'>x</span>\"",
            ["hex colour"],
            id="in-html",
        ),
        pytest.param('c = "#12345"', [], id="5-digits-is-not-a-colour"),
        pytest.param('c = "#1234567"', [], id="7-digits-is-not-a-colour"),
        pytest.param('c = "#ghi"', [], id="not-hex-digits"),
        pytest.param('t = "Top #1 customers"', [], id="rank-sign"),
        pytest.param('t = "&#123; entity"', [], id="html-entity"),
        pytest.param("# colour #fff in a comment\nx = 1", [], id="comment"),
        pytest.param(
            'def f():\n    """Uses #fff and rgb(1,2,3)."""\n', [], id="docstring"
        ),
        # --- colour functions --------------------------------------------------
        pytest.param('c = "rgb(1, 2, 3)"', ["colour function"], id="rgb"),
        pytest.param('c = "RGBA(1,2,3,.5)"', ["colour function"], id="rgba-upper"),
        pytest.param('c = "hsl(10, 50%, 50%)"', ["colour function"], id="hsl"),
        pytest.param('c = "argb(1)"', [], id="word-ending-in-rgb"),
        # --- colour names ------------------------------------------------------
        pytest.param('f(line_color="red")', ["colour name"], id="line_color"),
        pytest.param('f(paper_bgcolor="white")', ["colour name"], id="bgcolor"),
        pytest.param('f(colorscale="Viridis")', ["colour name"], id="colorscale"),
        pytest.param(
            'f(marker=dict(color="red"))', ["colour name"], id="color-in-marker-spec"
        ),
        pytest.param(
            'f(font={"color": "grey"})', ["colour name"], id="color-in-font-dict"
        ),
        pytest.param(
            'f(line_color="#fff")', ["hex colour"], id="one-finding-per-literal"
        ),
        pytest.param('bar_plot(df, "x", color="region")', [], id="color-is-a-column"),
        pytest.param("f(line_color=theme.accent)", [], id="colour-from-theme"),
        pytest.param("f(line_color=None)", [], id="colour-none"),
        # --- font families -----------------------------------------------------
        pytest.param('f(font=dict(family="Arial"))', ["font family"], id="family-kw"),
        pytest.param('f(font_family="Inter")', ["font family"], id="font_family-kw"),
        pytest.param('d = {"family": "Arial"}', ["font family"], id="family-dict-key"),
        pytest.param('s = "Inter, sans-serif"', ["font family"], id="font-stack"),
        pytest.param('s = "font-family: Inter"', ["font family"], id="css-declaration"),
        pytest.param("f(font=dict(family=theme.font))", [], id="family-from-theme"),
        pytest.param('kind = "serif"', [], id="single-word-is-not-a-stack"),
        pytest.param('t = "Revenue, cost, profit"', [], id="comma-text"),
        # --- pixel sizes -------------------------------------------------------
        pytest.param("f(font_size=12)", ["pixel size"], id="font_size"),
        pytest.param("f(title_font_size=18.5)", ["pixel size"], id="title_font_size"),
        pytest.param("f(marker_size=8)", ["pixel size"], id="marker_size"),
        pytest.param("f(marker=dict(size=8))", ["pixel size"], id="size-in-marker"),
        pytest.param(
            "f(font=dict(size=-12))", ["pixel size"], id="size-in-font-negative"
        ),
        pytest.param(
            'd = {"font": {"size": 12}}', ["pixel size"], id="size-in-font-dict"
        ),
        pytest.param("go.Font(size=12)", ["pixel size"], id="size-in-Font-class"),
        pytest.param("f(line=dict(width=1.5))", ["pixel size"], id="width-in-line"),
        pytest.param(
            "f(margin=dict(l=40, r=0, t=60, b=0))",
            ["pixel size", "pixel size"],
            id="margin-nonzero-only",
        ),
        pytest.param("f(margin_t=50)", ["pixel size"], id="margin_t"),
        pytest.param("fig.update_layout(width=1400)", ["pixel size"], id="width-call"),
        pytest.param("fig.update_layout(height=450)", ["pixel size"], id="height-call"),
        pytest.param(
            "def f(df, *, width: int = 900) -> None: ...",
            ["pixel size"],
            id="kwonly-default",
        ),
        pytest.param(
            "def f(df, height=300): ...", ["pixel size"], id="positional-default"
        ),
        pytest.param('t = "font-size:12px"', ["pixel size"], id="css-pixels"),
        pytest.param("f(width=None)", [], id="width-none"),
        pytest.param("f(width=config.width)", [], id="width-from-config"),
        pytest.param("f(width=0.8)", [], id="bar-width-float"),
        pytest.param("f(width=1)", [], id="width-one-is-not-pixels"),
        pytest.param("f(width=0, height=0)", [], id="zero"),
        pytest.param("f(font_size=0)", [], id="zero-font-size"),
        pytest.param("f(xbins=dict(size=5))", [], id="size-as-data-unit"),
        pytest.param("f(size=100)", [], id="size-outside-font-or-marker"),
        pytest.param("f(top_n=10, nbins=30)", [], id="other-numbers"),
        pytest.param("f(marker=dict(size=sizes))", [], id="size-is-a-variable"),
        pytest.param("f(width=True)", [], id="bool-is-not-a-number"),
        pytest.param(
            "def f(*, top_n: int = 10, size: int = 5): ...", [], id="other-defaults"
        ),
        pytest.param('t = "Size 12 px"', [], id="px-not-attached-to-number"),
    ],
)
def test_detector(source: str, expected: list[str]) -> None:
    assert [f.kind for f in detect_styling_literals(source)] == expected


def test_findings_carry_line_and_text() -> None:
    source = 'x = 1\nf(\n    line_color="red",\n    font_size=11,\n)\n'
    found = detect_styling_literals(source)
    assert [(f.line, f.kind, f.text) for f in found] == [
        (3, "colour name", "line_color='red'"),
        (4, "pixel size", "font_size=11"),
    ]
