"""Where the showcase reads its pages and its site credentials from.

`docs/` beside `src/` is where the pages are written. The wheel carries `docs/widgets`,
`docs/core` and `docs/start` under `sg_widgets_qt/_docs`, so an installed showcase draws the same
sidebar as a checkout does; the package copy is read through `importlib.resources` and the
checkout's `docs/` is what a run from source falls back to.

`.env.local` is the working directory's, or the first one above it. An installed package sits in
`site-packages`, where nothing above it belongs to the person running the showcase.
"""
from __future__ import annotations

import os
from importlib import resources
from pathlib import Path

__all__ = [
    "DOCS_DIR_ENV",
    "ENV_FILE_ENV",
    "PACKAGE_DOCS",
    "checkout_docs",
    "docs_dir",
    "env_file",
    "packaged_docs",
]

#: The folder inside `sg_widgets_qt` the wheel carries the pages in.
PACKAGE_DOCS = "_docs"

#: Overrides, for a host that keeps either elsewhere.
DOCS_DIR_ENV = "SG_WIDGETS_QT_DOCS"
ENV_FILE_ENV = "SG_WIDGETS_QT_ENV_FILE"

#: The name of the file live mode reads its three keys from.
ENV_FILE = ".env.local"


def _holds_pages(path: Path) -> bool:
    """True of a directory a page can be looked up in."""
    return (path / "widgets").is_dir()


def packaged_docs() -> Path | None:
    """The pages the installed package carries, or None where the import came from a checkout."""
    try:
        anchor = resources.files("sg_widgets_qt")
    except (ImportError, TypeError):
        return None
    try:
        found = Path(str(anchor)) / PACKAGE_DOCS
    except (TypeError, ValueError):
        return None
    return found if _holds_pages(found) else None


def checkout_docs() -> Path | None:
    """`docs/` of the checkout this module was imported from, or None outside one.

    The `pyproject.toml` beside it is what tells a checkout from a directory that happens to have
    a `docs` in it.
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "docs"
        if (parent / "pyproject.toml").is_file() and _holds_pages(candidate):
            return candidate
    return None


def docs_dir() -> Path:
    """The directory the pages are read from: the override, the package's copy, the checkout's.

    Where the package carries none and there is no checkout, the answer is where the wheel should
    have put them, so what is missing is named.
    """
    override = os.environ.get(DOCS_DIR_ENV)
    if override:
        return Path(override).expanduser()
    found = packaged_docs() or checkout_docs()
    if found is not None:
        return found
    return Path(__file__).resolve().parent.parent / PACKAGE_DOCS


def env_file() -> Path:
    """`.env.local`: the override, or the first one at or above the working directory."""
    override = os.environ.get(ENV_FILE_ENV)
    if override:
        return Path(override).expanduser()
    try:
        start = Path.cwd().resolve()
    except OSError:
        return Path(ENV_FILE)
    for base in (start, *start.parents):
        found = base / ENV_FILE
        if found.is_file():
            return found
    return start / ENV_FILE
