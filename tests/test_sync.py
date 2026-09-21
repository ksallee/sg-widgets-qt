"""The sync tools read a whole upstream checkout and amend a record in place."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

TOOLS = Path(__file__).resolve().parent.parent / "tools"

#: One file per upstream location the layout table calls ported, plus the ones a scan skips.
FAKE_UPSTREAM = (
    "packages/core/src/index.ts",
    "packages/core/src/status.ts",
    "packages/core/test/status.test.ts",
    "packages/core/test/hierarchy.test.ts",
    "packages/react/src/components/ui/button.tsx",
    "packages/react/src/registry/sg/components/entity-picker.tsx",
    "apps/site/src/theme/theme.ts",
    "apps/site/src/pages/themes.astro",
    "apps/site/src/pages/_themes/ThemeEditor.tsx",
    "apps/site/src/demos/entity-picker/Demo.tsx",
    "apps/site/src/demos/_shared/client.ts",
    "apps/site/src/content/docs/index.mdx",
    "apps/site/src/content/docs/widgets/index.mdx",
    "apps/site/src/content/docs/widgets/entity-picker.mdx",
    "apps/site/src/content/docs/start/install.mdx",
    "apps/site/src/content/docs/core/client.mdx",
    "apps/site/src/props/_types.ts",
    "apps/site/src/props/entity-picker.ts",
    "apps/site/src/props/state-line.ts",
)


def load(name: str) -> ModuleType:
    """A script in `tools/` as a module."""
    spec = importlib.util.spec_from_file_location(f"sg_tools_{name}", TOOLS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def upstream(tmp_path: Path) -> Path:
    root = tmp_path / "upstream"
    for rel in FAKE_UPSTREAM:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"// {rel}\n")
    return root


def write_manifest(path: Path, items: dict[str, Any], commit: str | None = None) -> None:
    upstream: dict[str, Any] = {"path": "~/dev/sg-widgets", "branch": "dev"}
    if commit:
        upstream["commit"] = commit
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"upstream": upstream, "items": items}, indent=2) + "\n")


class TestTheScan:
    def test_reads_every_upstream_location_the_layout_table_calls_ported(
        self, tmp_path: Path, upstream: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        status = load("sync_status")
        manifest = tmp_path / "manifest.json"
        write_manifest(
            manifest,
            {
                "core/status": {
                    "status": "complete",
                    "upstream": {
                        "packages/core/src/status.ts": sha256(upstream / "packages/core/src/status.ts"),
                        "packages/core/test/status.test.ts": sha256(
                            upstream / "packages/core/test/status.test.ts"
                        ),
                    },
                    "ported": ["src/sg_widgets_core/status.py"],
                    "note": "",
                }
            },
        )
        monkeypatch.setattr(status, "UPSTREAM", upstream)
        monkeypatch.setattr(status, "MANIFEST", manifest)

        assert status.report()["new"] == {
            "core/hierarchy": "packages/core/test/hierarchy.test.ts",
            "demos/entity-picker": "apps/site/src/demos/entity-picker",
            "docs/core-client": "apps/site/src/content/docs/core/client.mdx",
            "docs/entity-picker": "apps/site/src/content/docs/widgets/entity-picker.mdx",
            "docs/start-install": "apps/site/src/content/docs/start/install.mdx",
            "docs/state-line": "apps/site/src/props/state-line.ts",
            "primitives/button": "packages/react/src/components/ui/button.tsx",
            "theme/editor": "apps/site/src/pages/_themes/ThemeEditor.tsx",
            "theme/page": "apps/site/src/pages/themes.astro",
            "theme/theme": "apps/site/src/theme/theme.ts",
            "widgets/entity-picker": "packages/react/src/registry/sg/components/entity-picker.tsx",
        }

    def test_counts_a_test_file_as_ported_once_a_record_names_it(
        self, tmp_path: Path, upstream: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        status = load("sync_status")
        manifest = tmp_path / "manifest.json"
        write_manifest(
            manifest,
            {
                "core/status": {
                    "status": "complete",
                    "upstream": {
                        "packages/core/test/hierarchy.test.ts": sha256(
                            upstream / "packages/core/test/hierarchy.test.ts"
                        )
                    },
                    "ported": ["tests/core/test_hierarchy.py"],
                    "note": "",
                }
            },
        )
        monkeypatch.setattr(status, "UPSTREAM", upstream)
        monkeypatch.setattr(status, "MANIFEST", manifest)

        assert "core/hierarchy" not in status.report()["new"]

    def test_reports_a_deleted_upstream_file_as_drift(
        self, tmp_path: Path, upstream: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        status = load("sync_status")
        manifest = tmp_path / "manifest.json"
        write_manifest(
            manifest,
            {
                "core/gone": {
                    "status": "complete",
                    "upstream": {"packages/core/src/gone.ts": "0" * 64},
                    "ported": ["src/sg_widgets_core/gone.py"],
                    "note": "",
                }
            },
        )
        monkeypatch.setattr(status, "UPSTREAM", upstream)
        monkeypatch.setattr(status, "MANIFEST", manifest)

        assert status.report()["changed"] == {"core/gone": ["packages/core/src/gone.ts (deleted)"]}


class TestAddingToARecord:
    @pytest.fixture
    def record(self, tmp_path: Path, upstream: Path, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
        module = load("sync_record")
        repo = tmp_path / "repo"
        (repo / "tests/core").mkdir(parents=True)
        (repo / "tests/core/test_hierarchy.py").write_text("")
        monkeypatch.setattr(module, "UPSTREAM", upstream)
        monkeypatch.setattr(module, "HERE", repo)
        monkeypatch.setattr(module, "MANIFEST", repo / "sync" / "manifest.json")
        write_manifest(
            module.MANIFEST,
            {
                "core/mock": {
                    "status": "partial",
                    "upstream": {"packages/core/src/status.ts": "0" * 64},
                    "ported": ["src/sg_widgets_core/mock.py"],
                    "commit": "1111111111111111111111111111111111111111",
                    "note": "The clock is injected.",
                }
            },
            commit="1111111111111111111111111111111111111111",
        )
        return module

    def test_keeps_the_status_note_and_hashes_the_record_already_holds(self, record: ModuleType) -> None:
        assert (
            record.main(
                [
                    "core/mock",
                    "--add",
                    "--upstream",
                    "packages/core/test/hierarchy.test.ts",
                    "--ported",
                    "tests/core/test_hierarchy.py",
                ]
            )
            == 0
        )
        data = json.loads(record.MANIFEST.read_text())
        item = data["items"]["core/mock"]
        assert item["status"] == "partial"
        assert item["note"] == "The clock is injected."
        assert item["commit"] == "1111111111111111111111111111111111111111"
        assert data["upstream"]["commit"] == "1111111111111111111111111111111111111111"
        assert item["upstream"]["packages/core/src/status.ts"] == "0" * 64
        assert item["upstream"]["packages/core/test/hierarchy.test.ts"] == sha256(
            record.UPSTREAM / "packages/core/test/hierarchy.test.ts"
        )
        assert item["ported"] == ["src/sg_widgets_core/mock.py", "tests/core/test_hierarchy.py"]

    def test_refuses_an_item_no_record_names(self, record: ModuleType) -> None:
        assert (
            record.main(
                [
                    "core/nowhere",
                    "--add",
                    "--upstream",
                    "packages/core/test/hierarchy.test.ts",
                    "--ported",
                    "tests/core/test_hierarchy.py",
                ]
            )
            == 2
        )
