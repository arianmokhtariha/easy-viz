"""Tests for the global output defaults."""

import dataclasses
from collections.abc import Iterator

import pytest

from easy_viz.config import Config, get_config, set_config


@pytest.fixture(autouse=True)
def restore_config() -> Iterator[None]:
    """Give every test the defaults it found, whatever the test changed."""
    saved = get_config()
    yield
    set_config(width=saved.width, export_scale=saved.export_scale)


def test_defaults_match_the_documented_values() -> None:
    assert (Config().width, Config().export_scale) == (1400, 2.0)


def test_partial_update_keeps_the_other_value() -> None:
    set_config(width=900)
    assert get_config() == Config(width=900, export_scale=2.0)
    set_config(export_scale=3)
    assert get_config() == Config(width=900, export_scale=3)


@pytest.mark.parametrize(
    ("kwargs", "error", "named"),
    [
        ({"width": True}, ValueError, "width=True"),  # bool is an int subclass
        ({"width": 1400.5}, ValueError, "width=1400.5"),
        ({"width": 0}, ValueError, "width=0"),
        ({"width": -5}, ValueError, "width=-5"),
        ({"export_scale": True}, ValueError, "export_scale=True"),
        ({"export_scale": "2"}, ValueError, "export_scale='2'"),
        # NaN and infinity pass a "<= 0" check, then fail late inside Chrome.
        ({"export_scale": float("nan")}, ValueError, "export_scale=nan"),
        ({"export_scale": float("inf")}, ValueError, "export_scale=inf"),
        ({"export_scale": 0}, ValueError, "export_scale=0"),
        ({"export_scale": -1.5}, ValueError, "export_scale=-1.5"),
    ],
)
def test_invalid_values_raise_naming_the_parameter(
    kwargs: dict[str, object], error: type[Exception], named: str
) -> None:
    with pytest.raises(error, match=named):
        set_config(**kwargs)  # type: ignore[arg-type]  # invalid on purpose


def test_failed_set_config_leaves_the_active_config_untouched() -> None:
    set_config(width=800, export_scale=1.5)
    # The valid width must not be applied when the other value is rejected.
    with pytest.raises(ValueError, match="export_scale"):
        set_config(width=900, export_scale=-1)
    assert get_config() == Config(width=800, export_scale=1.5)


def test_config_is_immutable() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        get_config().width = 1  # type: ignore[misc]  # frozen on purpose
