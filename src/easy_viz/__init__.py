"""easy-viz: analytical plots in one call."""

from easy_viz._warnings import EasyVizWarning
from easy_viz.config import get_config, set_config
from easy_viz.export import save, save_many
from easy_viz.plots.comparison import bar_plot
from easy_viz.theme import Theme, get_theme, set_theme

__all__ = [
    "EasyVizWarning",
    "Theme",
    "bar_plot",
    "get_config",
    "get_theme",
    "save",
    "save_many",
    "set_config",
    "set_theme",
]
