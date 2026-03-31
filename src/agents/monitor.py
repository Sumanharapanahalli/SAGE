"""
SAGE[ai] - Monitor Agent
=========================
Polls Teams channels, Metabase errors, and GitLab for new events.
Routes detected events to the analyst or developer agent.

Each poller runs as a daemon thread.
Events are emitted as dicts: {"type": ..., "source": ..., "content": ..., "timestamp": ...}
"""

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

import requests
import yaml

logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config", "config.yaml",
)


def _load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            return yaml.safe_load(f) or {}
    return {}


class MonitorAgent:
    """
    Continuously monitors multiple event sources and routes events to handlers.

    Sources:
      - Microsoft Teams channels (error keyword scanning)
      - Metabase error question (new manufacturing errors)
      - GitLab issues labeled 'sage-ai'

    Events are routed via registered callbacks and also to the audit logger.
    """

    def __init__(self):
        self.logger = logging.getLogger("MonitorAgent")
        config = _load_config()

        # Teams config
        teams_cfg = config.get("teams", {})
        self._teams_team_id = os.environ.get("TEAMS_TEAM_ID", str(teams_cfg.get("team_id", "")).replace("${TEAMS_TEAM_ID}", ""))
        self._teams_channel_id = os.environ.get("TEAMS_CHANNEL_ID", str(teams_cfg.get("channel_id", "")).replace("${TEAMS_CHANNEL_ID}", ""))
        self._teams_poll_interval = int(teams_cfg.get("poll_interval_seconds", 30))

        # Metabase config
        metabase_cfg = config.get("metabase", {})
        self._metabase_poll_interval = int(metabase_cfg.get("poll_interval_seconds", 60))

        # GitLab config
        gitlab_cfg = config.get("gitlab", {})
        self._gitlab_url = os.environ.get("GITLAB_URL", str(gitlab_cfg.get("url", "")).replace("${GITLAB_URL}", "")).rstrip("/")
        self._gitlab_token = os.environ.get("GITLAB_TOKEN", str(gitlab_cfg.get("token", "")).replace("${GITLAB_TOKEN}", ""))
        self._gitlab_project_id = os.environ.get("GITLAB_PROJECT_ID", str(gitlab_cfg.get("default_project_id", "")).replace("${GITLAB_PROJECT_ID}", ""))
        self._gitlab_poll_interval = 120  # poll GitLab every 2 minutes

        # State
        self._running = False
        self._threads: List[threading.Thread] = []
        self._callbacks: Dict[str, List[Callable]] = {}
        self._seen_message_ids: set = set()
        self._seen_issue_ids: set = set()
        self._seen_mr_ids: set = set()
        self._last_error_check: Optional[datetime] = None

        # Lazy singletons
        self._audit_logger = None

    @property
    def audit(self):
        if self._audit_logger is None:
            from src.memory.audit_logger import audit_logger
            self._audit_logger = audit_logger
        return self._audit_logger

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def start(self):
        """Starts all background polling threads."""
        if self._running:
            self.logger.warning("MonitorAgent already running.")
            return

        self._running = True
        self.logger.info("MonitorAgent starting...")

        # Teams poller
        if self._teams_team_id and self._teams_channel_id:
            t_teams = threading.Thread(
                target=self._poll_teams,
                args=(self._teams_poll_interval,),
                name="MonitorAgent-Teams",
                daemon=True,
            )
            self._threads.append(t_teams)
            t_teams.start()
            self.logger.info("Teams poller started (interval: %ds)", self._teams_poll_interval)
        else:
            self.logger.warning("Teams polling disabled: TEAMS_TEAM_ID or TEAMS_CHANNEL_ID not set.")

        # Metabase poller
        metabase_url = os.environ.get("METABASE_URL", "")
        if metabase_url:
            t_meta = threading.Thread(
                target=self._poll_metabase,
                args=(self._metabase_poll_interval,),
                name="MonitorAgent-Metabase",
                daemon=True,
            )
            self._threads.append(t_meta)
            t_meta.start()
            self.logger.info("Metabase poller started (interval: %ds)", self._metabase_poll_interval)
        else:
            self.logger.warning("Metabase polling disabled: METABASE_URL not set.")

        # GitLab poller
        if self._gitlab_url and self._gitlab_token and self._gitlab_project_id:
            t_gitlab = threading.Thread(
                target=self._poll_gitlab_issues,
                args=(self._gitlab_poll_interval,),
                name="MonitorAgent-GitLab",
                daemon=True,
            )
            self._threads.append(t_gitlab)
            t_gitlab.start()
            self.logger.info("GitLab poller started (interval: %ds)", self._gitlab_poll_interval)

            # GitLab MR poller — auto-triggers REVIEW_MR tasks for new open MRs
            t_gitlab_mr = threading.Thread(
                target=self._poll_gitlab_mrs,
                args=(self._gitlab_poll_interval,),
                name="MonitorAgent-GitLab-MR",
                daemon=True,
            )
            self._threads.append(t_gitlab_mr)
            t_gitlab_mr.start()
            self.logger.info("GitLab MR poller started (interval: %ds)", self._gitlab_poll_interval)
        else:
            self.logger.warning("GitLab polling disabled: GITLAB_URL, GITLAB_TOKEN, or GITLAB_PROJECT_ID not set.")

        self.logger.info("MonitorAgent running with %d active pollers.", len(self._threads))

    def stop(self):
        """Signals all polling threads to stop."""
        self.logger.info("MonitorAgent stopping...")
        self._running = False
        for t in self._threads:
            t.join(timeout=5)
        self._threads.clear()
        self.logger.info("MonitorAgent stopped.")

    def register_callback(self, event_type: str, callback: Callable):
        """
        Registers a callback for a specific event type.

        Args:
            event_type: One of 'teams_error', 'metabase_error', 'gitlab_issue', or '*' for all.
            callback:   Callable receiving a single event dict argument.
        """
        if event_type not in self._callbacks:
            self._callbacks[event_type] = []
        self._callbacks[event_type].append(callback)
        self.logger.debug("Callback registered for event type: %s", event_type)

    def get_status(self) -> dict:
        """Returns the current status of all polling threads."""
        return {
            "running": self._running,
            "active_threads": [t.name for t in self._threads if t.is_alive()],
            "thread_count": len([t for t in self._threads if t.is_alive()]),
            "seen_messages": len(self._seen_message_ids),
            "seen_issues": len(self._seen_issue_ids),
            "teams_configured": bool(self._teams_team_id and self._teams_channel_id),
            "metabase_configured": bool(os.environ.get("METABASE_URL")),
            "gitlab_configured": bool(self._gitlab_url and self._gitlab_token),
        }

    # -----------------------------------------------------------------------
    # Polling Threads
    # -----------------------------------------------------------------------

    def _poll_teams(self, interval: int):
        """
        Polls the configured Teams channel for new error-related messages.
        Emits 'teams_error' events for messages containing error keywords.
        """
        ERROR_KEYWORDS = ["error", "failure", "fault", "exception", "critical", "alarm", "alert", "FAIL", "crash"]
        self.logger.info("Teams polling thread started.")

        while self._running:
            try:
                from mcp_servers.teams_server import get_messages_since
                result = get_messages_since(
                    team_id=self._teams_team_id,
                    channel_id=self._teams_channel_id,
                    since_minutes=max(interval // 60 + 2, 2),
                )

                if "error" not in result:
                    for msg in result.get("messages", []):
                        msg_id = msg.get("id", "")
                        if msg_id in self._seen_message_ids:
                            continue

                        content = msg.get("content", "").lower()
                        matched = [k for k in ERROR_KEYWORDS if k.lower() in content]
                        if matched:
                            self._seen_message_ids.add(msg_id)
                            self._on_event("teams_error", {
                                "type": "teams_error",
                                "source": "teams",
                                "content": msg.get("content", ""),
                                "from": msg.get("from", "Unknown"),
                                "timestamp": msg.get("created_datetime", datetime.now(timezone.utc).isoformat()),
                                "matched_keywords": matched,
                                "message_id": msg_id,
                            })
            except Exception as e:
                self.logger.error("Teams polling error: %s", e)

            time.sleep(interval)

        self.logger.info("Teams polling thread stopped.")

    def _poll_metabase(self, interval: int):
        """
        Polls the Metabase error question for new manufacturing errors.
        Emits 'metabase_error' events for newly detected errors.
        """
        self.logger.info("Metabase polling thread started.")

        while self._running:
            try:
                from mcp_servers.metabase_server import get_new_errors
                check_hours = max(interval // 3600 + 1, 1)
                result = get_new_errors(since_hours=check_hours)

                if "error" not in result and result.get("has_new_errors"):
                    errors = result.get("new_errors", [])
                    self.logger.info("Metabase: %d new error(s) detected.", len(errors))

                    for error_row in errors:
                        self._on_event("metabase_error", {
                            "type": "metabase_error",
                            "source": "metabase",
                            "content": json.dumps(error_row),
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "error_data": error_row,
                        })

                self._last_error_check = datetime.now(timezone.utc)

            except Exception as e:
                self.logger.error("Metabase polling error: %s", e)

            time.sleep(interval)

        self.logger.info("Metabase polling thread stopped.")

    def _poll_gitlab_issues(self, interval: int):
        """
        Polls GitLab for new issues labeled 'sage-ai' that require attention.
        Emits 'gitlab_issue' events for newly found issues.
        """
        self.logger.info("GitLab polling thread started.")
        api_base = f"{self._gitlab_url}/api/v4"
        headers = {"Private-Token": self._gitlab_token}

        while self._running:
            try:
                resp = requests.get(
                    f"{api_base}/projects/{self._gitlab_project_id}/issues",
                    headers=headers,
                    params={"state": "opened", "labels": "sage-ai", "per_page": 20},
                    timeout=30,
                )
                resp.raise_for_status()
                issues = resp.json()

                for issue in issues:
                    issue_id = issue.get("id")
                    if issue_id in self._seen_issue_ids:
                        continue

                    self._seen_issue_ids.add(issue_id)
                    self._on_event("gitlab_issue", {
                        "type": "gitlab_issue",
                        "source": "gitlab",
                        "content": f"Issue #{issue.get('iid')}: {issue.get('title', '')}",
                        "timestamp": issue.get("created_at", datetime.now(timezone.utc).isoformat()),
                        "issue_iid": issue.get("iid"),
                        "issue_id": issue_id,
                        "title": issue.get("title", ""),
                        "description": issue.get("description", ""),
                        "labels": issue.get("labels", []),
                        "web_url": issue.get("web_url", ""),
                    })

            except requests.RequestException as e:
                self.logger.error("GitLab polling error: %s", e)
            except Exception as e:
                self.logger.error("Unexpected GitLab polling error: %s", e)

            time.sleep(interval)

        self.logger.info("GitLab polling thread stopped.")

    def _poll_gitlab_mrs(self, interval: int):
        """
        Polls GitLab for open merge requests that have not yet been queued for
        review.  For each newly detected open MR, submits a REVIEW_MR task to
        the task queue with ``source="monitor_auto"`` so it is distinguishable
        from manually submitted reviews.

        Deduplication is based on the GitLab MR global ID.  An MR is only
        submitted once per process lifetime; if the process restarts, the queue
        manager's SQLite persistence prevents duplicate execution because the
        worker checks task history before processing.
        """
        self.logger.info("GitLab MR polling thread started.")
        api_base = f"{self._gitlab_url}/api/v4"
        headers = {"Private-Token": self._gitlab_token}

        while self._running:
            try:
                resp = requests.get(
                    f"{api_base}/projects/{self._gitlab_project_id}/merge_requests",
                    headers=headers,
                    params={"state": "opened", "per_page": 20},
                    timeout=30,
                )
                resp.raise_for_status()
                mrs = resp.json()

                for mr in mrs:
                    mr_id = mr.get("id")
                    if mr_id in self._seen_mr_ids:
                        continue

                    # Within-process deduplication is handled by _seen_mr_ids above.
                    # Cross-restart deduplication: scan the persisted task queue for any
                    # pending/in-progress REVIEW_MR task whose metadata records this mr_id.
                    already_queued = False
                    try:
                        from src.core.queue_manager import task_queue
                        for existing in task_queue.get_all_tasks():
                            if (
                                existing.get("task_type") == "REVIEW_MR"
                                and existing.get("status") in ("pending", "in_progress")
                                and existing.get("metadata", {}).get("mr_id") == mr_id
                            ):
                                already_queued = True
                                break
                    except Exception as qe:
                        self.logger.warning("Queue check failed for MR %s: %s", mr_id, qe)

                    self._seen_mr_ids.add(mr_id)

                    if already_queued:
                        self.logger.debug("MR %s already has a REVIEW_MR task — skipping.", mr_id)
                        continue

                    # Submit a new REVIEW_MR task
                    try:
                        from src.core.queue_manager import task_queue
                        task_id = task_queue.submit(
                            task_type="REVIEW_MR",
                            payload={
                                "mr_id": mr_id,
                                "mr_iid": mr.get("iid"),
                                "title": mr.get("title", ""),
                                "description": mr.get("description", ""),
                                "source_branch": mr.get("source_branch", ""),
                                "target_branch": mr.get("target_branch", ""),
                                "author": mr.get("author", {}).get("username", ""),
                                "web_url": mr.get("web_url", ""),
                                "project_id": self._gitlab_project_id,
                            },
                            priority=5,
                            source="monitor_auto",
                            metadata={"mr_id": mr_id},
                        )
                        self.logger.info(
                            "Auto-queued REVIEW_MR task %s for MR !%s: %s",
                            task_id, mr.get("iid"), mr.get("title", "")[:60],
                        )
                        self._on_event("gitlab_mr_opened", {
                            "type": "gitlab_mr_opened",
                            "source": "gitlab",
                            "content": f"MR !{mr.get('iid')}: {mr.get('title', '')}",
                            "timestamp": mr.get("created_at", datetime.now(timezone.utc).isoformat()),
                            "mr_id": mr_id,
                            "mr_iid": mr.get("iid"),
                            "title": mr.get("title", ""),
                            "web_url": mr.get("web_url", ""),
                            "task_id": task_id,
                        })
                    except Exception as submit_err:
                        self.logger.error("Failed to queue REVIEW_MR for MR %s: %s", mr_id, submit_err)

            except requests.RequestException as e:
                self.logger.error("GitLab MR polling error: %s", e)
            except Exception as e:
                self.logger.error("Unexpected GitLab MR polling error: %s", e)

            time.sleep(interval)

        self.logger.info("GitLab MR polling thread stopped.")

    # -----------------------------------------------------------------------
    # Event Handler
    # -----------------------------------------------------------------------

    def _on_event(self, event_type: str, payload: dict):
        """
        Unified event handler. Logs to audit trail and routes to registered callbacks.

        Args:
            event_type: Event category string
            payload:    Event data dict
        """
        self.logger.info("EVENT [%s] from %s: %s", event_type, payload.get("source", "?"), payload.get("content", "")[:100])

        # Audit log every event
        try:
            self.audit.log_event(
                actor="MonitorAgent",
                action_type=f"EVENT_{event_type.upper()}",
                input_context=payload.get("content", "")[:500],
                output_content=json.dumps(payload)[:1000],
                metadata={"event_type": event_type, "source": payload.get("source")},
            )
        except Exception as e:
            self.logger.error("Audit log failed for event %s: %s", event_type, e)

        # Publish to EventBus for decoupled subscribers
        try:
            from src.modules.event_bus import event_bus
            event_bus.publish(event_type, payload)
        except Exception:
            pass  # event bus is supplementary

        # Dispatch to registered callbacks
        dispatched = 0
        for registered_type, callbacks in self._callbacks.items():
            if registered_type in (event_type, "*"):
                for cb in callbacks:
                    try:
                        cb(payload)
                        dispatched += 1
                    except Exception as e:
                        self.logger.error("Callback error for event %s: %s", event_type, e)

        if dispatched == 0:
            self.logger.debug("No callbacks registered for event type: %s", event_type)


# ---------------------------------------------------------------------------
# Global access point
# ---------------------------------------------------------------------------
monitor_agent = MonitorAgent()
