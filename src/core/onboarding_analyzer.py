"""
SAGE[ai] - Onboarding Analyzer (Path A)
=========================================
Analyzes an existing project (GitHub URL, local path, or pasted text)
to auto-detect stack, CI/CD, and suggest SAGE configuration.
"""

import logging
import os
import re

logger = logging.getLogger("OnboardingAnalyzer")


class ProjectSignals:
    def __init__(self):
        self.detected_stack: list = []
        self.detected_ci: str = ""
        self.detected_integrations: list = []
        self.detected_domains: list = []
        self.compliance_hints: list = []
        self.suggested_task_types: list = []
        self.suggested_roles: list = []
        self.evidence: dict = {}

    def to_dict(self) -> dict:
        return {
            "detected_stack": self.detected_stack,
            "detected_ci": self.detected_ci,
            "detected_integrations": self.detected_integrations,
            "detected_domains": self.detected_domains,
            "compliance_hints": self.compliance_hints,
            "suggested_task_types": self.suggested_task_types,
            "suggested_roles": self.suggested_roles,
            "evidence": self.evidence,
        }


class OnboardingAnalyzer:
    """
    Analyzes project signals from text, local paths, or GitHub/GitLab URLs.
    Returns ProjectSignals used to auto-configure SAGE.
    """

    def analyze_text(self, text: str) -> ProjectSignals:
        """Analyze pasted text (README, package.json, etc.) for project signals."""
        signals = ProjectSignals()
        text_lower = text.lower()

        # Detect stack
        stack_patterns = [
            ("Flutter", ["flutter", "dart", "pubspec.yaml"]),
            ("React", ["react", "jsx", "next.js", "nextjs"]),
            ("Node.js", ["node.js", "nodejs", "express", "fastify", "npm"]),
            ("Python", ["python", "django", "fastapi", "flask", "uvicorn"]),
            ("Go", ["golang", "go.mod", "gin", "fiber"]),
            ("Rust", ["rust", "cargo.toml", "tokio"]),
            ("Java", ["java", "spring boot", "maven", "gradle"]),
            ("PostgreSQL", ["postgresql", "postgres", "pg"]),
            ("Docker", ["docker", "dockerfile", "docker-compose"]),
            ("Kubernetes", ["kubernetes", "k8s", "kubectl", "helm"]),
        ]
        for name, keywords in stack_patterns:
            if any(k in text_lower for k in keywords):
                signals.detected_stack.append(name)
                signals.evidence[name] = f"Detected '{keywords[0]}' in text"

        # Detect CI
        ci_patterns = [
            ("GitHub Actions", [".github/workflows", "github actions", "on: push", "on: pull_request"]),
            ("GitLab CI", [".gitlab-ci.yml", "gitlab-ci", "stages:", "- deploy"]),
            ("Jenkins", ["jenkinsfile", "jenkins"]),
            ("CircleCI", [".circleci", "circleci"]),
        ]
        for name, keywords in ci_patterns:
            if any(k in text_lower for k in keywords):
                signals.detected_ci = name
                signals.evidence["ci"] = f"Detected {name}"
                break

        # Detect integrations
        if any(k in text_lower for k in ["github.com", "github", "ghtoken"]):
            signals.detected_integrations.append("github")
        if any(k in text_lower for k in ["gitlab.com", "gitlab"]):
            signals.detected_integrations.append("gitlab")
        if "slack" in text_lower:
            signals.detected_integrations.append("slack")

        # Compliance hints
        if any(k in text_lower for k in ["hipaa", "health", "patient", "phi", "medical"]):
            signals.compliance_hints.append("HIPAA")
        if any(k in text_lower for k in ["iso 13485", "iec 62304", "medical device", "fda"]):
            signals.compliance_hints.extend(["ISO 13485", "IEC 62304"])
        if "soc 2" in text_lower:
            signals.compliance_hints.append("SOC 2")

        # Suggest task types based on stack/domain
        signals.suggested_task_types = ["ANALYZE_LOG", "PLAN_TASK"]
        if any(k in text_lower for k in ["pull request", "merge request", "pr", "mr", "code review"]):
            signals.suggested_task_types.extend(["REVIEW_MR", "CREATE_MR"])
        if any(k in text_lower for k in ["crash", "crashlytics", "sentry", "bugsnag"]):
            signals.suggested_task_types.append("ANALYZE_CRASH")
        if any(k in text_lower for k in ["ci", "pipeline", "workflow", "build"]):
            signals.suggested_task_types.append("ANALYZE_CI_FAILURE")

        # Deduplicate
        signals.suggested_task_types = list(dict.fromkeys(signals.suggested_task_types))
        signals.suggested_roles = ["analyst", "developer", "planner"]

        return signals

    def analyze_local_path(self, path: str) -> ProjectSignals:
        """Walk a local directory for key manifest and config files."""
        if not os.path.isdir(path):
            return ProjectSignals()

        # Collect key files (never read source code -- only manifests/configs)
        key_files = ["README.md", "README.rst", "package.json", "requirements.txt",
                     "pubspec.yaml", "Cargo.toml", "go.mod", "pom.xml",
                     ".github/workflows", ".gitlab-ci.yml", "docker-compose.yml"]

        collected_text = []
        for root, dirs, files in os.walk(path):
            # Skip common non-informative dirs
            dirs[:] = [d for d in dirs if d not in (".git", "node_modules", ".venv", "__pycache__", "dist", "build")]
            for fname in files:
                fpath = os.path.join(root, fname)
                rel = os.path.relpath(fpath, path)
                if any(rel == k or rel.startswith(k + os.sep) for k in key_files):
                    try:
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read(4000)  # read max 4KB per file
                        collected_text.append(content)
                    except Exception:
                        pass

        return self.analyze_text("\n".join(collected_text))

    def analyze_github_repo(self, url: str) -> ProjectSignals:
        """
        Fetch and analyze a public GitHub/GitLab repo's key files.
        Falls back to text analysis of URL if fetch fails.
        """
        signals = self.analyze_text(url)  # at minimum analyze URL string

        # Try to fetch README from GitHub API
        try:
            import urllib.request
            # Extract owner/repo from URL
            match = re.search(r"github\.com/([^/]+)/([^/\s?#]+)", url)
            if match:
                owner, repo = match.group(1), match.group(2).rstrip(".git")
                api_url = f"https://api.github.com/repos/{owner}/{repo}/readme"
                req = urllib.request.Request(
                    api_url,
                    headers={"User-Agent": "SAGE-Onboarding/1.0", "Accept": "application/vnd.github.raw"},
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    readme = resp.read(8000).decode("utf-8", errors="ignore")
                signals = self.analyze_text(readme + "\n" + url)
                signals.evidence["source"] = f"Fetched README from {owner}/{repo}"
        except Exception as e:
            logger.debug("GitHub fetch failed (non-fatal): %s", e)

        return signals
