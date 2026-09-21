"""What a published distribution owes a consumer: types, a small sdist, a timeout."""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

#: The checkout, one level above this suite, whatever the working directory is.
ROOT = Path(__file__).resolve().parents[1]

PACKAGES = ("sg_widgets_core", "sg_widgets_qt")

PYPROJECT = (ROOT / "pyproject.toml").read_text(encoding="utf-8")


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
