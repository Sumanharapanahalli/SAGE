# SAGE[ai] — Integrations Guide

Detailed guide for configuring and using each external system integration.

---

## Microsoft Teams

### Overview

Teams integration has two directions:
1. **Reading**: Monitor channel messages for error keywords → trigger analysis
2. **Sending**: Post adaptive cards for alerts and approval requests

### Reading Messages (Graph API)

The `MonitorAgent` polls the configured channel every 30 seconds (configurable in `config.yaml`).

**Authentication**: MSAL client credentials flow (app-to-app, no user interaction).

**Required Azure permissions**:
- `ChannelMessage.Read.All` (Application)
- `Team.ReadBasic.All` (Application)

**Configuration**:
```yaml
# config.yaml
teams:
  team_id: "${TEAMS_TEAM_ID}"
  channel_id: "${TEAMS_CHANNEL_ID}"
  poll_interval_seconds: 30
```

**Error keyword detection**: The monitor looks for these keywords by default:
```
error, failure, fault, exception, critical, alarm, alert, FAIL, crash
```

Matched messages are emitted as `teams_error` events and routed to `AnalystAgent`.

### Sending Notifications (Incoming Webhook)

`TeamsBot` posts adaptive cards to the configured webhook URL.

**Card types**:

| Method | Use Case |
|:-------|:---------|
| `send_analysis_alert()` | AI proposal with severity, root cause, action |
| `send_mr_created()` | MR creation notification with link |
| `send_error_alert()` | System error with severity color coding |
| `send_approval_request()` | Interactive card with Approve/Reject buttons |

**Approval flow**:
1. AI generates a proposal
2. `send_approval_request()` posts card with buttons linking to `/approve/{trace_id}` and `/reject/{trace_id}`
3. Engineer clicks button (opens browser to FastAPI endpoint)
4. FastAPI endpoint logs approval/rejection and triggers learning

### Finding Team and Channel IDs

```bash
# Install Graph Explorer or use this PowerShell:
# Connect-MgGraph -Scopes "Team.ReadBasic.All"
# Get-MgTeam | Select DisplayName, Id
# Get-MgTeamChannel -TeamId <team_id> | Select DisplayName, Id
```

Or use [Graph Explorer](https://developer.microsoft.com/graph/graph-explorer):
- `GET https://graph.microsoft.com/v1.0/me/joinedTeams`
- `GET https://graph.microsoft.com/v1.0/teams/{team_id}/channels`

---

## GitLab

### Overview

GitLab integration enables:
- Creating MRs automatically from `sage-ai` labeled issues
- AI-powered code review with summarized feedback
- Pipeline status monitoring
- Comment posting on MRs

### MR Workflow

```
Issue created with label "sage-ai"
          |
          v
MonitorAgent detects it (_poll_gitlab_issues)
          |
          v
Event routed to DeveloperAgent.create_mr_from_issue()
          |
          v
LLM drafts MR title + description based on issue
          |
          v
MR created via GitLab API
          |
          v
TeamsBot.send_mr_created() notifies channel
          |
          v
Human reviews MR in GitLab
          |
          v
DeveloperAgent.review_merge_request() optionally called
          |
          v
AI review posted as MR comment
```

### Issue-to-MR Automation

Label issues with `sage-ai` in GitLab. The monitor agent polls every 2 minutes for new issues with this label and triggers MR creation.

```bash
# Manually trigger MR creation:
curl -X POST http://localhost:8000/mr/create \
  -H "Content-Type: application/json" \
  -d '{"project_id": 42, "issue_iid": 15}'
```

### AI Code Review

```bash
# Trigger a review:
curl -X POST http://localhost:8000/mr/review \
  -H "Content-Type: application/json" \
  -d '{"project_id": 42, "mr_iid": 7}'
```

The review returns:
```json
{
  "summary": "...",
  "issues": ["..."],
  "suggestions": ["..."],
  "approved": false,
  "trace_id": "uuid"
}
```

### API Access Levels Required

| Action | GitLab Role Needed |
|:-------|:------------------|
| Read issues/MRs | Reporter |
| Create MRs | Developer |
| Post comments | Developer |
| Read pipelines | Reporter |

---

## Metabase

### Error Query Setup

1. In Metabase, create a **SQL question** that queries your error database:
   ```sql
   SELECT id, timestamp, error_code, message, device_id, severity
   FROM manufacturing_errors
   WHERE timestamp >= NOW() - INTERVAL 24 HOURS
   ORDER BY timestamp DESC
   ```

2. Save the question and note its ID (from the URL: `/question/123`).

3. Set `METABASE_ERROR_QUESTION_ID=123`.

### Polling Configuration

```yaml
# config.yaml
metabase:
  poll_interval_seconds: 60  # Check every minute
```

The monitor agent calls `get_new_errors(since_hours=1)` on each poll cycle. If `has_new_errors` is true, each error row is emitted as a `metabase_error` event.

### Timestamp Field Detection

The server auto-detects timestamp fields by looking for these keywords in column names:
`time`, `date`, `timestamp`, `created`, `occurred`

Ensure your error query includes a timestamp column with one of these words in its name.

### Dashboard Monitoring

Use the MCP tools for ad-hoc queries:
- `list_dashboards()` — browse available dashboards
- `get_dashboard(id)` — see all cards on a dashboard
- `get_question_results(id)` — run any saved question

---

## Spira

### Incident Management

SAGE[ai] can create incidents automatically when errors are detected:

```python
from mcp_servers.spira_server import create_incident

result = create_incident(
    project_id=1,
    name="Temperature sensor fault — Sterilizer Unit 3",
    description="Detected at 14:23 UTC. ErrorCode=0x4F. Cycle aborted.",
    type_id=1  # 1=Bug/Defect
)
print(result["incident_id"])
```

### Common Incident Status IDs

These are the default Spira statuses (may vary per installation):

| ID | Status |
|:---|:-------|
| 1 | New |
| 2 | Open |
| 3 | Assigned |
| 4 | In Progress |
| 5 | Resolved |
| 6 | Closed |

Verify your instance's IDs:
```python
from mcp_servers.spira_server import list_incidents
result = list_incidents(project_id=1)
# Look at status_id in each incident
```

### Test Run Monitoring

```python
from mcp_servers.spira_server import get_test_runs

result = get_test_runs(project_id=1)
print(f"Pass: {result['passed']}, Fail: {result['failed']}")
```

---

## Serial Port

### Device Communication

The serial MCP server supports:
1. **Command-response** (`send_serial_command`): Send a command, read one line of response
2. **Streaming** (`read_serial_output`): Read all output for N seconds
3. **Persistent connections** (`open_persistent_connection`): Keep port open for multiple calls

### Common Command Patterns

```python
# AT commands (modem-style devices)
result = send_serial_command("COM3", 115200, "AT+STATUS?")

# SCPI commands (test equipment)
result = send_serial_command("COM4", 9600, "*IDN?")

# Custom embedded device protocol
result = send_serial_command("COM5", 115200, "READ_TEMP")
```

### Persistent Connection Example

```python
from mcp_servers.serial_port_server import (
    open_persistent_connection,
    send_serial_command,
    close_connection,
)

conn = open_persistent_connection("COM3", 115200)
conn_id = conn["connection_id"]

# Use connection_id for subsequent calls
# (Note: current tools use per-call connections;
#  the persistent connection is stored for future session-aware tools)

close_connection(conn_id)
```

### Troubleshooting Serial

- **"Access is denied"**: Another application has the port open (close serial monitor, etc.)
- **No response**: Check baud rate, termination character (`\n` vs `\r\n`)
- **Garbled data**: Wrong baud rate

---

## J-Link

### Firmware Flashing Workflow

```python
from mcp_servers.jlink_server import connect_jlink, flash_firmware, reset_target

# 1. Connect
connect_jlink(device="STM32F407VG", interface="SWD", speed=4000)

# 2. Flash
result = flash_firmware(bin_path="C:/builds/firmware_v2.1.0.bin")
print(f"Flashed {result['bytes_flashed']} bytes")

# 3. Reset and run
reset_target(halt=False)
```

### Memory Inspection

```python
from mcp_servers.jlink_server import connect_jlink, read_memory, read_registers

connect_jlink(device="STM32F407VG")

# Read 64 bytes from SRAM start
mem = read_memory(0x20000000, 64)
print(mem["hex_data"])

# Read all registers
regs = read_registers()
for name, val in regs["registers"].items():
    print(f"  {name}: {val}")
```

### RTT Logging

RTT (Real-Time Transfer) allows reading printf-style debug output without a UART:

```python
from mcp_servers.jlink_server import connect_jlink, read_rtt_output

connect_jlink(device="nRF52840_xxAA")
output = read_rtt_output(duration_seconds=5.0)

for line in output["lines"]:
    print(line)
```

Requires the target firmware to include SEGGER RTT library and have it initialized.

### Supported Target Examples

| MCU Family | Device String | Notes |
|:-----------|:-------------|:------|
| STM32F4 | `STM32F407VG` | Common evaluation board |
| STM32H7 | `STM32H743VI` | High-performance |
| nRF52 | `nRF52840_xxAA` | BLE devices |
| LPC | `LPC1768` | NXP Cortex-M3 |
| SAMD | `ATSAMD21G18` | Arduino-compatible |

Find the exact device string in the J-Link device database:
```bash
JLinkExe -commanderscript
# Then type: ShowEmuList
```
