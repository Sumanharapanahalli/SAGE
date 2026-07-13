"""Collect every route path from a FastAPI app, including included sub-routers.

`[r.path for r in app.routes]` was the idiom across the endpoint-existence tests. It
raises AttributeError on the installed FastAPI: `app.routes` can hold an
`_IncludedRouter`, which has no `.path` — it holds nested `.routes`. That turned seven
"does this endpoint exist?" tests into guaranteed errors, which is worse than a failure:
a crashing test cannot detect a genuinely missing endpoint, so it was false safety.

Walk the tree instead, so a route is found whether it is declared on the app directly
or contributed by an included router.
"""
from __future__ import annotations

from typing import Any


def route_paths(app: Any) -> list[str]:
    """Every route path reachable from ``app``, recursing through included routers."""
    paths: list[str] = []
    stack = list(getattr(app, "routes", []) or [])
    seen: set[int] = set()

    while stack:
        route = stack.pop()
        if id(route) in seen:  # defensive: a router cycle must not hang the suite
            continue
        seen.add(id(route))

        path = getattr(route, "path", None)
        if isinstance(path, str):
            paths.append(path)

        # An _IncludedRouter (or an APIRouter) carries its routes here.
        nested = getattr(route, "routes", None)
        if nested:
            stack.extend(nested)

    return paths
