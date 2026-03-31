"""
SAGE Framework — Vector Memory (RAG + Feedback Learning)
=========================================================
Uses ChromaDB + sentence-transformers for semantic search.

MINIMAL MODE (low-RAM machines):
  Set SAGE_MINIMAL=1 (or install without chromadb/sentence-transformers).
  Falls back to a simple keyword-match in-memory list — fully functional,
  just without semantic similarity ranking.

Memory footprint:
  Full mode  : ~500 MB RAM (sentence-transformers model)
  Minimal mode: ~5 MB RAM  (keyword fallback list)
"""

import os
import logging
import threading
import yaml
from typing import List

logger = logging.getLogger(__name__)

_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config", "config.yaml",
)


def _get_sage_solutions_dir() -> str:
    """Return the solutions directory, honouring the SAGE_SOLUTIONS_DIR env var."""
    return os.environ.get(
        "SAGE_SOLUTIONS_DIR",
        os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "solutions",
        ),
    )


def _load_base_config() -> dict:
    try:
        with open(_CONFIG_PATH) as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}

# ---------------------------------------------------------------------------
# Minimal-mode flag — set SAGE_MINIMAL=1 to skip all heavy vector deps
# ---------------------------------------------------------------------------
_MINIMAL = os.environ.get("SAGE_MINIMAL", "").strip() in ("1", "true", "yes")

# ---------------------------------------------------------------------------
# Graceful imports — each dependency checked individually
# ---------------------------------------------------------------------------
_HAS_CHROMADB   = False
_HAS_EMBEDDINGS = False
Chroma          = None
EmbeddingClass  = None
_embedding_source = None

if not _MINIMAL:
    try:
        import chromadb  # noqa: F401
        _HAS_CHROMADB = True
    except ImportError:
        pass

    try:
        from langchain_chroma import Chroma
    except ImportError:
        try:
            from langchain_community.vectorstores import Chroma
        except ImportError:
            pass

    try:
        from langchain_huggingface import HuggingFaceEmbeddings
        EmbeddingClass    = HuggingFaceEmbeddings
        _embedding_source = "langchain_huggingface"
    except ImportError:
        try:
            from langchain_community.embeddings import HuggingFaceEmbeddings
            EmbeddingClass    = HuggingFaceEmbeddings
            _embedding_source = "langchain_community"
        except ImportError:
            pass


# ---------------------------------------------------------------------------
# VectorMemory
# ---------------------------------------------------------------------------

class VectorMemory:
    """
    Persistent vector memory for RAG and feedback learning.

    Degrades gracefully through three modes:
      1. Full       — ChromaDB + semantic embeddings (best recall)
      2. Lite       — ChromaDB without sentence-transformers (basic)
      3. Minimal    — In-memory keyword fallback (no heavy deps)

    The system NEVER crashes due to missing vector DB dependencies.
    """

    def __init__(self, explicit_solution: str = None):
        self._explicit_solution = explicit_solution  # MUST be set before _initialize_db()
        self._embedding_function  = None   # lazy-loaded on first use
        self._vector_store        = None
        self._llamaindex_index    = None   # set when backend == "llamaindex"
        self._fallback_memory: List[str] = []
        self._fallback_lock = threading.Lock()  # protects _fallback_memory
        self._ready = False
        self._mode  = "minimal"

        if _MINIMAL:
            logger.info("VectorMemory: minimal mode (SAGE_MINIMAL=1) — keyword fallback only")
            return

        if _HAS_CHROMADB and Chroma is not None:
            self._initialize_db()
        else:
            missing = []
            if not _HAS_CHROMADB:
                missing.append("chromadb")
            if Chroma is None:
                missing.append("langchain-chroma")
            logger.warning(
                "VectorMemory: ChromaDB unavailable (%s). "
                "Using keyword fallback. Install with: pip install %s",
                ", ".join(missing), " ".join(missing),
            )

    def _get_collection_name(self) -> str:
        """Use solution-specific collection name so solutions never share vectors."""
        try:
            from src.core.project_loader import project_config
            # 1. Solution project.yaml settings.memory.collection_name
            solution_name = (
                project_config.get_project_setting("settings", {})
                .get("memory", {})
                .get("collection_name")
            )
            if solution_name:
                return solution_name
            # 2. Base config.yaml memory.collection_name (if non-empty)
            cfg_name = _load_base_config().get("memory", {}).get("collection_name", "").strip()
            if cfg_name:
                return cfg_name
            # 3. Default: <solution>_knowledge — always domain-scoped
            return project_config.metadata.get("project", "sage") + "_knowledge"
        except Exception:
            return "sage_knowledge"

    def _get_vector_db_path(self) -> str:
        """
        Resolve vector DB path to the active solution's .sage/ directory.

        Priority:
          1. explicit_solution override (factory-created instances)
          2. solution project.yaml override
          3. <solution_dir>/.sage/chroma_db (default)

        Each solution's knowledge base is fully isolated in its own .sage/
        directory — same convention as audit_log.db. The .sage/ folder travels
        with the solution repository and is never committed to git.
        """
        # Org-aware override: explicit solution name provided by factory
        if getattr(self, "_explicit_solution", None):
            solutions_dir = _get_sage_solutions_dir()
            sage_dir = os.path.join(solutions_dir, self._explicit_solution, ".sage")
            os.makedirs(sage_dir, exist_ok=True)
            return os.path.join(sage_dir, "chroma_db")

        try:
            from src.core.project_loader import project_config
            # Solution-level override (project.yaml settings.memory.vector_db_path)
            solution_path = (
                project_config.get_project_setting("settings", {})
                .get("memory", {})
                .get("vector_db_path")
            )
            if solution_path:
                return solution_path
            # Default: solution's .sage/ dir — fully isolated per solution
            return os.path.join(project_config.sage_data_dir, "chroma_db")
        except Exception:
            return os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                ".sage", "chroma_db",
            )

    def _lazy_load_embeddings(self):
        """Load the embedding model only on first use (saves startup RAM)."""
        if self._embedding_function is not None:
            return
        if EmbeddingClass is None:
            return
        try:
            self._embedding_function = EmbeddingClass(model_name="all-MiniLM-L6-v2")
            logger.info("Embeddings loaded via %s", _embedding_source)
        except Exception as exc:
            logger.warning("Failed to load embeddings (%s) — proceeding without.", exc)

    def _initialize_db(self):
        # Check config to decide backend
        backend = _load_base_config().get("memory", {}).get("backend", "chroma")
        if backend == "llamaindex":
            self._initialize_llamaindex_db()
        else:
            self._initialize_chroma_db()

    def _initialize_chroma_db(self):
        persist_path    = self._get_vector_db_path()
        collection_name = self._get_collection_name()
        try:
            self._lazy_load_embeddings()
            kwargs: dict = {
                "collection_name":  collection_name,
                "persist_directory": persist_path,
            }
            if self._embedding_function:
                kwargs["embedding_function"] = self._embedding_function
            self._vector_store = Chroma(**kwargs)
            self._ready = True
            self._mode  = "full" if self._embedding_function else "lite"
            logger.info("VectorMemory ready (chroma/%s) at %s", self._mode, persist_path)
        except Exception as exc:
            logger.error("VectorMemory init failed (%s) — keyword fallback active.", exc)

    def _initialize_llamaindex_db(self):
        """LlamaIndex backend with ChromaDB vector store — better chunking and re-ranking."""
        persist_path    = self._get_vector_db_path()
        collection_name = self._get_collection_name()
        try:
            import chromadb
            from llama_index.core import VectorStoreIndex, StorageContext
            from llama_index.vector_stores.chroma import ChromaVectorStore

            chroma_client     = chromadb.PersistentClient(path=persist_path)
            chroma_collection = chroma_client.get_or_create_collection(collection_name)
            lf_vector_store   = ChromaVectorStore(chroma_collection=chroma_collection)
            storage_context   = StorageContext.from_defaults(vector_store=lf_vector_store)
            self._llamaindex_index = VectorStoreIndex([], storage_context=storage_context)
            self._ready = True
            self._mode  = "llamaindex"
            logger.info("VectorMemory ready (llamaindex) at %s", persist_path)
        except ImportError as exc:
            logger.warning(
                "LlamaIndex backend unavailable (%s) — falling back to chroma. "
                "Install with: pip install llama-index-core llama-index-vector-stores-chroma",
                exc,
            )
            self._initialize_chroma_db()
        except Exception as exc:
            logger.error("LlamaIndex init failed (%s) — keyword fallback active.", exc)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def search(self, query: str, k: int = 3) -> List[str]:
        """Retrieve relevant context. LlamaIndex / ChromaDB / keyword fallback."""
        # LlamaIndex path
        if self._mode == "llamaindex" and self._ready:
            try:
                retriever = self._llamaindex_index.as_retriever(similarity_top_k=k)
                nodes = retriever.retrieve(query)
                return [n.get_content() for n in nodes]
            except Exception as exc:
                logger.error("LlamaIndex search failed: %s", exc)

        # ChromaDB (langchain) path
        if self._vector_store and self._ready:
            try:
                docs = self._vector_store.similarity_search(query, k=k)
                return [doc.page_content for doc in docs]
            except Exception as exc:
                logger.error("Vector search failed: %s", exc)

        # Keyword fallback — works with zero ML deps
        with self._fallback_lock:
            if self._fallback_memory:
                query_lower = query.lower()
                matches = [
                    m for m in self._fallback_memory
                    if any(word in m.lower() for word in query_lower.split()[:5])
                ]
                return matches[:k]
        return []

    # ------------------------------------------------------------------
    # Knowledge Base CRUD (Phase 7)
    # ------------------------------------------------------------------

    def list_entries(self, limit: int = 50) -> list[dict]:
        """
        Return up to `limit` stored knowledge entries with their IDs.
        Returns [{id, text, metadata}, ...].
        """
        results = []

        # ChromaDB direct peek
        if self._vector_store and self._ready:
            try:
                col = self._vector_store._collection
                data = col.get(limit=limit, include=["documents", "metadatas"])
                for doc_id, doc, meta in zip(
                    data.get("ids", []),
                    data.get("documents", []),
                    data.get("metadatas", []),
                ):
                    results.append({"id": doc_id, "text": doc, "metadata": meta or {}})
                return results
            except Exception as exc:
                logger.warning("ChromaDB list_entries failed: %s", exc)

        # Fallback list — IDs are positional
        with self._fallback_lock:
            for i, text in enumerate(self._fallback_memory[:limit]):
                results.append({"id": str(i), "text": text, "metadata": {}})
        return results

    def add_entry(self, text: str, metadata: dict = None) -> str:
        """
        Add a knowledge entry directly (not just feedback).
        Returns the assigned entry ID.
        """
        import uuid as _uuid
        entry_id = str(_uuid.uuid4())
        with self._fallback_lock:
            self._fallback_memory.append(text)

        if self._mode == "llamaindex" and self._ready:
            try:
                from llama_index.core import Document
                self._llamaindex_index.insert(
                    Document(text=text, metadata={**(metadata or {}), "entry_id": entry_id})
                )
                return entry_id
            except Exception as exc:
                logger.warning("LlamaIndex add_entry failed: %s", exc)

        if self._vector_store and self._ready:
            try:
                ids = self._vector_store.add_texts(
                    texts=[text],
                    metadatas=[{**(metadata or {}), "entry_id": entry_id}],
                    ids=[entry_id],
                )
                return ids[0] if ids else entry_id
            except Exception as exc:
                logger.warning("ChromaDB add_entry failed: %s", exc)

        return entry_id

    def delete_entry(self, entry_id: str) -> bool:
        """
        Delete a knowledge entry by ID.
        Returns True on success, False if not found.
        """
        if self._vector_store and self._ready:
            try:
                self._vector_store._collection.delete(ids=[entry_id])
                logger.info("Deleted knowledge entry %s from ChromaDB", entry_id)
                return True
            except Exception as exc:
                logger.warning("ChromaDB delete_entry failed: %s", exc)

        # Fallback: try positional removal if id is an integer string
        with self._fallback_lock:
            try:
                idx = int(entry_id)
                if 0 <= idx < len(self._fallback_memory):
                    self._fallback_memory.pop(idx)
                    return True
            except (ValueError, IndexError):
                pass
        return False

    def bulk_import(self, entries: list[dict]) -> int:
        """
        Add multiple knowledge entries at once.
        Each entry: {"text": str, "metadata": dict (optional)}.
        Returns the count of successfully added entries.
        """
        count = 0
        for entry in entries:
            text = entry.get("text", "").strip()
            if not text:
                continue
            self.add_entry(text, metadata=entry.get("metadata", {}))
            count += 1
        logger.info("Bulk imported %d knowledge entries", count)
        return count

    def add_feedback(self, text: str, metadata: dict = None):
        """Learn from human feedback — saved to vector DB or fallback list."""
        with self._fallback_lock:
            self._fallback_memory.append(text)   # always save (cheap)

        # LlamaIndex path
        if self._mode == "llamaindex" and self._ready:
            try:
                from llama_index.core import Document
                self._llamaindex_index.insert(Document(text=text, metadata=metadata or {}))
                logger.info("Feedback saved to LlamaIndex store.")
                return
            except Exception as exc:
                logger.error("Failed to save to LlamaIndex store: %s", exc)

        # ChromaDB (langchain) path
        if self._vector_store and self._ready:
            try:
                self._vector_store.add_texts(texts=[text], metadatas=[metadata or {}])
                logger.info("Feedback saved to ChromaDB.")
                return
            except Exception as exc:
                logger.error("Failed to save to ChromaDB: %s", exc)

        logger.info("Feedback saved to in-memory fallback.")

    @property
    def mode(self) -> str:
        """Returns 'full', 'lite', or 'minimal'."""
        return self._mode


def get_vector_memory(solution_name: str) -> "VectorMemory":
    """Return a VectorMemory scoped to a specific solution's .sage/chroma_db/."""
    return VectorMemory(explicit_solution=solution_name)


def org_aware_query(
    query_text: str,
    solution_name: str,
    loader,
    n_results: int = 5,
) -> list:
    """
    Query every store in the solution's parent chain and return merged, deduplicated results.

    search() returns List[str] (plain strings). Results are deduplicated by exact content
    and truncated to n_results. Falls back to [] on any unrecoverable error.
    """
    all_results: list = []
    try:
        chain = loader.get_parent_chain(solution_name)
        for sol in chain:
            vm = get_vector_memory(sol)
            try:
                results = vm.search(query_text, k=n_results)
                all_results.extend(results)
            except Exception as exc:
                logger.debug("org_aware_query: search failed for %s: %s", sol, exc)

        # Deduplicate while preserving order (first occurrence wins)
        seen: set = set()
        deduped: list = []
        for item in all_results:
            if item not in seen:
                seen.add(item)
                deduped.append(item)

        return deduped[:n_results]
    except Exception as exc:
        logger.warning("org_aware_query failed (non-fatal): %s", exc)
        return []


# Global singleton
vector_memory = VectorMemory()
