# Security Policy

## Supported Versions

| Version | Supported |
|---|---|
| Latest `main` | Yes |
| Older releases | Best effort |

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Instead, please report security issues by emailing the maintainers directly or using GitHub's private vulnerability reporting feature:

1. Go to the repository's **Security** tab
2. Click **Report a vulnerability**
3. Provide a description of the issue, steps to reproduce, and potential impact

You should receive a response within 48 hours. We will work with you to understand the issue and coordinate a fix before any public disclosure.

## Security Considerations

SAGE is used in regulated industries (medical devices, automotive, avionics). Security is treated as a P0 concern:

- **Audit log integrity**: HMAC hash chain protects against log tampering (21 CFR Part 11)
- **No secrets in code**: All API keys and credentials must be provided via environment variables
- **HITL approval gate**: Agent proposals require human approval before execution
- **Data isolation**: Each solution gets its own `.sage/` directory; data never mixes between solutions
- **Dependency scanning**: Users should run `pip audit` and `npm audit` regularly

## Scope

The following are in scope for security reports:
- Authentication/authorization bypass
- SQL injection, XSS, CSRF, or command injection
- Sensitive data exposure (API keys, credentials, PII)
- Audit log tampering or bypass
- Approval gate bypass (agent executing without human approval)

The following are out of scope:
- Denial of service (SAGE is designed for local/private deployment)
- Issues in third-party dependencies (report upstream, but let us know)
- Social engineering attacks
