"""Port of `packages/core/test/query.test.ts`.

Upstream reads the mock client and awaits; here the cache is synchronous and the
concurrent callers are two threads.
"""
from __future__ import annotations

import math
import threading

import pytest

from sg_widgets_core.client import SearchOptions, SgApiError, UploadFile
from sg_widgets_core.query import QueryCacheOptions, create_query_cache

from .fake_client import CountingClient, FakeClient, FakeClock, concurrently


class TestCaching:
    def test_answers_a_repeat_call_without_touching_the_client(self) -> None:
        client = CountingClient(FakeClient())
        cache = create_query_cache(client)
        first = cache.fields("Shot")
        second = cache.fields("Shot")
        assert client.calls == ["fields Shot -"]
        # The same object comes back, so a UI can compare by identity.
        assert second is first

    def test_keys_on_the_arguments_so_a_different_project_or_filter_is_a_different_entry(self) -> None:
        client = CountingClient(FakeClient())
        cache = create_query_cache(client)
        cache.fields("Shot")
        cache.fields("Shot", 70)
        cache.fields("Shot", 71)
        cache.fields("Asset", 70)
        assert client.calls == ["fields Shot -", "fields Shot 70", "fields Shot 71", "fields Asset 70"]

        cache.search("Shot", SearchOptions(fields=["code"], page={"size": 5}))
        cache.search("Shot", SearchOptions(fields=["code"], page={"size": 6}))
        assert len([c for c in client.calls if c.startswith("search")]) == 2

    def test_is_insensitive_to_the_order_of_keys_in_the_options_object(self) -> None:
        client = CountingClient(FakeClient())
        cache = create_query_cache(client)
        cache.search("Shot", SearchOptions(fields=["code"], sort="code", page={"size": 5, "number": 1}))
        cache.search("Shot", SearchOptions(page={"number": 1, "size": 5}, sort="code", fields=["code"]))
        assert client.calls == ["search Shot"]


class TestTheReadsANotesAppMakes:
    def test_caches_a_thread_and_a_follow_list_and_never_caches_the_event_log(self) -> None:
        client = CountingClient(FakeClient())
        cache = create_query_cache(client)
        cache.thread_contents(11030)
        cache.thread_contents(11030)
        cache.thread_contents(11030, {"Note": ["subject"]})
        cache.following(20)
        cache.following(20)
        # A change feed answered from a cache reports that nothing changed.
        cache.event_log()
        cache.event_log()
        assert client.calls == [
            "thread_contents 11030",
            "thread_contents 11030",
            "following 20",
            "event_log",
            "event_log",
        ]


class TestTheWrites:
    def test_drops_every_cached_page_of_a_type_after_a_create_and_after_an_upload(self) -> None:
        client = CountingClient(FakeClient())
        cache = create_query_cache(client)
        cache.search("Note", SearchOptions(fields=["subject"]))
        cache.create("Note", {"project": {"type": "Project", "id": 70}, "subject": "Fresh"})
        cache.search("Note", SearchOptions(fields=["subject"]))
        cache.upload("Note", 11030, UploadFile(filename="a.png", data=b"\x01", field="attachments"))
        cache.search("Note", SearchOptions(fields=["subject"]))
        assert client.calls == [
            "search Note",
            "create Note",
            "search Note",
            "upload Note 11030",
            "search Note",
        ]

    def test_drops_a_cached_thread_after_a_reply_an_upload_and_an_update_within_the_ttl(self) -> None:
        client = CountingClient(FakeClient())
        cache = create_query_cache(client, QueryCacheOptions(ttl_ms=math.inf))
        before = cache.thread_contents(11030)
        reply = cache.create("Reply", {"entity": {"type": "Note", "id": 11030}, "content": "Seen it."})
        replied = cache.thread_contents(11030)
        assert len(replied) == len(before) + 1
        assert replied[-1].id == reply.id

        cache.upload("Note", 11030, UploadFile(filename="a.png", data=b"\x01", field="attachments"))
        attached = cache.thread_contents(11030)
        assert len([row for row in attached if row.type == "Attachment"]) == (
            len([row for row in replied if row.type == "Attachment"]) + 1
        )

        cache.update("Note", 11030, {"content": "Edited."})
        edited = cache.thread_contents(11030)
        assert edited[0].content == "Edited."
        assert len([c for c in client.calls if c.startswith("thread_contents")]) == 4


class TestDeduping:
    def test_makes_one_request_for_two_concurrent_identical_calls(self) -> None:
        inner = FakeClient()
        client = CountingClient(inner)
        cache = create_query_cache(client)
        values, errors = concurrently(inner, cache.statuses)
        assert errors == [None, None]
        assert client.calls == ["statuses"]
        assert values[1] is values[0]

    def test_dedupes_even_with_caching_switched_off(self) -> None:
        inner = FakeClient()
        client = CountingClient(inner)
        cache = create_query_cache(client, QueryCacheOptions(ttl_ms=0))
        concurrently(inner, cache.entity_types)
        assert client.calls == ["entity_types"]
        # Nothing was stored, so the next call is a fresh request.
        cache.entity_types()
        assert client.calls == ["entity_types", "entity_types"]


class TestErrors:
    def test_does_not_cache_a_failure(self) -> None:
        fake = FakeClient()
        client = CountingClient(fake)
        cache = create_query_cache(client)
        fake.fail_next(503)
        with pytest.raises(SgApiError):
            cache.statuses()
        # The retry reaches the client again, and its answer is cached.
        assert isinstance(cache.statuses(), list)
        cache.statuses()
        assert client.calls == ["statuses", "statuses"]

    def test_rejects_every_concurrent_caller_of_a_failed_request(self) -> None:
        fake = FakeClient()
        cache = create_query_cache(fake)
        fake.fail_next(500)
        _, errors = concurrently(fake, cache.statuses)
        assert [isinstance(error, SgApiError) for error in errors] == [True, True]


class TestInvalidate:
    def test_drops_everything_with_no_argument(self) -> None:
        client = CountingClient(FakeClient())
        cache = create_query_cache(client)
        cache.fields("Shot")
        cache.statuses()
        cache.invalidate()
        cache.fields("Shot")
        cache.statuses()
        assert client.calls == ["fields Shot -", "statuses", "fields Shot -", "statuses"]

    def test_drops_only_the_keys_under_a_prefix(self) -> None:
        client = CountingClient(FakeClient())
        cache = create_query_cache(client)
        cache.fields("Shot")
        cache.fields("Asset")
        cache.statuses()
        # A key is `<method>:<json args>`, so this narrows to Shot's schema alone.
        cache.invalidate('fields:["Shot"')
        cache.fields("Shot")
        cache.fields("Asset")
        cache.statuses()
        assert client.calls == ["fields Shot -", "fields Asset -", "statuses", "fields Shot -"]

        # The method name alone drops every schema read.
        cache.invalidate("fields")
        cache.fields("Shot")
        cache.fields("Asset")
        assert len([c for c in client.calls if c.startswith("fields")]) == 5

    def test_does_not_let_an_in_flight_request_repopulate_a_key_that_was_invalidated(self) -> None:
        inner = FakeClient()
        client = CountingClient(inner)
        cache = create_query_cache(client)
        inner.entered.clear()
        inner.gate = threading.Event()
        done = threading.Event()

        def read() -> None:
            cache.statuses()
            done.set()

        threading.Thread(target=read).start()
        assert inner.entered.wait(5)
        cache.invalidate()
        inner.gate.set()
        assert done.wait(5)
        inner.gate = None
        cache.statuses()
        assert client.calls == ["statuses", "statuses"]


class TestTtl:
    def test_refetches_once_a_value_has_gone_stale(self) -> None:
        clock = FakeClock()
        client = CountingClient(FakeClient())
        cache = create_query_cache(client, QueryCacheOptions(ttl_ms=1000, now=clock))
        cache.entity_types()
        clock.advance(0.5)
        cache.entity_types()
        assert client.calls == ["entity_types"]
        clock.advance(0.6)
        cache.entity_types()
        assert client.calls == ["entity_types", "entity_types"]

    def test_keeps_a_value_forever_with_an_infinite_ttl(self) -> None:
        clock = FakeClock()
        client = CountingClient(FakeClient())
        cache = create_query_cache(client, QueryCacheOptions(ttl_ms=math.inf, now=clock))
        cache.entity_types()
        clock.advance(10 * 365 * 24 * 3600)
        cache.entity_types()
        assert client.calls == ["entity_types"]


class TestAsAnSgClient:
    def test_passes_every_method_through_and_returns_the_same_answers(self) -> None:
        fake = FakeClient()
        cache = create_query_cache(fake)
        assert cache.entity_types() == fake.entity_types()
        assert cache.fields("Shot", 70) == fake.fields("Shot", 70)
        assert cache.statuses() == fake.statuses()
        assert cache.text_search("sh010", {"Shot": None}) == fake.text_search("sh010", {"Shot": None})
        options = SearchOptions(fields=["code"], page={"size": 3})
        assert cache.search("Shot", options) == fake.search("Shot", options)


class TestWrites:
    def test_is_never_cached_and_drops_the_cached_pages_of_the_type_it_touched(self) -> None:
        client = CountingClient(FakeClient())
        cache = create_query_cache(client)
        cache.search("Shot", SearchOptions(fields=["code"], page={"size": 2}))
        cache.search("Version", SearchOptions(fields=["code"], page={"size": 2}))
        cache.search("Shot", SearchOptions(fields=["code"], page={"size": 2}))
        assert client.calls == ["search Shot", "search Version"]

        cache.update("Shot", 862, {"description": "x"})
        cache.search("Shot", SearchOptions(fields=["code"], page={"size": 2}))
        # Version's page survives; Shot's is read again.
        cache.search("Version", SearchOptions(fields=["code"], page={"size": 2}))
        assert client.calls == ["search Shot", "search Version", "update Shot 862", "search Shot"]

    def test_re_reads_the_changed_value_through_the_cache(self) -> None:
        cache = create_query_cache(FakeClient())
        cache.search("Shot", SearchOptions(fields=["description"], page={"size": 1}))
        cache.update("Shot", 862, {"description": "written through the cache"})
        after = cache.search("Shot", SearchOptions(fields=["description"], page={"size": 1}))
        assert after.data[0].values["description"] == "written through the cache"
