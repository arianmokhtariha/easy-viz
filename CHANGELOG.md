# Changelog

User-visible changes to easy-viz. Format: [Keep a Changelog](https://keepachangelog.com/);
versions follow [Semantic Versioning](https://semver.org/).

## Unreleased

### Added
- Themes: `Theme`, `set_theme()` and `get_theme()`, with two built-in themes, `dark`
  (the original house style) and `light`. Both are also registered as the Plotly
  templates `easy_viz_dark` and `easy_viz_light` for your own figures; easy-viz never
  changes Plotly's default template.
- Global output defaults: `get_config()` and `set_config()` for the default figure
  width (1400 px) and export resolution (2x).
- Static export: `save()` for one figure and `save_many()` for a batch in a single
  Chrome session. PNG, JPEG and WebP use the configured resolution; SVG and PDF are
  written at the figure's true size. Needs `pip install "easy-viz[export]"` and
  Chrome.
- `EasyVizWarning`: every easy-viz warning uses it, and it points at the line of your
  own call, so `warnings.filterwarnings("ignore", category=ev.EasyVizWarning)`
  silences easy-viz without silencing other libraries.
- Type information for type checkers (`py.typed`).
