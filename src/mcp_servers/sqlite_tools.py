"""
SAGE MCP Server — SQLite Tools
================================
Query the solution's .sage/ SQLite databases (audit_log.db, eval history, etc.)
through a safe, read-only interface. Write operations are restricted to
SAGE-managed tables only.

Works with any LLM provider — agents call these through MCPRegistry.invoke().
"""

import logging
import os
import sqlite3

logger = logging.getLogger("sqlite_tools_mcp")

try:
    from fastmcp import FastMCP
    mcp = FastMCP("sqlite-tools")
except ImportError:
    logger.warning("fastmcp not installed — MCP server cannot start standalone")
    mcp = None


def _get_sage_db_path(db_name: str = "audit_log.db") -> str:
    """Resolve path to a database in the active solution's .sage/ directory."""
    try:
        from src.core.project_loader import project_config, _SOLUTIONS_DIR
        return os.path.join(
            _SOLUTIONS_DIR, project_config.project_name, ".sage", db_name
        )
    except Exception:
        return ""


def _validate_db_path(db_name: str) -> str:
    """Validate the database exists and is inside .sage/. Returns path or raises."""
    if ".." in db_name or "/" in db_name or "\\" in db_name:
        raise ValueError(f"Invalid database name: {db_name}")
    if not db_name.endswith(".db"):
        db_name = db_name + ".db"

    path = _get_sage_db_path(db_name)
    if not path:
        raise ValueError("No active solution — cannot locate .sage/ directory")
    return path


_DANGEROUS_KEYWORDS = {"DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE", "ATTACH", "DETACH"}


def _is_read_only(sql: str) -> bool:
    """Check if SQL is read-only (SELECT, EXPLAIN, PRAGMA)."""
    stripped = sql.strip().upper()
    first_word = stripped.split()[0] if stripped.split() else ""
    if first_word in ("SELECT", "EXPLAIN", "PRAGMA", "WITH"):
        # Extra safety: ensure no dangerous keywords appear (prevent injection via subqueries)
        tokens = set(stripped.replace("(", " ").replace(")", " ").split())
        return not tokens.intersection(_DANGEROUS_KEYWORDS)
    return False


if mcp:
    @mcp.tool()
    def query_db(
        sql: str,
        db_name: str = "audit_log.db",
        max_rows: int = 100,
    ) -> dict:
        """
        Execute a read-only SQL query against a .sage/ database.

        Args:
            sql:      SQL query (SELECT, EXPLAIN, PRAGMA only).
            db_name:  Database filename in .sage/ (default: audit_log.db).
            max_rows: Maximum rows to return (default 100).

        Returns query results as list of dicts.
        """
        try:
            if not _is_read_only(sql):
                return {
                    "success": False,
                    "error": "Only read-only queries (SELECT, EXPLAIN, PRAGMA) are allowed",
                }

            db_path = _validate_db_path(db_name)
            if not os.path.isfile(db_path):
                return {"success": False, "error": f"Database not found: {db_name}"}

            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = [dict(row) for row in cursor.fetchmany(max_rows)]
            total = len(rows)

            # Check if there are more rows
            has_more = cursor.fetchone() is not None
            conn.close()

            return {
                "success": True,
                "db_name": db_name,
                "columns": columns,
                "rows": rows,
                "row_count": total,
                "truncated": has_more,
            }
        except ValueError as e:
            return {"success": False, "error": str(e)}
        except sqlite3.Error as e:
            return {"success": False, "error": f"SQLite error: {e}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool()
    def list_tables(db_name: str = "audit_log.db") -> dict:
        """
        List all tables in a .sage/ database.

        Args:
            db_name: Database filename in .sage/ (default: audit_log.db).

        Returns list of table names with row counts.
        """
        try:
            db_path = _validate_db_path(db_name)
            if not os.path.isfile(db_path):
                return {"success": False, "error": f"Database not found: {db_name}"}

            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = []
            for (name,) in cursor.fetchall():
                count_cursor = conn.execute(f"SELECT COUNT(*) FROM [{name}]")
                count = count_cursor.fetchone()[0]
                tables.append({"name": name, "row_count": count})

            conn.close()
            return {
                "success": True,
                "db_name": db_name,
                "tables": tables,
                "table_count": len(tables),
            }
        except ValueError as e:
            return {"success": False, "error": str(e)}
        except sqlite3.Error as e:
            return {"success": False, "error": f"SQLite error: {e}"}

    @mcp.tool()
    def describe_table(table_name: str, db_name: str = "audit_log.db") -> dict:
        """
        Get schema information for a table in a .sage/ database.

        Args:
            table_name: Name of the table to describe.
            db_name:    Database filename in .sage/ (default: audit_log.db).

        Returns column names, types, and constraints.
        """
        try:
            db_path = _validate_db_path(db_name)
            if not os.path.isfile(db_path):
                return {"success": False, "error": f"Database not found: {db_name}"}

            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)

            # Get column info
            cursor = conn.execute(f"PRAGMA table_info([{table_name}])")
            columns = []
            for row in cursor.fetchall():
                columns.append({
                    "cid": row[0],
                    "name": row[1],
                    "type": row[2],
                    "notnull": bool(row[3]),
                    "default": row[4],
                    "pk": bool(row[5]),
                })

            if not columns:
                conn.close()
                return {"success": False, "error": f"Table not found: {table_name}"}

            # Get row count
            count_cursor = conn.execute(f"SELECT COUNT(*) FROM [{table_name}]")
            row_count = count_cursor.fetchone()[0]

            conn.close()
            return {
                "success": True,
                "db_name": db_name,
                "table_name": table_name,
                "columns": columns,
                "row_count": row_count,
            }
        except ValueError as e:
            return {"success": False, "error": str(e)}
        except sqlite3.Error as e:
            return {"success": False, "error": f"SQLite error: {e}"}

    @mcp.tool()
    def list_databases() -> dict:
        """
        List all .db files in the active solution's .sage/ directory.

        Returns list of database filenames with sizes.
        """
        try:
            from src.core.project_loader import project_config, _SOLUTIONS_DIR
            sage_dir = os.path.join(
                _SOLUTIONS_DIR, project_config.project_name, ".sage"
            )
        except Exception:
            return {"success": False, "error": "No active solution"}

        if not os.path.isdir(sage_dir):
            return {"success": True, "databases": [], "note": ".sage/ directory not yet created"}

        databases = []
        for f in sorted(os.listdir(sage_dir)):
            if f.endswith(".db"):
                full = os.path.join(sage_dir, f)
                databases.append({
                    "name": f,
                    "size_bytes": os.path.getsize(full),
                })

        return {
            "success": True,
            "sage_dir": sage_dir,
            "databases": databases,
            "count": len(databases),
        }


if __name__ == "__main__":
    if mcp is None:
        print("ERROR: fastmcp not installed. Run: pip install fastmcp")
        import sys
        sys.exit(1)
    mcp.run()
