import easy_viz


def test_public_api_is_exactly_all() -> None:
    # Every name in __all__ must resolve, and nothing public may be missing from
    # it: __all__ is the public API.
    for name in easy_viz.__all__:
        assert hasattr(easy_viz, name), name
    public = {
        name
        for name, value in vars(easy_viz).items()
        if not name.startswith("_") and not isinstance(value, type(easy_viz))
    }
    assert public == set(easy_viz.__all__)
