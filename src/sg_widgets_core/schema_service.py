"""Schema service.

The one place a widget asks about types, fields, dotted paths and the statuses a
project offers. Every read goes through a `QueryCache`, so a type's fields are
fetched once however many widgets ask: `/schema/<Type>/fields` is 48KB and ~330ms
and must never be looped (probe 002).

Field reads are site scope. `project_id` changes only `hidden_values` (probe 009),
so the project-scoped read is the single-field endpoint, 1.2KB against 48KB.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass

from .client import EntityTypeInfo, SgClient
from .query import QueryCache, QueryCacheOptions, create_query_cache
from .schema import FieldSchema, status_field_for
from .status import StatusOption, intersect_statuses, usable_statuses

__all__ = [
    "DEFAULT_TTL_MS",
    "PathSegment",
    "SchemaService",
    "SchemaServiceOptions",
    "create_schema_service",
]

#: One hour. Schema is site configuration; it does not move under a session.
DEFAULT_TTL_MS = 3_600_000.0


@dataclass
class SchemaServiceOptions:
    #: How long a schema read stays fresh. Ignored when a `QueryCache` is passed in. Default one hour.
    ttl_ms: float = DEFAULT_TTL_MS


@dataclass
class PathSegment:
    """One step of a resolved dotted path."""

    #: Type this segment was read on.
    entity_type: str
    #: Programmatic field name.
    name: str
    display_name: str
    data_type: str
    field: FieldSchema
    #: For a link that the path continues through: the type the next segment reads on.
    through: str | None = None


def _is_query_cache(client: SgClient | QueryCache) -> bool:
    return callable(getattr(client, "invalidate", None))


class SchemaService:
    """Types, fields, dotted paths and the statuses a project offers."""

    def __init__(self, client: SgClient | QueryCache, options: SchemaServiceOptions | None = None) -> None:
        settings = options if options is not None else SchemaServiceOptions()
        self._owned = not _is_query_cache(client)
        self._cache: QueryCache = (
            create_query_cache(client, QueryCacheOptions(ttl_ms=settings.ttl_ms))
            if self._owned
            else client  # type: ignore[assignment]
        )

    def entity_types(self) -> list[EntityTypeInfo]:
        """Enabled types with their display names."""
        return self._cache.entity_types()

    def fields(self, entity_type: str) -> dict[str, FieldSchema]:
        """Every field of a type, at site scope."""
        return self._cache.fields(entity_type)

    def field(self, entity_type: str, name: str) -> FieldSchema | None:
        return self.fields(entity_type).get(name)

    def hidden_values(self, entity_type: str, name: str, project_id: int) -> list[str]:
        """Codes the project hides on a list or status field."""
        scoped = self._cache.field_with_project(entity_type, name, project_id)
        return scoped.hidden_values if scoped.hidden_values is not None else []

    def status_field(self, entity_type: str) -> FieldSchema | str:
        """The type's status field, or its conventional name when the type has none."""
        return status_field_for(entity_type, self.fields(entity_type))

    def _scoped_status_field(
        self,
        entity_type: str,
        project_id: int | None = None,
        name: str | None = None,
    ) -> FieldSchema | None:
        """The status field's site vocabulary with the project's hidden codes attached."""
        found = self.status_field(entity_type) if name is None else self.fields(entity_type).get(name)
        if found is None or isinstance(found, str):
            return None
        if project_id is None:
            return found
        return dataclasses.replace(found, hidden_values=self.hidden_values(entity_type, found.name, project_id))

    def status_options(
        self,
        entity_type: str,
        project_id: int | None = None,
        field: str | None = None,
    ) -> list[StatusOption]:
        """Statuses a picker may offer.

        Without `project_id` the site vocabulary, which hides nothing. `field` names a
        list or status field other than the type's own status field.
        """
        found = self._scoped_status_field(entity_type, project_id, field)
        return usable_statuses(found) if found is not None else []

    def status_options_for_projects(
        self,
        entity_type: str,
        project_ids: list[int],
        field: str | None = None,
    ) -> list[StatusOption]:
        """Statuses usable in every one of the projects."""
        if len(project_ids) == 0:
            return []
        scoped = [self._scoped_status_field(entity_type, project_id, field) for project_id in project_ids]
        present = [f for f in scoped if f is not None]
        return intersect_statuses(present) if len(present) == len(project_ids) else []

    def resolve_path(self, root_type: str, dotted_path: str) -> list[PathSegment]:
        """Walk `entity.Shot.code` into its segments.

        Raises naming the whole path when a segment does not resolve.
        """
        parts = [p for p in dotted_path.split(".") if p]
        if len(parts) == 0:
            raise ValueError(f"Empty field path on {root_type}.")
        # A path is `field`, or `field.Type.field` repeated: every hop names the type it travels through.
        if len(parts) % 2 == 0:
            raise ValueError(f"{root_type}.{dotted_path} is not a field path: it ends on a type.")
        segments: list[PathSegment] = []
        entity_type = root_type
        i = 0
        while i < len(parts):
            name = parts[i]
            schema = self.fields(entity_type).get(name)
            if schema is None:
                raise ValueError(
                    f"{root_type}.{dotted_path} does not exist: {entity_type} has no field '{name}'."
                )
            if i == len(parts) - 1:
                segments.append(PathSegment(
                    entity_type=entity_type,
                    name=name,
                    display_name=schema.display_name,
                    data_type=schema.data_type,
                    field=schema,
                ))
                break
            # A dotted path names the type it travels through, and a projection checks that
            # middle segment against the field's `valid_types` (probe 059).
            through = parts[i + 1]
            if through not in (schema.valid_types or []):
                raise ValueError(
                    f"{root_type}.{dotted_path} does not exist: {entity_type}.{name} does not link {through}."
                )
            segments.append(PathSegment(
                entity_type=entity_type,
                name=name,
                display_name=schema.display_name,
                data_type=schema.data_type,
                field=schema,
                through=through,
            ))
            entity_type = through
            i += 2
        return segments

    def invalidate(self) -> None:
        # A shared cache holds the caller's row reads too, so drop only the schema keys.
        if self._owned:
            self._cache.invalidate()
        else:
            for prefix in ("entity_types", "fields", "field_with_project"):
                self._cache.invalidate(prefix)


def create_schema_service(
    client: SgClient | QueryCache,
    options: SchemaServiceOptions | None = None,
) -> SchemaService:
    """A schema service over a client, or over a cache several services share."""
    return SchemaService(client, options)
