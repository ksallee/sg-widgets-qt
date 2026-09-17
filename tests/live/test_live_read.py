"""Read-only smoke test of `ShotgunClient` against the test site.

It runs only when `.env.local` holds the three keys, and it asserts shapes and
counts. Nothing it reads is printed.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from sg_widgets_core.client import Page, SearchOptions, SgApiError, SummarizeOptions, SummaryGrouping
from sg_widgets_core.schema import FieldSchema
from sg_widgets_core.shotgun_client import API_KEY_ENV, SCRIPT_NAME_ENV, SITE_URL_ENV, ShotgunClient
from sg_widgets_core.status import StatusRecord

pytestmark = pytest.mark.live

ENV_FILE = Path(__file__).resolve().parents[2] / ".env.local"
KEYS = (SITE_URL_ENV, SCRIPT_NAME_ENV, API_KEY_ENV)


def load_env(path: Path) -> dict[str, str]:
    """`KEY=value` lines of a dotenv file, comments and blanks skipped."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip("'\"")
    return values


@pytest.fixture(scope="module")
def client() -> ShotgunClient:
    env = load_env(ENV_FILE)
    missing = [key for key in KEYS if not env.get(key)]
    if missing:
        pytest.skip(f"{ENV_FILE.name} is missing {len(missing)} of the {len(KEYS)} keys")
    return ShotgunClient.from_env(env)


def test_entity_types(client: ShotgunClient) -> None:
    types = client.entity_types()
    assert len(types) > 20
    assert all(t.name and t.display_name for t in types)
    assert any(t.name == "Version" for t in types)


def test_fields_of_version(client: ShotgunClient) -> None:
    fields = client.fields("Version")
    assert len(fields) > 20
    assert isinstance(fields["sg_status_list"], FieldSchema)
    assert fields["sg_status_list"].data_type == "status_list"
    assert fields["sg_status_list"].valid_values


def test_statuses(client: ShotgunClient) -> None:
    statuses = client.statuses()
    assert len(statuses) > 5
    assert all(isinstance(s, StatusRecord) and s.code for s in statuses)
    # A shipped status carries a colour and an icon (probe 010, 061).
    assert any(s.bg_color for s in statuses)
    assert any(s.icon is not None for s in statuses)


def test_search_a_page_of_versions(client: ShotgunClient) -> None:
    result = client.search(
        "Version",
        SearchOptions(fields=["code", "sg_status_list", "image"], sort="-id", page=Page(size=5)),
    )
    assert len(result.data) <= 5
    for row in result.data:
        assert row.type == "Version"
        assert isinstance(row.id, int)
        assert set(row.values) >= {"code", "sg_status_list", "image"}


def test_text_search(client: ShotgunClient) -> None:
    # The call refuses a term under three characters, which the REST endpoint accepts.
    with pytest.raises(SgApiError):
        client.text_search("a", {"Version": {}})
    rows = client.text_search("abc", {"Version": {}})
    assert len(rows) <= 25
    for row in rows:
        assert row.type == "Version"
        assert isinstance(row.id, int)
        assert len(row.links) == 2


def test_summarize_versions_by_status(client: ShotgunClient) -> None:
    result = client.summarize(
        "Version", SummarizeOptions(grouping=[SummaryGrouping(field="sg_status_list")])
    )
    assert "id" in result.summaries
    assert sum(g.summaries.get("id", 0) for g in result.groups) == result.summaries["id"]


def test_hierarchy_expand_of_the_first_project(client: ShotgunClient) -> None:
    # A template or an archived project is not in the navigation tree: expanding one
    # answers `Unexpected result looking for project`.
    projects = client.search(
        "Project",
        SearchOptions(
            filters={
                "logical_operator": "and",
                "conditions": [["is_template", "is", False], ["archived", "is", False]],
            },
            fields=["name"],
            sort="id",
            page=Page(size=1),
        ),
    )
    if not projects.data:
        pytest.skip("the site has no live project to expand")
    node = client.hierarchy_expand(f"/Project/{projects.data[0].id}")
    assert node.path == f"/Project/{projects.data[0].id}"
    assert node.ref.kind in ("entity", "entity_type", "empty")
    assert all(child.path for child in node.children)
