"""The image loader: the inline decode, the read that happens once, the failure, and the loop.

Nothing here reaches the network: a `data:` url is decoded where it stands, and every `http` one
is answered by a reader put in place of `images._read`, which is the only thing in the module that
touches a socket.
"""
from __future__ import annotations

import base64
import threading
import time

import pytest
from qtpy.QtCore import QSize, QThread
from qtpy.QtGui import QPixmap

from sg_widgets_qt import images
from sg_widgets_qt.images import ImageLoader, image_loader, image_pool
from sg_widgets_qt.workers import JobPool, default_pool

#: An 8 by 8 block, as a self-contained data URI.
RED_PNG = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAACXBIWXMAAA7EAAAOxAGV"
    "Kw4bAAAAFklEQVQYlWM8oaHxnwEPYMInOXwUAAArkgInxYgTRAAAAABJRU5ErkJggg=="
)

#: A truncated PNG: nothing in it decodes, which is the failure a widget draws its own state from.
BROKEN_PNG = "data:image/png;base64,iVBORw0KGgo="

#: The bytes the stand-in reader answers with, which are the ones `RED_PNG` carries.
RED_BYTES = base64.b64decode(RED_PNG.split(",", 1)[1])

#: A url that never leaves this process.
URL = "https://site.example.com/thumbs/one.png"

#: How long a read may hold the GUI thread. A read runs on a worker, so this is the whole budget.
BLOCKING_BUDGET_MS = 50

#: Urls a table of thumbnails asks for at once. More than any pool has threads.
PAGE_OF_THUMBNAILS = 25

#: How long a write may wait while a page of thumbnails is out. Far under a single read's own
#: time, so a write that queued behind one cannot pass.
WRITE_BUDGET_MS = 1000


@pytest.fixture
def pool(qapp):
    made = JobPool()
    yield made
    made.cancel_all()
    made.wait(5000)


@pytest.fixture
def loader(pool):
    """A loader of its own, so one test's cache never answers another's."""
    return ImageLoader(pool=pool)


def test_a_data_url_decodes_where_it_stands(loader):
    """No worker, no loop: a self-contained URI answers inside the call that asked for it."""
    seen: list = []
    loader.load(RED_PNG, seen.append)
    assert len(seen) == 1
    assert isinstance(seen[0], QPixmap)
    assert seen[0].size() == QSize(8, 8)
    assert loader.pending == 0


def test_a_data_url_that_does_not_decode_answers_nothing(loader):
    seen: list = []
    loader.load(BROKEN_PNG, seen.append)
    assert seen == [None]
    assert loader.has(BROKEN_PNG) is True


def test_two_loads_of_one_url_cost_one_read(qtbot, loader, monkeypatch):
    """The second caller joins the read in flight, so a table of rows costs one read per url."""
    reads: list[str] = []

    def reader(url: str, timeout: int) -> bytes:
        reads.append(url)
        time.sleep(0.05)
        return RED_BYTES

    monkeypatch.setattr(images, "_read", reader)
    first: list = []
    second: list = []
    loader.load(URL, first.append)
    loader.load(URL, second.append)
    assert loader.pending == 1
    qtbot.waitUntil(lambda: bool(first) and bool(second), timeout=5000)

    assert reads == [URL]
    assert first[0] is not None
    assert second[0] is not None

    # A url already read answers on the spot, and still costs nothing.
    third: list = []
    loader.load(URL, third.append)
    assert len(third) == 1
    assert reads == [URL]


def test_a_failure_is_delivered_as_none_on_the_gui_thread(qtbot, loader, monkeypatch):
    """A read that raised is `None`, on the thread that asked, never an exception in a worker."""
    caller = QThread.currentThread()
    seen: dict = {}

    def reader(url: str, timeout: int) -> bytes:
        seen["worker"] = QThread.currentThread()
        raise OSError("the site refused the connection")

    monkeypatch.setattr(images, "_read", reader)
    loader.load(URL, lambda pixmap: seen.update(pixmap=pixmap, thread=QThread.currentThread()))
    qtbot.waitUntil(lambda: "thread" in seen, timeout=5000)

    assert seen["pixmap"] is None
    assert seen["thread"] is caller
    assert seen["worker"] is not caller
    # The failure is remembered, so a broken picture is asked for once.
    assert loader.has(URL) is True
    assert loader.pixmap_cached(URL) is None


def test_a_load_never_holds_the_loop(qtbot, loader, monkeypatch):
    """A slow site holds a worker, never the GUI thread: `load` returns inside the budget."""
    started = threading.Event()

    def reader(url: str, timeout: int) -> bytes:
        started.set()
        time.sleep(0.4)
        return RED_BYTES

    monkeypatch.setattr(images, "_read", reader)
    seen: list = []
    before = time.monotonic()
    loader.load(URL, seen.append)
    asked = (time.monotonic() - before) * 1000.0
    assert asked < BLOCKING_BUDGET_MS

    # The loop keeps turning while the read is out: a spin costs nothing like the read's own time.
    assert started.wait(2.0) is True
    spun = time.monotonic()
    qtbot.wait(20)
    assert (time.monotonic() - spun) * 1000.0 < 20 + BLOCKING_BUDGET_MS
    assert not seen

    qtbot.waitUntil(lambda: bool(seen), timeout=5000)
    assert seen[0] is not None


def test_the_pictures_read_on_a_pool_of_their_own(qapp):
    """A loader that names no pool takes the image pool, never the one the reads and writes hold."""
    assert image_pool() is image_pool()
    assert image_pool() is not default_pool()
    assert image_loader().pool is image_pool()
    assert ImageLoader().pool is image_pool()


def test_a_page_of_thumbnails_never_queues_a_write_behind_it(qtbot, monkeypatch):
    """Every image thread held, and a write submitted after them still lands inside its budget."""
    release = threading.Event()

    def reader(url: str, timeout: int) -> bytes:
        release.wait(10.0)
        return RED_BYTES

    monkeypatch.setattr(images, "_read", reader)
    loader = ImageLoader()
    try:
        for number in range(PAGE_OF_THUMBNAILS):
            loader.load(f"{URL}?n={number}", lambda _pixmap: None)
        assert loader.pending == PAGE_OF_THUMBNAILS

        written: list = []
        before = time.monotonic()
        default_pool().submit(lambda: "written", on_result=written.append)
        qtbot.waitUntil(lambda: bool(written), timeout=WRITE_BUDGET_MS)
        assert (time.monotonic() - before) * 1000.0 < WRITE_BUDGET_MS
    finally:
        release.set()
        image_pool().wait(10000)
