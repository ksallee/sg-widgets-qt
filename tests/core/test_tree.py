"""Port of `packages/core/test/tree.test.ts`."""
from __future__ import annotations

import re
from typing import Any, Callable

from sg_widgets_core.filter import EntityRef
from sg_widgets_core.mock import MOCK_NOW, MockClient
from sg_widgets_core.schema_service import create_schema_service
from sg_widgets_core.status_service import create_status_service
from sg_widgets_core.tree import (
    HierarchyLoaderOptions,
    HierarchySearcherOptions,
    TreeEngine,
    TreeKey,
    TreeLevel,
    TreeOptions,
    TreeRow,
    create_tree,
    hierarchy_loader,
    hierarchy_searcher,
    resolve_tree_fields,
)

ROOT = "/Project/70"
ASSETS = "/Project/70/Asset"
SHOTS = "/Project/70/Shot"
SEQUENCE = "/Project/70/Shot/sg_sequence/Sequence/100"
SHOT = "/Project/70/Shot/sg_sequence/Sequence/100/id/862"
#: The project whose Shots are grouped by a field no row of it fills (064).
LOOSE_ROOT = "/Project/72"
LOOSE_SHOTS = "/Project/72/Shot"


def client() -> MockClient:
    return MockClient(seed=1, now=MOCK_NOW)


def tree(now: Callable[[], float] | None = None) -> tuple[TreeEngine, list[str]]:
    """A tree over the mock hierarchy, and the calls it made."""
    calls: list[str] = []
    load = hierarchy_loader(client())

    def loader(path: str) -> TreeLevel:
        calls.append(path)
        return load(path)

    engine = create_tree(TreeOptions(root_path=ROOT, loader=loader, now=now))
    return engine, calls


def search_tree() -> tuple[TreeEngine, list[str]]:
    """The same tree, with the two endpoints a search chains behind it."""
    mock = client()
    calls: list[str] = []
    load = hierarchy_loader(mock)

    def loader(path: str) -> TreeLevel:
        calls.append(path)
        return load(path)

    engine = create_tree(TreeOptions(
        root_path=ROOT,
        loader=loader,
        searcher=hierarchy_searcher(mock, ROOT, HierarchySearcherOptions(schema=create_schema_service(mock))),
    ))
    return engine, calls


def labels(engine: TreeEngine) -> list[str]:
    return [row.node.label for row in engine.snapshot().rows]


def paths(engine: TreeEngine) -> list[str]:
    return [row.node.path for row in engine.snapshot().rows]


def row_at(engine: TreeEngine, path: str) -> TreeRow | None:
    return next((row for row in engine.snapshot().rows if row.node.path == path), None)


class TestLoadingALevel:
    def test_reads_the_root_and_opens_it(self) -> None:
        engine, calls = tree()
        assert engine.snapshot().status == "idle"
        engine.load()
        assert calls == [ROOT]
        assert engine.snapshot().status == "ready"
        assert labels(engine) == ["Blue Moon Rising", "Assets", "Shots"]
        assert engine.snapshot().rows[0].node.level == 0
        assert engine.snapshot().rows[1].node.level == 1

    def test_reads_a_level_once_however_often_it_is_opened(self) -> None:
        engine, calls = tree()
        engine.load()
        engine.expand(ASSETS)
        engine.collapse(ASSETS)
        engine.expand(ASSETS)
        assert calls == [ROOT, ASSETS]
        assert "charAda" in labels(engine)

    def test_never_opens_a_node_with_nothing_under_it(self) -> None:
        engine, calls = tree()
        engine.load()
        engine.expand(SHOTS)
        assert len(engine.child_paths(SHOTS)) > 0
        calls.clear()
        # A sequence says it has children, an unread path says it has none.
        engine.expand("/Project/70/nowhere")
        assert calls == []

    def test_carries_a_loading_flag_on_the_node_being_read_and_nowhere_else(self) -> None:
        load = hierarchy_loader(client())
        seen: dict[str, bool] = {}

        def loader(path: str) -> TreeLevel:
            if path == ASSETS:
                assets = row_at(engine, ASSETS)
                shots = row_at(engine, SHOTS)
                seen["assets"] = assets is not None and assets.loading
                seen["shots"] = shots is not None and shots.loading
            return load(path)

        engine = create_tree(TreeOptions(root_path=ROOT, loader=loader))
        engine.load()
        engine.expand(ASSETS)
        assert seen["assets"] is True
        assert seen["shots"] is False
        row = row_at(engine, ASSETS)
        assert row is not None and row.loading is False

    def test_holds_the_error_a_failed_read_threw_and_keeps_the_rows_it_had(self) -> None:
        load = hierarchy_loader(client())

        def loader(path: str) -> TreeLevel:
            if path == ASSETS:
                raise Exception("no")
            return load(path)

        engine = create_tree(TreeOptions(root_path=ROOT, loader=loader))
        engine.load()
        engine.expand(ASSETS)
        assert str(engine.snapshot().error) == "no"
        assert engine.snapshot().status == "ready"
        assert labels(engine) == ["Blue Moon Rising", "Assets", "Shots"]

    def test_reports_a_root_that_is_not_there(self) -> None:
        engine = create_tree(TreeOptions(root_path="/Project/999999999", loader=hierarchy_loader(client())))
        engine.load()
        assert engine.snapshot().status == "error"
        assert engine.snapshot().rows == []

    def test_tells_a_subscriber_every_time_the_state_moves(self) -> None:
        engine, _ = tree()
        seen = [0]

        def on_change() -> None:
            seen[0] += 1

        stop = engine.subscribe(on_change)
        engine.load()
        assert seen[0] > 0
        before = seen[0]
        stop()
        engine.expand(ASSETS)
        assert seen[0] == before


class TestExpandingToAPath:
    def test_opens_one_level_per_call_down_to_a_seed(self) -> None:
        engine, calls = tree()
        engine.expand_to_path(SHOT)
        assert calls == [ROOT, SHOTS, SEQUENCE]
        assert SHOT in paths(engine)
        assert engine.snapshot().cursor == SHOT

    def test_takes_the_incremental_path_a_hierarchy_search_answers(self) -> None:
        mock = client()
        engine = create_tree(TreeOptions(root_path=ROOT, loader=hierarchy_loader(mock)))
        found = mock.hierarchy_search(ROOT, EntityRef(type="Shot", id=862))
        engine.expand_to_path(found[0].incremental_path if found else [])
        assert engine.snapshot().cursor == SHOT

    def test_stops_where_the_seed_leaves_the_tree(self) -> None:
        engine, _ = tree()
        engine.expand_to_path("/Project/70/Shot/sg_sequence/Sequence/100/id/999999")
        assert engine.snapshot().cursor == SEQUENCE


class TestCheckboxes:
    def test_checks_every_loaded_node_under_the_one_that_was_checked(self) -> None:
        engine, _ = tree()
        engine.load()
        engine.expand(ASSETS)
        engine.set_checked(ASSETS, True)
        assert engine.check_state_of(ASSETS) == "checked"
        for path in engine.child_paths(ASSETS):
            assert engine.check_state_of(path) == "checked"

    def test_reads_mixed_on_a_parent_once_one_child_is_unchecked_and_checked_again_when_it_comes_back(self) -> None:
        engine, _ = tree()
        engine.load()
        engine.expand(ASSETS)
        engine.set_checked(ASSETS, True)
        first = engine.child_paths(ASSETS)[0]
        engine.set_checked(first, False)
        assert engine.check_state_of(ASSETS) == "mixed"
        assert engine.check_state_of(ROOT) == "mixed"
        engine.set_checked(first, True)
        assert engine.check_state_of(ASSETS) == "checked"

    def test_checks_a_level_read_after_its_branch_was_checked(self) -> None:
        engine, _ = tree()
        engine.load()
        engine.set_checked(ASSETS, True)
        assert engine.check_state_of(ASSETS) == "checked"
        engine.expand(ASSETS)
        for path in engine.child_paths(ASSETS):
            assert engine.check_state_of(path) == "checked"

    def test_checks_the_parent_once_every_child_of_it_is_checked(self) -> None:
        engine, _ = tree()
        engine.load()
        engine.expand(ASSETS)
        for path in engine.child_paths(ASSETS):
            engine.set_checked(path, True)
        assert engine.check_state_of(ASSETS) == "checked"

    def test_reports_the_rows_the_checked_nodes_stand_for_and_not_the_folders(self) -> None:
        engine, _ = tree()
        engine.load()
        engine.expand(ASSETS)
        engine.set_checked(ASSETS, True)
        refs = engine.checked_refs()
        assert all(ref.type == "Asset" for ref in refs)
        assert len(refs) == len(engine.child_paths(ASSETS))

    def test_unchecks_a_branch_and_everything_under_it(self) -> None:
        engine, _ = tree()
        engine.load()
        engine.expand(ASSETS)
        engine.toggle_checked(ASSETS)
        engine.toggle_checked(ASSETS)
        assert engine.snapshot().checked == []
        assert engine.checked_refs() == []


class TestSelection:
    def test_holds_one_node_at_a_time(self) -> None:
        engine, _ = tree()
        engine.load()
        engine.select(ASSETS)
        engine.select(SHOTS)
        assert engine.snapshot().selected == [SHOTS]

    def test_adds_and_drops_nodes_when_the_mode_is_multiple(self) -> None:
        engine = create_tree(TreeOptions(
            root_path=ROOT, loader=hierarchy_loader(client()), selection="multiple",
        ))
        engine.load()
        engine.select(ASSETS)
        engine.select(SHOTS, additive=True)
        assert engine.snapshot().selected == [ASSETS, SHOTS]
        engine.select(ASSETS, additive=True)
        assert engine.snapshot().selected == [SHOTS]

    def test_selects_nothing_when_the_mode_is_none(self) -> None:
        engine = create_tree(TreeOptions(root_path=ROOT, loader=hierarchy_loader(client()), selection="none"))
        engine.load()
        engine.select(ASSETS)
        assert engine.snapshot().selected == []


class TestTheKeyboard:
    def test_walks_the_visible_list_with_down_up_home_and_end(self) -> None:
        engine, _ = tree()
        engine.load()
        assert engine.snapshot().cursor == ROOT
        engine.key_down(TreeKey(key="ArrowDown"))
        assert engine.snapshot().cursor == ASSETS
        engine.key_down(TreeKey(key="ArrowDown"))
        assert engine.snapshot().cursor == SHOTS
        engine.key_down(TreeKey(key="ArrowDown"))
        assert engine.snapshot().cursor == SHOTS
        engine.key_down(TreeKey(key="ArrowUp"))
        assert engine.snapshot().cursor == ASSETS
        engine.key_down(TreeKey(key="End"))
        assert engine.snapshot().cursor == SHOTS
        engine.key_down(TreeKey(key="Home"))
        assert engine.snapshot().cursor == ROOT

    def test_opens_a_branch_with_right_and_steps_into_it_on_the_second_press(self) -> None:
        engine, _ = tree()
        engine.load()
        engine.focus(SHOTS)
        engine.key_down(TreeKey(key="ArrowRight"))
        # The key made the read; this finds the level already there.
        engine.expand(SHOTS)
        row = row_at(engine, SHOTS)
        assert row is not None and row.expanded is True
        engine.key_down(TreeKey(key="ArrowRight"))
        assert engine.snapshot().cursor == SEQUENCE

    def test_shuts_a_branch_with_left_and_climbs_to_the_parent_from_a_closed_one(self) -> None:
        engine, _ = tree()
        engine.load()
        engine.expand(SHOTS)
        engine.focus(SEQUENCE)
        engine.key_down(TreeKey(key="ArrowLeft"))
        assert engine.snapshot().cursor == SHOTS
        engine.key_down(TreeKey(key="ArrowLeft"))
        row = row_at(engine, SHOTS)
        assert row is not None and row.expanded is False
        engine.key_down(TreeKey(key="ArrowLeft"))
        assert engine.snapshot().cursor == ROOT

    def test_toggles_the_checkbox_with_space_and_selects_with_enter(self) -> None:
        engine, _ = tree()
        engine.load()
        engine.focus(ASSETS)
        engine.key_down(TreeKey(key=" "))
        assert engine.check_state_of(ASSETS) == "checked"
        engine.key_down(TreeKey(key=" "))
        assert engine.check_state_of(ASSETS) == "unchecked"
        engine.key_down(TreeKey(key="Enter"))
        assert engine.snapshot().selected == [ASSETS]

    def test_leaves_a_key_it_does_not_use_to_the_caller(self) -> None:
        engine, _ = tree()
        engine.load()
        assert engine.key_down(TreeKey(key="Tab")) is False
        assert engine.key_down(TreeKey(key="a", ctrl_key=True)) is False
        assert engine.key_down(TreeKey(key="ArrowDown")) is True


class TestTypeAhead:
    def test_jumps_to_the_node_whose_label_starts_with_what_was_typed(self) -> None:
        engine, _ = tree()
        engine.load()
        engine.expand(ASSETS)
        engine.focus(ROOT)
        for char in "prop":
            engine.key_down(TreeKey(key=char))
        assert engine.snapshot().cursor == "/Project/70/Asset/id/1228"

    def test_walks_the_matches_when_the_same_letter_is_pressed_again(self) -> None:
        engine, _ = tree()
        engine.load()
        engine.expand(ASSETS)
        engine.focus(ROOT)
        engine.key_down(TreeKey(key="p"))
        assert engine.snapshot().cursor == "/Project/70/Asset/id/1228"
        engine.key_down(TreeKey(key="p"))
        assert engine.snapshot().cursor == "/Project/70/Asset/id/1229"

    def test_starts_a_new_buffer_once_the_old_one_has_gone_stale(self) -> None:
        clock = [0.0]
        engine, _ = tree(now=lambda: clock[0])
        engine.load()
        engine.expand(ASSETS)
        engine.focus(ROOT)
        engine.key_down(TreeKey(key="e"))
        assert engine.snapshot().cursor == "/Project/70/Asset/id/1230"
        clock[0] += 5000
        engine.key_down(TreeKey(key="v"))
        assert engine.snapshot().cursor == "/Project/70/Asset/id/1232"

    def test_stays_where_it_is_when_nothing_matches(self) -> None:
        engine, _ = tree()
        engine.load()
        assert engine.key_down(TreeKey(key="z")) is False
        assert engine.snapshot().cursor == ROOT


class TestSearching:
    def test_opens_the_tree_onto_every_hit_and_marks_it(self) -> None:
        engine, _ = search_tree()
        engine.load()
        engine.search("sh010_0010")
        snap = engine.snapshot()
        assert SHOT in paths(engine)
        assert SHOT in snap.matches
        assert snap.cursor == SHOT
        # The rest of the tree stays on show, so a hit keeps its context.
        assert "Assets" in labels(engine)
        row = row_at(engine, ASSETS)
        assert row is not None and row.match is False

    def test_opens_a_branch_two_hits_share_once(self) -> None:
        engine, calls = search_tree()
        engine.load()
        calls.clear()
        engine.search("sh010")
        assert len([path for path in calls if path == SHOTS]) == 1
        assert len(engine.snapshot().matches) > 1

    def test_restores_the_expansion_it_opened_onto_when_the_text_is_cleared(self) -> None:
        engine, _ = search_tree()
        engine.load()
        engine.expand(ASSETS)
        engine.search("sh010_0010")
        assert SHOT in paths(engine)
        engine.search("")
        assert ASSETS in paths(engine)
        assert SHOT not in paths(engine)
        assert engine.snapshot().matches == []

    def test_marks_nothing_when_the_words_match_no_row(self) -> None:
        engine, _ = search_tree()
        engine.load()
        engine.search("nothing matches this")
        assert engine.snapshot().matches == []
        assert engine.snapshot().searching is False

    def test_marks_the_labels_already_loaded_when_there_is_no_searcher(self) -> None:
        engine, _ = tree()
        engine.load()
        engine.expand(ASSETS)
        engine.search("lantern")
        marked = [engine.node(path).label for path in engine.snapshot().matches if engine.node(path)]
        assert marked == ["propLantern"]

    def test_searches_the_types_the_levels_already_read_stand_for(self) -> None:
        seen: list[list[str]] = []
        mock = client()
        inner = hierarchy_searcher(mock, ROOT, HierarchySearcherOptions(schema=create_schema_service(mock)))

        def searcher(text: str, types: Any) -> Any:
            seen.append(sorted(types))
            return inner(text, types)

        engine = create_tree(TreeOptions(root_path=ROOT, loader=hierarchy_loader(mock), searcher=searcher))
        engine.load()
        engine.search("sh010_0010")
        assert seen[0] == ["Asset", "Shot"]


class TestExpandingABranch:
    def test_opens_every_level_under_a_node_down_to_the_depth_asked_for(self) -> None:
        engine, _ = tree()
        engine.load()
        engine.expand_all(SHOTS, 2)
        # Every sequence of the project, and every shot under each of them.
        assert SHOT in paths(engine)
        shots = [path for path in paths(engine) if re.search(r"/Sequence/\d+/id/\d+$", path)]
        assert len(shots) == 22

    def test_stops_at_the_depth_asked_for(self) -> None:
        engine, _ = tree()
        engine.load()
        engine.expand_all(SHOTS, 1)
        assert SEQUENCE in paths(engine)
        assert SHOT not in paths(engine)

    def test_carries_the_loading_flag_on_the_node_until_every_level_is_read(self) -> None:
        engine, _ = tree()
        engine.load()
        busy: list[bool] = []

        def on_change() -> None:
            row = row_at(engine, SHOTS)
            busy.append(row.loading if row is not None else False)

        stop = engine.subscribe(on_change)
        engine.expand_all(SHOTS, 2)
        stop()
        assert busy[0] is True
        assert busy[-1] is False

    def test_opens_every_branch_at_the_focus_level_on_the_asterisk(self) -> None:
        engine, _ = tree()
        engine.load()
        engine.expand(SHOTS)
        engine.focus(SEQUENCE)
        assert engine.key_down(TreeKey(key="*")) is True
        assert SHOT in paths(engine)
        opened = [row for row in engine.snapshot().rows if "/Sequence/" in row.node.path and row.expanded]
        assert len(opened) > 1


class TestALevelWhoseGroupingFieldHasNoRows:
    def test_answers_the_ungrouped_rows_in_place_of_the_empty_child(self) -> None:
        engine = create_tree(TreeOptions(root_path=LOOSE_ROOT, loader=hierarchy_loader(client())))
        engine.load()
        engine.expand(LOOSE_SHOTS)
        assert labels(engine) == ["Night Ferry", "Assets", "Shots", "nf_0010", "nf_0020", "nf_0030"]

    def test_follows_a_seed_path_spelling_the_bucket_the_way_the_search_endpoint_does(self) -> None:
        mock = client()
        engine = create_tree(TreeOptions(root_path=LOOSE_ROOT, loader=hierarchy_loader(mock)))
        found = mock.hierarchy_search(LOOSE_ROOT, EntityRef(type="Shot", id=892))
        assert found[0].incremental_path[2] == f"{LOOSE_SHOTS}/sg_sequence/__none__"
        engine.expand_to_path(found[0].incremental_path)
        node = engine.node(engine.snapshot().cursor or "")
        assert node is not None and node.entity == EntityRef(type="Shot", id=892)

    def test_places_a_hit_under_it_when_the_tree_is_searched(self) -> None:
        mock = client()
        engine = create_tree(TreeOptions(
            root_path=LOOSE_ROOT,
            loader=hierarchy_loader(mock),
            searcher=hierarchy_searcher(
                mock, LOOSE_ROOT, HierarchySearcherOptions(schema=create_schema_service(mock)),
            ),
        ))
        engine.load()
        engine.search("nf_0020")
        marked = [engine.node(path).label for path in engine.snapshot().matches if engine.node(path)]
        assert marked == ["nf_0020"]


class TestTheHierarchyLoader:
    def test_reads_the_fields_of_the_rows_a_level_stands_for_one_read_per_type(self) -> None:
        mock = client()
        reads = [0]
        inner = mock.search

        def counting(entity_type: str, options: Any = None) -> Any:
            reads[0] += 1
            return inner(entity_type, options)

        mock.search = counting  # type: ignore[method-assign]
        engine = create_tree(TreeOptions(
            root_path=ROOT,
            loader=hierarchy_loader(mock, HierarchyLoaderOptions(fields=["sg_status_list", "description"])),
        ))
        engine.load()
        engine.expand(ASSETS)
        first = engine.node(engine.child_paths(ASSETS)[0])
        assert first is not None and isinstance(first.values["sg_status_list"], str)
        # One read for the project at the root, one for the assets of the level below it.
        assert reads[0] == 2

    def test_leaves_a_folder_that_stands_for_no_row_without_values(self) -> None:
        engine = create_tree(TreeOptions(
            root_path=ROOT,
            loader=hierarchy_loader(client(), HierarchyLoaderOptions(fields=["sg_status_list"])),
        ))
        engine.load()
        assets = engine.node(ASSETS)
        root = engine.node(ROOT)
        assert assets is not None and assets.entity is None
        assert assets.values == {}
        assert root is not None and root.entity == EntityRef(type="Project", id=70)


class TestControlledExpansionAndSelection:
    def test_reports_the_open_paths_and_opens_exactly_the_ones_it_is_given(self) -> None:
        engine, _ = tree()
        engine.load()
        assert engine.snapshot().expanded == [ROOT]

        engine.set_expanded([SHOTS, SEQUENCE])
        assert engine.snapshot().expanded == [ROOT, SHOTS, SEQUENCE]
        assert SHOT in paths(engine)

        # The list it is given is the whole truth: what is not in it shuts.
        engine.set_expanded([ASSETS])
        assert engine.snapshot().expanded == [ROOT, ASSETS]
        assert SHOT not in paths(engine)

    def test_selects_exactly_the_paths_it_is_given_one_at_a_time_in_single_mode(self) -> None:
        engine, _ = tree()
        engine.load()
        engine.set_selected([SHOTS, ASSETS])
        assert engine.snapshot().selected == [SHOTS]
        engine.set_selected([])
        assert engine.snapshot().selected == []


class TestADisabledNode:
    @staticmethod
    def disabled_tree() -> TreeEngine:
        """The tree with its Assets branch disabled."""
        return create_tree(TreeOptions(
            root_path=ROOT,
            loader=hierarchy_loader(client()),
            disabled=lambda node: node.path == ASSETS,
        ))

    def test_is_skipped_by_the_arrows_and_never_takes_the_cursor(self) -> None:
        engine = self.disabled_tree()
        engine.load()
        assert engine.snapshot().rows[1].disabled is True
        assert engine.snapshot().cursor == ROOT
        # Assets sits between the root and Shots, and Down steps over it.
        engine.key_down(TreeKey(key="ArrowDown"))
        assert engine.snapshot().cursor == SHOTS
        engine.key_down(TreeKey(key="ArrowUp"))
        assert engine.snapshot().cursor == ROOT
        engine.focus(ASSETS)
        assert engine.snapshot().cursor == ROOT

    def test_refuses_selection_and_its_checkbox(self) -> None:
        engine = self.disabled_tree()
        engine.load()
        engine.select(ASSETS)
        assert engine.snapshot().selected == []
        engine.set_checked(ASSETS, True)
        assert engine.snapshot().checked == []
        engine.set_selected([ASSETS])
        assert engine.snapshot().selected == []

    def test_is_skipped_by_type_ahead(self) -> None:
        engine = self.disabled_tree()
        engine.load()
        # "Assets" is the only row starting with a, and it is disabled.
        assert engine.key_down(TreeKey(key="a")) is False
        assert engine.snapshot().cursor == ROOT


class TestWhatARowDrawsWith:
    def test_finds_the_status_field_of_a_type_that_has_one_and_skips_the_one_that_has_not(self) -> None:
        mock = client()
        plan = resolve_tree_fields(
            create_schema_service(mock), create_status_service(mock), ["Shot", "Project"],
        )
        status = plan.status["Shot"]
        assert status is not None and status.name == "sg_status_list"
        # Project's `sg_status` is a plain `list`, so it carries no Status row.
        assert plan.status["Project"] is None
        assert plan.statuses is not None and plan.statuses["ip"].code == "ip"

    def test_reads_no_status_table_when_nothing_on_show_is_a_status(self) -> None:
        mock = client()
        plan = resolve_tree_fields(
            create_schema_service(mock), create_status_service(mock), ["Project"], "code",
        )
        secondary = plan.secondary["Project"]
        assert secondary is not None and secondary.name == "code"
        assert plan.statuses is None

