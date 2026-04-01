# Risk Management Plan
**Document ID:** RMP-001-v2.1
**Product:** SAGE Wearable Fall Detection System (nRF5340)
**Standard:** ISO 14971:2019
**Date:** 2026-03-27
**Status:** APPROVED

---

## 1. Scope
This Risk Management Plan governs all risk management activities for the SAGE wearable fall detection device from concept through post-market surveillance. It applies to hardware (PCB Rev wearable_nrf5340_v1), embedded firmware (build_9f301b21), TLS communication stack, and cloud alert pipeline.

## 2. Risk Management Team
| Role | Name | Signature | Date |
|---|---|---|---|
| Safety Engineer | J. Hartmann | *Signed* | 2026-03-27 |
| QA Director | M. Okonkwo | *Signed* | 2026-03-27 |
| Firmware Lead | R. Patel | *Signed* | 2026-03-27 |
| Clinical Affairs | Dr. S. Lim | *Signed* | 2026-03-27 |

## 3. Risk Acceptability Criteria
### Severity Scale (S)
| Level | Score | Definition |
|---|---|---|
| Negligible | 1 | No injury, inconvenience only |
| Minor | 2 | Minor injury, no medical intervention |
| Moderate | 3 | Injury requiring medical intervention |
| Serious | 4 | Permanent impairment or life-threatening |
| Catastrophic | 5 | Death |

### Occurrence Scale (O)
| Level | Score | Probability |
|---|---|---|
| Remote | 1 | < 1 in 1,000,000 |
| Unlikely | 2 | 1 in 100,000 – 1,000,000 |
| Occasional | 3 | 1 in 10,000 – 100,000 |
| Probable | 4 | 1 in 100 – 10,000 |
| Frequent | 5 | > 1 in 100 |

### Detection Scale (D)
| Level | Score | Definition |
|---|---|---|
| Almost Certain | 1 | Error always detected before patient impact |
| High | 2 | High likelihood of detection |
| Moderate | 3 | Moderate detection capability |
| Low | 4 | Low detection capability |
| Almost Impossible | 5 | Undetectable |

### Risk Priority Number (RPN)
**RPN = S × O × D**

| RPN Range | Risk Level | Action Required |
|---|---|---|
| 1–20 | Acceptable | Monitor |
| 21–50 | ALARP | Reduce if practicable |
| 51–100 | Unacceptable | Must reduce |
| >100 | Critical | Halt until mitigated |

## 4. Risk Control Strategy
Priority order per ISO 14971 Clause 6.2:
1. Inherent safety by design
2. Protective measures
3. Information for safety
