"""
conftest.py — pytest fixtures for HIL test suite.

Fixtures:
    hil          — connected HILController (session scope)
    hil_fresh    — HILController with reset fall count (function scope)
    fall_dataset — 50-sample fall events loaded from CSV
    adl_dataset  — 200-sample ADL events loaded from CSV
    dhf          — DHFReporter instance (session scope, finaliser saves report)

Configuration (via pytest.ini or CLI):
    --hil-port     Serial port           default: /dev/ttyACM0
    --hil-baud     Baud rate             default: 115200
    --hil-timeout  Command timeout (s)   default: 5.0
    --dataset-dir  Path to CSV datasets  default: ../datasets

IEC 62304 traceability: STS-HIL-002
"""

from __future__ import annotations

import csv
import logging
import os
import time
from pathlib import Path
from typing import List, Dict

import pytest

from hil_controller import HILController
from dhf_reporter import DHFReporter

log = logging.getLogger(__name__)

# ── CLI options ───────────────────────────────────────────────────────────────

def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--hil-port",    default=os.environ.get("HIL_PORT",    "/dev/ttyACM0"))
    parser.addoption("--hil-baud",    default=int(os.environ.get("HIL_BAUD", "115200")),
                     type=int)
    parser.addoption("--hil-timeout", default=float(os.environ.get("HIL_TIMEOUT", "5.0")),
                     type=float)
    parser.addoption("--dataset-dir", default=os.environ.get("DATASET_DIR",
                     str(Path(__file__).parent.parent / "datasets")))
    parser.addoption("--dhf-output",  default=os.environ.get("DHF_OUTPUT",
                     str(Path(__file__).parent.parent / "dhf" / "HIL_Test_Report.json")))
    parser.addoption("--skip-hil",    action="store_true", default=False,
                     help="Skip tests requiring physical HIL board")

# ── HIL board fixtures ────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def hil_config(request: pytest.FixtureRequest) -> Dict[str, object]:
    return {
        "port":    request.config.getoption("--hil-port"),
        "baud":    request.config.getoption("--hil-baud"),
        "timeout": request.config.getoption("--hil-timeout"),
    }


@pytest.fixture(scope="session")
def hil(hil_config: Dict[str, object], request: pytest.FixtureRequest) -> HILController:
    """Session-scoped HIL controller — connected for entire test run."""
    if request.config.getoption("--skip-hil"):
        pytest.skip("--skip-hil: no HIL board available")

    ctrl = HILController(
        port=str(hil_config["port"]),
        baud=int(hil_config["baud"]),      # type: ignore[arg-type]
        timeout=float(hil_config["timeout"]),  # type: ignore[arg-type]
    )
    ctrl.connect()
    log.info("HIL session fixture: connected, version=%s", ctrl.version())
    yield ctrl
    ctrl.disconnect()


@pytest.fixture(scope="function")
def hil_fresh(hil: HILController) -> HILController:
    """Function-scoped fixture: resets fall count and pings before each test."""
    hil.reset_fall_count()
    hil.ping()
    yield hil

# ── Dataset fixtures ──────────────────────────────────────────────────────────

def _load_dataset(path: Path) -> List[Dict[str, int]]:
    """Load CSV accelerometer dataset. Columns: ax,ay,az,gx,gy,gz (mg/mdps)."""
    samples: List[Dict[str, int]] = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            samples.append({
                "ax": int(row["ax"]),
                "ay": int(row["ay"]),
                "az": int(row["az"]),
                "gx": int(row.get("gx", "0")),
                "gy": int(row.get("gy", "0")),
                "gz": int(row.get("gz", "0")),
            })
    return samples


def _load_labeled_dataset(path: Path) -> List[Dict]:
    """Load labeled dataset CSV. Columns: label,event_id,start_sample,end_sample,..."""
    events: List[Dict] = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            events.append(dict(row))
    return events


@pytest.fixture(scope="session")
def dataset_dir(request: pytest.FixtureRequest) -> Path:
    d = Path(str(request.config.getoption("--dataset-dir")))
    if not d.exists():
        pytest.skip(f"Dataset directory not found: {d}")
    return d


@pytest.fixture(scope="session")
def fall_dataset(dataset_dir: Path) -> List[Dict]:
    """50 real-fall event descriptors from captured accelerometer CSV."""
    path = dataset_dir / "falls_50_labeled.csv"
    if not path.exists():
        pytest.skip(f"Fall dataset not found: {path}")
    return _load_labeled_dataset(path)


@pytest.fixture(scope="session")
def adl_dataset(dataset_dir: Path) -> List[Dict]:
    """200 ADL (Activities of Daily Living) event descriptors."""
    path = dataset_dir / "adl_200_labeled.csv"
    if not path.exists():
        pytest.skip(f"ADL dataset not found: {path}")
    return _load_labeled_dataset(path)


@pytest.fixture(scope="session")
def raw_samples(dataset_dir: Path) -> Dict[str, List[Dict[str, int]]]:
    """
    Lazy loader for individual event raw sample CSVs.
    Files named: <event_id>.csv (e.g. fall_001.csv, adl_001.csv)
    """
    cache: Dict[str, List[Dict[str, int]]] = {}

    def _get(event_id: str) -> List[Dict[str, int]]:
        if event_id not in cache:
            p = dataset_dir / "events" / f"{event_id}.csv"
            if not p.exists():
                raise FileNotFoundError(f"Event samples not found: {p}")
            cache[event_id] = _load_dataset(p)
        return cache[event_id]

    return _get   # type: ignore[return-value]

# ── DHF reporter fixture ──────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def dhf(request: pytest.FixtureRequest) -> DHFReporter:
    """Session-scoped DHF reporter. Saves report on teardown."""
    output = Path(str(request.config.getoption("--dhf-output")))
    reporter = DHFReporter(output_path=output)
    yield reporter
    reporter.save()
    log.info("DHF report saved to %s", output)

# ── Timing helper ─────────────────────────────────────────────────────────────

@pytest.fixture
def stopwatch():
    """Returns a simple elapsed-ms function."""
    t0 = [0.0]

    def start() -> None:
        t0[0] = time.perf_counter()

    def elapsed_ms() -> float:
        return (time.perf_counter() - t0[0]) * 1000.0

    return start, elapsed_ms
