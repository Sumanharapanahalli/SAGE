"""
SAGE Framework — Exception Hierarchy
=====================================

Structured exception types for clear error handling across the framework.
Replaces generic ``except Exception`` with domain-specific types that
callers can catch and handle appropriately.
"""


class SAGEError(Exception):
    """Base exception for all SAGE framework errors."""


# ── LLM / Provider errors ────────────────────────────────────────────

class LLMProviderError(SAGEError):
    """An LLM provider returned an error or is unreachable."""


class LLMTimeoutError(LLMProviderError):
    """LLM inference exceeded the configured timeout."""


class LLMRateLimitError(LLMProviderError):
    """LLM provider rate limit exceeded."""


# ── Proposal / Approval errors ───────────────────────────────────────

class ProposalError(SAGEError):
    """Base for proposal-related errors."""


class ProposalNotFoundError(ProposalError):
    """Referenced proposal does not exist."""


class ProposalExpiredError(ProposalError):
    """Proposal has expired and can no longer be approved."""


# ── Runner / Execution errors ────────────────────────────────────────

class RunnerError(SAGEError):
    """Base for runner execution errors."""


class RunnerUnavailableError(RunnerError):
    """Requested runner is not available (missing toolchain, container, etc.)."""


class RunnerTimeoutError(RunnerError):
    """Runner execution exceeded the configured timeout."""


class SandboxError(RunnerError):
    """Sandbox environment setup or teardown failed."""


# ── Configuration errors ─────────────────────────────────────────────

class ConfigError(SAGEError):
    """Invalid or missing configuration."""


class SolutionNotFoundError(ConfigError):
    """Referenced solution does not exist."""


class YAMLValidationError(ConfigError):
    """YAML configuration failed schema validation."""
