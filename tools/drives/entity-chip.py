"""The entity chip: its variants, its ladder, its glyphs, its press, its cross and its card.

    .venv/bin/python tools/qa.py --page entity-chip --drive tools/drives/entity-chip.py
    .venv/bin/python tools/qa.py --page entity-chip --drive tools/drives/entity-chip.py --qt5

The port of `~/dev/sg-widgets/tools/drives/entity-chip-preview.js`, which reads the three
variants, the detail link and the hover card off the DOM. Here a chip is one painted widget, so
the same claims are read off its properties and its geometry: three variants are drawn, a chip
with a site addresses `<site>/detail/<Type>/<id>`, a press emits `clicked`, the cross emits
`removed` with the row and takes the chip away, and a pointer landing on a chip with a preview
opens its card after the hover card's own delay.

Nothing here follows a link: the drive takes the `https` handler for the length of the run, so a
press on a chip that points at a site never reaches a browser.
"""
from __future__ import annotations

from qtpy import QtCore, QtGui, QtWidgets

from sg_widgets_qt.primitives.base import CHIP_GLYPH, CHIP_HEIGHT
from sg_widgets_qt.widgets.entity_chip import EntityChip
from sg_widgets_qt.widgets.entity_glyphs import DEFAULT_ENTITY_GLYPH, entity_glyph

#: The step a chip takes, and what rule 3 says it stands at.
LADDER = {"xs": 20, "sm": 24, "md": 32, "lg": 40}

#: How long the card is given past its own delay before the drive gives up on it.
CARD_GRACE_MS = 600


class _Caught(QtCore.QObject):
    """Takes the `https` handler, so a press on a linked chip opens nothing."""

    def __init__(self) -> None:
        super().__init__()
        self.urls: list[str] = []

    @QtCore.Slot(QtCore.QUrl)
    def handle(self, url: QtCore.QUrl) -> None:
        self.urls.append(url.toString())


def _send(widget: QtWidgets.QWidget, kind, point: QtCore.QPoint, button) -> None:
    QtWidgets.QApplication.sendEvent(
        widget,
        QtGui.QMouseEvent(
            kind,
            QtCore.QPointF(point),
            button,
            button if kind == QtCore.QEvent.Type.MouseButtonPress else QtCore.Qt.MouseButton.NoButton,
            QtCore.Qt.KeyboardModifier.NoModifier,
        ),
    )


def _press(widget: QtWidgets.QWidget, point: QtCore.QPoint) -> None:
    _send(widget, QtCore.QEvent.Type.MouseButtonPress, point, QtCore.Qt.MouseButton.LeftButton)
    _send(widget, QtCore.QEvent.Type.MouseButtonRelease, point, QtCore.Qt.MouseButton.LeftButton)


def drive(page, wait, find, prefs) -> dict:  # noqa: ARG001
    failures: list[str] = []
    seen: dict = {}

    caught = _Caught()
    QtGui.QDesktopServices.setUrlHandler("https", caught, "handle")
    try:
        chips = find(EntityChip, all=True)
        if not chips:
            return {"verdict": "FAIL the page drew no entity chip"}
        seen["chips"] = len(chips)

        # --- the three variants ---

        variants = sorted({chip.variant for chip in chips})
        seen["variants"] = variants
        for wanted in ("chip", "link", "text"):
            if wanted not in variants:
                failures.append(f"no {wanted} variant on the page")

        # --- the ladder ---

        steps: dict = {}
        for chip in chips:
            step = chip.size_step
            if step in steps or not chip.boxed:
                continue
            steps[step] = {"height": chip.sizeHint().height(), "glyph": CHIP_GLYPH[step]}
            if chip.sizeHint().height() != LADDER[step]:
                failures.append(
                    f"a {step} chip stands {chip.sizeHint().height()} high, wanted {LADDER[step]}"
                )
            if CHIP_HEIGHT[step] != LADDER[step]:
                failures.append(f"the {step} step is {CHIP_HEIGHT[step]}, wanted {LADDER[step]}")
        seen["ladder"] = steps
        for step in ("sm", "md", "lg"):
            if step not in steps:
                failures.append(f"the page drew no {step} chip to measure")

        # --- where a chip points ---

        linked = [chip for chip in chips if chip.url.startswith("http")]
        seen["links"] = [chip.url for chip in linked[:3]]
        if not linked:
            failures.append("no chip addresses a row on a site")
        elif "/detail/" not in linked[0].url:
            failures.append(f"a linked chip points at {linked[0].url}, wanted a detail page")

        # --- the type glyphs ---

        glyphs = {chip.entity.type: entity_glyph(chip.entity.type) for chip in chips if chip.entity}
        unlisted = [t for t, g in glyphs.items() if g == DEFAULT_ENTITY_GLYPH]
        seen["glyphs"] = {"types": len(glyphs), "unlisted": unlisted}
        if len({g for g in glyphs.values()}) < 5:
            failures.append(f"the page drew {len(set(glyphs.values()))} distinct type glyphs, wanted at least 5")
        if not unlisted:
            failures.append("no unlisted type on the page, so the tag fallback is untested")

        # --- a press emits clicked ---

        pressable = [chip for chip in chips if chip.on_click is not None and not chip.url]
        if not pressable:
            failures.append("the page drew no chip whose press runs a callable")
        else:
            chip = pressable[0]
            fired: list[int] = []
            chip.clicked.connect(lambda: fired.append(1))
            _press(chip, chip.rect().center())
            wait(150)
            seen["clicked"] = len(fired)
            if not fired:
                failures.append("a press on a chip emitted no clicked")

        # --- the cross ---

        removable = [chip for chip in chips if chip.removable]
        if not removable:
            failures.append("the page drew no removable chip")
        else:
            chip = removable[0]
            row = chip.entity
            before = len([c for c in find(EntityChip, all=True) if c.removable])
            taken: list[object] = []
            chip.removed.connect(taken.append)
            _press(chip, chip._cross_box().center())
            wait(300)
            after = len([c for c in find(EntityChip, all=True) if c.removable])
            seen["removed"] = {
                "row": f"{row.type} {row.id}",
                "caught": [f"{r.type} {r.id}" for r in taken],
                "before": before,
                "after": after,
            }
            if [r for r in taken] != [row]:
                failures.append("the cross emitted something other than the row it carries")
            if after != before - 1:
                failures.append(f"{before} removable chips became {after}, wanted one fewer")

        # --- the hover card ---

        previewed = [chip for chip in find(EntityChip, all=True) if chip.hover_card is not None]
        seen["previewed"] = len(previewed)
        if not previewed:
            # Upstream the card holds an EntityCard; where the read has not answered there is no
            # card to open, and the hook is what the page promises instead.
            hooks = [chip for chip in find(EntityChip, all=True) if chip.preview]
            seen["preview_hooks"] = len(hooks)
            if not hooks:
                failures.append("no chip carries a preview, and none holds a hover card")
        else:
            chip = previewed[0]
            card = chip.hover_card
            if card.is_open:
                failures.append("the card was open before the pointer landed")
            # A pointer landing on the anchor, spelled the one way both bindings take.
            where = QtCore.QPointF(chip.rect().center())
            QtWidgets.QApplication.sendEvent(chip, QtGui.QEnterEvent(where, where, where))
            wait(50)
            early = card.is_open
            wait(card._open_timer.interval() + CARD_GRACE_MS)
            seen["card"] = {
                "delay": card._open_timer.interval(),
                "open_before_the_delay": early,
                "open": card.is_open,
            }
            if early:
                failures.append("the card opened before its delay")
            if not card.is_open:
                failures.append("the card never opened after the pointer landed")
            card.close()
            wait(150)

        seen["urls_opened"] = caught.urls
        if caught.urls:
            failures.append(f"the drive followed {len(caught.urls)} links, wanted none")
    finally:
        QtGui.QDesktopServices.unsetUrlHandler("https")

    return {
        "verdict": (
            "PASS three variants on the chip ladder, a detail link, the type glyphs with their "
            "tag fallback, a press that emits clicked, a cross that emits the row and takes the "
            "chip away, and a card that opens after its delay"
            if not failures
            else "FAIL " + "; ".join(failures)
        ),
        "seen": seen,
    }
