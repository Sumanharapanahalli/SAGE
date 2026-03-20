# Org Foundation + Project Import — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a company mission/vision/values settings page and a folder-import path in the onboarding wizard that scans a codebase and generates solution YAML via LLM, with a plain-English review loop.

**Architecture:** Backend gains `FolderScanner` (reads files, builds LLM context), `PUT /org` (saves mission/vision/values to org.yaml), `POST /onboarding/scan-folder` and `POST /onboarding/refine` (LLM-powered YAML generation with org context injection). Frontend gains an Organization settings page, a Dashboard empty state for first-time users, and a full-screen onboarding page refactor with a two-tab Step 1 (describe vs. import) and a Summary/YAML review panel with an unlimited refine loop.

**Tech Stack:** Python 3.11 FastAPI, pytest, React 18 + TypeScript, Vite, TanStack Query, lucide-react

---

## File Map

| File | Status | Responsibility |
|---|---|---|
| `src/core/folder_scanner.py` | NEW | Walk directory, read files by priority, return LLM-ready string |
| `src/interface/api.py` | MODIFY | Add PUT /org, POST /onboarding/scan-folder, POST /onboarding/refine; inject org context into POST /onboarding/generate |
| `web/src/api/client.ts` | MODIFY | Add saveOrg(), scanFolder(), refineGeneration() + response types |
| `web/src/pages/settings/Organization.tsx` | NEW | Org name / mission / vision / core values form |
| `web/src/App.tsx` | MODIFY | Add /settings/organization route |
| `web/src/components/layout/Sidebar.tsx` | MODIFY | Add Organization nav entry under Admin |
| `web/src/components/layout/Header.tsx` | MODIFY | Add /settings/organization to ROUTE_TO_AREA and PAGE_TITLES |
| `web/src/registry/modules.ts` | MODIFY | Add 'organization' module entry |
| `web/src/components/dashboard/EmptyState.tsx` | NEW | Two-step guidance card for zero-solution state |
| `web/src/pages/Dashboard.tsx` | MODIFY | Render EmptyState when projects list is empty |
| `web/src/pages/Onboarding.tsx` | MODIFY | Full-screen refactor; mission banner; LLM gate; Describe/Import tabs |
| `web/src/components/onboarding/ImportFlow.tsx` | NEW | 3-step import: path+intent → scanning spinner → ReviewPanel |
| `web/src/components/onboarding/ReviewPanel.tsx` | NEW | Summary tab (plain English) + YAML tab + amber refine box |
| `tests/test_folder_scanner.py` | NEW | Unit tests for FolderScanner |
| `web/src/pages/Settings.tsx` | MODIFY | Add Organization tab/link entry |
| `tests/test_onboarding_import_endpoints.py` | NEW | Tests for PUT /org, scan-folder, refine |

---

## Task 1: FolderScanner

**Files:**
- Create: `src/core/folder_scanner.py`
- Test: `tests/test_folder_scanner.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_folder_scanner.py
import os
import tempfile
import pytest
from src.core.folder_scanner import FolderScanner


def _make_tree(base: str, files: dict) -> None:
    """Create a directory tree from a {rel_path: content} dict."""
    for rel_path, content in files.items():
        abs_path = os.path.join(base, rel_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)


def test_scan_nonexistent_path_raises():
    scanner = FolderScanner()
    with pytest.raises(FileNotFoundError):
        scanner.scan("/nonexistent/path/xyz")


def test_scan_reads_readme_first():
    with tempfile.TemporaryDirectory() as tmp:
        _make_tree(tmp, {
            "README.md": "# My Project\nThis is the readme.",
            "src/main.py": "def main(): pass",
        })
        scanner = FolderScanner()
        result = scanner.scan(tmp)
        # README should appear before main.py
        assert result.index("README.md") < result.index("main.py")
        assert "This is the readme." in result
        assert "def main" in result


def test_scan_skips_git_and_node_modules():
    with tempfile.TemporaryDirectory() as tmp:
        _make_tree(tmp, {
            ".git/config": "secret git config",
            "node_modules/pkg/index.js": "module.exports = {}",
            "__pycache__/app.cpython-311.pyc": "bytecode",
            "src/app.py": "print('hello')",
        })
        scanner = FolderScanner()
        result = scanner.scan(tmp)
        assert ".git/config" not in result
        assert "node_modules" not in result
        assert "__pycache__" not in result
        assert "print('hello')" in result


def test_scan_respects_token_budget():
    with tempfile.TemporaryDirectory() as tmp:
        # Create files totalling well over 1000 chars
        for i in range(20):
            _make_tree(tmp, {f"src/file_{i}.py": "x = " + "a" * 200})
        scanner = FolderScanner()
        result = scanner.scan(tmp, max_tokens=50)  # ~200 chars
        # Result should be truncated
        assert len(result) <= 300  # rough check


def test_scan_includes_file_headers():
    with tempfile.TemporaryDirectory() as tmp:
        _make_tree(tmp, {"src/utils.py": "def helper(): pass"})
        scanner = FolderScanner()
        result = scanner.scan(tmp)
        assert "utils.py" in result
        assert "def helper" in result


def test_scan_empty_folder_returns_empty_string():
    with tempfile.TemporaryDirectory() as tmp:
        scanner = FolderScanner()
        result = scanner.scan(tmp)
        assert result == ""
```

- [ ] **Step 2: Run tests — verify they all fail**

```bash
cd C:\sandbox\SAGE
python -m pytest tests/test_folder_scanner.py -v
```
Expected: `ERROR` or `ImportError` — module does not exist yet.

- [ ] **Step 3: Implement FolderScanner**

```python
# src/core/folder_scanner.py
import os
import logging

logger = logging.getLogger(__name__)

_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".sage", "dist", "build", ".next"}
_SKIP_EXTENSIONS = {
    ".pyc", ".pyo", ".class", ".o", ".a", ".so", ".dll", ".exe",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg",
    ".pdf", ".zip", ".tar", ".gz", ".7z", ".rar",
    ".mp3", ".mp4", ".avi", ".mov", ".wav",
    ".db", ".sqlite", ".lock",
}
_PRIORITY_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".c", ".cpp", ".h", ".md", ".yaml", ".yml", ".json", ".txt", ".rst"}
_MAX_FILE_BYTES = 500 * 1024  # 500KB


def _priority(rel_path: str) -> int:
    """Lower number = higher priority (read first)."""
    lower = rel_path.lower()
    name = os.path.basename(lower)
    if name.startswith("readme"):
        return 0
    parts = lower.replace("\\", "/").split("/")
    if any(p in ("docs", "doc", "documentation") for p in parts):
        return 1
    ext = os.path.splitext(lower)[1]
    if ext in _PRIORITY_EXTENSIONS:
        return 2
    return 3


class FolderScanner:
    def scan(self, folder_path: str, max_tokens: int = 24_000) -> str:
        """
        Walk folder_path, read text files in priority order, return
        concatenated content with file-path headers, capped at max_tokens.

        Raises FileNotFoundError if folder_path does not exist.
        """
        if not os.path.isdir(folder_path):
            raise FileNotFoundError(f"Folder not found: {folder_path}")

        # Collect eligible files
        candidates: list[tuple[int, str]] = []  # (priority, abs_path)
        for root, dirs, files in os.walk(folder_path):
            # Prune skipped directories in-place
            dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith(".")]
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext in _SKIP_EXTENSIONS:
                    continue
                abs_path = os.path.join(root, fname)
                try:
                    if os.path.getsize(abs_path) > _MAX_FILE_BYTES:
                        continue
                except OSError:
                    continue
                rel_path = os.path.relpath(abs_path, folder_path)
                candidates.append((_priority(rel_path), abs_path))

        candidates.sort(key=lambda x: x[0])

        budget = max_tokens * 4  # chars
        parts: list[str] = []

        for _, abs_path in candidates:
            if budget <= 0:
                break
            rel_path = os.path.relpath(abs_path, folder_path)
            try:
                with open(abs_path, encoding="utf-8", errors="replace") as f:
                    content = f.read(budget)
            except OSError:
                continue
            if not content.strip():
                continue
            chunk = f"# --- {rel_path} ---\n{content}\n"
            parts.append(chunk)
            budget -= len(chunk)

        return "".join(parts)
```

- [ ] **Step 4: Run tests — verify they all pass**

```bash
python -m pytest tests/test_folder_scanner.py -v
```
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/core/folder_scanner.py tests/test_folder_scanner.py
git commit -m "feat(onboarding): FolderScanner — directory reader with priority ordering and token budget"
```

---

## Task 2: PUT /org + org context injection in /onboarding/generate

**Files:**
- Modify: `src/interface/api.py`
- Test: `tests/test_onboarding_import_endpoints.py` (first batch)

The existing `GET /org` already works. This task adds `PUT /org` and modifies `POST /onboarding/generate` to inject org mission/vision/values into the LLM prompt.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_onboarding_import_endpoints.py
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from src.interface.api import app

client = TestClient(app)


# ── PUT /org ──────────────────────────────────────────────────────────────────

def test_put_org_saves_mission():
    with patch("src.interface.api.reload_org_loader") as mock_reload:
        resp = client.put("/org", json={
            "name": "Acme Corp",
            "mission": "Make the world better",
            "vision": "A better world by 2040",
            "core_values": ["Integrity", "Speed"],
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "saved"
    assert "org" in data


def test_put_org_reloads_org_loader():
    with patch("src.interface.api.reload_org_loader") as mock_reload:
        client.put("/org", json={"mission": "Test mission"})
    mock_reload.assert_called_once()


def test_put_org_partial_update_accepted():
    """PUT /org with only mission field — should not error."""
    with patch("src.interface.api.reload_org_loader"):
        resp = client.put("/org", json={"mission": "Only mission"})
    assert resp.status_code == 200


def test_put_org_empty_body_accepted():
    """PUT /org with empty body — nothing to save, still 200."""
    with patch("src.interface.api.reload_org_loader"):
        resp = client.put("/org", json={})
    assert resp.status_code == 200
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
python -m pytest tests/test_onboarding_import_endpoints.py::test_put_org_saves_mission -v
```
Expected: `404` or `AttributeError` — endpoint does not exist yet.

- [ ] **Step 3: Add PUT /org to api.py**

Find the `@app.get("/org")` endpoint in `src/interface/api.py`. Add the Pydantic model and PUT endpoint immediately after the existing org endpoints (after the last `@app.delete("/org/solutions/{name}")` handler):

```python
# Add this Pydantic model near the other org models (or at top with other models):
class OrgUpdateRequest(BaseModel):
    name: Optional[str] = None
    mission: Optional[str] = None
    vision: Optional[str] = None
    core_values: Optional[list[str]] = None

@app.put("/org")
async def org_update(req: OrgUpdateRequest):
    """Save mission/vision/core_values to org.yaml. Merges — does not overwrite unset fields."""
    from src.core.org_loader import _SOLUTIONS_DIR, reload_org_loader
    import yaml as _yaml

    org_path = os.path.join(_SOLUTIONS_DIR, "org.yaml")

    # Load existing or start fresh
    existing: dict = {}
    if os.path.exists(org_path):
        try:
            with open(org_path, encoding="utf-8") as f:
                existing = _yaml.safe_load(f) or {}
        except Exception:
            existing = {}

    # Merge only supplied fields
    if not isinstance(existing.get("org"), dict):
        existing["org"] = {}
    org_section = existing["org"]

    if req.name is not None:
        org_section["name"] = req.name
    if req.mission is not None:
        org_section["mission"] = req.mission
    if req.vision is not None:
        org_section["vision"] = req.vision
    if req.core_values is not None:
        org_section["core_values"] = req.core_values

    os.makedirs(os.path.dirname(org_path), exist_ok=True)
    with open(org_path, "w", encoding="utf-8") as f:
        _yaml.dump(existing, f, default_flow_style=False, allow_unicode=True)

    reload_org_loader()

    audit_logger.log_event(
        actor="human_via_settings",
        action_type="ORG_SAVED",
        input_context=f"name={req.name}, mission={req.mission}",
        output_content=str(org_section),
        metadata={"source": "PUT /org"},
    )

    return {"status": "saved", "org": org_section}
```

Note: `audit_logger` is already imported at the top of `api.py`. Add it if not present: `from src.memory.audit_logger import audit_logger`.

- [ ] **Step 4: Run tests — verify they pass**

```bash
python -m pytest tests/test_onboarding_import_endpoints.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Add org context injection to POST /onboarding/generate**

Find the `@app.post("/onboarding/generate")` handler in `src/interface/api.py`. Before the call to `generate_solution(...)`, add org context loading:

```python
# At the top of the /onboarding/generate handler, before calling generate_solution():
from src.core.org_loader import org_loader as _org_loader
_org = _org_loader.org_data if hasattr(_org_loader, 'org_data') else {}
_org_section = _org.get("org", {}) if isinstance(_org, dict) else {}
_org_context = ""
if _org_section.get("mission"):
    parts = [f"Mission: {_org_section['mission']}"]
    if _org_section.get("vision"):
        parts.append(f"Vision: {_org_section['vision']}")
    if _org_section.get("core_values"):
        vals = "\n  - ".join(_org_section["core_values"])
        parts.append(f"Core values:\n  - {vals}")
    _org_context = "\n".join(parts)
```

Then update the call to `generate_solution()` to pass `org_context=_org_context` if the function accepts it. Check `src/core/onboarding.py` — if it does not have an `org_context` parameter, add it:

In `src/core/onboarding.py`, add `org_context: str = ""` parameter to `generate_solution()`. Prepend org context to the LLM prompt when non-empty:

```python
# In generate_solution(), in the system/user prompt construction, prepend:
if org_context:
    description = f"Company context:\n{org_context}\n\n---\n\n{description}"
```

- [ ] **Step 6: Run full test suite**

```bash
python -m pytest --tb=short -q
```
Expected: all existing tests pass + 4 new tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/interface/api.py src/core/onboarding.py tests/test_onboarding_import_endpoints.py
git commit -m "feat(onboarding): PUT /org endpoint + org context injection into solution generation"
```

---

## Task 3: POST /onboarding/scan-folder + POST /onboarding/refine

**Files:**
- Modify: `src/interface/api.py`
- Modify: `tests/test_onboarding_import_endpoints.py` (add more tests — note: spec names this `test_onboarding_endpoints.py` but use `test_onboarding_import_endpoints.py` throughout this plan to avoid conflicts)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_onboarding_import_endpoints.py`:

```python
# ── POST /onboarding/scan-folder ──────────────────────────────────────────────
import tempfile, os as _os

def test_scan_folder_nonexistent_returns_400():
    resp = client.post("/onboarding/scan-folder", json={
        "folder_path": "/nonexistent/path/xyz",
        "intent": "Build a QA agent",
        "solution_name": "test_qa",
    })
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "folder_not_found"


def test_scan_folder_empty_returns_400():
    with tempfile.TemporaryDirectory() as tmp:
        resp = client.post("/onboarding/scan-folder", json={
            "folder_path": tmp,
            "intent": "Build a QA agent",
            "solution_name": "test_qa",
        })
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "folder_empty"


def test_scan_folder_calls_llm_and_returns_files():
    mock_llm_response = '''{"project.yaml": "name: Test QA\\ndomain: test-qa", "prompts.yaml": "roles: []", "tasks.yaml": "task_types: []"}'''
    with tempfile.TemporaryDirectory() as tmp:
        with open(_os.path.join(tmp, "README.md"), "w") as f:
            f.write("# Test Project")
        with patch("src.interface.api._get_llm_gateway") as mock_gw:
            mock_gw.return_value.generate.return_value = mock_llm_response
            resp = client.post("/onboarding/scan-folder", json={
                "folder_path": tmp,
                "intent": "Build a QA agent",
                "solution_name": "test_qa",
            })
    assert resp.status_code == 200
    data = resp.json()
    assert "files" in data
    assert "project.yaml" in data["files"]
    assert "summary" in data


def test_scan_folder_missing_intent_returns_422():
    resp = client.post("/onboarding/scan-folder", json={
        "folder_path": "/any",
        "solution_name": "test_qa",
        # intent missing
    })
    assert resp.status_code == 422


# ── POST /onboarding/refine ───────────────────────────────────────────────────

def test_refine_calls_llm_with_feedback():
    current_files = {
        "project.yaml": "name: Test\ndomain: test",
        "prompts.yaml": "roles: []",
        "tasks.yaml": "task_types: []",
    }
    mock_response = '{"project.yaml": "name: Test QA\\ndomain: test-qa", "prompts.yaml": "roles: []", "tasks.yaml": "task_types: []"}'
    with patch("src.interface.api._get_llm_gateway") as mock_gw:
        mock_gw.return_value.generate.return_value = mock_response
        resp = client.post("/onboarding/refine", json={
            "solution_name": "test_qa",
            "current_files": current_files,
            "feedback": "Focus on firmware only",
        })
    assert resp.status_code == 200
    data = resp.json()
    assert "files" in data
    assert "summary" in data


def test_refine_missing_feedback_returns_422():
    resp = client.post("/onboarding/refine", json={
        "solution_name": "test_qa",
        "current_files": {"project.yaml": "", "prompts.yaml": "", "tasks.yaml": ""},
        # feedback missing
    })
    assert resp.status_code == 422
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
python -m pytest tests/test_onboarding_import_endpoints.py -k "scan_folder or refine" -v
```
Expected: failures/404s.

- [ ] **Step 3: Add Pydantic models and endpoints to api.py**

Add models (near other onboarding models at top of file):

```python
class ScanFolderRequest(BaseModel):
    folder_path: str
    intent: str
    solution_name: str

class RefineRequest(BaseModel):
    solution_name: str
    current_files: dict  # {"project.yaml": str, "prompts.yaml": str, "tasks.yaml": str}
    feedback: str
```

Add helper to load org context (add as a module-level helper function in api.py):

```python
def _load_org_context() -> str:
    """Load mission/vision/core_values from org.yaml for LLM injection."""
    try:
        from src.core.org_loader import _SOLUTIONS_DIR
        import yaml as _yaml
        org_path = os.path.join(_SOLUTIONS_DIR, "org.yaml")
        if not os.path.exists(org_path):
            return ""
        with open(org_path, encoding="utf-8") as f:
            data = _yaml.safe_load(f) or {}
        org = data.get("org", {})
        if not org.get("mission"):
            return ""
        parts = [f"Mission: {org['mission']}"]
        if org.get("vision"):
            parts.append(f"Vision: {org['vision']}")
        if org.get("core_values"):
            vals = "\n  - ".join(org["core_values"])
            parts.append(f"Core values:\n  - {vals}")
        return "\n".join(parts)
    except Exception:
        return ""
```

Add helper to parse LLM YAML output and build summary:

```python
def _parse_generated_files(raw: str) -> tuple[dict, dict]:
    """
    Parse LLM output — expects JSON with project.yaml/prompts.yaml/tasks.yaml keys.
    Returns (files_dict, summary_dict).
    """
    import json as _json, yaml as _yaml
    # Strip markdown fences
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        files = _json.loads(text)
    except Exception:
        # Fallback: treat entire response as project.yaml
        files = {"project.yaml": text, "prompts.yaml": "roles: {}", "tasks.yaml": "task_types: []"}

    # Build summary from project.yaml
    summary = {"name": "", "description": "", "task_types": [], "compliance_standards": [], "integrations": []}
    try:
        proj = _yaml.safe_load(files.get("project.yaml", "")) or {}
        summary["name"] = proj.get("name", "")
        summary["description"] = proj.get("description", "")
        summary["compliance_standards"] = proj.get("compliance_standards", [])
        summary["integrations"] = proj.get("integrations", [])
        tasks_raw = _yaml.safe_load(files.get("tasks.yaml", "")) or {}
        for tt in tasks_raw.get("task_types", []):
            if isinstance(tt, dict):
                summary["task_types"].append({
                    "name": tt.get("name", ""),
                    "description": tt.get("description", ""),
                })
    except Exception:
        pass
    return files, summary
```

Add endpoints:

```python
@app.post("/onboarding/scan-folder")
async def onboarding_scan_folder(req: ScanFolderRequest):
    """Scan a local folder and generate solution YAML using the LLM."""
    from src.core.folder_scanner import FolderScanner

    # Validate folder
    try:
        scanner = FolderScanner()
        folder_content = scanner.scan(req.folder_path)
    except FileNotFoundError:
        raise HTTPException(400, detail={"error": "folder_not_found", "message": f"Folder not found: {req.folder_path}"})

    if not folder_content.strip():
        raise HTTPException(400, detail={"error": "folder_empty", "message": "No readable files found in this folder."})

    org_context = _load_org_context()

    system_prompt = (
        "You are a SAGE solution architect. Generate three YAML files for a SAGE solution: "
        "project.yaml, prompts.yaml, and tasks.yaml. "
        "Return ONLY a JSON object with keys 'project.yaml', 'prompts.yaml', 'tasks.yaml' — "
        "each value is the full YAML content as a string. No other text."
    )
    user_prompt_parts = []
    if org_context:
        user_prompt_parts.append(f"Company context:\n{org_context}\n")
    user_prompt_parts.append(f"Intent: {req.intent}")
    user_prompt_parts.append(f"Solution name: {req.solution_name}")
    user_prompt_parts.append(f"\nCodebase content:\n{folder_content}")
    user_prompt = "\n\n".join(user_prompt_parts)

    llm = _get_llm_gateway()
    try:
        raw = llm.generate(system_prompt=system_prompt, user_prompt=user_prompt)
    except Exception as exc:
        logger.error("LLM error in scan-folder: %s", exc)
        raise HTTPException(503, detail={"error": "llm_unavailable", "message": "Could not reach the LLM."})

    files, summary = _parse_generated_files(raw)

    audit_logger.log_event(
        actor="human_via_onboarding",
        action_type="ONBOARDING_SCAN",
        input_context=req.intent,
        output_content=str(files.get("project.yaml", ""))[:2000],
        metadata={"solution_name": req.solution_name, "folder_path": req.folder_path},
    )

    return {"solution_name": req.solution_name, "files": files, "summary": summary}


@app.post("/onboarding/refine")
async def onboarding_refine(req: RefineRequest):
    """Refine previously generated solution YAML based on user feedback."""
    org_context = _load_org_context()

    system_prompt = (
        "You are a SAGE solution architect. Refine the provided YAML files based on the feedback. "
        "Return ONLY a JSON object with keys 'project.yaml', 'prompts.yaml', 'tasks.yaml' — "
        "each value is the full YAML content as a string. No other text."
    )
    user_prompt_parts = []
    if org_context:
        user_prompt_parts.append(f"Company context:\n{org_context}\n")
    user_prompt_parts.append(f"Solution name: {req.solution_name}")
    user_prompt_parts.append(f"Feedback: {req.feedback}")
    user_prompt_parts.append(
        f"\nCurrent YAML files:\n"
        + "\n---\n".join(f"# {k}\n{v}" for k, v in req.current_files.items())
    )
    user_prompt = "\n\n".join(user_prompt_parts)

    llm = _get_llm_gateway()
    try:
        raw = llm.generate(system_prompt=system_prompt, user_prompt=user_prompt)
    except Exception as exc:
        logger.error("LLM error in refine: %s", exc)
        raise HTTPException(503, detail={"error": "llm_unavailable", "message": "Could not reach the LLM."})

    files, summary = _parse_generated_files(raw)

    audit_logger.log_event(
        actor="human_via_onboarding",
        action_type="ONBOARDING_REFINE",
        input_context=req.feedback,
        output_content=str(files.get("project.yaml", ""))[:2000],
        metadata={"solution_name": req.solution_name},
    )

    return {"solution_name": req.solution_name, "files": files, "summary": summary}
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_onboarding_import_endpoints.py -v
```
Expected: all 10 tests pass.

- [ ] **Step 5: Run full suite**

```bash
python -m pytest --tb=short -q
```
Expected: all passing.

- [ ] **Step 7: Add `POST /onboarding/save-solution` endpoint**

This endpoint writes the accepted YAML files to disk so the solution is loadable after the user clicks "Looks good — continue".

Add model and endpoint to `src/interface/api.py`:

```python
class SaveSolutionRequest(BaseModel):
    solution_name: str
    files: dict  # {"project.yaml": str, "prompts.yaml": str, "tasks.yaml": str}

@app.post("/onboarding/save-solution")
async def onboarding_save_solution(req: SaveSolutionRequest):
    """Write generated YAML files to disk under SAGE_SOLUTIONS_DIR/<solution_name>/."""
    from src.core.org_loader import _SOLUTIONS_DIR
    solution_dir = os.path.join(_SOLUTIONS_DIR, req.solution_name)
    os.makedirs(solution_dir, exist_ok=True)
    for filename, content in req.files.items():
        # Only allow the three known YAML files
        if filename not in {"project.yaml", "prompts.yaml", "tasks.yaml"}:
            continue
        with open(os.path.join(solution_dir, filename), "w", encoding="utf-8") as f:
            f.write(content)
    audit_logger.log_event(
        actor="human_via_onboarding",
        action_type="ONBOARDING_COMPLETE",
        input_context=req.solution_name,
        output_content=str(req.files.get("project.yaml", ""))[:2000],
        metadata={"solution_name": req.solution_name},
    )
    return {"status": "saved", "solution_name": req.solution_name}
```

Add a test to `tests/test_onboarding_import_endpoints.py`:

```python
def test_save_solution_writes_files(tmp_path, monkeypatch):
    monkeypatch.setenv("SAGE_SOLUTIONS_DIR", str(tmp_path))
    resp = client.post("/onboarding/save-solution", json={
        "solution_name": "test_save",
        "files": {
            "project.yaml": "name: Test Save\ndomain: test-save",
            "prompts.yaml": "roles: {}",
            "tasks.yaml": "task_types: []",
        },
    })
    assert resp.status_code == 200
    assert (tmp_path / "test_save" / "project.yaml").exists()
```

- [ ] **Step 8: Run tests**

```bash
python -m pytest tests/test_onboarding_import_endpoints.py -v
```
Expected: all tests pass (including the new save-solution test).

- [ ] **Step 9: Commit**

```bash
git add src/interface/api.py tests/test_onboarding_import_endpoints.py
git commit -m "feat(onboarding): POST /onboarding/scan-folder + /onboarding/refine + /onboarding/save-solution"
```

---

## Task 4: Organization Settings page (frontend)

**Files:**
- Create: `web/src/pages/settings/Organization.tsx`
- Modify: `web/src/App.tsx`
- Modify: `web/src/components/layout/Sidebar.tsx`
- Modify: `web/src/components/layout/Header.tsx`
- Modify: `web/src/registry/modules.ts`
- Modify: `web/src/api/client.ts`

- [ ] **Step 1: Add saveOrg() to client.ts**

In `web/src/api/client.ts`, add after the existing `fetchOrg` / `reloadOrg` functions:

```typescript
export interface OrgUpdateRequest {
  name?: string
  mission?: string
  vision?: string
  core_values?: string[]
}

export interface OrgUpdateResponse {
  status: string
  org: {
    name?: string
    mission?: string
    vision?: string
    core_values?: string[]
  }
}

```

The `post` helper uses method POST but we need PUT. Add a `put` helper alongside `post`:

```typescript
async function put<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`PUT ${path} failed: ${res.statusText}`)
  return res.json()
}

export const saveOrg = (req: OrgUpdateRequest) =>
  put<OrgUpdateResponse>('/org', req)
```

- [ ] **Step 2: Create the `web/src/pages/settings/` directory and Organization.tsx**

The `web/src/pages/settings/` directory does not currently exist — create it as part of creating the file.

```tsx
// web/src/pages/settings/Organization.tsx
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchOrg, saveOrg } from '../../api/client'

export default function Organization() {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({ queryKey: ['org'], queryFn: fetchOrg })

  const org = (data as any)?.org ?? {}

  const [name, setName] = useState<string>('')
  const [mission, setMission] = useState<string>('')
  const [vision, setVision] = useState<string>('')
  const [values, setValues] = useState<string>('')
  const [initialised, setInitialised] = useState(false)
  const [saved, setSaved] = useState(false)

  // Populate fields once data loads
  if (!isLoading && !initialised) {
    setName(org.name ?? '')
    setMission(org.mission ?? '')
    setVision(org.vision ?? '')
    setValues((org.core_values ?? []).join('\n'))
    setInitialised(true)
  }

  const mutation = useMutation({
    mutationFn: () => saveOrg({
      name: name.trim() || undefined,
      mission: mission.trim() || undefined,
      vision: vision.trim() || undefined,
      core_values: values.trim() ? values.split('\n').map(v => v.trim()).filter(Boolean) : undefined,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['org'] })
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    },
  })

  const linkedSolutions: string[] = (data as any)?.org?.solutions ?? []

  const fieldStyle: React.CSSProperties = {
    width: '100%',
    background: 'rgba(255,255,255,0.05)',
    color: 'var(--sage-sidebar-active-text, #f1f5f9)',
    border: '1px solid rgba(255,255,255,0.12)',
    padding: '8px 12px',
    borderRadius: '6px',
    fontSize: '13px',
    fontFamily: 'inherit',
  }

  if (isLoading) return <div style={{ padding: 32, color: 'var(--sage-sidebar-text, #94a3b8)' }}>Loading...</div>

  return (
    <div style={{ maxWidth: 640, margin: '0 auto', padding: '32px 24px', display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--sage-sidebar-active-text, #f1f5f9)', margin: 0 }}>Organization</h1>
        <p style={{ fontSize: 13, color: 'var(--sage-sidebar-text, #94a3b8)', marginTop: 4 }}>
          Define your company mission and values. All solution generation will be shaped by this context.
        </p>
      </div>

      {/* Name */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <label style={{ fontSize: 11, color: 'var(--sage-sidebar-text, #94a3b8)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          Organization Name
        </label>
        <input
          style={{ ...fieldStyle, width: 320 }}
          value={name}
          onChange={e => setName(e.target.value)}
          placeholder="Acme Corp"
        />
      </div>

      {/* Mission */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <label style={{ fontSize: 11, color: 'var(--sage-sidebar-text, #94a3b8)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          Mission <span style={{ color: '#ef4444' }}>*</span>
        </label>
        <p style={{ fontSize: 11, color: 'rgba(255,255,255,0.35)', margin: 0 }}>Why the company exists — the root all solutions branch from.</p>
        <textarea
          style={{ ...fieldStyle, height: 72, resize: 'vertical' }}
          value={mission}
          onChange={e => setMission(e.target.value)}
          placeholder="We help end unnecessary diabetic amputations through AI-assisted early detection."
        />
      </div>

      {/* Vision */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <label style={{ fontSize: 11, color: 'var(--sage-sidebar-text, #94a3b8)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          Vision
        </label>
        <p style={{ fontSize: 11, color: 'rgba(255,255,255,0.35)', margin: 0 }}>Where you are going in 10 years.</p>
        <textarea
          style={{ ...fieldStyle, height: 64, resize: 'vertical' }}
          value={vision}
          onChange={e => setVision(e.target.value)}
          placeholder="A world where no patient loses a limb due to a late or missed diagnosis."
        />
      </div>

      {/* Core Values */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <label style={{ fontSize: 11, color: 'var(--sage-sidebar-text, #94a3b8)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          Core Values
        </label>
        <p style={{ fontSize: 11, color: 'rgba(255,255,255,0.35)', margin: 0 }}>One per line — guides how every agent reasons.</p>
        <textarea
          style={{ ...fieldStyle, height: 88, resize: 'vertical' }}
          value={values}
          onChange={e => setValues(e.target.value)}
          placeholder={'Patient safety above all\nEvidence-based, never experimental\nTransparency with clinicians'}
        />
      </div>

      {/* Save */}
      <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
        <button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
          style={{
            background: 'var(--sage-sidebar-accent, #6366f1)',
            color: '#fff',
            border: 'none',
            padding: '9px 22px',
            borderRadius: 6,
            fontSize: 13,
            fontWeight: 500,
            cursor: mutation.isPending ? 'not-allowed' : 'pointer',
            opacity: mutation.isPending ? 0.7 : 1,
          }}
        >
          {mutation.isPending ? 'Saving...' : 'Save Organization'}
        </button>
        {saved && <span style={{ fontSize: 12, color: '#10b981' }}>Saved</span>}
        {mutation.isError && <span style={{ fontSize: 12, color: '#ef4444' }}>Save failed — try again</span>}
      </div>

      {/* Linked solutions */}
      {linkedSolutions.length > 0 && (
        <div style={{ borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: 20 }}>
          <div style={{ fontSize: 11, color: 'var(--sage-sidebar-text, #94a3b8)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>
            Linked Solutions
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {linkedSolutions.map(s => (
              <span key={s} style={{
                background: 'rgba(255,255,255,0.05)',
                color: 'var(--sage-sidebar-text, #94a3b8)',
                padding: '4px 12px',
                borderRadius: 12,
                fontSize: 12,
                border: '1px solid rgba(255,255,255,0.1)',
              }}>{s}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Wire route in App.tsx**

In `web/src/App.tsx`, find the existing settings routes (near `<Route path="/settings"`) and add:

```tsx
import Organization from './pages/settings/Organization'
// ...
<Route path="/settings/organization" element={<Organization />} />
```

- [ ] **Step 4: Add nav entry in Sidebar.tsx**

In `web/src/components/layout/Sidebar.tsx`, find the Admin `NavArea` (the one with `id: 'admin'`). Add to its `items` array:

```typescript
{ to: '/settings/organization', icon: Building2, label: 'Organization', moduleId: 'organization', tooltip: 'Company mission, vision and values' },
```

`Building2` is already imported (used in the SolutionRail). If not, add `Building2` to the lucide-react import.

- [ ] **Step 5: Add to ROUTE_TO_AREA and PAGE_TITLES in Header.tsx**

In `web/src/components/layout/Header.tsx`:

```typescript
// In PAGE_TITLES:
'/settings/organization': 'Organization',

// In ROUTE_TO_AREA:
'/settings/organization': 'Admin',
```

- [ ] **Step 6: Add to MODULE_REGISTRY in modules.ts**

In `web/src/registry/modules.ts`, add to `MODULE_REGISTRY`:

```typescript
organization: {
  id: 'organization',
  name: 'Organization',
  description: 'Company mission, vision, and core values — the root context for all solutions.',
  version: '1.0.0',
  route: '/settings/organization',
  features: [
    'Define company mission statement',
    'Set vision and core values',
    'Context auto-injected into all solution generation',
    'View linked solutions',
  ],
  improvementHints: [],
},
```

- [ ] **Step 7: Add Organization link to Settings.tsx**

Read `web/src/pages/Settings.tsx` first to understand its current structure, then add an entry linking to `/settings/organization`:

```tsx
// In the Settings page, add a nav item or card for Organization:
// (exact placement depends on current structure — read the file first)
// Example if Settings renders a list of setting areas:
{ label: 'Organization', description: 'Mission, vision, and core values', route: '/settings/organization' }
```

- [ ] **Step 8: TypeScript check**

```bash
cd C:\sandbox\SAGE\web && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 9: Commit**

```bash
git add web/src/pages/settings/Organization.tsx web/src/App.tsx web/src/components/layout/Sidebar.tsx web/src/components/layout/Header.tsx web/src/registry/modules.ts web/src/api/client.ts web/src/pages/Settings.tsx
git commit -m "feat(org): Organization settings page — mission, vision, core values"
```

---

## Task 5: Dashboard empty state

**Files:**
- Create: `web/src/components/dashboard/EmptyState.tsx`
- Modify: `web/src/pages/Dashboard.tsx`

- [ ] **Step 1: Create EmptyState.tsx**

```tsx
// web/src/components/dashboard/EmptyState.tsx
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchOrg } from '../../api/client'

export default function EmptyState() {
  const navigate = useNavigate()
  const { data: orgData } = useQuery({ queryKey: ['org'], queryFn: fetchOrg })
  const hasMission = Boolean((orgData as any)?.org?.mission)

  const cardStyle: React.CSSProperties = {
    background: 'rgba(255,255,255,0.03)',
    border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: 10,
    padding: '20px 24px',
    display: 'flex',
    alignItems: 'flex-start',
    gap: 16,
  }

  const stepNumStyle = (done: boolean): React.CSSProperties => ({
    width: 28,
    height: 28,
    borderRadius: '50%',
    background: done ? '#16a34a' : 'rgba(255,255,255,0.08)',
    color: done ? '#fff' : 'var(--sage-sidebar-text, #94a3b8)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: 13,
    fontWeight: 600,
    flexShrink: 0,
  })

  return (
    <div style={{ maxWidth: 560, margin: '80px auto', padding: '0 24px', display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <h2 style={{ fontSize: 20, fontWeight: 600, color: 'var(--sage-sidebar-active-text, #f1f5f9)', margin: 0 }}>Welcome to SAGE</h2>
        <p style={{ fontSize: 13, color: 'var(--sage-sidebar-text, #94a3b8)', marginTop: 6 }}>
          Get started by defining your organization, then create your first solution.
        </p>
      </div>

      {/* Step 1 */}
      <div style={cardStyle}>
        <div style={stepNumStyle(hasMission)}>{hasMission ? '✓' : '1'}</div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--sage-sidebar-active-text, #f1f5f9)', marginBottom: 4 }}>
            Define your organization
          </div>
          <p style={{ fontSize: 12, color: 'var(--sage-sidebar-text, #94a3b8)', margin: '0 0 12px' }}>
            Set your company mission, vision, and core values. SAGE uses this as the root context for every solution you build.
          </p>
          {!hasMission && (
            <button
              onClick={() => navigate('/settings/organization')}
              style={{
                background: 'var(--sage-sidebar-accent, #6366f1)',
                color: '#fff',
                border: 'none',
                padding: '7px 16px',
                borderRadius: 6,
                fontSize: 12,
                cursor: 'pointer',
              }}
            >
              Set up organization
            </button>
          )}
          {hasMission && <span style={{ fontSize: 12, color: '#10b981' }}>Done</span>}
        </div>
      </div>

      {/* Step 2 */}
      <div style={cardStyle}>
        <div style={stepNumStyle(false)}>2</div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--sage-sidebar-active-text, #f1f5f9)', marginBottom: 4 }}>
            Create your first solution
          </div>
          <p style={{ fontSize: 12, color: 'var(--sage-sidebar-text, #94a3b8)', margin: '0 0 12px' }}>
            Describe a domain or import an existing codebase — SAGE generates the agent configuration for you.
          </p>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <button
              onClick={() => navigate('/onboarding')}
              style={{
                background: 'rgba(99,102,241,0.15)',
                color: '#a5b4fc',
                border: '1px solid rgba(99,102,241,0.3)',
                padding: '7px 16px',
                borderRadius: 6,
                fontSize: 12,
                cursor: 'pointer',
              }}
            >
              Create solution
            </button>
            <button
              onClick={() => navigate('/onboarding')}
              style={{ background: 'transparent', color: 'var(--sage-sidebar-text, #94a3b8)', border: 'none', fontSize: 12, cursor: 'pointer' }}
            >
              Skip for now
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Use EmptyState in Dashboard.tsx**

Read `web/src/pages/Dashboard.tsx` first to understand its current imports and query usage.

Add the import and empty-state check. `fetchProjects` is not currently imported in Dashboard.tsx — add it explicitly:

```tsx
import EmptyState from '../components/dashboard/EmptyState'
import { fetchProjects } from '../api/client'  // add if not already present

// In the Dashboard component, add (or reuse the existing projects query):
const { data: projectsData } = useQuery({ queryKey: ['projects'], queryFn: fetchProjects })
const hasProjects = (projectsData?.projects?.length ?? 0) > 0

// Near the top of the JSX return (before the main dashboard layout):
if (!hasProjects) return <EmptyState />
```

If `fetchProjects` is already called in Dashboard.tsx under a different query key, reuse that existing data — do not add a duplicate query.

- [ ] **Step 3: TypeScript check**

```bash
cd C:\sandbox\SAGE\web && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add web/src/components/dashboard/EmptyState.tsx web/src/pages/Dashboard.tsx
git commit -m "feat(dashboard): empty state guidance card for first-time users"
```

---

## Task 6: Onboarding full-screen refactor + mission banner + LLM gate

**Files:**
- Modify: `web/src/pages/Onboarding.tsx`
- Modify: `web/src/api/client.ts` (add scanFolder, refineGeneration)

The existing `OnboardingWizard.tsx` is a modal component. We need to make `Onboarding.tsx` a full-screen page that either renders the existing wizard inline or the new import flow based on a tab toggle.

- [ ] **Step 1: Add scanFolder and refineGeneration to client.ts**

```typescript
export interface ScanFolderRequest {
  folder_path: string
  intent: string
  solution_name: string
}

export interface GeneratedFiles {
  'project.yaml': string
  'prompts.yaml': string
  'tasks.yaml': string
}

export interface ScanSummary {
  name: string
  description: string
  task_types: Array<{ name: string; description: string }>
  compliance_standards: string[]
  integrations: string[]
}

export interface ScanFolderResponse {
  solution_name: string
  files: GeneratedFiles
  summary: ScanSummary
}

export interface RefineRequest {
  solution_name: string
  current_files: GeneratedFiles
  feedback: string
}

export interface SaveSolutionRequest {
  solution_name: string
  files: GeneratedFiles
}

export const scanFolder = (req: ScanFolderRequest) =>
  post<ScanFolderResponse>('/onboarding/scan-folder', req)

export const refineGeneration = (req: RefineRequest) =>
  post<ScanFolderResponse>('/onboarding/refine', req)

export const saveSolution = (req: SaveSolutionRequest) =>
  post<{ status: string; solution_name: string }>('/onboarding/save-solution', req)
```

- [ ] **Step 2: Refactor Onboarding.tsx to full-screen page**

Read the current `web/src/pages/Onboarding.tsx` first, then rewrite it as a full-screen page:

```tsx
// web/src/pages/Onboarding.tsx
import { useQuery } from '@tanstack/react-query'
import { fetchOrg, fetchHealth } from '../api/client'
import ImportFlow from '../components/onboarding/ImportFlow'

// Re-export the existing wizard inline (not as modal)
// The existing OnboardingWizard expects onClose + onTourStart props
// For the full-screen page, onClose navigates back to '/'
import { useNavigate } from 'react-router-dom'
import OnboardingWizard from '../components/onboarding/OnboardingWizard'
import { useTourContext } from '../context/TourContext'

export default function Onboarding() {
  const navigate = useNavigate()
  const { startTour } = useTourContext()
  const [mode, setMode] = useState<'describe' | 'import'>('describe')

  const { data: orgData } = useQuery({ queryKey: ['org'], queryFn: fetchOrg })
  const { data: health } = useQuery({ queryKey: ['health'], queryFn: fetchHealth, refetchInterval: 10_000 })

  const org = (orgData as any)?.org ?? {}
  const llmConnected = (health as any)?.llm_connected ?? (health as any)?.status === 'ok'

  return (
    <div style={{ minHeight: '100vh', background: 'var(--sage-sidebar-bg, #0f172a)', padding: '32px 24px' }}>

      {/* LLM gate banner */}
      {!llmConnected && (
        <div style={{
          background: 'rgba(251,191,36,0.08)',
          border: '1px solid rgba(251,191,36,0.25)',
          borderRadius: 8,
          padding: '10px 16px',
          marginBottom: 20,
          fontSize: 13,
          color: '#fbbf24',
          display: 'flex',
          gap: 8,
          alignItems: 'center',
        }}>
          LLM is not connected — generation is disabled.
          <a href="/llm" style={{ color: '#fbbf24', textDecoration: 'underline', marginLeft: 4 }}>Go to Settings → LLM</a>
        </div>
      )}

      {/* Mission banner */}
      {org.mission && (
        <div style={{
          background: 'rgba(99,102,241,0.08)',
          border: '1px solid rgba(99,102,241,0.2)',
          borderLeft: '3px solid var(--sage-sidebar-accent, #6366f1)',
          borderRadius: 6,
          padding: '10px 16px',
          marginBottom: 24,
        }}>
          <div style={{ fontSize: 10, color: '#818cf8', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 2 }}>
            Building under — {org.name || 'Your Organization'}
          </div>
          <div style={{ fontSize: 13, color: 'var(--sage-sidebar-active-text, #f1f5f9)' }}>{org.mission}</div>
        </div>
      )}

      {/* Mode toggle */}
      <div style={{ display: 'flex', gap: 0, border: '1px solid rgba(255,255,255,0.1)', borderRadius: 6, overflow: 'hidden', width: 'fit-content', marginBottom: 28 }}>
        {(['describe', 'import'] as const).map(m => (
          <button
            key={m}
            onClick={() => setMode(m)}
            style={{
              padding: '8px 20px',
              background: mode === m ? 'rgba(99,102,241,0.2)' : 'transparent',
              color: mode === m ? '#a5b4fc' : '#64748b',
              border: 'none',
              borderRight: m === 'describe' ? '1px solid rgba(255,255,255,0.1)' : 'none',
              cursor: 'pointer',
              fontSize: 13,
            }}
          >
            {m === 'describe' ? 'Describe it' : 'Import from folder'}
          </button>
        ))}
      </div>

      {/* Content */}
      {mode === 'describe' ? (
        <OnboardingWizard
          onClose={() => navigate('/')}
          onTourStart={(id) => { startTour(id); navigate('/') }}
          llmConnected={llmConnected}
          inline
        />
      ) : (
        <ImportFlow llmConnected={llmConnected} />
      )}
    </div>
  )
}
```

Note: `OnboardingWizard` will need an `inline` prop to suppress its modal chrome and an `llmConnected` prop to disable the Generate button. Add these optional props to `OnboardingWizard.tsx`:

```tsx
// In OnboardingWizard.tsx, add to props interface:
interface OnboardingWizardProps {
  onClose: () => void
  onTourStart: (solutionId: string) => void
  inline?: boolean       // suppress modal wrapper when true
  llmConnected?: boolean // disable generate button when false
}
```

When `inline` is true, render the wizard content directly without the modal overlay/backdrop. When `llmConnected` is false, disable the "Generate" button with a tooltip "LLM not connected".

- [ ] **Step 3: Verify existing OnboardingWizard call sites still compile**

The `inline` and `llmConnected` props added to `OnboardingWizard` are optional (`?`) so existing call sites that pass only `onClose` and `onTourStart` must still compile without changes. Grep for usages:

```bash
grep -rn "OnboardingWizard" web/src --include="*.tsx" --include="*.ts"
```

Confirm every call site either uses the new props or omits them (both are valid since they're optional). The TypeScript check in Step 4 will catch any failures.

- [ ] **Step 4: TypeScript check**

```bash
cd C:\sandbox\SAGE\web && npx tsc --noEmit
```
Fix any type errors. Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add web/src/pages/Onboarding.tsx web/src/components/onboarding/OnboardingWizard.tsx web/src/api/client.ts
git commit -m "feat(onboarding): full-screen page with mission banner, LLM gate, describe/import tabs"
```

---

## Task 7: ImportFlow + ReviewPanel components

**Files:**
- Create: `web/src/components/onboarding/ImportFlow.tsx`
- Create: `web/src/components/onboarding/ReviewPanel.tsx`

- [ ] **Step 1: Create ReviewPanel.tsx**

```tsx
// web/src/components/onboarding/ReviewPanel.tsx
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { refineGeneration } from '../../api/client'
import type { ScanFolderResponse, GeneratedFiles } from '../../api/client'

interface ReviewPanelProps {
  result: ScanFolderResponse
  onAccept: (files: GeneratedFiles) => void
  onStartOver: () => void
}

export default function ReviewPanel({ result, onAccept, onStartOver }: ReviewPanelProps) {
  const [viewTab, setViewTab] = useState<'summary' | 'yaml'>('summary')
  const [yamlSubTab, setYamlSubTab] = useState<keyof GeneratedFiles>('project.yaml')
  const [files, setFiles] = useState<GeneratedFiles>(result.files)
  const [summary, setSummary] = useState(result.summary)
  const [feedback, setFeedback] = useState('')

  const refineMutation = useMutation({
    mutationFn: () => refineGeneration({
      solution_name: result.solution_name,
      current_files: files,
      feedback,
    }),
    onSuccess: (data) => {
      setFiles(data.files)
      setSummary(data.summary)
      setFeedback('')
    },
  })

  const tabBtn = (label: string, active: boolean, onClick: () => void) => (
    <button onClick={onClick} style={{
      padding: '6px 16px',
      background: 'transparent',
      color: active ? '#a5b4fc' : '#64748b',
      border: 'none',
      borderBottom: active ? '2px solid #6366f1' : '2px solid transparent',
      cursor: 'pointer',
      fontSize: 12,
    }}>{label}</button>
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 700 }}>

      {/* Tab bar */}
      <div style={{ display: 'flex', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
        {tabBtn('Summary', viewTab === 'summary', () => setViewTab('summary'))}
        {tabBtn('YAML', viewTab === 'yaml', () => setViewTab('yaml'))}
      </div>

      {/* Summary tab */}
      {viewTab === 'summary' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, background: 'rgba(255,255,255,0.03)', borderRadius: 8, padding: 16 }}>
            <div style={{ width: 36, height: 36, background: 'rgba(99,102,241,0.2)', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#a5b4fc', fontSize: 16, fontWeight: 700, flexShrink: 0 }}>
              {(summary.name || result.solution_name)[0]?.toUpperCase()}
            </div>
            <div>
              <div style={{ color: 'var(--sage-sidebar-active-text, #f1f5f9)', fontSize: 14, fontWeight: 600, marginBottom: 4 }}>{summary.name || result.solution_name}</div>
              <div style={{ color: 'var(--sage-sidebar-text, #94a3b8)', fontSize: 12, lineHeight: 1.5 }}>{summary.description}</div>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <div style={{ background: 'rgba(255,255,255,0.03)', borderRadius: 8, padding: 14 }}>
              <div style={{ fontSize: 10, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>What it can do</div>
              {summary.task_types.length > 0 ? summary.task_types.map(t => (
                <div key={t.name} style={{ display: 'flex', gap: 8, fontSize: 12, color: 'var(--sage-sidebar-text, #94a3b8)', marginBottom: 4 }}>
                  <span style={{ color: '#10b981' }}>✓</span> {t.name}
                </div>
              )) : <div style={{ fontSize: 12, color: '#475569' }}>No task types defined yet</div>}
            </div>
            <div style={{ background: 'rgba(255,255,255,0.03)', borderRadius: 8, padding: 14 }}>
              {summary.compliance_standards.length > 0 && (
                <>
                  <div style={{ fontSize: 10, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>Compliance</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 12 }}>
                    {summary.compliance_standards.map(s => (
                      <span key={s} style={{ background: 'rgba(99,102,241,0.15)', color: '#a5b4fc', padding: '3px 10px', borderRadius: 12, fontSize: 11 }}>{s}</span>
                    ))}
                  </div>
                </>
              )}
              {summary.integrations.length > 0 && (
                <>
                  <div style={{ fontSize: 10, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>Integrations</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {summary.integrations.map(i => (
                      <span key={i} style={{ background: 'rgba(16,185,129,0.1)', color: '#6ee7b7', padding: '3px 10px', borderRadius: 12, fontSize: 11 }}>{i}</span>
                    ))}
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* YAML tab */}
      {viewTab === 'yaml' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ display: 'flex', gap: 6 }}>
            {(['project.yaml', 'prompts.yaml', 'tasks.yaml'] as const).map(k => (
              <button key={k} onClick={() => setYamlSubTab(k)} style={{
                background: yamlSubTab === k ? 'rgba(99,102,241,0.2)' : 'rgba(255,255,255,0.04)',
                color: yamlSubTab === k ? '#a5b4fc' : '#64748b',
                border: 'none',
                padding: '4px 12px',
                borderRadius: 12,
                fontSize: 11,
                cursor: 'pointer',
              }}>{k}</button>
            ))}
          </div>
          <textarea
            value={files[yamlSubTab]}
            onChange={e => setFiles(prev => ({ ...prev, [yamlSubTab]: e.target.value }))}
            style={{
              width: '100%',
              height: 200,
              background: 'rgba(255,255,255,0.03)',
              color: '#a5b4fc',
              border: '1px solid rgba(255,255,255,0.08)',
              padding: '10px 12px',
              borderRadius: 6,
              fontSize: 12,
              fontFamily: 'monospace',
              resize: 'vertical',
            }}
          />
        </div>
      )}

      {/* Refine box */}
      <div style={{ background: 'rgba(251,191,36,0.05)', border: '1px solid rgba(251,191,36,0.2)', borderRadius: 6, padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ fontSize: 11, color: '#fbbf24' }}>Not quite right? Tell SAGE what to change:</div>
        <textarea
          value={feedback}
          onChange={e => setFeedback(e.target.value)}
          placeholder="e.g. Focus only on the embedded C code, ignore Python tooling"
          style={{ width: '100%', height: 52, background: 'rgba(255,255,255,0.05)', color: 'var(--sage-sidebar-active-text, #f1f5f9)', border: '1px solid rgba(255,255,255,0.1)', padding: '8px 10px', borderRadius: 6, fontSize: 12, resize: 'vertical', fontFamily: 'inherit' }}
        />
        <button
          onClick={() => refineMutation.mutate()}
          disabled={!feedback.trim() || refineMutation.isPending}
          style={{ background: 'rgba(251,191,36,0.1)', color: '#fbbf24', border: '1px solid rgba(251,191,36,0.25)', padding: '7px 16px', borderRadius: 6, fontSize: 12, cursor: (!feedback.trim() || refineMutation.isPending) ? 'not-allowed' : 'pointer', width: 'fit-content', opacity: (!feedback.trim() || refineMutation.isPending) ? 0.6 : 1 }}
        >
          {refineMutation.isPending ? 'Regenerating...' : 'Regenerate →'}
        </button>
        {refineMutation.isError && <span style={{ fontSize: 11, color: '#ef4444' }}>Regeneration failed — try again</span>}
      </div>

      {/* Action buttons */}
      <div style={{ display: 'flex', gap: 10 }}>
        <button
          onClick={() => onAccept(files)}
          style={{ background: '#16a34a', color: '#fff', border: 'none', padding: '9px 22px', borderRadius: 6, fontSize: 13, cursor: 'pointer' }}
        >
          Looks good — continue
        </button>
        <button
          onClick={onStartOver}
          style={{ background: 'transparent', color: 'var(--sage-sidebar-text, #94a3b8)', border: '1px solid rgba(255,255,255,0.1)', padding: '9px 22px', borderRadius: 6, fontSize: 13, cursor: 'pointer' }}
        >
          Start over
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Create ImportFlow.tsx**

```tsx
// web/src/components/onboarding/ImportFlow.tsx
import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { scanFolder, saveSolution, switchProject } from '../../api/client'
import type { GeneratedFiles, ScanFolderResponse } from '../../api/client'
import ReviewPanel from './ReviewPanel'
import { useNavigate } from 'react-router-dom'

interface ImportFlowProps {
  llmConnected: boolean
}

type Step = 'input' | 'scanning' | 'review' | 'done'

export default function ImportFlow({ llmConnected }: ImportFlowProps) {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [step, setStep] = useState<Step>('input')
  const [folderPath, setFolderPath] = useState('')
  const [intent, setIntent] = useState('')
  const [solutionName, setSolutionName] = useState('')
  const [scanResult, setScanResult] = useState<ScanFolderResponse | null>(null)
  const [scanError, setScanError] = useState<string | null>(null)

  const scanMutation = useMutation({
    mutationFn: () => scanFolder({ folder_path: folderPath, intent, solution_name: solutionName }),
    onMutate: () => { setStep('scanning'); setScanError(null) },
    onSuccess: (data) => { setScanResult(data); setStep('review') },
    onError: (err: any) => {
      const detail = err?.detail ?? {}
      const code = detail?.error ?? 'unknown'
      const messages: Record<string, string> = {
        folder_not_found: 'Folder not found. Check the path and try again.',
        folder_empty: 'No readable files found in this folder.',
        llm_unavailable: 'Could not reach the LLM. Check Settings → LLM.',
        generation_failed: 'Generation failed. Try again or use Describe it instead.',
      }
      setScanError(messages[code] ?? 'An error occurred. Please try again.')
      setStep('input')
    },
  })

  const handleAccept = async (files: GeneratedFiles) => {
    // Write accepted files to disk, then switch to the new solution
    try {
      await saveSolution({ solution_name: solutionName, files })
      await switchProject(solutionName)
      qc.invalidateQueries({ queryKey: ['projects'] })
    } catch {
      // Even if switch fails, files are saved — navigate home
    }
    navigate('/')
  }

  const fieldStyle: React.CSSProperties = {
    background: 'rgba(255,255,255,0.05)',
    color: 'var(--sage-sidebar-active-text, #f1f5f9)',
    border: '1px solid rgba(255,255,255,0.12)',
    padding: '8px 12px',
    borderRadius: 6,
    fontSize: 13,
    fontFamily: 'inherit',
  }

  if (step === 'review' && scanResult) {
    return (
      <ReviewPanel
        result={scanResult}
        onAccept={handleAccept}
        onStartOver={() => { setStep('input'); setScanResult(null) }}
      />
    )
  }

  return (
    <div style={{ maxWidth: 600, display: 'flex', flexDirection: 'column', gap: 18 }}>

      {step === 'scanning' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, padding: '20px 0' }}>
          {['Reading README files', 'Reading docs / specs', 'Reading source files', 'Generating solution YAML…'].map((label, i) => (
            <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 13, color: i < 3 ? 'var(--sage-sidebar-text, #94a3b8)' : 'var(--sage-sidebar-active-text, #f1f5f9)' }}>
              <span style={{ width: 16, textAlign: 'center', color: i < 3 ? '#10b981' : '#6366f1' }}>
                {i < 3 ? '✓' : '…'}
              </span>
              {label}
            </div>
          ))}
        </div>
      )}

      {step === 'input' && (
        <>
          {scanError && (
            <div style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 6, padding: '10px 14px', fontSize: 12, color: '#fca5a5' }}>
              {scanError}
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={{ fontSize: 11, color: 'var(--sage-sidebar-text, #94a3b8)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Folder path</label>
            <div style={{ display: 'flex', gap: 8 }}>
              <input
                style={{ ...fieldStyle, flex: 1 }}
                value={folderPath}
                onChange={e => setFolderPath(e.target.value)}
                placeholder="C:\projects\my-codebase  or  /home/user/projects/app"
              />
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={{ fontSize: 11, color: 'var(--sage-sidebar-text, #94a3b8)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>What do you want to build from this?</label>
            <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.35)' }}>Be specific — this guides the LLM.</div>
            <textarea
              style={{ ...fieldStyle, height: 72, resize: 'vertical' }}
              value={intent}
              onChange={e => setIntent(e.target.value)}
              placeholder={'e.g. A QA agent that reviews firmware PRs against IEC 62304\ne.g. A documentation agent that generates API docs from source comments'}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={{ fontSize: 11, color: 'var(--sage-sidebar-text, #94a3b8)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Solution name</label>
            <input
              style={{ ...fieldStyle, width: 260 }}
              value={solutionName}
              onChange={e => setSolutionName(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, '_'))}
              placeholder="e.g. firmware_qa"
            />
          </div>

          <button
            onClick={() => scanMutation.mutate()}
            disabled={!llmConnected || !folderPath.trim() || !intent.trim() || !solutionName.trim()}
            title={!llmConnected ? 'LLM not connected' : undefined}
            style={{
              background: 'rgba(99,102,241,0.15)',
              color: '#a5b4fc',
              border: '1px solid rgba(99,102,241,0.3)',
              padding: '9px 20px',
              borderRadius: 6,
              fontSize: 13,
              cursor: (!llmConnected || !folderPath.trim() || !intent.trim() || !solutionName.trim()) ? 'not-allowed' : 'pointer',
              width: 'fit-content',
              opacity: (!llmConnected || !folderPath.trim() || !intent.trim() || !solutionName.trim()) ? 0.5 : 1,
            }}
          >
            Scan & generate →
          </button>
        </>
      )}
    </div>
  )
}
```

- [ ] **Step 3: TypeScript check**

```bash
cd C:\sandbox\SAGE\web && npx tsc --noEmit
```
Fix any type errors. Expected: no errors.

- [ ] **Step 4: Run full test suite**

```bash
cd C:\sandbox\SAGE && python -m pytest --tb=short -q
```
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/onboarding/ImportFlow.tsx web/src/components/onboarding/ReviewPanel.tsx
git commit -m "feat(onboarding): ImportFlow + ReviewPanel — folder scan, plain-English summary, YAML edit, refine loop"
```

---

## Final verification

- [ ] Run full Python test suite: `python -m pytest --tb=short -q` — all pass
- [ ] Run TypeScript check: `cd web && npx tsc --noEmit` — no errors
- [ ] Verify routes: open http://localhost:5173/settings/organization — Organization page loads
- [ ] Verify empty state: temporarily break `fetchProjects` to return empty — EmptyState card shown
- [ ] Verify onboarding: http://localhost:5173/onboarding — full-screen, mission banner visible if org set, import tab available
