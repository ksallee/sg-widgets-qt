"""What a published distribution owes a consumer: types, a small sdist, a README, a changelog."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

#: The checkout, one level above this suite, whatever the working directory is.
ROOT = Path(__file__).resolve().parents[1]

PACKAGES = ("sg_widgets_core", "sg_widgets_qt")

PYPROJECT = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")

#: The marker on a fenced block that reads a site: it is read here, never run.
NEEDS_A_SITE = "# Needs a site"

#: An example builds a widget offscreen and returns. None of them waits on input.
EXAMPLE_TIMEOUT_S = 90

#: Where a README image has to be served from for PyPI to draw it: an absolute raw URL on `main`.
RAW = "https://raw.githubusercontent.com/ksallee/sg-widgets-qt/main/"


def _readme_images() -> list[tuple[str, str]]:
    """The alt text and the source of every image the README draws."""
    return re.findall(r"!\[([^\]]*)\]\(([^)\s]+)\)", README)


def _readme_examples() -> list[str]:
    """The source of every fenced Python block in the README, in the order they are printed."""
    return re.findall(r"^```python\n(.*?)^```", README, re.S | re.M)


def test_both_packages_carry_py_typed() -> None:
    for package in PACKAGES:
        assert (ROOT / "src" / package / "py.typed").is_file()


def test_the_wheel_target_ships_py_typed() -> None:
    for package in PACKAGES:
        assert f'"src/{package}"' in PYPROJECT


def test_the_sdist_leaves_out_the_shots_the_drives_and_the_live_reads() -> None:
    body = PYPROJECT.split("[tool.hatch.build.targets.sdist]", 1)[1].split("\n[", 1)[0]
    excluded = body.split("exclude", 1)[1]
    for path in ("tools/drives/", "tests/live/"):
        assert f'"{path}"' in excluded
    assert "shots" not in body.split("exclude", 1)[0]


def test_nothing_imports_typing_extensions() -> None:
    hits = [
        path
        for path in (ROOT / "src").rglob("*.py")
        if "typing_extensions" in path.read_text(encoding="utf-8")
    ]
    assert hits == []
    assert "typing_extensions" not in PYPROJECT


def test_pytest_times_a_test_out() -> None:
    assert re.search(r"^timeout\s*=\s*\d+", PYPROJECT, re.MULTILINE)


def test_the_project_names_its_pages() -> None:
    urls = PYPROJECT.split("[project.urls]", 1)[1].split("\n[", 1)[0]
    for key in ("Homepage", "Documentation", "Issues", "Changelog", "Source"):
        assert f"{key} =" in urls


def test_the_readme_is_the_long_description() -> None:
    assert 'readme = "README.md"' in PYPROJECT


def test_every_readme_screenshot_is_a_raw_url_on_main() -> None:
    images = _readme_images()
    assert len(images) >= 6
    for _alt, url in images:
        assert url.startswith(RAW + "docs/screenshots/")


def test_every_readme_screenshot_is_in_the_checkout() -> None:
    images = _readme_images()
    assert images
    for _alt, url in images:
        assert (ROOT / url[len(RAW) :]).is_file()


def test_every_readme_screenshot_carries_alt_text() -> None:
    for alt, _url in _readme_images():
        assert alt.strip()


def test_the_readme_links_resolve_away_from_the_checkout() -> None:
    for name in ("CLAUDE.md", "STATUS.md", "porting-conventions"):
        assert name not in README


def test_the_changelog_covers_the_version_being_published() -> None:
    version = re.search(r'^version = "([^"]+)"', PYPROJECT, re.MULTILINE)
    assert version
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [{version.group(1)}]" in changelog


def test_the_workflows_are_there() -> None:
    gates = (ROOT / ".github" / "workflows" / "gates.yml").read_text(encoding="utf-8")
    release = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "ruff" in gates and "pytest" in gates
    assert "pyqt5" in gates and "PySide6" in gates
    assert "id-token: write" in release and "pypa/gh-action-pypi-publish" in release
    assert "password" not in release


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not on PATH")
def test_a_shot_in_a_subdirectory_is_ignored() -> None:
    answer = subprocess.run(
        ["git", "check-ignore", "shots/states/probe.png", "shots/probe.png"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if answer.returncode == 128:
        pytest.skip("not a git work tree")
    assert answer.stdout.split() == ["shots/states/probe.png", "shots/probe.png"]


def test_the_readme_runs_on_the_mock_before_it_reads_a_site() -> None:
    examples = _readme_examples()
    assert len(examples) >= 2
    assert NEEDS_A_SITE not in examples[0]
    assert NEEDS_A_SITE in examples[1]


@pytest.mark.parametrize("index", range(len(_readme_examples())))
def test_every_readme_example_runs_as_printed(index: int, tmp_path: Path) -> None:
    source = _readme_examples()[index]
    if NEEDS_A_SITE in source:
        pytest.skip("the example reads a site")
    script = tmp_path / f"example_{index}.py"
    script.write_text(source, encoding="utf-8")
    done = subprocess.run(
        [sys.executable, str(script)],
        cwd=tmp_path,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        capture_output=True,
        text=True,
        timeout=EXAMPLE_TIMEOUT_S,
    )
    assert done.returncode == 0, done.stderr


def _packaged_counts() -> tuple[int, int, int]:
    """The widgets the docs index lists, the core modules and the pages the wheel carries."""
    index = json.loads((ROOT / "docs" / "widgets" / "_index.json").read_text(encoding="utf-8"))
    widgets = sum(len(category["items"]) for category in index["widgets"])
    core = len([p for p in (ROOT / "src" / "sg_widgets_core").glob("*.py") if p.name != "__init__.py"])
    pages = len([p for s in ("start", "core", "widgets") for p in (ROOT / "docs" / s).rglob("*.md")])
    return widgets, core, pages


def test_the_status_line_counts_what_the_wheel_ships() -> None:
    widgets, core, pages = _packaged_counts()
    assert f"{widgets} widgets, {core} core modules and {pages} documentation pages" in README


def test_every_widget_page_the_wheel_carries_is_in_the_sidebar_index() -> None:
    index = json.loads((ROOT / "docs" / "widgets" / "_index.json").read_text(encoding="utf-8"))
    listed = {index["overview"], *(name for c in index["widgets"] for name in c["items"])}
    shipped = {page.stem for page in (ROOT / "docs" / "widgets").rglob("*.md")}
    assert shipped - listed == set()
