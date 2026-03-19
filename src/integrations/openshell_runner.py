"""
SAGE OpenShell Integration — sandboxed execution for AI agent tasks.

Wraps NVIDIA OpenShell CLI to run agent subprocesses in isolated sandboxes
with declarative YAML policies (filesystem + network + process constraints).

Gracefully degrades when OpenShell is not installed.

Usage:
    runner = OpenShellRunner()
    if runner.is_available():
        with runner.sandbox("task-abc123", policy_dict) as sb:
            result = sb.exec(["python", "task_runner.py"])
"""

import json
import logging
import os
import shutil
import subprocess
import tempfile
import threading
import uuid
from contextlib import contextmanager
from typing import Optional

import yaml

logger = logging.getLogger(__name__)


class SandboxHandle:
    """Represents a running OpenShell sandbox. Use via OpenShellRunner.sandbox() context manager."""

    def __init__(self, name: str, ssh_config_path: str):
        self.name = name
        self._ssh_config = ssh_config_path
        self.logger = logging.getLogger(f"OpenShell.{name[:8]}")

    def exec(self, command: list, timeout: int = 300) -> subprocess.CompletedProcess:
        """Run a command inside this sandbox via SSH."""
        ssh_cmd = [
            "ssh", "-F", self._ssh_config,
            "-o", "StrictHostKeyChecking=no",
            "sandbox",
            "--",
        ] + command
        self.logger.info("Sandbox exec: %s", " ".join(command))
        return subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )


class OpenShellRunner:
    """
    Manages OpenShell sandbox lifecycle for SAGE tasks.

    Checks for OpenShell availability at init. All methods degrade gracefully
    when OpenShell is not installed — tasks run without sandboxing.
    """

    def __init__(self):
        self.logger = logging.getLogger("OpenShellRunner")
        self._openshell_path = shutil.which("openshell")
        self._available = self._openshell_path is not None
        if self._available:
            self.logger.info("OpenShell available at %s", self._openshell_path)
        else:
            self.logger.warning(
                "OpenShell not found. Agent tasks will run without sandboxing. "
                "Install with: uv tool install -U openshell"
            )

    def is_available(self) -> bool:
        return self._available

    def status(self) -> dict:
        """Return availability and version info."""
        if not self._available:
            return {
                "available": False,
                "reason": "openshell not found in PATH",
                "install": "uv tool install -U openshell",
            }
        try:
            result = subprocess.run(
                [self._openshell_path, "version"],
                capture_output=True, text=True, timeout=10,
            )
            version = result.stdout.strip() or result.stderr.strip()
        except Exception as exc:
            version = f"error: {exc}"
        return {"available": True, "path": self._openshell_path, "version": version}

    def generate_policy_yaml(self, policy_config: dict) -> str:
        """Convert a SAGE task policy config dict to OpenShell policy YAML string."""
        policy = {"version": 1}
        if "filesystem_policy" in policy_config:
            policy["filesystem_policy"] = policy_config["filesystem_policy"]
        if "network_policies" in policy_config:
            policy["network_policies"] = policy_config["network_policies"]
        if "process" in policy_config:
            policy["process"] = policy_config["process"]
        else:
            policy["process"] = {"run_as_user": "sandbox", "run_as_group": "sandbox"}
        if "landlock" in policy_config:
            policy["landlock"] = policy_config["landlock"]
        return yaml.dump(policy, default_flow_style=False, sort_keys=False)

    @contextmanager
    def sandbox(self, name: str, policy: dict = None):
        """
        Context manager that creates an OpenShell sandbox, applies policy,
        and yields a SandboxHandle. Destroys sandbox on exit.

        If OpenShell is unavailable, yields None (caller must handle).
        """
        if not self._available:
            self.logger.warning("OpenShell unavailable — yielding None sandbox for %s", name)
            yield None
            return

        # Sanitise sandbox name (alphanumeric + dashes only)
        safe_name = "sage-" + "".join(c if c.isalnum() or c == "-" else "-" for c in name)[:32]
        policy_file = None
        ssh_config_file = None

        try:
            # 1. Create sandbox (--keep keeps it alive after initial command)
            create_cmd = [
                self._openshell_path, "sandbox", "create",
                "--name", safe_name,
                "--keep",
                "--no-auto-providers",
                "--no-tty",
                "--", "echo", "sage-sandbox-ready",
            ]
            self.logger.info("Creating sandbox: %s", safe_name)
            result = subprocess.run(create_cmd, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                raise RuntimeError(f"Sandbox create failed: {result.stderr}")

            # 2. Apply policy if provided
            if policy:
                policy_yaml = self.generate_policy_yaml(policy)
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".yaml", delete=False, prefix="sage-policy-"
                ) as f:
                    f.write(policy_yaml)
                    policy_file = f.name

                self.logger.info("Applying policy to sandbox: %s", safe_name)
                policy_result = subprocess.run(
                    [self._openshell_path, "policy", "set", safe_name,
                     "--policy", policy_file, "--wait"],
                    capture_output=True, text=True, timeout=30,
                )
                if policy_result.returncode != 0:
                    self.logger.warning("Policy apply failed (non-fatal): %s", policy_result.stderr)

            # 3. Get SSH config
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".conf", delete=False, prefix="sage-ssh-"
            ) as f:
                ssh_config_file = f.name

            ssh_config_result = subprocess.run(
                [self._openshell_path, "sandbox", "ssh-config", safe_name],
                capture_output=True, text=True, timeout=15,
            )
            if ssh_config_result.returncode != 0:
                raise RuntimeError(f"SSH config failed: {ssh_config_result.stderr}")

            with open(ssh_config_file, "w") as f:
                f.write(ssh_config_result.stdout)

            yield SandboxHandle(name=safe_name, ssh_config_path=ssh_config_file)

        except Exception as exc:
            self.logger.error("Sandbox error for %s: %s", safe_name, exc)
            yield None

        finally:
            # Always cleanup
            for tmp in filter(None, [policy_file, ssh_config_file]):
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
            try:
                subprocess.run(
                    [self._openshell_path, "sandbox", "delete", safe_name],
                    capture_output=True, timeout=30,
                )
                self.logger.info("Sandbox deleted: %s", safe_name)
            except Exception as _del_exc:
                self.logger.warning("Sandbox delete failed: %s", _del_exc)


# Module-level singleton
_runner: Optional[OpenShellRunner] = None
_runner_lock = threading.Lock()


def get_openshell_runner() -> OpenShellRunner:
    global _runner
    if _runner is None:
        with _runner_lock:
            if _runner is None:
                _runner = OpenShellRunner()
    return _runner
