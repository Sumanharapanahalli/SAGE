# SAGE Privacy & Telemetry

This document describes **exactly what SAGE Desktop collects when
telemetry is enabled**, how long it keeps data, and how to opt out.
It is the canonical contract for the `sage-desktop` client; if the
code and this doc disagree, the code is wrong and should be fixed
to match this doc.

> **One-line summary:** Telemetry is OFF by default. When a user
> explicitly opts in, SAGE Desktop sends a tiny, strictly
> allowlisted stream of event counters — no content, no identifiers
> beyond an anonymous UUID, no raw prompts, no file paths. Phase 4
> ships the local buffer only; no network egress.

---

## 1. What *other* SAGE interfaces collect

Before we get to sage-desktop: the **web UI** (`src/interface/api.py`
+ `web/`) and the **VS Code extension** collect nothing about you.
They store your proposals, approvals, audit trail, and vector memory
under your solution's `.sage/` directory on your own disk. Nothing
leaves your machine unless you wire up an integration (LangFuse,
Slack, etc.) that inherently needs to.

This document is specifically about the **opt-in telemetry stream**
introduced by `sage-desktop` Phase 4.

---

## 2. Default stance

- **Disabled on first launch.** A fresh install has `enabled: false`
  in `%APPDATA%\sage-desktop\config.json`. Nothing is recorded, nothing
  is buffered, nothing is sent.
- **Affirmative action required.** The user must visit **Settings →
  Telemetry** and check the box themselves. There is no dark pattern,
  no pre-checked box, no "click accept to continue" flow.
- **Opting back out clears the buffer.** Unchecking the box disables
  recording *and* deletes `%APPDATA%\sage-desktop\telemetry.ndjson`
  in the same operation.

---

## 3. The allowlist (enforced by construction)

The single source of truth lives in
`sage-desktop/sidecar/handlers/telemetry.py`:

```python
_ALLOWED_EVENTS = frozenset({
    "approval.decided",
    "build.started",
    "build.completed",
    "solution.switched",
    "onboarding.generated",
    "update.checked",
    "update.installed",
    "llm.switched",
})

_ALLOWED_FIELDS = frozenset({
    "event",
    "kind",
    "status",
    "action_type",
    "route",
    "duration_ms",
    "count",
    "ok",
    "error_kind",
})
```

### 3.1 Event names

| Event | When emitted | What it means |
|---|---|---|
| `approval.decided` | User approves or rejects a proposal | A HITL decision was made. |
| `build.started` | `builds.start` RPC succeeds | A BuildOrchestrator run began. |
| `build.completed` | BuildOrchestrator reaches terminal state | A build ran to completion (success or failure). |
| `solution.switched` | Runtime solution switch completes | The active solution changed. |
| `onboarding.generated` | Onboarding wizard finishes | A new solution was generated. |
| `update.checked` | User clicks "Check for updates" | An update manifest was fetched. |
| `update.installed` | Updater applies a new release | A signed update was installed. |
| `llm.switched` | `llm.switch` RPC succeeds | LLM provider or model changed. |

Anything *not* in this list is dropped by `filter_payload()` — the
function builds a new dict and copies only allowlisted keys from the
input, so an unknown event name produces `None` and the record call
no-ops.

### 3.2 Field semantics

| Field | Type | Example | Never contains |
|---|---|---|---|
| `event` | string | `"approval.decided"` | n/a — this is the name above |
| `kind` | string | `"code_diff"`, `"yaml_edit"` | specific file or diff content |
| `status` | string | `"approved"`, `"rejected"`, `"completed"` | reason text |
| `action_type` | string | `"proposal_approval"`, `"build_start"` | payload body |
| `route` | string | `"/approvals"`, `"/builds"` | query strings, hash fragments |
| `duration_ms` | integer | `418` | wall-clock timestamps, dates |
| `count` | integer | `3` | identifiers |
| `ok` | boolean | `true` | n/a |
| `error_kind` | string | `"InvalidParams"`, `"SidecarDown"` | error messages, tracebacks |

Every event also carries two system fields that the client adds after
`filter_payload`:

- `anon_id` — a persisted UUIDv4 generated the first time you opt in.
  It is kept across opt-out so re-enabling doesn't look like a new
  user.
- `session_id` — a UUIDv4 generated per-launch, never persisted to
  disk. It lets post-hoc analysis distinguish two launches by the
  same anon user; it cannot be linked back to you.

---

## 4. What we guarantee **not** to collect

This is the explicit negative list. The allowlist above is the
positive definition; these are the categories we promise never appear
in a telemetry payload, enforced by the allowlist mechanic:

- Proposal content (code diffs, YAML edits, implementation plans,
  agent-hire rationales).
- `trace_id` values or any other per-decision correlation ID.
- User identifiers: name, email, OS user, Windows SID, machine
  hostname.
- Solution names, paths, repo URLs, or any breadcrumb of what you are
  building.
- File paths, file names, or file contents.
- Raw prompts sent to an LLM or raw responses received from one.
- Stack traces, error messages, or exception bodies. (`error_kind` is
  the Rust `DesktopError` enum variant as a stringly-typed name —
  e.g. `"SidecarDown"`, not the message.)
- Any form of browsing history, window titles, or screen contents.

The tests at `sage-desktop/sidecar/tests/test_telemetry.py` name
`user_email`, `trace_id`, and `raw_prompt` explicitly and assert they
cannot leak through `filter_payload()` — those are regression
anchors, not the full list.

---

## 5. Storage & transport

### 5.1 Local files

| File | What it holds | Format | Wiped when |
|---|---|---|---|
| `%APPDATA%\sage-desktop\config.json` | `enabled` flag, `anon_id` | JSON | Opt-out keeps both fields (anon_id stays so re-enable isn't a new identity); manually deletable any time |
| `%APPDATA%\sage-desktop\telemetry.ndjson` | Buffered events not yet sent | NDJSON (one event per line) | On opt-out, cleared immediately |

### 5.2 Transport (Phase 4)

**Phase 4 does not ship an uploader.** Events land in
`telemetry.ndjson` and stay there. No HTTP client runs, no network
sockets are opened. If you enable telemetry and never use the app
again, nothing ever leaves the device.

The HTTPS transport is scoped to **Phase 4.6**. Its release notes
will:

1. Publish the destination URL before any egress is added.
2. Add a per-user opt-in confirmation dialog on the first launch
   post-upgrade, even for users who previously opted in (a new
   destination is a new consent decision).
3. Document the retention period at the receiving end.

Until then: enabling telemetry is equivalent to asking the client to
count a few local events. Nothing reaches the internet.

---

## 6. How to opt out

### Via the app

1. Open SAGE Desktop.
2. Settings → Telemetry.
3. Uncheck "Enable anonymous telemetry".

This flips the flag in `config.json` to `false` and truncates
`telemetry.ndjson`. The `anon_id` field is preserved on disk so if you
re-enable later, existing event counts aren't attributed to a new
user. Delete the file manually if you want even that field gone.

### Manually

```powershell
# PowerShell
Remove-Item "$env:APPDATA\sage-desktop\telemetry.ndjson" -ErrorAction SilentlyContinue
Remove-Item "$env:APPDATA\sage-desktop\config.json" -ErrorAction SilentlyContinue
```

Or uninstall the app and delete `%APPDATA%\sage-desktop\`. Your
solution's `.sage/` directory is untouched by either flow — SAGE never
stores telemetry-related data there.

---

## 7. Verifying the code matches this doc

- Allowlist: `sage-desktop/sidecar/handlers/telemetry.py` — the
  frozensets `_ALLOWED_EVENTS` and `_ALLOWED_FIELDS` must match
  §3.1 / §3.2 above. A change to either requires a PR that updates
  this doc.
- Tests: `sage-desktop/sidecar/tests/test_telemetry.py` must name at
  minimum `user_email`, `trace_id`, and `raw_prompt` as fields that
  cannot leak through `filter_payload()`.
- Default: on a fresh install the checkbox in `TelemetryPanel.tsx`
  must render unchecked; tests under
  `sage-desktop/src/__tests__/components/TelemetryPanel.test.tsx`
  assert this.
- No uploader: `grep`ing `sage-desktop/` for HTTP clients in Phase 4
  should return zero hits outside of the updater (which talks only
  to the updater feed, carrying only an `If-None-Match` header — no
  event data).

If any of these invariants are violated, the PR that violated them
is a bug and should be reverted.

---

## 8. Changelog

| Date | Change |
|---|---|
| 2026-04-17 | Initial publication — Phase 4 telemetry contract, local buffer only, no uploader. |
