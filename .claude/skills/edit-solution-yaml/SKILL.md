---
name: edit-solution-yaml
description: >
  Edit a solution's YAML configuration file (project.yaml, prompts.yaml,
  or tasks.yaml) and reload the running backend. Use when the user asks to
  change a prompt, add a task type, update active modules, or tweak any
  solution config. $ARGUMENTS format: "<solution> <file> <instruction>"
  e.g. "medtech prompts update the analyst prompt to include RTOS context"
user-invocable: true
allowed-tools: Read, Edit, Bash, Grep
---

Edit a SAGE solution YAML config file based on $ARGUMENTS.

## Argument parsing

$ARGUMENTS should be in the form: `<solution> <file> <natural-language-instruction>`

Examples:
- `medtech prompts add RTOS fault context to the analyst system prompt`
- `dfs tasks add a new task type FLASH_DIAGNOSTICS for flashing diagnostics`
- `medtech project add 'ISO 27001' to compliance_standards`
- `poseengine project set domain to ml-mobile`

## Steps

1. **Parse** solution name, file name (project/prompts/tasks), and instruction from $ARGUMENTS.

2. **Read** the current file at `solutions/<solution>/<file>.yaml`.

3. **Apply** the requested change using the Edit tool. Make only the specific change asked.
   Do not reformat, reorder, or clean up surrounding content.

4. **Validate** the YAML is still syntactically correct:
   ```bash
   python -c "import yaml; yaml.safe_load(open('solutions/<solution>/<file>.yaml'))" && echo OK
   ```
   If validation fails, revert the change and explain the YAML error.

5. **Reload** the backend if it's running:
   ```bash
   curl -s -X POST http://localhost:8000/config/switch \
     -H "Content-Type: application/json" \
     -d '{"project": "<solution>"}'
   ```
   If the backend isn't running, skip this step and note that the change will
   take effect on next `make run`.

6. **Confirm** the change:
   - Show the before/after diff (the changed lines only)
   - Confirm whether reload succeeded

## Rules
- Never change a file's overall structure — only the requested value.
- If the instruction is ambiguous, ask a clarifying question before editing.
- For `prompts.yaml` changes: quote the new prompt text in the confirmation
  so the user can verify the wording before it goes live.
- Never edit files in `src/` — only solution YAML files.
