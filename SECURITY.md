# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 2.x     | Yes       |
| 1.x     | Security fixes only |
| < 1.0   | No        |

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Instead, please email: **sage-security@proton.me**

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

## Response Timeline

| Stage | Timeline |
|-------|----------|
| Acknowledgment | Within 48 hours |
| Initial assessment | Within 5 business days |
| Fix development | Within 30 days for critical, 90 days for others |
| Public disclosure | After fix is released |

## PII Handling

SAGE processes data through LLM providers. The framework:
- Does **not** store raw API keys in logs or audit trails
- Supports PII detection via Presidio (configurable in `config.yaml`)
- Isolates solution data in per-solution `.sage/` directories
- Never transmits solution data to the SAGE framework repository

## Scope

This policy covers the SAGE framework (`src/`, `web/`, `config/`). For vulnerabilities in specific solution configurations, contact the solution maintainer directly.
