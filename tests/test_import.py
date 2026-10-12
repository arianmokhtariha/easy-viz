import easy_viz


def test_package_imports() -> None:
    assert isinstance(easy_viz.__all__, list)
