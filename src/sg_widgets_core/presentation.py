"""How a reference and a field path are presented.

Two pure functions widgets share: where a row lives in the web app, and the label
a dotted path carries above a value.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from .filter import EntityRef
from .schema_service import PathSegment

__all__ = ["PATH_SEPARATOR", "PathLabelOptions", "entity_detail_url", "normalize_site_url", "path_label"]


def normalize_site_url(site_url: str | None) -> str:
    """Trailing slashes off, so a site url composes with an absolute path."""
    if site_url is None:
        return ""
    return str(site_url).strip().rstrip("/")


def _is_finite(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def entity_detail_url(site_url: str | None, ref: EntityRef | None) -> str | None:
    """The web app's page for one row.

    `Project.landing_page_url` is the only detail address the API hands out, and it is
    the site-relative path `/detail/Project/<id>` with the site url left to the caller
    (entity_types/Project). The same shape addresses every type: on the test site
    `/detail/<Type>/<id>` answers 302 to `/user/login` carrying itself as `return_path`,
    so the route resolves before authentication decides. Site measurement, pending a
    corpus card.

    Answers None when there is no site to link into or no row to link to.
    """
    site = normalize_site_url(site_url)
    if len(site) == 0 or ref is None or not ref.type or not _is_finite(ref.id):
        return None
    return f"{site}/detail/{ref.type}/{ref.id}"


#: The character between the hops of a path label.
PATH_SEPARATOR = " › "


@dataclass
class PathLabelOptions:
    #: Name the type a hop travels through when the hop's field links several types. Default True.
    type_when_ambiguous: bool = True
    #: Display names by schema type name, from `entity_types()`.
    type_labels: dict[str, str] | None = None
    separator: str | None = None


def path_label(segments: Sequence[PathSegment], options: PathLabelOptions | None = None) -> str:
    """The label of a resolved path.

    A hop names its field, and the type only when the field's `valid_types` holds more
    than one: `sg_task.Task.sg_status_list` reads `Task › Status`, while
    `note_links.Shot.sg_sequence` reads `Link › Shot › Sequence` because the same field
    could have gone to an Asset. A projection resolves a dotted path against that
    `valid_types` list (probe 059), so the ambiguity the label spells out is the one the
    read itself has to settle.
    """
    settings = options if options is not None else PathLabelOptions()
    parts: list[str] = []
    for segment in segments:
        parts.append(segment.display_name)
        if segment.through is None:
            continue
        if settings.type_when_ambiguous and len(segment.field.valid_types or []) > 1:
            parts.append((settings.type_labels or {}).get(segment.through, segment.through))
    return (settings.separator if settings.separator is not None else PATH_SEPARATOR).join(parts)
