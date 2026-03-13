"""
SAGE Framework — Long-Term Memory (mem0)
=========================================
Personalized, multi-session memory layer on top of SAGE's existing
vector store. Remembers user- and project-specific preferences across
conversations and sessions.

Complements vector_store.py (document search) with:
  - User-scoped memory: "this engineer prefers root-cause first"
  - Project-scoped memory: "project X never approves without test evidence"
  - Temporal memory: "last time we saw this error, the fix was Y"

Degrades gracefully when mem0ai is not installed — falls back to the
existing vector_memory search.

Usage:
    from src.memory.long_term_memory import long_term_memory
    long_term_memory.remember("Always check thread-safety first", user_id="eng_01")
    results = long_term_memory.recall("code review approach", user_id="eng_01")
"""

import logging
import os

logger = logging.getLogger("LongTermMemory")

# ---------------------------------------------------------------------------
# Check if mem0ai is available
# ---------------------------------------------------------------------------
_HAS_MEM0 = False
try:
    import mem0  # noqa: F401
    _HAS_MEM0 = True
except ImportError:
    pass


class LongTermMemory:
    """
    Multi-session personalized memory using mem0.

    Falls back to SAGE's vector_memory when mem0 is not installed.
    Never crashes — always returns a list of strings.
    """

    def __init__(self):
        self._client = None
        self._mode   = "fallback"

        if not _HAS_MEM0:
            logger.info(
                "LongTermMemory: mem0ai not installed — using vector_memory fallback. "
                "Install with: pip install mem0ai"
            )
            return

        # Check if mem0 is explicitly enabled (optional — enabled by default if installed)
        try:
            import yaml
            cfg_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "config", "config.yaml",
            )
            with open(cfg_path) as f:
                cfg = yaml.safe_load(f) or {}
            if not cfg.get("memory", {}).get("mem0_enabled", True):
                logger.info("LongTermMemory: mem0 disabled in config — using vector_memory fallback.")
                return
        except Exception:
            pass  # config read failure — proceed with mem0

        try:
            from mem0 import Memory
            self._client = Memory()
            self._mode   = "mem0"
            logger.info("LongTermMemory ready (mem0)")
        except Exception as exc:
            logger.warning("mem0 initialisation failed (%s) — using vector_memory fallback.", exc)

    def remember(self, text: str, user_id: str = "default", metadata: dict = None) -> None:
        """
        Store a preference, pattern, or correction for a specific user or project.

        Args:
            text:     The memory text to store.
            user_id:  User or project identifier (scopes the memory).
            metadata: Optional extra context tags.
        """
        if self._client is not None:
            try:
                self._client.add(text, user_id=user_id, metadata=metadata or {})
                logger.info("Long-term memory stored for user_id=%s", user_id)
                return
            except Exception as exc:
                logger.warning("mem0.add failed (%s) — falling back to vector_memory.", exc)

        # Fallback: store in SAGE's vector memory
        try:
            from src.memory.vector_store import vector_memory
            vector_memory.add_feedback(
                f"[user:{user_id}] {text}",
                metadata={"user_id": user_id, **(metadata or {}), "type": "long_term"},
            )
        except Exception as exc:
            logger.error("LongTermMemory fallback store failed: %s", exc)

    def recall(self, query: str, user_id: str = "default", limit: int = 5) -> list[str]:
        """
        Retrieve relevant memories for a specific user or project.

        Args:
            query:   Topic or question to search memories for.
            user_id: User or project identifier to scope the search.
            limit:   Maximum number of memories to return.

        Returns:
            List of memory strings (empty list if none found).
        """
        if self._client is not None:
            try:
                results = self._client.search(query, user_id=user_id, limit=limit)
                return [r["memory"] for r in results.get("results", [])]
            except Exception as exc:
                logger.warning("mem0.search failed (%s) — falling back to vector_memory.", exc)

        # Fallback: query SAGE's vector memory with user scope prefix
        try:
            from src.memory.vector_store import vector_memory
            raw = vector_memory.search(f"[user:{user_id}] {query}", k=limit)
            return raw
        except Exception as exc:
            logger.error("LongTermMemory fallback recall failed: %s", exc)
            return []

    @property
    def mode(self) -> str:
        """Returns 'mem0' or 'fallback'."""
        return self._mode


# Global singleton
long_term_memory = LongTermMemory()
