"""Write src/sg_widgets_qt/theme/palettes.json from the upstream token files.

    python tools/export_palettes.py

Reads `apps/site/src/styles/global.css` and `apps/site/src/styles/themes.css` from the upstream
checkout (`SG_WIDGETS_UPSTREAM`, default `~/dev/sg-widgets`) and writes one light and one dark set
of sRGB hex values per palette. This is the sync path for palettes: run it when either file moves.

The cascade is reproduced, not guessed. `global.css` defines the base tokens on `:root,
[data-stage]` and the base dark tokens on `:root[data-theme='dark'], [data-stage].dark`;
`themes.css` overrides them per palette. A palette's light block and the base dark block carry the
same specificity, and the base block is later in source order, so in dark mode the base dark value
wins over the palette's light value and only the palette's own dark block outranks it.

`default` is the name the showcase gives the base tokens: it has no block in `themes.css`, which
says so at its head, and `demo-prefs.ts` lists it first. `nova` is the separate block that holds
the token set the registry packages ship on `:root`.
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
UPSTREAM = Path(os.environ.get("SG_WIDGETS_UPSTREAM", os.path.expanduser("~/dev/sg-widgets")))
GLOBAL_CSS = "apps/site/src/styles/global.css"
THEMES_CSS = "apps/site/src/styles/themes.css"
OUT = HERE / "src" / "sg_widgets_qt" / "theme" / "palettes.json"

# The showcase order, from `apps/site/src/components/demo-prefs.ts`.
PALETTES: tuple[str, ...] = ("default", "nova", "vercel", "supabase", "claude", "twitter", "catppuccin")

# Every token `themes.css` names, in the order the blocks write them.
TOKENS: tuple[str, ...] = (
    "background",
    "foreground",
    "card",
    "card-foreground",
    "popover",
    "popover-foreground",
    "primary",
    "primary-foreground",
    "secondary",
    "secondary-foreground",
    "muted",
    "muted-foreground",
    "accent",
    "accent-foreground",
    "destructive",
    "destructive-foreground",
    "success",
    "success-foreground",
    "warning",
    "warning-foreground",
    "info",
    "info-foreground",
    "border",
    "input",
    "ring",
    "chart-1",
    "chart-2",
    "chart-3",
    "chart-4",
    "chart-5",
    "sidebar",
    "sidebar-foreground",
    "sidebar-primary",
    "sidebar-primary-foreground",
    "sidebar-accent",
    "sidebar-accent-foreground",
    "sidebar-border",
    "sidebar-ring",
)

WANTED = set(TOKENS) | {"radius", "font-sans", "font-mono"}

# A stack that opens on one of these asks for the platform's own UI font, which a `QFont` with no
# family already is. The palette then names no family and the theme keeps the application font.
SYSTEM_FAMILIES = {"ui-sans-serif", "system-ui", "-apple-system", "blinkmacsystemfont", "ui-monospace"}
GENERIC_FAMILIES = {"sans-serif", "serif", "monospace", "cursive", "fantasy", "inherit", "initial"}

ROOT_PX = 16.0

# oklch -> linear sRGB, from CSS Color 4 and Bjorn Ottosson's published OKLab matrices.
LMS_FROM_OKLAB = (
    (1.0, 0.3963377774, 0.2158037573),
    (1.0, -0.1055613458, -0.0638541728),
    (1.0, -0.0894841775, -1.2914855480),
)
LINEAR_RGB_FROM_LMS = (
    (4.0767416621, -3.3077115913, 0.2309699292),
    (-1.2684380046, 2.6097574011, -0.3413193965),
    (-0.0041960863, -0.7034186147, 1.7076147010),
)
LMS_FROM_LINEAR_RGB = (
    (0.4122214708, 0.5363325363, 0.0514459929),
    (0.2119034982, 0.6806995451, 0.1073969566),
    (0.0883024619, 0.2817188376, 0.6299787005),
)
OKLAB_FROM_LMS = (
    (0.2104542553, 0.7936177850, -0.0040720468),
    (1.9779984951, -2.4285922050, 0.4505937099),
    (0.0259040371, 0.7827717662, -0.8086757660),
)

# CSS Color 4 gamut mapping: the just-noticeable difference in OKLab, and the search precision.
JND = 0.02
EPSILON = 0.0001


# --- colour ----------------------------------------------------------------------------------


def _gamma(c: float) -> float:
    """Linear sRGB channel to gamma-encoded sRGB, the CSS Color 4 transfer function."""
    if c <= 0.0031308:
        return 12.92 * c
    return 1.055 * (abs(c) ** (1 / 2.4)) - 0.055


def _oklch_to_linear(lightness: float, chroma: float, hue: float) -> tuple[float, float, float]:
    rad = math.radians(hue)
    lab = (lightness, chroma * math.cos(rad), chroma * math.sin(rad))
    lms = []
    for row in LMS_FROM_OKLAB:
        v = row[0] * lab[0] + row[1] * lab[1] + row[2] * lab[2]
        lms.append(v * v * v)
    out = []
    for row in LINEAR_RGB_FROM_LMS:
        out.append(row[0] * lms[0] + row[1] * lms[1] + row[2] * lms[2])
    return out[0], out[1], out[2]


def _linear_to_oklab(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    lms = []
    for row in LMS_FROM_LINEAR_RGB:
        v = row[0] * rgb[0] + row[1] * rgb[1] + row[2] * rgb[2]
        lms.append(math.copysign(abs(v) ** (1 / 3), v))
    return tuple(row[0] * lms[0] + row[1] * lms[1] + row[2] * lms[2] for row in OKLAB_FROM_LMS)


def _in_gamut(rgb: tuple[float, float, float], eps: float = 1e-6) -> bool:
    return all(-eps <= c <= 1 + eps for c in rgb)


def _clip(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    return tuple(min(max(c, 0.0), 1.0) for c in rgb)


def oklch_to_srgb(lightness: float, chroma: float, hue: float) -> tuple[int, int, int]:
    """oklch to 8-bit sRGB, gamut-clipped the way CSS Color 4 clips.

    A colour written outside sRGB keeps its lightness and its hue and gives up chroma: the search
    is CSS Color 4's, binary on chroma, taking the clipped candidate as soon as it sits within a
    just-noticeable difference in OKLab of the candidate it clips.
    """
    rgb = _oklch_to_linear(lightness, chroma, hue)
    if not _in_gamut(rgb):
        if lightness <= 0:
            rgb = (0.0, 0.0, 0.0)
        elif lightness >= 1:
            rgb = (1.0, 1.0, 1.0)
        else:
            low, high, low_in_gamut = 0.0, chroma, True
            while high - low > EPSILON:
                mid = (low + high) / 2
                rgb = _oklch_to_linear(lightness, mid, hue)
                if low_in_gamut and _in_gamut(rgb):
                    low = mid
                    continue
                clipped = _clip(rgb)
                delta = math.dist(_linear_to_oklab(clipped), _linear_to_oklab(rgb))
                if delta >= JND:
                    high = mid
                elif JND - delta < EPSILON:
                    rgb = clipped
                    break
                else:
                    low_in_gamut = False
                    low = mid
    return tuple(max(0, min(255, round(_gamma(c) * 255))) for c in _clip(rgb))


def _hsl_to_srgb(hue: float, sat: float, light: float) -> tuple[int, int, int]:
    def channel(n: float) -> float:
        k = (n + hue / 30.0) % 12
        a = sat * min(light, 1 - light)
        return light - a * max(-1.0, min(k - 3, 9 - k, 1.0))

    return tuple(max(0, min(255, round(channel(n) * 255))) for n in (0.0, 8.0, 4.0))  # type: ignore[return-value]


def _hex(rgb: tuple[int, int, int], alpha: float) -> str:
    out = "#{:02x}{:02x}{:02x}".format(*rgb)
    if alpha < 1.0:
        out += f"{max(0, min(255, round(alpha * 255))):02x}"
    return out


def _number(text: str, scale: float = 1.0) -> float:
    text = text.strip()
    if text.endswith("%"):
        return float(text[:-1]) / 100.0
    return float(text) / scale if scale != 1.0 else float(text)


def to_hex(value: str) -> str:
    """A CSS colour from the token files as `#rrggbb` or `#rrggbbaa`."""
    value = value.strip()
    match = re.fullmatch(r"oklch\(\s*([^)]*)\)", value, re.IGNORECASE)
    if match:
        body = match.group(1)
        parts = body.split("/")
        comps = parts[0].split()
        alpha = _number(parts[1]) if len(parts) > 1 else 1.0
        lightness = _number(comps[0])
        chroma = float(comps[1]) if len(comps) > 1 else 0.0
        hue = float(comps[2]) if len(comps) > 2 else 0.0
        return _hex(oklch_to_srgb(lightness, chroma, hue), alpha)

    match = re.fullmatch(r"#([0-9a-fA-F]{3,8})", value)
    if match:
        digits = match.group(1)
        if len(digits) in (3, 4):
            digits = "".join(c * 2 for c in digits)
        if len(digits) == 6:
            return "#" + digits.lower()
        if len(digits) == 8:
            return "#" + digits.lower()
        raise ValueError("unreadable hex: " + value)

    match = re.fullmatch(r"hsla?\(\s*([^)]*)\)", value, re.IGNORECASE)
    if match:
        body = match.group(1).replace(",", " ")
        parts = body.split("/")
        comps = parts[0].split()
        alpha = _number(parts[1]) if len(parts) > 1 else (_number(comps[3]) if len(comps) > 3 else 1.0)
        hue = float(re.sub(r"deg$", "", comps[0]))
        return _hex(_hsl_to_srgb(hue, _number(comps[1]), _number(comps[2])), alpha)

    match = re.fullmatch(r"rgba?\(\s*([^)]*)\)", value, re.IGNORECASE)
    if match:
        body = match.group(1).replace(",", " ")
        parts = body.split("/")
        comps = parts[0].split()
        alpha = _number(parts[1]) if len(parts) > 1 else (_number(comps[3]) if len(comps) > 3 else 1.0)
        chans = tuple(round(_number(c) * (255 if c.strip().endswith("%") else 1)) for c in comps[:3])
        return _hex(chans, alpha)  # type: ignore[arg-type]

    raise ValueError("unreadable colour: " + value)


# --- css -------------------------------------------------------------------------------------


Block = dict[str, str]


def read_blocks(text: str) -> list[tuple[list[str], Block]]:
    """Every innermost rule in a stylesheet, as its selectors and the declarations we want."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    out: list[tuple[list[str], Block]] = []
    for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", text):
        # An at-statement (`@import`, `@source`) ends on a semicolon and leaves no brace, so what
        # precedes the last one is not part of this rule's selector.
        selector = selector.rsplit(";", 1)[-1]
        selectors = [re.sub(r"\s+", " ", s).strip() for s in selector.split(",")]
        selectors = [s for s in selectors if s]
        decls: Block = {}
        for line in body.split(";"):
            if ":" not in line:
                continue
            name, _, value = line.partition(":")
            name = name.strip()
            if name.startswith("--") and name[2:] in WANTED:
                decls[name[2:]] = value.strip()
        if decls:
            out.append((selectors, decls))
    return out


def merge(target: Block, source: Block) -> Block:
    target.update(source)
    return target


def resolve_vars(block: Block) -> Block:
    """Flatten `var(--other)` inside a block, which the base token block uses for its foregrounds."""
    for _ in range(8):
        changed = False
        for name, value in list(block.items()):
            match = re.fullmatch(r"var\(\s*--([a-z0-9-]+)\s*\)", value.strip())
            if match and match.group(1) in block:
                block[name] = block[match.group(1)]
                changed = True
        if not changed:
            break
    return block


def first_family(stack: str) -> str:
    """The family a `--font-sans` stack names, or an empty string when it asks for the system font."""
    for part in stack.split(","):
        name = part.strip().strip("'\"").strip()
        if not name:
            continue
        low = name.lower()
        if low in SYSTEM_FAMILIES:
            return ""
        if low in GENERIC_FAMILIES:
            continue
        if name.endswith(" Variable"):
            name = name[: -len(" Variable")]
        return name
    return ""


def radius_px(value: str) -> int:
    value = value.strip()
    if value.endswith("rem"):
        return int(round(float(value[:-3]) * ROOT_PX))
    if value.endswith("px"):
        return int(round(float(value[:-2])))
    return int(round(float(value) * ROOT_PX))


def collect(global_css: str, themes_css: str) -> tuple[dict[str, dict[str, Block]], dict[str, int], str]:
    base_light: Block = {}
    base_dark: Block = {}
    default_font = ""
    for selectors, decls in read_blocks(global_css):
        joined = set(selectors)
        if joined == {":root", "[data-stage]"}:
            merge(base_light, decls)
        elif joined == {":root[data-theme='dark']", "[data-stage].dark"}:
            merge(base_dark, decls)
        elif selectors == ["@theme inline"] and "font-sans" in decls:
            default_font = decls["font-sans"]

    palette_light: dict[str, Block] = {name: {} for name in PALETTES}
    palette_dark: dict[str, Block] = {name: {} for name in PALETTES}
    radii: dict[str, int] = {}
    for selectors, decls in read_blocks(themes_css):
        for selector in selectors:
            match = re.fullmatch(r"\.sg-demo\[data-theme='([a-z]+)'\](\.dark)?", selector)
            if match:
                name, dark = match.group(1), bool(match.group(2))
                if name not in palette_light:
                    continue
                merge(palette_dark[name] if dark else palette_light[name], decls)
                continue
            match = re.fullmatch(r"\.sg-demo\[data-radius='([a-z]+)'\]", selector)
            if match and "radius" in decls:
                radii[match.group(1)] = radius_px(decls["radius"])
    return (
        {
            name: {
                "light": resolve_vars(merge(dict(base_light), palette_light[name])),
                "dark": resolve_vars(
                    merge(merge(merge(dict(base_light), palette_light[name]), base_dark), palette_dark[name])
                ),
            }
            for name in PALETTES
        },
        radii,
        default_font,
    )


def to_theme(block: Block, default_font: str) -> dict[str, object]:
    out: dict[str, object] = {}
    for token in TOKENS:
        if token not in block:
            raise SystemExit(f"token --{token} is defined nowhere")
        out[token.replace("-", "_")] = to_hex(block[token])
    out["radius"] = radius_px(block["radius"])
    out["font_sans"] = first_family(block.get("font-sans", default_font))
    out["font_mono"] = first_family(block.get("font-mono", ""))
    return out


def main(argv: list[str] | None = None) -> int:
    for name in (GLOBAL_CSS, THEMES_CSS):
        if not (UPSTREAM / name).exists():
            print("upstream file not found: %s" % (UPSTREAM / name), file=sys.stderr)
            return 2
    blocks, radii, default_font = collect(
        (UPSTREAM / GLOBAL_CSS).read_text(encoding="utf-8"),
        (UPSTREAM / THEMES_CSS).read_text(encoding="utf-8"),
    )
    out = {name: {mode: to_theme(block, default_font) for mode, block in modes.items()} for name, modes in blocks.items()}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"{len(out)} palettes -> {OUT}")
    print("radius override: " + ", ".join("{} {}px".format(*item) for item in sorted(radii.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
