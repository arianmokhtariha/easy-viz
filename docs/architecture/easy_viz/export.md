# Static image export

Covers: src/easy_viz/export.py

## Responsibilities
Turn finished figures into image files (`png`, `jpg`/`jpeg`, `webp`, `svg`, `pdf`) for
reports, with one call per figure (`save`) or one call per set of figures
(`save_many`). Both are thin wrappers over Plotly's `write_image` / `write_images`.
What they add:
- the format comes from the file extension, and a wrong one fails with the list of
  valid ones
- the resolution comes from [`config`](config.md), so a project picks it once
- inputs plain Plotly would silently ignore are rejected
- the parent directory is created, and the absolute path written is returned

## How it works
- **`save(fig, path, *, scale, width, height)`:**
  1. validates the extension, `scale`, `width` and `height`
  2. checks that kaleido is installed
  3. creates the parent directory
  4. calls `pio.write_image`
  5. returns `Path(path).expanduser().resolve()`
- **`save_many(figs, directory, *, format, scale)`:** validates the format, the
  mapping (not empty, every name usable as a file name) and the scale, then makes
  **one** `pio.write_images` call for all figures. Paths come back in the order of the
  mapping.
- **Scale:** `scale=None` reads `get_config().export_scale` at call time, so a later
  `set_config()` applies.
- **Optional dependency:** kaleido ships in the `export` extra. `_require_kaleido()`
  tests for it with `importlib.util.find_spec` and never imports it; plotly itself
  imports kaleido only when export is first used. A missing kaleido raises
  `ImportError` with the `pip install "easy-viz[export]"` hint.
- **Chrome** (kaleido 1.x draws images in a headless Chrome): not checked here. When
  it is missing, Plotly raises a `RuntimeError` whose text tells the user to run
  `plotly_get_chrome`, and that message passes through unchanged.

## Invariants
- The figure is never modified. Plotly converts it to a dict before exporting.
- Validation runs before any directory or file is created, so a rejected call leaves
  the disk untouched. Order inside `save`: extension, then scale and sizes, then
  kaleido, so the cheap errors do not depend on the environment.
- `save_many` makes exactly one `write_images` call, and passes every figure's width
  and height explicitly (see below).
- Error messages follow `"<function>: <what is wrong>. <how to fix it>."`.

## Pitfalls
- **Each kaleido export starts Chrome (about 2 seconds).** Writing ten figures with
  ten `save` calls costs ten starts; `save_many` costs one. Code that needs several
  images must use `save_many` ([conventions](../../conventions.md)).
- **`pio.write_images` ignores the figure's own `layout.width` / `layout.height`**
  and falls back to Plotly's 700x500 default, unlike `pio.write_image`, which uses the
  figure's size. Without correction, a 1400 px figure would be written 700 px wide
  (times the scale) by `save_many` but correctly by `save`. `save_many` therefore
  reads each figure's size (falling back to its template's) and passes it in. The
  real-export test in `tests/test_export.py` guards this.
- **Plotly treats a falsy `scale`, `width` or `height` as "not given".** `scale=0`
  would silently export at Plotly's default scale, so easy-viz rejects values that
  are not positive.
- **`scale` has no effect on `svg` and `pdf`**, which are vector formats. It is not
  an error: users set one scale for a mixed batch.
- **File names are checked for portability, not only validity.** `save_many` rejects
  `/`, `\`, `:`, `.` and `..` and names that differ only by case, because on Windows
  and macOS two such names are the same file and the second export would silently
  overwrite the first.
- **An empty mapping raises** instead of returning `[]`: a filter that left no
  figures is more likely a bug than an intended no-op, and a silent empty result is
  the kind of guess the product principles forbid.
- **`ImageFormat` repeats Plotly's supported list.** `eps`, which Plotly 6 accepted,
  is gone with kaleido 1.x. If Plotly adds a format, add it to `ImageFormat`.
- **Tests that export for real** carry the `export` marker and skip, not fail, when
  kaleido or Chrome is missing (a session fixture tries one tiny export). CI's
  runners have Chrome, so they run there.
