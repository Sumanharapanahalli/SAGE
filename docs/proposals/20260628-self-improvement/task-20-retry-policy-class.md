# Task 20: Retry policy class

**Category:** architecture  
**Score:** 0.0/10  
**Converged:** False  
**Iterations:** 3  
**Elapsed:** 25s  

---

## Task

Extract the ad-hoc retry logic scattered across llm_gateway.py into a src/modules/retry_policy.py module. Define a RetryPolicy dataclass: max_attempts, base_delay_s, max_delay_s, jitter (bool). Add a retry() context manager / decorator that implements exponential backoff with optional jitter. Replace all manual retry loops in llm_gateway.py with RetryPolicy.

## Criteria

retry_policy.py exists with RetryPolicy dataclass and retry mechanism; exponential backoff formula is correct (base * 2^attempt); jitter adds 0-25% random variance when enabled; llm_gateway.py has no manual retry loops; existing LLM tests pass.

## Proposal (submit to HITL approval gate)

Error from Claude Code CLI: Unknown error

---

## Iteration History

**Iter 1** — score 0.0 pass=False  
Feedback: (no parseable feedback)  

**Iter 2** — score 0.0 pass=False  
Feedback: (no parseable feedback)  

**Iter 3** — score 0.0 pass=False  
Feedback: (no parseable feedback)  

