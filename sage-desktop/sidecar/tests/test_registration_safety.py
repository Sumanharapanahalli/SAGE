"""End-to-end registration tests for safety.*.

``handlers/safety.py`` was fully written and unit-tested (see test_safety.py)
but never imported in ``app.py``, so it was absent from ``_build_dispatcher``
and every call returned -32601. test_safety.py could not catch that: it
imports the handler module directly and never goes through the dispatcher.

These tests drive the REAL NDJSON event loop (io.StringIO in/out, same as
test_main.py), so dropping a registration fails here.

``functional_safety.py`` is a stateless, stdlib-only computation engine with
nothing to wire at startup, so these drive the sidecar with an empty argv —
no solution is required.
"""

from __future__ import annotations

import io
import json

import app as sidecar_app

METHOD_NOT_FOUND = -32601


def _req(id: str, method: str, params: dict | None = None) -> str:
    return json.dumps(
        {"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}}
    )


def _drive(lines: list[str]) -> list[dict]:
    stdin = io.StringIO("".join(line + "\n" for line in lines))
    stdout = io.StringIO()
    sidecar_app.run(stdin=stdin, stdout=stdout, argv=[])
    stdout.seek(0)
    return [json.loads(ln) for ln in stdout.read().splitlines() if ln.strip()]


FMEA_ENTRIES = [
    {
        "component": "pump",
        "failure_mode": "stall",
        "effect": "no flow",
        "severity": 9,
        "occurrence": 7,
        "detection": 6,
    },
    {
        "component": "sensor",
        "failure_mode": "drift",
        "effect": "bad reading",
        "severity": 2,
        "occurrence": 2,
        "detection": 2,
    },
]

# Nested tree — the shape calculate_fta() actually expects. Each leaf carries
# BOTH "event" and "probability": the engine keys probability off one and cut
# sets off the other, so omitting either silently degrades one of the results.
FTA_TREE = {
    "top_event": "loss of infusion",
    "gate": "OR",
    "children": [
        {"event": "pump stall", "probability": 0.001},
        {"event": "power loss", "probability": 0.002},
    ],
}


def test_all_safety_methods_are_registered():
    """The regression this whole file exists for: every safety.* method must
    resolve. A missing registration shows up as -32601."""
    methods = [
        ("safety.fmea", {"entries": FMEA_ENTRIES}),
        ("safety.fta", {"tree": FTA_TREE}),
        (
            "safety.asil",
            {"severity": "S3", "exposure": "E4", "controllability": "C3"},
        ),
        ("safety.sil", {"probability_dangerous_failure_per_hour": 1e-8}),
        ("safety.iec62304", {"risk_level": "death_possible"}),
    ]
    out = _drive([_req(str(i), m, p) for i, (m, p) in enumerate(methods)])

    assert len(out) == len(methods)
    for resp, (method, _) in zip(out, methods):
        assert "result" in resp, f"{method} not registered/failed: {resp}"
        error = resp.get("error")
        assert error is None or error.get("code") != METHOD_NOT_FOUND


def test_fmea_returns_engine_shape_sorted_by_rpn():
    out = _drive([_req("1", "safety.fmea", {"entries": FMEA_ENTRIES})])
    result = out[0]["result"]

    assert result["summary"]["total_entries"] == 2
    rpns = [e["rpn"] for e in result["entries"]]
    assert rpns == sorted(rpns, reverse=True), "entries must be RPN-descending"
    # 9 * 7 * 6 = 378
    assert result["entries"][0]["rpn"] == 378
    assert result["entries"][0]["component"] == "pump"


def test_fta_accepts_a_nested_tree_and_returns_cut_sets():
    """Regression guard against the web UI's bug: it posts a FLAT ``gates``
    list, which this engine cannot walk. Desktop must send the nested tree."""
    out = _drive([_req("1", "safety.fta", {"tree": FTA_TREE})])
    result = out[0]["result"]

    assert result["top_event"] == "loss of infusion"
    assert result["probability"] > 0, "flat/malformed trees silently yield 0.0"
    assert result["minimal_cut_sets"], "leaf nodes need both event+probability"
    # An OR of two single events — each event alone fails the top event.
    assert len(result["single_point_failures"]) == 2


def test_asil_returns_asil_not_asil_level():
    """The engine's field is ``asil``. The web page reads ``asil_level ??
    classification`` — neither exists, so its ASIL tab renders blank. Pin the
    real contract so the desktop page is built against it."""
    out = _drive(
        [
            _req(
                "1",
                "safety.asil",
                {"severity": "S3", "exposure": "E4", "controllability": "C3"},
            )
        ]
    )
    result = out[0]["result"]

    assert result["asil"] == "D"
    assert "asil_level" not in result
    assert "classification" not in result
    assert result["standard"] == "ISO 26262"


def test_sil_returns_sil_not_sil_level():
    out = _drive(
        [_req("1", "safety.sil", {"probability_dangerous_failure_per_hour": 1e-8})]
    )
    result = out[0]["result"]

    assert result["sil"] == 4
    assert "sil_level" not in result
    assert result["standard"] == "IEC 61508"


def test_iec62304_returns_required_processes_not_requirements():
    out = _drive([_req("1", "safety.iec62304", {"risk_level": "death_possible"})])
    result = out[0]["result"]

    assert result["safety_class"] == "C"
    assert isinstance(result["required_processes"], list)
    assert result["required_processes"]
    assert "requirements" not in result


def test_invalid_params_surface_as_invalid_params_not_method_not_found():
    """A bad call must reach the handler's own validation — proving the method
    resolved rather than falling through to the unknown-method path."""
    out = _drive(
        [
            _req("1", "safety.fmea", {"entries": []}),
            _req("2", "safety.sil", {"probability_dangerous_failure_per_hour": -1}),
            _req("3", "safety.asil", {"severity": "S3"}),
        ]
    )
    for resp in out:
        assert "error" in resp
        assert resp["error"]["code"] != METHOD_NOT_FOUND
        assert resp["error"]["code"] == -32602
