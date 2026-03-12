# SAGE[ai] MCP Servers Reference

Model Context Protocol (MCP) servers that expose hardware and external systems as tools for LLMs (Gemini CLI and Claude Code).

---

## Overview

| Server | File | Purpose | Key Dependency |
|:-------|:-----|:--------|:--------------|
| Serial Port | `mcp_servers/serial_port_server.py` | COM port communication | `pyserial` |
| J-Link | `mcp_servers/jlink_server.py` | JTAG/SWD debugger | `pylink-square` |
| Metabase | `mcp_servers/metabase_server.py` | Analytics / error queries | `requests` |
| Spira | `mcp_servers/spira_server.py` | Test management / incidents | `requests` |
| Teams | `mcp_servers/teams_server.py` | Teams messages + webhooks | `msal`, `requests` |
| GitLab | `@zereight/mcp-gitlab` (npm) | Code review, MRs | Node.js / npx |

---

## Serial Port Server

**Purpose**: Enables the LLM to communicate with embedded devices via COM ports.

### Tools

| Tool | Parameters | Returns |
|:-----|:-----------|:--------|
| `list_serial_ports()` | — | `{ports: [{device, description, hwid}], count}` |
| `send_serial_command(port, baud_rate, command, timeout=2.0)` | port: str, baud_rate: int, command: str, timeout: float | `{port, command, response}` |
| `read_serial_output(port, baud_rate, duration_seconds=3.0)` | port: str, baud_rate: int, duration_seconds: float | `{output, lines, byte_count}` |
| `open_persistent_connection(port, baud_rate)` | port: str, baud_rate: int | `{connection_id, port, baud_rate, status}` |
| `close_connection(connection_id)` | connection_id: str | `{connection_id, status, port}` |

### Configuration

No environment variables required. Port and baud rate are passed per-tool-call.

### Running Standalone

```bash
python mcp_servers/serial_port_server.py
```

### Testing

```python
from mcp_servers.serial_port_server import test_connection
test_connection()
```

---

## J-Link Debugger Server

**Purpose**: Exposes JTAG/SWD debugging capabilities for MCU inspection, memory operations, and firmware flashing.

### Tools

| Tool | Parameters | Returns |
|:-----|:-----------|:--------|
| `connect_jlink(device, interface="SWD", speed=4000)` | device: str | `{status, device, interface, speed_khz, jlink_info}` |
| `disconnect_jlink()` | — | `{status}` |
| `read_memory(address, num_bytes)` | address: int, num_bytes: int | `{address, hex_data, preview}` |
| `write_memory(address, data_hex)` | address: int, data_hex: str | `{status, address, bytes_written}` |
| `read_registers()` | — | `{registers: {name: hex_value}, count}` |
| `flash_firmware(bin_path)` | bin_path: str | `{status, bin_path, bytes_flashed}` |
| `reset_target(halt=True)` | halt: bool | `{status}` |
| `get_jlink_info()` | — | `{serial_number, firmware_version, hardware_version, product_name}` |
| `read_rtt_output(duration_seconds=2.0)` | duration_seconds: float | `{output, lines, byte_count}` |

### Configuration

| Env Var | Description |
|:--------|:------------|
| `JLINK_DEVICE` | Target device name (e.g. `STM32F407VG`) |
| `JLINK_SERIAL` | J-Link serial number (optional) |

### Notes

- `connect_jlink()` must be called before any other tool
- Flash base address (`0x08000000`) is hardcoded for STM32 — adjust `flash_firmware()` for other targets
- RTT requires the target firmware to have SEGGER RTT initialized

---

## Metabase Server

**Purpose**: Queries Metabase analytics platform for manufacturing error data and dashboard information.

### Tools

| Tool | Parameters | Returns |
|:-----|:-----------|:--------|
| `get_session_token()` | — | `{token_obtained, cached_until}` |
| `get_question_results(question_id)` | question_id: int | `{columns, rows, row_count}` |
| `list_dashboards()` | — | `{dashboards: [{id, name, description}], count}` |
| `get_dashboard(dashboard_id)` | dashboard_id: int | `{dashboard_name, cards, card_count}` |
| `search_errors(since_hours=24)` | since_hours: int | `{errors, count, total_in_question}` |
| `get_new_errors(since_hours=1)` | since_hours: int | `{new_errors, count, has_new_errors, checked_at}` |

### Configuration

| Env Var | Description |
|:--------|:------------|
| `METABASE_URL` | Metabase server URL (no trailing slash) |
| `METABASE_USERNAME` | Service account email |
| `METABASE_PASSWORD` | Service account password |
| `METABASE_ERROR_QUESTION_ID` | Question ID for the error query |

### Authentication

The server authenticates via `POST /api/session` and caches the session token for 10 minutes to avoid repeated logins.

---

## Spira Server

**Purpose**: Manages incidents, requirements, test runs, and releases in SpiraTeam/SpiraTest.

### Tools

| Tool | Parameters | Returns |
|:-----|:-----------|:--------|
| `list_incidents(project_id, status_id=None)` | project_id: int | `{incidents, count}` |
| `get_incident(project_id, incident_id)` | project_id: int, incident_id: int | Full incident dict |
| `create_incident(project_id, name, description, type_id=1)` | project_id: int, name: str, description: str | Created incident dict |
| `update_incident(project_id, incident_id, fields)` | project_id: int, incident_id: int, fields: dict | `{status, updated_fields}` |
| `list_requirements(project_id)` | project_id: int | `{requirements, count}` |
| `get_test_runs(project_id, release_id=None)` | project_id: int | `{test_runs, count, passed, failed}` |
| `list_releases(project_id)` | project_id: int | `{releases, count}` |
| `get_project_info(project_id)` | project_id: int | `{name, description, active}` |

### Configuration

| Env Var | Description |
|:--------|:------------|
| `SPIRA_URL` | Spira server URL |
| `SPIRA_USERNAME` | Spira username |
| `SPIRA_API_KEY` | API key from Spira profile |
| `SPIRA_PROJECT_ID` | Default project ID |

### API Version

Uses Spira REST API v7: `{SPIRA_URL}/services/v7_0/RestService.svc/`

---

## Teams Server

**Purpose**: Reads Teams channel messages via Graph API and sends notifications via incoming webhooks.

### Tools

| Tool | Parameters | Returns |
|:-----|:-----------|:--------|
| `get_access_token()` | — | `{token_obtained, expires_at}` |
| `list_team_channels(team_id)` | team_id: str | `{channels, count}` |
| `get_recent_messages(team_id, channel_id, top=20)` | team_id: str, channel_id: str, top: int | `{messages, count}` |
| `get_messages_since(team_id, channel_id, since_minutes=60)` | team_id: str, channel_id: str, since_minutes: int | `{messages, count, since_datetime}` |
| `search_error_messages(team_id, channel_id, keywords=None)` | team_id: str, channel_id: str, keywords: list | `{error_messages, count, keywords_searched}` |
| `send_notification(webhook_url, title, message, color="0078D7")` | webhook_url: str, title: str, message: str | `{status}` |
| `send_alert(title, message, severity="info")` | title: str, message: str, severity: str | `{status}` |

### Configuration

| Env Var | Description |
|:--------|:------------|
| `TEAMS_TENANT_ID` | Azure AD tenant ID |
| `TEAMS_CLIENT_ID` | App registration client ID |
| `TEAMS_CLIENT_SECRET` | App registration client secret |
| `TEAMS_TEAM_ID` | Target Teams team ID |
| `TEAMS_CHANNEL_ID` | Target channel ID |
| `TEAMS_INCOMING_WEBHOOK_URL` | Incoming webhook URL for posting |

### Severity Colors for `send_alert()`

| Severity | Color | Use Case |
|:---------|:------|:---------|
| `info` | Blue | General notifications |
| `warning` | Orange | Attention needed |
| `error` | Red | Action required |
| `critical` | Dark Red | Emergency |

---

## GitLab MCP Server (npm-based)

The GitLab MCP uses the community package `@zereight/mcp-gitlab` via npx. It is configured in `.mcp.json` and `~/.gemini/settings.json`.

### Configuration

| Env Var | Description |
|:--------|:------------|
| `GITLAB_URL` | GitLab instance URL |
| `GITLAB_TOKEN` | Personal Access Token with `api` scope |

### Running

The GitLab MCP is invoked automatically by the LLM client when configured. To test manually:

```bash
npx -y @zereight/mcp-gitlab
```

---

## Integration with Gemini CLI

After running `python scripts/setup_gemini_mcp.py`, the MCP servers are registered in `~/.gemini/settings.json`. Gemini CLI will start each server on demand.

Example prompt to Gemini CLI:
```
List the available COM ports on this machine.
```

Gemini will call the `list_serial_ports` tool automatically.

---

## Integration with Claude Code

The `.mcp.json` file in the project root is automatically loaded by Claude Code. All tools become available in the Claude Code conversation context.

Example usage in Claude Code:
- "Flash the firmware at /path/to/firmware.bin to the connected STM32"
- "Check Metabase for new errors in the last hour"
- "Create a Spira incident for this manufacturing defect"
