"""
Traceability Matrix Engine
===========================
Bidirectional requirement-to-design-to-test-to-verification linking.
Core compliance requirement for IEC 62304, ISO 26262, DO-178C, and EN 50128.

Each TraceLink connects two items. The matrix provides:
  - Forward traceability: requirement → design → test → verification
  - Backward traceability: verification → test → design → requirement
  - Coverage analysis: which requirements lack tests, which tests lack requirements
  - Gap detection: orphaned items at any level
"""

import json
import logging
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Set

from src.core.db import get_connection

logger = logging.getLogger(__name__)


class TraceLevel(Enum):
    """Levels in the traceability hierarchy."""
    USER_NEED = "user_need"
    SYSTEM_REQ = "system_requirement"
    SOFTWARE_REQ = "software_requirement"
    DESIGN = "design_element"
    IMPLEMENTATION = "implementation"
    UNIT_TEST = "unit_test"
    INTEGRATION_TEST = "integration_test"
    SYSTEM_TEST = "system_test"
    VERIFICATION = "verification"
    VALIDATION = "validation"


@dataclass
class TraceItem:
    """An item in the traceability matrix."""
    id: str
    level: TraceLevel
    title: str
    description: str = ""
    source_file: str = ""
    source_line: int = 0
    status: str = "active"  # active, deprecated, deleted
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        d = asdict(self)
        d["level"] = self.level.value
        return d


@dataclass
class TraceLink:
    """A directional link between two trace items."""
    id: str
    source_id: str
    target_id: str
    link_type: str = "derives"  # derives, implements, verifies, validates, satisfies
    rationale: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    created_by: str = "system"

    def to_dict(self) -> dict:
        return asdict(self)


class TraceabilityMatrix:
    """
    Manages bidirectional traceability across the full V-model.

    Storage: SQLite in the solution's .sage/ directory.
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = self._default_db_path()
        self.db_path = db_path
        self._init_db()

    @staticmethod
    def _default_db_path() -> str:
        project = os.environ.get("SAGE_PROJECT", "").strip().lower()
        solutions_dir = os.environ.get(
            "SAGE_SOLUTIONS_DIR",
            os.path.join(os.path.dirname(__file__), "..", "..", "solutions"),
        )
        if project:
            sage_dir = os.path.join(os.path.abspath(solutions_dir), project, ".sage")
        else:
            sage_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                ".sage",
            )
        os.makedirs(sage_dir, exist_ok=True)
        return os.path.join(sage_dir, "traceability.db")

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = get_connection(self.db_path, row_factory=None)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trace_items (
                id TEXT PRIMARY KEY,
                level TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                source_file TEXT DEFAULT '',
                source_line INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active',
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trace_links (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                link_type TEXT DEFAULT 'derives',
                rationale TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                created_by TEXT DEFAULT 'system',
                FOREIGN KEY (source_id) REFERENCES trace_items(id),
                FOREIGN KEY (target_id) REFERENCES trace_items(id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_links_source ON trace_links(source_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_links_target ON trace_links(target_id)")
        conn.commit()
        conn.close()

    # -- CRUD: Items ----------------------------------------------------------

    def add_item(self, level: TraceLevel, title: str, description: str = "",
                 source_file: str = "", source_line: int = 0, item_id: str = None) -> TraceItem:
        item = TraceItem(
            id=item_id or f"{level.value[:3].upper()}-{uuid.uuid4().hex[:8]}",
            level=level, title=title, description=description,
            source_file=source_file, source_line=source_line,
        )
        conn = get_connection(self.db_path, row_factory=None)
        conn.execute(
            "INSERT INTO trace_items (id, level, title, description, source_file, source_line, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (item.id, item.level.value, item.title, item.description,
             item.source_file, item.source_line, item.status, item.created_at),
        )
        conn.commit()
        conn.close()
        return item

    def get_item(self, item_id: str) -> Optional[TraceItem]:
        conn = get_connection(self.db_path, row_factory=None)
        row = conn.execute("SELECT * FROM trace_items WHERE id = ?", (item_id,)).fetchone()
        conn.close()
        if not row:
            return None
        return TraceItem(
            id=row[0], level=TraceLevel(row[1]), title=row[2], description=row[3],
            source_file=row[4], source_line=row[5], status=row[6], created_at=row[7],
        )

    def list_items(self, level: Optional[TraceLevel] = None, status: str = "active") -> List[TraceItem]:
        conn = get_connection(self.db_path, row_factory=None)
        if level:
            rows = conn.execute(
                "SELECT * FROM trace_items WHERE level = ? AND status = ? ORDER BY id", (level.value, status)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM trace_items WHERE status = ? ORDER BY id", (status,)
            ).fetchall()
        conn.close()
        return [
            TraceItem(id=r[0], level=TraceLevel(r[1]), title=r[2], description=r[3],
                      source_file=r[4], source_line=r[5], status=r[6], created_at=r[7])
            for r in rows
        ]

    # -- CRUD: Links ----------------------------------------------------------

    def add_link(self, source_id: str, target_id: str, link_type: str = "derives",
                 rationale: str = "", created_by: str = "system") -> TraceLink:
        link = TraceLink(
            id=str(uuid.uuid4()), source_id=source_id, target_id=target_id,
            link_type=link_type, rationale=rationale, created_by=created_by,
        )
        conn = get_connection(self.db_path, row_factory=None)
        conn.execute(
            "INSERT INTO trace_links (id, source_id, target_id, link_type, rationale, created_at, created_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (link.id, link.source_id, link.target_id, link.link_type, link.rationale, link.created_at, link.created_by),
        )
        conn.commit()
        conn.close()
        return link

    def get_forward_links(self, item_id: str) -> List[dict]:
        """Get all items this item traces TO (forward traceability)."""
        conn = get_connection(self.db_path, row_factory=None)
        rows = conn.execute("""
            SELECT tl.link_type, tl.rationale, ti.id, ti.level, ti.title, ti.status
            FROM trace_links tl JOIN trace_items ti ON tl.target_id = ti.id
            WHERE tl.source_id = ?
        """, (item_id,)).fetchall()
        conn.close()
        return [{"link_type": r[0], "rationale": r[1], "target_id": r[2],
                 "target_level": r[3], "target_title": r[4], "target_status": r[5]} for r in rows]

    def get_backward_links(self, item_id: str) -> List[dict]:
        """Get all items that trace TO this item (backward traceability)."""
        conn = get_connection(self.db_path, row_factory=None)
        rows = conn.execute("""
            SELECT tl.link_type, tl.rationale, ti.id, ti.level, ti.title, ti.status
            FROM trace_links tl JOIN trace_items ti ON tl.source_id = ti.id
            WHERE tl.target_id = ?
        """, (item_id,)).fetchall()
        conn.close()
        return [{"link_type": r[0], "rationale": r[1], "source_id": r[2],
                 "source_level": r[3], "source_title": r[4], "source_status": r[5]} for r in rows]

    # -- Analysis -------------------------------------------------------------

    def coverage_report(self) -> dict:
        """
        Compute traceability coverage per level.
        Returns items with and without forward/backward links.
        """
        items = self.list_items()
        conn = get_connection(self.db_path, row_factory=None)
        all_sources = {r[0] for r in conn.execute("SELECT DISTINCT source_id FROM trace_links").fetchall()}
        all_targets = {r[0] for r in conn.execute("SELECT DISTINCT target_id FROM trace_links").fetchall()}
        conn.close()

        coverage = {}
        for level in TraceLevel:
            level_items = [i for i in items if i.level == level]
            if not level_items:
                continue
            traced_forward = [i for i in level_items if i.id in all_sources]
            traced_backward = [i for i in level_items if i.id in all_targets]
            orphaned = [i for i in level_items if i.id not in all_sources and i.id not in all_targets]
            total = len(level_items)
            coverage[level.value] = {
                "total": total,
                "traced_forward": len(traced_forward),
                "traced_backward": len(traced_backward),
                "orphaned": len(orphaned),
                "forward_coverage_pct": round(len(traced_forward) / total * 100, 1) if total else 0,
                "backward_coverage_pct": round(len(traced_backward) / total * 100, 1) if total else 0,
                "orphaned_ids": [i.id for i in orphaned],
            }

        total_items = len(items)
        total_linked = len(all_sources | all_targets)
        return {
            "total_items": total_items,
            "total_linked": total_linked,
            "overall_coverage_pct": round(total_linked / total_items * 100, 1) if total_items else 0,
            "per_level": coverage,
        }

    def gap_analysis(self) -> dict:
        """
        Identify traceability gaps per IEC 62304:
        - Requirements without tests
        - Tests without requirements
        - Design elements without implementation
        """
        items = self.list_items()
        conn = get_connection(self.db_path, row_factory=None)
        all_sources = {r[0] for r in conn.execute("SELECT DISTINCT source_id FROM trace_links").fetchall()}
        all_targets = {r[0] for r in conn.execute("SELECT DISTINCT target_id FROM trace_links").fetchall()}
        conn.close()

        reqs = [i for i in items if i.level in (TraceLevel.SYSTEM_REQ, TraceLevel.SOFTWARE_REQ)]
        tests = [i for i in items if i.level in (TraceLevel.UNIT_TEST, TraceLevel.INTEGRATION_TEST, TraceLevel.SYSTEM_TEST)]
        designs = [i for i in items if i.level == TraceLevel.DESIGN]

        reqs_without_tests = [i.id for i in reqs if i.id not in all_sources]
        tests_without_reqs = [i.id for i in tests if i.id not in all_targets]
        design_without_impl = [i.id for i in designs if i.id not in all_sources]

        gaps = []
        if reqs_without_tests:
            gaps.append({"type": "requirements_without_tests", "severity": "HIGH",
                         "count": len(reqs_without_tests), "ids": reqs_without_tests,
                         "remediation": "Add test cases covering these requirements"})
        if tests_without_reqs:
            gaps.append({"type": "tests_without_requirements", "severity": "MEDIUM",
                         "count": len(tests_without_reqs), "ids": tests_without_reqs,
                         "remediation": "Link tests to source requirements or remove orphaned tests"})
        if design_without_impl:
            gaps.append({"type": "design_without_implementation", "severity": "HIGH",
                         "count": len(design_without_impl), "ids": design_without_impl,
                         "remediation": "Implement design elements or update design to match reality"})

        return {
            "total_gaps": len(gaps),
            "gaps": gaps,
            "requirements_count": len(reqs),
            "tests_count": len(tests),
            "design_count": len(designs),
        }

    def export_matrix(self) -> List[dict]:
        """Export the full traceability matrix as a flat list for document generation."""
        items = self.list_items()
        result = []
        for item in items:
            forward = self.get_forward_links(item.id)
            backward = self.get_backward_links(item.id)
            result.append({
                **item.to_dict(),
                "traces_to": forward,
                "traced_from": backward,
            })
        return result
