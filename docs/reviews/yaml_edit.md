# SAGE Feature Review — `yaml_edit`

**Reviewer:** Gemini (independent, cross-vendor)  
**Solution probed:** four_in_a_line  
**Backend:** `sage-desktop/sidecar/handlers/yaml_edit.py`  
**Frontend:** `YamlEdit.tsx`  
**Review time:** 63s

---

## Verdict
The `yaml_edit` feature is partly usable but carries severe risks of silent configuration corruption, data loss, and compliance audit bypasses.
**Works:** partly
**Score:** 5/10

## What Actually Works
* **File Reading:** The backend successfully loads target files from the solution directory, as verified by the `yaml.read` live execution returning the contents of `project.yaml` at path `C:\sandbox\DL-Sandbox\repo-split-v2\SAGE\solutions\four_in_a_line\project.yaml`.
* **Basic Syntax Validation:** The backend uses `_yaml.safe_load(content)` inside `yaml_edit.py` to prevent writing structurally invalid YAML syntax.
* **Basic Change Detection:** The frontend correctly computes the `dirty` state when a file is successfully loaded, enabling or disabling the "Save" and "Revert" buttons.

## System-Level Findings
1. **No Schema/Semantic Validation (High Severity):** While `yaml_edit.py` verifies the payload is syntactically valid YAML, it performs zero schema validation. An operator can delete required fields (e.g., `active_modules`) or input invalid data types. The backend will save this directly, causing downstream crashes or silent failures across the SAGE framework.
2. **Bypassing the Compliance Audit Trail (Medium Severity):** Changing solution configuration files (`project.yaml`, `prompts.yaml`, `tasks.yaml`) alters how agents behave. For a compliance-first framework in regulated industries, human edits to system configurations *must* be logged. Currently, `yaml_edit.py` writes directly to disk without emitting any audit log entry.
3. **No File Backups or Restore Safeguards (Medium Severity):** The backend handler overwrites files directly using `path.write_text()`. If an operator saves corrupted or incomplete content, there is no automatic backup file (`.bak` or timestamped copy) created to allow recovery.
4. **Global Mutable State (Low Severity):** The backend utilizes global module-level variables (`_solution_path` and `_solution_name`). In a concurrent or multi-user environment, this creates race conditions and risks writing modifications to the wrong solution.

## Usability Findings
1. **Silent Data Loss on File Switch:** If an operator edits `project.yaml` (making the editor `dirty`) and switches the dropdown select to `prompts.yaml`, the frontend immediately reloads. Unsaved changes to the previous file are permanently and silently discarded without any warning or confirmation modal.
2. **Permanent Lockout on Missing Files:** If a configuration file (such as `tasks.yaml`) is missing on disk, the read query fails. Because `dirty` is calculated as `read.data ? draft !== read.data.content : false`, it evaluates to `false` when `read.data` is missing. This permanently disables the "Save" button, preventing an operator from ever seeding or creating the missing file via the UI.
3. **No Loading States:** The frontend does not render a spinner or block user input while loading files. When switching files, the old file's content remains in the textarea until the network request completes, which is highly misleading.
4. **Bare-Bones Editor Experience:** The editor is an unstyled, plain HTML `<textarea>` lacking line numbers, syntax highlighting, autocomplete, or YAML linter feedback.

## Top 3 Fixes (optimizer-ready)

1. **Implement Unsaved Changes Confirmation in `YamlEdit.tsx`**
   * **Task:** Add a confirmation check when changing the selected file. If `dirty` is true when the dropdown `onChange` event fires, display a browser confirmation modal (`window.confirm`). If the operator cancels, abort the file switch and preserve the modified draft.
   * **Acceptance Criteria:** 
     * Switching files with unsaved changes prompts the user.
     * Canceling the prompt retains the current file selection and dirty draft content.
     * Confirming the prompt discards changes and loads the new file.

2. **Allow Creation and Seeding of Missing Files**
   * **Task:** Modify `yaml_edit.py`'s `read` function to return an empty string and a path instead of raising an `RpcError` if the YAML file does not exist. Update `YamlEdit.tsx`'s `dirty` logic to evaluate against an empty string when `read.data` is unseeded, allowing the "Save" button to become active.
   * **Acceptance Criteria:**
     * Selecting a non-existent YAML file does not render an error alert; instead, it provides an empty text area.
     * Typing into the empty text area of a missing file enables the "Save" button.
     * Clicking "Save" successfully creates the file on disk.

3. **Integrate Schema Validation and Audit Logging in `yaml_edit.py`**
   * **Task:** Add validation against SAGE's expected YAML structure (using a JSON Schema validator or Pydantic models) in the backend `write` function before saving. If invalid, raise an RPC error showing the specific field validation failure. Upon successful write, call SAGE's central audit/compliance logger to log the update.
   * **Acceptance Criteria:**
     * Saving a YAML file with missing mandatory properties (e.g., missing `name` in `project.yaml`) is rejected with a clear error path.
     * Saving a valid file triggers an audit log write containing the timestamp, user info, and file name.

---

## Live Runtime Evidence (raw)

```
[LIVE OK]    yaml.read
  -> {"file": "project", "solution": "four_in_a_line", "content": "# ==============================================================================\n# SAGE Solution \u2014 Four in a Line (Casual Game)\n# ==============================================================================\n# Example: cross-platform casual puzzle game (Unity or React Native)\n# Shows: game logic analysis, player analytics, monetisation review\n# ==============================================================================\n\nname: \"Four in a Line \u2014 Game Studio\"\nversion: \"1.0.0\"\ndomain: \"game-dev\"\ndescription: >\n  AI agent system for a cross-platform Four in a Line puzzle game. Agents\n  analyze game crash reports and bug logs, monitor player analytics for\n  retention and churn signals, review game logic and AI opponent code,\n  and assist with game balance and feature planning.\n\nactive_modules:\n  - dashboard\n  - analyst\n  - developer\n  - monitor\n  - audit\n  - improvements\n  - agents\n  - llm\n  - settings\n  - yaml-editor\n  - live-console\n  - integrations\n\ncompliance_standards:\n  - \"GDPR (player data and analytics)\"\n  - \"COPPA (if targeting under-13 players)\"\n  - \"Apple App Store Guidelines\"\n  - \"Google Play Policy\"\n\nintegrations:\n  - github\n  - slack\n\nsettings:\n  memory:\n    collection_name: \"four_in_a_line_knowledge\"\n  system:\n    max_concurrent_tasks: 1\n\nui_labels:\n  analyst_page_title:   \"Bug & Signal Analyzer\"\n  analyst_input_label:  \"Paste a crash log, bug report, or player analytics signal\"\n  developer_page_title: \"Game Code Reviewer\"\n  monitor_page_title:   \"Player Health Monitor\"\n  dashboard_subtitle:   \"Four in a Line \u2014 Studio Health\"\n\ndashboard:\n  badge_color: \"bg-yellow-100 text-yellow-800\"\n  context_color: \"border-yellow-200 bg-yellow-50\"\n  context_items:\n    - label: \"Platform\"\n      description: \"Cross-platform (iOS, Android, Web) \u2014 Unity or React Native\"\n    - label: \"Key Signals\"\n      description: \"Crash reports, DAU/retention, level completion funnels\"\n    - label: \"Team\"\n      description: \"Small indie studio \u2014 developer, designer, QA, game designer\"\n  quick_actions:\n    - { label: \"Analyze Bug\",       route: \"/analyst\",   description: \"Triage a crash or game bug\" }\n    - { label: \"Review Code\",       route: \"/developer\", description: \"Game logic or AI code review\" }\n    - { label: \"Player Analytics\",  route: \"/monitor\",   description: \"Retention and funnel signals\" }\n    - { label: \"Game Advisor\",      route: \"/agents\",    description: \"Balance and design advisor\" }\n", "path": "C:\\sandbox\\DL-Sandbox\\repo-split-v2\\SAGE\\solutions\\four_in_a_line\\project.yaml"}
```
