"""
Streak Engine — computes meditation streaks with full timezone + DST awareness.
A "day" is always resolved in the user's local timezone so that DST transitions
(spring-forward / fall-back) and UTC-offset midnight boundaries are handled
correctly.
"""
from __future__ import annotations

from datetime import datetime, date, timedelta
from typing import List, Optional

import pytz


class StreakEngineError(Exception):
    """Raised for configuration errors (e.g. unknown timezone)."""


class StreakEngine:
    """
    Computes streak data from a list of UTC session timestamps.

    Args:
        timezone: IANA timezone name, e.g. "US/Eastern", "Asia/Kolkata", "UTC".
    """

    def __init__(self, timezone: str = "UTC") -> None:
        try:
            self.tz = pytz.timezone(timezone)
        except pytz.UnknownTimeZoneError as exc:
            raise StreakEngineError(f"Unknown timezone: {timezone!r}") from exc

    def compute(
        self,
        session_timestamps: List[str],
        reference_date: Optional[date] = None,
    ) -> dict:
        """
        Compute streak data.

        Args:
            session_timestamps: ISO-8601 UTC timestamps of completed sessions.
                Accepts both Z suffix and +00:00 offset. Timezone-naive strings
                are treated as UTC.
            reference_date: Override "today" for deterministic tests.
                Defaults to datetime.now(tz).date().

        Returns:
            dict with keys:
                currentStreak  — days in the active trailing run (0 if broken)
                longestStreak  — days in the all-time best run
                totalSessions  — raw count of timestamps (not de-duplicated)
                completedDays  — sorted list of unique local-date strings
        """
        total = len(session_timestamps)

        if not session_timestamps:
            return {
                "currentStreak": 0,
                "longestStreak": 0,
                "totalSessions": 0,
                "completedDays": [],
            }

        # Multiple sessions on the same local day count once
        local_dates: List[date] = sorted(
            {self._to_local_date(ts) for ts in session_timestamps}
        )

        if reference_date is None:
            reference_date = datetime.now(self.tz).date()
        yesterday = reference_date - timedelta(days=1)

        longest = self._longest_streak(local_dates)

        # Current streak is only "active" when the last session was today/yesterday
        current = 0
        if local_dates[-1] in (reference_date, yesterday):
            current = self._trailing_streak(local_dates)

        return {
            "currentStreak": current,
            "longestStreak": longest,
            "totalSessions": total,
            "completedDays": [d.isoformat() for d in local_dates],
        }

    def is_streak_active(self, completed_days: List[str]) -> bool:
        """Return True if the last session was today or yesterday in user's TZ."""
        if not completed_days:
            return False
        today = datetime.now(self.tz).date()
        yesterday = today - timedelta(days=1)
        last = date.fromisoformat(completed_days[-1])
        return last in (today, yesterday)

    # ------------------------------------------------------------------
    # private helpers
    # ------------------------------------------------------------------

    def _to_local_date(self, iso_timestamp: str) -> date:
        """Convert an ISO UTC timestamp to a date in self.tz."""
        ts = iso_timestamp.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = pytz.utc.localize(dt)
        return dt.astimezone(self.tz).date()

    @staticmethod
    def _longest_streak(sorted_dates: List[date]) -> int:
        if not sorted_dates:
            return 0
        best = streak = 1
        for i in range(1, len(sorted_dates)):
            if (sorted_dates[i] - sorted_dates[i - 1]).days == 1:
                streak += 1
                best = max(best, streak)
            else:
                streak = 1
        return best

    @staticmethod
    def _trailing_streak(sorted_dates: List[date]) -> int:
        """Length of the consecutive-day run ending at sorted_dates[-1]."""
        if not sorted_dates:
            return 0
        streak = 1
        for i in range(len(sorted_dates) - 1, 0, -1):
            if (sorted_dates[i] - sorted_dates[i - 1]).days == 1:
                streak += 1
            else:
                break
        return streak
