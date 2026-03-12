---
name: new-solution
description: >
  Scaffold a new SAGE solution from the medtech template. Use when the user
  wants to create a new domain configuration (e.g. "create a solution for X").
  $ARGUMENTS is the solution name (e.g. "robotics" or "fintech").
user-invocable: true
allowed-tools: Bash, Read, Write, Edit, Glob
---

Scaffold a new SAGE Framework solution named $ARGUMENTS.

## Steps

1. **Validate the name** — must be lowercase letters, numbers, hyphens only.
   Reject if `solutions/$ARGUMENTS/` already exists.

2. **Copy the medtech template:**
   ```bash
   cp -r solutions/medtech solutions/$ARGUMENTS
   rm -f solutions/$ARGUMENTS/LICENSE   # will create fresh one
   ```

3. **Edit `solutions/$ARGUMENTS/project.yaml`:**
   - Set `name:` to a human-readable title based on the argument
   - Set `domain:` to the argument value
   - Clear `compliance_standards:` (leave empty list — user will add their own)
   - Keep `active_modules:` as-is (all modules visible by default)
   - Clear `integrations:` (empty list)
   - Update the `description:` to describe the new domain

4. **Edit `solutions/$ARGUMENTS/prompts.yaml`:**
   - Replace all medtech-specific language (firmware, ISO 13485, UART, etc.)
     with generic placeholders appropriate for the new domain
   - Keep the prompt structure intact (analyst, developer, planner, monitor sections)

5. **Edit `solutions/$ARGUMENTS/tasks.yaml`:**
   - Replace medtech-specific task types with generic ones for the new domain
   - Keep at minimum: `ANALYZE_LOG`, `REVIEW_MR`, `CREATE_MR`, `MONITOR_CHECK`, `PLAN_TASK`

6. **Create `solutions/$ARGUMENTS/LICENSE`:**
   If the solution name matches a known proprietary pattern (dfs, customer_*, private_*),
   write a PROPRIETARY NOTICE. Otherwise write MIT.

7. **Create `solutions/$ARGUMENTS/README.md`** with:
   - One-line description
   - How to run: `make run PROJECT=$ARGUMENTS`
   - What task types are configured

8. **Remove medtech-specific test data** from the copied tests directory.
   Clear `solutions/$ARGUMENTS/tests/` but keep the directory and `conftest.py`.
   Update `conftest.py`'s `SAGE_ROOT` path depth if needed.

9. **Confirm** by showing the user:
   ```
   Solution '$ARGUMENTS' created at solutions/$ARGUMENTS/
   Run with: make run PROJECT=$ARGUMENTS
   Edit prompts: solutions/$ARGUMENTS/prompts.yaml
   ```

## Rules
- Never modify `src/` for a new solution. If you feel the need to, it means
  the framework has a gap — report it to the user instead.
- Never hardcode the solution name anywhere in `src/` or `web/`.
- If the solution name is `dfs` or contains `customer_` or `private_`,
  add it to `.gitignore` and write a PROPRIETARY NOTICE.
