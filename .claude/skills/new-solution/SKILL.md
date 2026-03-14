---
name: new-solution
description: >
  Scaffold a new SAGE solution from the starter template. Use when the user
  wants to create a new domain configuration (e.g. "create a solution for X").
  $ARGUMENTS is the solution name (e.g. "robotics" or "fintech").
user-invocable: true
allowed-tools: Bash, Read, Write, Edit, Glob
---

Scaffold a new SAGE Framework solution named $ARGUMENTS.

## Steps

1. **Validate the name** — must be lowercase letters, numbers, underscores only.
   Reject if `solutions/$ARGUMENTS/` already exists.

2. **Copy the starter template:**
   ```bash
   cp -r solutions/starter solutions/$ARGUMENTS
   ```

3. **Edit `solutions/$ARGUMENTS/project.yaml`:**
   - Set `name:` to a human-readable title based on the argument
   - Set `domain:` to the argument value
   - Clear `compliance_standards:` (leave empty list — user will add their own)
   - Keep `active_modules:` as-is (all modules visible by default)
   - Clear `integrations:` (empty list)
   - Update the `description:` to describe the new domain
   - Set `collection_name` in `settings.memory` to `<argument>_knowledge`

4. **Edit `solutions/$ARGUMENTS/prompts.yaml`:**
   - Replace the generic placeholder language with domain-appropriate context
   - Keep the prompt structure intact (analyst, developer, planner, monitor, roles sections)
   - Add at least one custom role relevant to the domain

5. **Edit `solutions/$ARGUMENTS/tasks.yaml`:**
   - Replace generic task types with domain-specific ones
   - Keep at minimum: `CREATE_MR` and `PLAN_TASK`
   - Add task_descriptions and task_payloads for every task type listed

6. **Create `solutions/$ARGUMENTS/README.md`** with:
   - One-line description
   - How to run: `make run PROJECT=$ARGUMENTS`
   - What task types are configured

7. **Confirm** by showing the user:
   ```
   Solution '$ARGUMENTS' created at solutions/$ARGUMENTS/
   Run with: make run PROJECT=$ARGUMENTS
   Edit prompts: solutions/$ARGUMENTS/prompts.yaml
   ```

## Rules
- Never modify `src/` for a new solution. If you feel the need to, it means
  the framework has a gap — report it to the user instead.
- Never hardcode the solution name anywhere in `src/` or `web/`.
- If the solution is proprietary (company-specific), remind the user to add
  it to `.gitignore` and store it in a separate private repository, mounted
  at runtime via `SAGE_SOLUTIONS_DIR`.
