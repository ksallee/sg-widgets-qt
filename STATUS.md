# Status

What is ported from `~/dev/sg-widgets`, what is partial, what is left. `python tools/sync_status.py`
is the live version of this page; this one adds the reasons.

## Core

| module | status | note |
|---|---|---|

## Theme, workers, icons

| item | status | note |
|---|---|---|

## Primitives

| item | status | note |
|---|---|---|

## Widgets

| widget | core | widget | demo | tables | docs | tests | shots |
|---|---|---|---|---|---|---|---|

## Not ported

| upstream | reason |
|---|---|
| `packages/core/src/proxy-client.ts`, `proxy-handler.ts` | A browser proxy over the REST API. A Qt app holds its own credentials and calls shotgun_api3 directly. |
| `packages/core/src/session-auth.ts` | The App Session Launcher flow for a browser. A later pass may port it for a person signing in from a DCC. |
| `packages/core/src/client.ts` `RestClient` | Replaced by `ShotgunClient` on shotgun_api3. |
