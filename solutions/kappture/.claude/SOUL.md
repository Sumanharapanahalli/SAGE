# SOUL.md — kappture solution

## What This Solution Is

Kappture is a human tracking software product — people counting, zone analytics,
dwell time measurement — used in retail, transport, and public spaces.

## Domain Context

- **Computer vision:** RTSP camera streams, multi-object tracking, anonymisation
- **GDPR compliance:** All person data must be anonymised at the edge; no raw images stored
- **Infrastructure:** Prometheus metrics, Grafana dashboards, edge compute deployment
- **Clients:** B2B — retailers and venue operators expecting high uptime SLAs

## Key Concerns

- GDPR is non-negotiable: any code change that could re-enable face storage or
  biometric capture must be flagged RED and blocked
- Tracking accuracy regressions affect SLA contractual obligations — monitor closely
- Edge devices have limited compute; MR reviews should flag memory/CPU regressions

## Running

```bash
make run PROJECT=kappture
make ui
```
