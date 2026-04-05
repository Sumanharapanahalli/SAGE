"""
SAGE Consensus Engine — Multi-Agent Voting & Debate
=====================================================

For critical decisions, multiple agents independently evaluate and vote.
Supports majority voting, weighted voting (by agent confidence), and
disagreement detection for human escalation.

Pattern: Constitutional AI, Multi-Agent Debate (Du et al.)
"""

import logging
import statistics
import threading
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class Vote:
    """A single agent's vote."""
    voter: str             # agent role
    decision: str          # the vote value (e.g., "approve", "reject", "abstain")
    confidence: float = 0.5
    reasoning: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "voter": self.voter,
            "decision": self.decision,
            "confidence": self.confidence,
            "reasoning": self.reasoning[:200],
            "timestamp": self.timestamp,
        }


@dataclass
class ConsensusResult:
    """Result of a consensus round."""
    consensus_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    question: str = ""
    votes: list = field(default_factory=list)
    decision: str = ""           # majority decision
    agreement_ratio: float = 0.0  # 0-1, how much agents agreed
    needs_human: bool = False     # escalate if disagreement too high
    method: str = "majority"      # majority | weighted | unanimous
    started_at: str = ""
    completed_at: str = ""

    def to_dict(self) -> dict:
        return {
            "consensus_id": self.consensus_id,
            "question": self.question[:200],
            "votes": [v.to_dict() if hasattr(v, 'to_dict') else v
                      for v in self.votes],
            "decision": self.decision,
            "agreement_ratio": self.agreement_ratio,
            "needs_human": self.needs_human,
            "method": self.method,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


class ConsensusEngine:
    """
    Multi-agent voting for critical decisions.

    Usage:
        engine = ConsensusEngine()
        result = engine.vote(
            question="Should we approve this code change?",
            voters=["security_auditor", "qa_engineer", "architect"],
            evaluator=lambda role, question: {decision: str, confidence: float, reasoning: str},
        )
    """

    def __init__(
        self,
        disagreement_threshold: float = 0.5,
        min_confidence: float = 0.3,
    ):
        self._disagreement_threshold = disagreement_threshold
        self._min_confidence = min_confidence
        self._results: dict[str, ConsensusResult] = {}
        self._lock = threading.Lock()

    def vote(
        self,
        question: str,
        voters: list[str],
        evaluator: Callable[[str, str], dict],
        context: str = "",
        method: str = "majority",
    ) -> ConsensusResult:
        """
        Run a consensus round.

        Args:
            question: The decision to vote on
            voters: List of agent roles to vote
            evaluator: Callable(role, question_with_context) → {decision, confidence, reasoning}
            context: Additional context for voters
            method: "majority" | "weighted" | "unanimous"

        Returns:
            ConsensusResult with decision, agreement ratio, and escalation flag
        """
        result = ConsensusResult(
            question=question,
            method=method,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        self._emit("consensus.started", {
            "consensus_id": result.consensus_id,
            "question": question[:100],
            "voter_count": len(voters),
            "method": method,
        })

        full_question = f"{question}\n\nContext: {context}" if context else question

        # Collect votes
        votes: list[Vote] = []
        for role in voters:
            try:
                response = evaluator(role, full_question)
                vote = Vote(
                    voter=role,
                    decision=str(response.get("decision", "abstain")),
                    confidence=float(response.get("confidence", 0.5)),
                    reasoning=str(response.get("reasoning", "")),
                )
            except Exception as exc:
                vote = Vote(
                    voter=role,
                    decision="abstain",
                    confidence=0.0,
                    reasoning=f"Error: {exc}",
                )
                logger.warning("Voter %s failed: %s", role, exc)

            votes.append(vote)

            self._emit("consensus.vote", {
                "consensus_id": result.consensus_id,
                "voter": role,
                "decision": vote.decision,
                "confidence": vote.confidence,
            })

        result.votes = votes

        # Resolve
        if method == "weighted":
            result.decision = self._resolve_weighted(votes)
        elif method == "unanimous":
            result.decision = self._resolve_unanimous(votes)
        else:
            result.decision = self._resolve_majority(votes)

        # Calculate agreement
        result.agreement_ratio = self._calc_agreement(votes, result.decision)
        result.needs_human = result.agreement_ratio < self._disagreement_threshold

        result.completed_at = datetime.now(timezone.utc).isoformat()

        self._emit("consensus.resolved", {
            "consensus_id": result.consensus_id,
            "decision": result.decision,
            "agreement_ratio": result.agreement_ratio,
            "needs_human": result.needs_human,
        })

        with self._lock:
            self._results[result.consensus_id] = result

        return result

    def _resolve_majority(self, votes: list[Vote]) -> str:
        """Simple majority voting (most common non-abstain decision)."""
        decisions = [v.decision for v in votes if v.decision != "abstain"]
        if not decisions:
            return "abstain"
        counter = Counter(decisions)
        return counter.most_common(1)[0][0]

    def _resolve_weighted(self, votes: list[Vote]) -> str:
        """Confidence-weighted voting."""
        scores: dict[str, float] = {}
        for v in votes:
            if v.decision == "abstain":
                continue
            scores[v.decision] = scores.get(v.decision, 0) + v.confidence
        if not scores:
            return "abstain"
        return max(scores, key=scores.get)

    def _resolve_unanimous(self, votes: list[Vote]) -> str:
        """Unanimous voting — all must agree or decision is 'no_consensus'."""
        decisions = set(v.decision for v in votes if v.decision != "abstain")
        if len(decisions) == 1:
            return decisions.pop()
        return "no_consensus"

    @staticmethod
    def _calc_agreement(votes: list[Vote], decision: str) -> float:
        """Calculate ratio of voters who agree with the decision."""
        non_abstain = [v for v in votes if v.decision != "abstain"]
        if not non_abstain:
            return 0.0
        agreeing = sum(1 for v in non_abstain if v.decision == decision)
        return round(agreeing / len(non_abstain), 3)

    def get_result(self, consensus_id: str) -> Optional[dict]:
        with self._lock:
            r = self._results.get(consensus_id)
        return r.to_dict() if r else None

    def list_results(self, limit: int = 20) -> list[dict]:
        with self._lock:
            items = sorted(
                self._results.values(),
                key=lambda r: r.started_at,
                reverse=True,
            )[:limit]
        return [r.to_dict() for r in items]

    def get_stats(self) -> dict:
        with self._lock:
            results = list(self._results.values())
        if not results:
            return {"total_rounds": 0, "avg_agreement": 0,
                    "escalation_rate": 0, "unanimous_rate": 0}
        escalated = sum(1 for r in results if r.needs_human)
        unanimous = sum(1 for r in results if r.agreement_ratio == 1.0)
        return {
            "total_rounds": len(results),
            "avg_agreement": round(
                sum(r.agreement_ratio for r in results) / len(results), 3
            ),
            "escalation_rate": round(escalated / len(results), 3),
            "unanimous_rate": round(unanimous / len(results), 3),
        }

    @staticmethod
    def _emit(event_type: str, data: dict) -> None:
        try:
            from src.core.event_bus import get_event_bus
            get_event_bus().publish(event_type, data, source="consensus_engine")
        except Exception:
            pass


# Singleton
_consensus: Optional[ConsensusEngine] = None
_ce_lock = threading.Lock()


def get_consensus_engine() -> ConsensusEngine:
    global _consensus
    if _consensus is None:
        with _ce_lock:
            if _consensus is None:
                _consensus = ConsensusEngine()
    return _consensus
