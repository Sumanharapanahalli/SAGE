"""Tests for the safety handler.

functional_safety.py is a pure, stateless computation engine (like
compliance_flags.py) — no store to wire, so the handler imports it directly.

Several of these assertions are deliberate regression checks against the web
UI's broken safety page: the FTA tree must be passed through NESTED (web sent
a flat `gates` list to a path written with backslashes), and the result field
names are the engine's real ones (`asil`, `sil`, `required_processes`), not
the names the web page reads (`asil_level`, `sil_level`, `requirements`).
"""

from __future__ import annotations

import pytest

from handlers import safety
from rpc import RpcError


# ── FMEA ───────────────────────────────────────────────────────────────────


def test_fmea_computes_rpn_and_sorts_descending():
    out = safety.fmea(
        {
            "entries": [
                {
                    "component": "sensor",
                    "failure_mode": "drift",
                    "effect": "bad reading",
                    "severity": 2,
                    "occurrence": 2,
                    "detection": 2,
                },
                {
                    "component": "pump",
                    "failure_mode": "stall",
                    "effect": "no flow",
                    "severity": 9,
                    "occurrence": 5,
                    "detection": 6,
                },
            ]
        }
    )
    rpns = [e["rpn"] for e in out["entries"]]
    assert rpns == [270, 8]
    assert out["entries"][0]["risk_level"] == "critical"
    assert out["entries"][0]["action_required"] is True
    assert out["summary"]["max_rpn"] == 270
    assert out["summary"]["total_entries"] == 2
    assert out["summary"]["critical_count"] == 1


def test_fmea_rejects_out_of_range_score():
    with pytest.raises(RpcError) as ei:
        safety.fmea(
            {
                "entries": [
                    {
                        "component": "c",
                        "failure_mode": "f",
                        "effect": "e",
                        "severity": 11,
                        "occurrence": 1,
                        "detection": 1,
                    },
                ]
            }
        )
    assert ei.value.code == -32602  # invalid params, not a generic sidecar error


def test_fmea_rejects_non_integer_score():
    with pytest.raises(RpcError):
        safety.fmea(
            {
                "entries": [
                    {
                        "component": "c",
                        "failure_mode": "f",
                        "effect": "e",
                        "severity": "high",
                        "occurrence": 1,
                        "detection": 1,
                    },
                ]
            }
        )


def test_fmea_requires_non_empty_entries():
    with pytest.raises(RpcError):
        safety.fmea({"entries": []})
    with pytest.raises(RpcError):
        safety.fmea({})


# ── FTA ────────────────────────────────────────────────────────────────────


def _tree() -> dict:
    # Leaves carry BOTH "event" and "probability": the engine keys probability
    # off one and cut sets off the other.
    return {
        "top_event": "Loss of therapy",
        "gate": "OR",
        "children": [
            {"event": "PSU dead", "probability": 0.01},
            {
                "gate": "AND",
                "children": [
                    {"event": "Primary sensor fails", "probability": 0.1},
                    {"event": "Backup sensor fails", "probability": 0.2},
                ],
            },
        ],
    }


def test_fta_passes_the_nested_tree_through_and_finds_cut_sets():
    out = safety.fta({"tree": _tree()})
    assert out["top_event"] == "Loss of therapy"
    # OR of 0.01 and (AND 0.1*0.2 = 0.02) -> 1 - .99*.98 = 0.0298
    assert out["probability"] == pytest.approx(0.0298)
    assert out["minimal_cut_sets"] == [
        ["PSU dead"],
        ["Backup sensor fails", "Primary sensor fails"],
    ]
    assert out["single_point_failures"] == [["PSU dead"]]


def test_fta_rejects_a_non_dict_tree():
    with pytest.raises(RpcError):
        safety.fta({"tree": [{"event": "x", "probability": 0.1}]})
    with pytest.raises(RpcError):
        safety.fta({})


# ── ASIL (ISO 26262) ───────────────────────────────────────────────────────


def test_asil_derives_d_at_the_worst_corner_of_the_matrix():
    out = safety.asil({"severity": "S3", "exposure": "E4", "controllability": "C3"})
    assert out["asil"] == "D"
    assert out["standard"] == "ISO 26262"


def test_asil_derives_qm_for_a_no_injury_hazard():
    out = safety.asil({"severity": "S0", "exposure": "E4", "controllability": "C3"})
    assert out["asil"] == "QM"


def test_asil_requires_all_three_parameters():
    with pytest.raises(RpcError):
        safety.asil({"severity": "S3", "exposure": "E4"})


# ── SIL (IEC 61508) ────────────────────────────────────────────────────────


def test_sil_classifies_from_the_failure_rate():
    assert safety.sil({"probability_dangerous_failure_per_hour": 1e-7})["sil"] == 3
    assert safety.sil({"probability_dangerous_failure_per_hour": 1e-9})["sil"] == 4
    below = safety.sil({"probability_dangerous_failure_per_hour": 1e-3})
    assert below["sil"] == 0


def test_sil_rejects_a_non_numeric_rate():
    with pytest.raises(RpcError):
        safety.sil({"probability_dangerous_failure_per_hour": "1e-7"})
    with pytest.raises(RpcError):
        safety.sil({})


# ── IEC 62304 ──────────────────────────────────────────────────────────────


def test_iec62304_derives_class_c_for_death_possible():
    out = safety.iec62304({"risk_level": "death_possible"})
    assert out["safety_class"] == "C"
    assert "full_traceability" in out["required_processes"]


def test_iec62304_derives_class_a_for_no_injury():
    out = safety.iec62304({"risk_level": "no_injury"})
    assert out["safety_class"] == "A"


def test_iec62304_requires_risk_level():
    with pytest.raises(RpcError):
        safety.iec62304({})
