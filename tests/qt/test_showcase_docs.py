"""Where an installed showcase finds its pages and its `.env.local`.

The wheel carries `docs/` under `sg_widgets_qt/_docs`, so the slow test here builds it, installs it
into a venv of its own and asks that copy what it resolves. Nothing in this file reaches the
network beyond what `uv` has already cached.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from sg_widgets_qt.showcase import paths
from sg_widgets_qt.showcase.window import read_index, sidebar_model

ROOT = Path(__file__).resolve().parents[2]

#: A build, a venv and an install, on a cold cache.
BUILD_TIMEOUT_S = 600

#: What the installed copy is asked, run with the checkout nowhere near the working directory.
PROBE = """
import json
from pathlib import Path

from sg_widgets_qt.showcase import paths

directory = paths.docs_dir()
print(json.dumps({
    "packaged": str(paths.packaged_docs() or ""),
    "checkout": str(paths.checkout_docs() or ""),
    "root": str(directory),
    "pages": sorted(str(page.relative_to(directory)) for page in directory.rglob("*.md")),
    "env_file": str(paths.env_file()),
}))
"""


def _checkout_pages() -> list[str]:
    docs = ROOT / "docs"
    out: list[str] = []
    for section in ("widgets", "core", "start"):
        out.extend(
            str(page.relative_to(docs)) for page in (docs / section).rglob("*.md")
        )
    return sorted(out)


# --- the resolver ------------------------------------------------------------------------------


def test_a_checkout_reads_the_docs_beside_its_src():
    assert paths.packaged_docs() is None
    assert paths.checkout_docs() == ROOT / "docs"
    assert paths.docs_dir() == ROOT / "docs"


def test_the_packaged_copy_wins_over_the_checkout(monkeypatch, tmp_path):
    carried = tmp_path / "_docs"
    (carried / "widgets").mkdir(parents=True)
    monkeypatch.setattr(paths, "packaged_docs", lambda: carried)
    assert paths.docs_dir() == carried


def test_an_override_names_the_docs_directory(monkeypatch, tmp_path):
    monkeypatch.setenv(paths.DOCS_DIR_ENV, str(tmp_path))
    assert paths.docs_dir() == tmp_path


def test_the_env_file_is_found_from_the_working_directory_upward(monkeypatch, tmp_path):
    (tmp_path / ".env.local").write_text("FPT_API_SITE_URL=https://example.invalid\n")
    deep = tmp_path / "one" / "two"
    deep.mkdir(parents=True)
    monkeypatch.delenv(paths.ENV_FILE_ENV, raising=False)
    monkeypatch.chdir(deep)
    assert paths.env_file() == tmp_path.resolve() / ".env.local"


def test_no_env_file_anywhere_names_the_working_directory(monkeypatch, tmp_path):
    monkeypatch.delenv(paths.ENV_FILE_ENV, raising=False)
    monkeypatch.chdir(tmp_path)
    found = paths.env_file()
    assert not found.is_file()
    assert found.parent == tmp_path.resolve()


def test_an_override_names_the_env_file(monkeypatch, tmp_path):
    target = tmp_path / "site.env"
    monkeypatch.setenv(paths.ENV_FILE_ENV, str(target))
    assert paths.env_file() == target


def test_missing_docs_say_so_instead_of_an_empty_sidebar(tmp_path, caplog):
    with caplog.at_level("WARNING"):
        assert read_index(tmp_path) == {}
    assert str(tmp_path / "widgets" / "_index.json") in caplog.text


# --- the wheel ---------------------------------------------------------------------------------


@pytest.mark.slow
def test_the_installed_wheel_resolves_the_same_pages_as_the_checkout(tmp_path):
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv builds the wheel this reads")
    dist = tmp_path / "dist"
    subprocess.run(
        [uv, "build", "--wheel", "--out-dir", str(dist), str(ROOT)],
        check=True,
        capture_output=True,
        timeout=BUILD_TIMEOUT_S,
    )
    wheels = sorted(dist.glob("*.whl"))
    assert len(wheels) == 1

    venv = tmp_path / "venv"
    subprocess.run(
        [uv, "venv", "--python", "3.9", str(venv)],
        check=True,
        capture_output=True,
        timeout=BUILD_TIMEOUT_S,
    )
    python = venv / "bin" / "python"
    subprocess.run(
        [uv, "pip", "install", "--python", str(python), "--no-deps", str(wheels[0])],
        check=True,
        capture_output=True,
        timeout=BUILD_TIMEOUT_S,
    )

    # Run from a directory that is no relation of the checkout: an installed showcase has no
    # checkout above it, and the resolver may not wander into one.
    home = tmp_path / "elsewhere"
    home.mkdir()
    done = subprocess.run(
        [str(python), "-c", PROBE],
        cwd=str(home),
        check=True,
        capture_output=True,
        text=True,
        timeout=BUILD_TIMEOUT_S,
    )
    found = json.loads(done.stdout)

    assert found["packaged"], "the wheel carries no docs"
    assert not found["checkout"]
    assert found["root"] == found["packaged"]
    assert str(venv) in found["root"]
    assert found["pages"] == _checkout_pages()
    assert found["env_file"] == str(home / ".env.local")

    # The sidebar the installed copy would draw is the one the checkout draws.
    installed = [entry.name for entry in sidebar_model(Path(found["root"]))]
    assert installed == [entry.name for entry in sidebar_model(ROOT / "docs")]
    assert len([name for name in installed if name]) >= 40
