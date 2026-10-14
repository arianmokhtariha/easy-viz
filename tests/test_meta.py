import re
from pathlib import Path

import plotly.graph_objects as go
import pytest

from easy_viz._meta import ROLES, tag

CONVENTIONS = Path(__file__).parents[1] / "docs" / "conventions.md"


def test_roles_match_conventions_table() -> None:
    # Users target traces by the roles documented in conventions; the code and the
    # table must name exactly the same set.
    text = CONVENTIONS.read_text(encoding="utf-8")
    section = text.split("## Trace roles", 1)[1].split("\n## ", 1)[0]
    documented = set(re.findall(r"^\| `(\w+)` \|", section, flags=re.MULTILINE))
    assert documented == ROLES


def test_tag_sets_role_and_group_and_returns_same_trace() -> None:
    trace = go.Scatter(x=[1, 2], y=[3, 4])
    assert tag(trace, "trendline", "North") is trace
    assert trace.meta == {"role": "trendline", "group": "North"}


def test_tag_rejects_unknown_role() -> None:
    with pytest.raises(ValueError, match="unknown trace role 'trend'"):
        tag(go.Scatter(), "trend")  # type: ignore[arg-type]
