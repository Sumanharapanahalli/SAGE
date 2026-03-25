"""
SAGE MCP Server — Filesystem Tools
====================================
Sandboxed filesystem operations for SAGE agents. All paths are restricted
to the active solution's directory (project root + .sage/) to prevent
agents from accessing arbitrary system files.

Works with any LLM provider — agents call these through MCPRegistry.invoke().
"""

import logging
import os
import glob as glob_mod

logger = logging.getLogger("filesystem_tools_mcp")

try:
    from fastmcp import FastMCP
    mcp = FastMCP("filesystem-tools")
except ImportError:
    logger.warning("fastmcp not installed — MCP server cannot start standalone")
    mcp = None


def _resolve_sandbox() -> str:
    """Return the active solution directory as the sandbox root."""
    try:
        from src.core.project_loader import project_config, _SOLUTIONS_DIR
        return os.path.join(_SOLUTIONS_DIR, project_config.project_name)
    except Exception:
        return ""


def _enforce_sandbox(path: str) -> str:
    """
    Resolve path and verify it is inside the solution sandbox.
    Raises ValueError if the path escapes the sandbox.
    """
    sandbox = _resolve_sandbox()
    if not sandbox:
        raise ValueError("No active solution — cannot resolve sandbox root")

    resolved = os.path.realpath(os.path.join(sandbox, path))
    if not resolved.startswith(os.path.realpath(sandbox)):
        raise ValueError(
            f"Path escapes sandbox: {path} resolves to {resolved} "
            f"(sandbox: {sandbox})"
        )
    return resolved


if mcp:
    @mcp.tool()
    def read_file(path: str, encoding: str = "utf-8", max_bytes: int = 500_000) -> dict:
        """
        Read a file from the active solution directory.

        Args:
            path:      Relative path within the solution directory.
            encoding:  File encoding (default utf-8).
            max_bytes: Maximum bytes to read (default 500KB).

        Returns file content or error.
        """
        try:
            resolved = _enforce_sandbox(path)
            if not os.path.isfile(resolved):
                return {"success": False, "error": f"File not found: {path}"}
            size = os.path.getsize(resolved)
            with open(resolved, "r", encoding=encoding, errors="replace") as f:
                content = f.read(max_bytes)
            return {
                "success": True,
                "path": path,
                "size_bytes": size,
                "truncated": size > max_bytes,
                "content": content,
            }
        except ValueError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool()
    def write_file(path: str, content: str, encoding: str = "utf-8") -> dict:
        """
        Write content to a file in the active solution directory.
        Creates parent directories if needed.

        Args:
            path:     Relative path within the solution directory.
            content:  Text content to write.
            encoding: File encoding (default utf-8).

        Returns write status.
        """
        try:
            resolved = _enforce_sandbox(path)
            os.makedirs(os.path.dirname(resolved), exist_ok=True)
            with open(resolved, "w", encoding=encoding) as f:
                f.write(content)
            return {
                "success": True,
                "path": path,
                "bytes_written": len(content.encode(encoding)),
            }
        except ValueError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool()
    def list_directory(path: str = ".", pattern: str = "*") -> dict:
        """
        List files and directories within the active solution directory.

        Args:
            path:    Relative directory path (default: solution root).
            pattern: Glob pattern to filter entries (default: "*").

        Returns list of entries with type and size.
        """
        try:
            resolved = _enforce_sandbox(path)
            if not os.path.isdir(resolved):
                return {"success": False, "error": f"Not a directory: {path}"}

            entries = []
            for name in sorted(os.listdir(resolved)):
                if not glob_mod.fnmatch.fnmatch(name, pattern):
                    continue
                full = os.path.join(resolved, name)
                entry = {
                    "name": name,
                    "type": "directory" if os.path.isdir(full) else "file",
                }
                if os.path.isfile(full):
                    entry["size_bytes"] = os.path.getsize(full)
                entries.append(entry)

            return {
                "success": True,
                "path": path,
                "count": len(entries),
                "entries": entries[:500],
            }
        except ValueError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool()
    def file_exists(path: str) -> dict:
        """
        Check if a file or directory exists in the solution directory.

        Args:
            path: Relative path within the solution directory.

        Returns existence and type info.
        """
        try:
            resolved = _enforce_sandbox(path)
            exists = os.path.exists(resolved)
            return {
                "success": True,
                "path": path,
                "exists": exists,
                "is_file": os.path.isfile(resolved) if exists else False,
                "is_directory": os.path.isdir(resolved) if exists else False,
            }
        except ValueError as e:
            return {"success": False, "error": str(e)}

    @mcp.tool()
    def search_files(pattern: str, path: str = ".") -> dict:
        """
        Recursively search for files matching a glob pattern.

        Args:
            pattern: Glob pattern (e.g. "**/*.py", "*.yaml").
            path:    Relative directory to search from (default: solution root).

        Returns matching file paths relative to solution root.
        """
        try:
            resolved = _enforce_sandbox(path)
            sandbox = _resolve_sandbox()
            matches = []
            for match in glob_mod.glob(os.path.join(resolved, pattern), recursive=True):
                real_match = os.path.realpath(match)
                if real_match.startswith(os.path.realpath(sandbox)):
                    rel = os.path.relpath(real_match, sandbox)
                    matches.append(rel)

            return {
                "success": True,
                "pattern": pattern,
                "path": path,
                "count": len(matches),
                "matches": sorted(matches)[:200],
            }
        except ValueError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            return {"success": False, "error": str(e)}


if __name__ == "__main__":
    if mcp is None:
        print("ERROR: fastmcp not installed. Run: pip install fastmcp")
        import sys
        sys.exit(1)
    mcp.run()
