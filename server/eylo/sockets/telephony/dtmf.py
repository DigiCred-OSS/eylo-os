"""Inbound DTMF collection helpers for telephony media streams."""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(frozen=True)
class DTMFCollectionResult:
    """Completed DTMF sequence ready for downstream processing."""

    digits: str
    completed_by: str


class DTMFCollector:
    """Collect DTMF digits until termination, digit limit, or timeout."""

    def __init__(
        self,
        *,
        digit_limit: int = 16,
        termination_key: str = "#",
        timeout_ms: int = 5000,
    ) -> None:
        self.digit_limit = digit_limit
        self.termination_key = termination_key
        self.timeout_ms = timeout_ms
        self._digits: list[str] = []
        self._last_digit_at: float | None = None

    def collect(self, digits: str) -> DTMFCollectionResult | None:
        """Add provider digits and return a completed sequence when ready."""
        now = time.monotonic() * 1000
        if (
            self._last_digit_at is not None
            and now - self._last_digit_at > self.timeout_ms
            and self._digits
        ):
            result = self._complete("timeout")
            self._append_digits(digits, now)
            return result

        self._append_digits(digits, now)
        if self.termination_key and self.termination_key in self._digits:
            return self._complete("termination_key")
        if len(self._digits) >= self.digit_limit:
            return self._complete("digit_limit")
        return None

    def flush(self) -> DTMFCollectionResult | None:
        """Return the current buffered digits, if any."""
        if not self._digits:
            return None
        return self._complete("flush")

    def _append_digits(self, digits: str, now: float) -> None:
        for digit in digits:
            if digit in "0123456789*#":
                self._digits.append(digit)
                self._last_digit_at = now

    def _complete(self, completed_by: str) -> DTMFCollectionResult:
        digits = "".join(d for d in self._digits if d != self.termination_key)
        self._digits.clear()
        self._last_digit_at = None
        return DTMFCollectionResult(digits=digits, completed_by=completed_by)
