"""The pictures a widget draws, fetched once and kept by url.

A thumbnail, an avatar and the stock status sprite are all images the site hands out as a url. A
`data:` url is decoded where it stands; an `http` or `https` one is read on the image pool, so a
widget never blocks on a socket, and the bytes cross back to the thread that asked for them, where
the `QPixmap` is built: a pixmap belongs to the GUI thread.

    loader = image_loader()
    loader.load(row.values["image"], self._on_ready, size=QSize(64, 36))

The cache key is the url exactly as it was given. An `image` field is presigned and re-minted on
every read (field_types/image), so two reads of one row give two keys and a stored key expires:
the loader never assumes a url it once read still lives. A url that failed is remembered as
nothing, so a broken picture is asked for once and a fresh url tries again.

`invert_lightness` is what the stock sprite wears in dark, per `docs/design-rules.md` rule 9: the
sprite was drawn as dark marks for a light page, so its lightness turns over and its hue stays.
"""
from __future__ import annotations

import base64
import binascii
import urllib.parse
import urllib.request
from typing import Callable, Optional, Union

from qtpy import QtSvg
from qtpy.QtCore import QByteArray, QObject, QRectF, QSize, Qt
from qtpy.QtGui import QColor, QImage, QPainter, QPixmap

from .workers import JobPool

__all__ = [
    "DEFAULT_TIMEOUT_S",
    "IMAGE_THREADS",
    "USER_AGENT",
    "ImageLoader",
    "grayscale",
    "image_loader",
    "image_pool",
    "invert_lightness",
    "pixmap_cached",
    "pixmap_from_bytes",
]

#: A read that has not answered by then is a failure. A site under load still answers inside it.
DEFAULT_TIMEOUT_S = 10

#: Sites refuse a request with no agent, so every read names itself.
USER_AGENT = "sg-widgets-qt"

#: The schemes a url may be read over. Anything else is a failure, never a file read.
SCHEMES = ("http", "https")

#: Threads the pictures read on. Small, because a picture is worth less than the read beside it.
IMAGE_THREADS = 4

ReadyCallback = Callable[[Optional[QPixmap]], None]
SizeLike = Union[QSize, int, None]

_IMAGE_POOL: JobPool | None = None


def image_pool() -> JobPool:
    """The pool every picture is read on.

    A pool of its own, never the one a schema read, a facet count or a field write runs on: a
    table of thumbnails asks for more urls than any pool has threads, and a write behind them
    would wait out every one.
    """
    global _IMAGE_POOL
    if _IMAGE_POOL is None:
        _IMAGE_POOL = JobPool(IMAGE_THREADS)
    return _IMAGE_POOL


def _as_size(size: SizeLike) -> QSize | None:
    if size is None:
        return None
    if isinstance(size, QSize):
        return size if size.isValid() else None
    side = int(size)
    return QSize(side, side) if side > 0 else None


def _is_svg(data: bytes) -> bool:
    head = data[:512].lstrip()
    return head.startswith(b"<svg") or (head.startswith(b"<?xml") and b"<svg" in data[:2048])


def pixmap_from_bytes(data: bytes, size: QSize | None = None) -> QPixmap | None:
    """The bytes as a pixmap, SVG included. None when nothing in them decodes."""
    if not data:
        return None
    if _is_svg(data):
        return _svg_pixmap(data, size)
    out = QPixmap()
    if not out.loadFromData(QByteArray(data)) or out.isNull():
        return None
    return out


def _svg_pixmap(data: bytes, size: QSize | None) -> QPixmap | None:
    """An SVG drawn at its own size, or at `size` when one is asked for."""
    renderer = QtSvg.QSvgRenderer(QByteArray(data))
    if not renderer.isValid():
        return None
    box = size if size is not None and size.isValid() else renderer.defaultSize()
    if not box.isValid() or box.width() <= 0 or box.height() <= 0:
        box = QSize(64, 64)
    out = QPixmap(box)
    out.fill(Qt.GlobalColor.transparent)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter, QRectF(0.0, 0.0, float(box.width()), float(box.height())))
    painter.end()
    return out


def _decode_data_url(url: str) -> QPixmap | None:
    """A `data:` url decoded where it stands, base64 or percent-encoded."""
    _, _, rest = url.partition(":")
    meta, _, payload = rest.partition(",")
    if not payload:
        return None
    try:
        if meta.rstrip().endswith(";base64"):
            data = base64.b64decode(payload, validate=False)
        else:
            data = urllib.parse.unquote_to_bytes(payload)
    except (binascii.Error, ValueError):
        return None
    return pixmap_from_bytes(data)


def _read(url: str, timeout: int) -> bytes:
    """The bytes behind an http url. Runs on a worker, never on the GUI thread."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as answer:  # noqa: S310
        return answer.read()


class ImageLoader(QObject):
    """Every picture a page draws, read once per url and kept in memory.

    One url asked for twice while the first read is in flight costs one read: the second caller
    joins the first. A failure is delivered as `None`, which is what a widget draws its own broken
    state from.
    """

    def __init__(
        self,
        pool: JobPool | None = None,
        timeout: int = DEFAULT_TIMEOUT_S,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._pool = pool if pool is not None else image_pool()
        self._timeout = int(timeout)
        self._cache: dict[str, QPixmap | None] = {}
        self._scaled: dict[tuple[str, int, int], QPixmap] = {}
        self._waiting: dict[str, list[tuple[ReadyCallback, QSize | None]]] = {}

    @property
    def pool(self) -> JobPool:
        """The pool the reads run on."""
        return self._pool

    @property
    def pending(self) -> int:
        """Urls being read now."""
        return len(self._waiting)

    def pixmap_cached(self, url: str | None) -> QPixmap | None:
        """What is already in memory for a url, at its own size. None while nothing is."""
        if not url:
            return None
        return self._cache.get(str(url))

    def has(self, url: str | None) -> bool:
        """True once the url has been read, whether it answered a picture or nothing."""
        return bool(url) and str(url) in self._cache

    def load(self, url: str | None, on_ready: ReadyCallback, size: SizeLike = None) -> None:
        """Hand the picture behind `url` to `on_ready`, or `None` when there is none.

        `size` is the box the picture is drawn in: the pixmap delivered covers it, so a caller
        clips rather than scaling on every paint. A url already read answers on the spot, and so
        does a `data:` url, which is decoded here.
        """
        box = _as_size(size)
        if not url:
            on_ready(None)
            return
        key = str(url)
        if key in self._cache:
            on_ready(self._fit(key, box))
            return
        if key.startswith("data:"):
            self._keep(key, _decode_data_url(key))
            on_ready(self._fit(key, box))
            return
        if urllib.parse.urlsplit(key).scheme not in SCHEMES:
            self._keep(key, None)
            on_ready(None)
            return
        waiting = self._waiting.get(key)
        if waiting is not None:
            waiting.append((on_ready, box))
            return
        self._waiting[key] = [(on_ready, box)]
        self._pool.submit(
            _read,
            key,
            self._timeout,
            on_result=lambda data, url=key: self._answered(url, data),
            on_error=lambda error, url=key: self._answered(url, None),
        )

    def clear(self) -> None:
        """Forget every picture. Reads in flight still deliver."""
        self._cache.clear()
        self._scaled.clear()

    def _answered(self, url: str, data: object) -> None:
        pixmap = pixmap_from_bytes(data) if isinstance(data, (bytes, bytearray)) else None
        self._keep(url, pixmap)
        for callback, box in self._waiting.pop(url, []):
            callback(self._fit(url, box))

    def _keep(self, url: str, pixmap: QPixmap | None) -> None:
        self._cache[url] = pixmap if pixmap is not None and not pixmap.isNull() else None

    def _fit(self, url: str, box: QSize | None) -> QPixmap | None:
        """The cached picture, scaled to cover `box` and kept at that size."""
        source = self._cache.get(url)
        if source is None or box is None:
            return source
        key = (url, box.width(), box.height())
        found = self._scaled.get(key)
        if found is None:
            found = source.scaled(
                box,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._scaled[key] = found
        return found


_LOADER: ImageLoader | None = None


def image_loader() -> ImageLoader:
    """The loader a widget reads through when its caller names none."""
    global _LOADER
    if _LOADER is None:
        _LOADER = ImageLoader()
    return _LOADER


def pixmap_cached(url: str | None) -> QPixmap | None:
    """What the shared loader already holds for a url."""
    return image_loader().pixmap_cached(url)


_INVERTED: dict[int, QPixmap] = {}
_GRAY: dict[int, QPixmap] = {}


def invert_lightness(pixmap: QPixmap) -> QPixmap:
    """The picture with its lightness turned over and its hue kept.

    What the stock status sprite wears on a dark page (`docs/design-rules.md` rule 9): the sprite
    was drawn as dark marks for a light page, so a mark that was black reads white and a green
    tick stays green.
    """
    if pixmap.isNull():
        return pixmap
    key = int(pixmap.cacheKey())
    found = _INVERTED.get(key)
    if found is not None:
        return found
    image = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    for y in range(image.height()):
        for x in range(image.width()):
            colour = image.pixelColor(x, y)
            if colour.alpha() == 0:
                continue
            h, s, lightness, a = colour.getHsl()
            colour.setHsl(h, s, 255 - lightness, a)
            image.setPixelColor(x, y, colour)
    out = QPixmap.fromImage(image)
    out.setDevicePixelRatio(pixmap.devicePixelRatio())
    _INVERTED[key] = out
    return out


def grayscale(pixmap: QPixmap) -> QPixmap:
    """The picture with its colour taken out, which is what a disabled tile shows (rule 5)."""
    if pixmap.isNull():
        return pixmap
    key = int(pixmap.cacheKey())
    found = _GRAY.get(key)
    if found is not None:
        return found
    image = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    for y in range(image.height()):
        for x in range(image.width()):
            colour = image.pixelColor(x, y)
            if colour.alpha() == 0:
                continue
            grey = round(0.2126 * colour.red() + 0.7152 * colour.green() + 0.0722 * colour.blue())
            image.setPixelColor(x, y, QColor(grey, grey, grey, colour.alpha()))
    out = QPixmap.fromImage(image)
    out.setDevicePixelRatio(pixmap.devicePixelRatio())
    _GRAY[key] = out
    return out
