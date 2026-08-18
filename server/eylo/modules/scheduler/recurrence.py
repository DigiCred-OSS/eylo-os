"""Validate recurrence policy and resolve a bounded set of due occurrences."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dateutil.rrule import rrulestr

from eylo.common.contracts.scheduler import (
    DueResolution,
    InvalidRecurrence,
    MisfirePolicy,
    Recurrence,
)

# A schedule that fires more often than this is a loop with extra steps, and
# the platform would spend itself delivering it. Sub-minute work belongs on the
# task queue directly, not on a schedule.
MIN_INTERVAL_SECONDS = 60

# How many occurrences one resolution will ever return, whatever the policy.
# A `fire_all` schedule idle for a year must not produce a year of occurrences
# in one batch — that is an outage turning into a second outage.
MAX_OCCURRENCES_PER_RESOLUTION = 100

# How far `skipped` is counted before it becomes a floor rather than a total.
# Counting is enumeration, and a minutely schedule idle for a year is half a
# million occurrences nobody needs the exact count of — "at least 1000 missed"
# tells an operator everything the precise number would.
MAX_SKIPPED_COUNTED = 1000

# Guards the walk that finds a valid local instant across a DST gap. Gaps are
# an hour; this is generous and bounded rather than a `while True`.
_MAX_GAP_MINUTES = 180

_DTSTART_IN_RULE = re.compile(r"\bDTSTART\b", re.IGNORECASE)
_SUB_MINUTE = re.compile(r"FREQ=SECONDLY", re.IGNORECASE)


def validate(recurrence: Recurrence) -> None:
    """Refuse a recurrence that cannot produce a usable schedule.

    Called on the way in, so an operator learns at the moment they can fix it
    rather than from a schedule that never fires.
    """
    try:
        zone = ZoneInfo(recurrence.timezone)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise InvalidRecurrence(
            f"'{recurrence.timezone}' is not an IANA timezone name "
            "(for example 'Europe/Berlin' or 'Asia/Kolkata')."
        ) from error

    if recurrence.starts_at.tzinfo is None:
        raise InvalidRecurrence("starts_at must be timezone-aware.")
    if recurrence.ends_at and recurrence.ends_at <= recurrence.starts_at:
        raise InvalidRecurrence("ends_at must be after starts_at.")

    if recurrence.rule is None:
        return

    if _DTSTART_IN_RULE.search(recurrence.rule):
        # Two anchors for one schedule, and nothing says which wins.
        raise InvalidRecurrence(
            "The rule must not contain DTSTART; the schedule's starts_at is its anchor."
        )
    if _SUB_MINUTE.search(recurrence.rule):
        raise InvalidRecurrence(
            "FREQ=SECONDLY is not schedulable here; the minimum interval is "
            f"{MIN_INTERVAL_SECONDS} seconds."
        )

    local_start = recurrence.starts_at.astimezone(zone).replace(tzinfo=None)
    try:
        rule = rrulestr(recurrence.rule, dtstart=local_start)
    except Exception as error:  # noqa: BLE001 - dateutil raises several types
        raise InvalidRecurrence("RRULE is invalid.") from error

    # Two occurrences is enough to measure the interval, and cheap even for a
    # rule with a distant first occurrence.
    sample = list(rule[:2])
    if len(sample) == 2:
        gap = (sample[1] - sample[0]).total_seconds()
        if gap < MIN_INTERVAL_SECONDS:
            raise InvalidRecurrence(
                f"That rule fires every {int(gap)}s; the minimum interval is "
                f"{MIN_INTERVAL_SECONDS}s."
            )


def _to_utc(local: datetime, zone: ZoneInfo) -> datetime:
    """A naive local wall-clock time as a UTC instant.

    Handles both directions of the DST discontinuity — see the module
    docstring for why each choice is the way it is.
    """
    candidate = local.replace(tzinfo=zone)

    # Spring forward: this wall-clock time does not exist. Python still yields
    # a datetime, but round-tripping it through UTC lands somewhere else, which
    # is how the gap is detected without hard-coding transition rules.
    if (
        candidate.astimezone(ZoneInfo("UTC")).astimezone(zone).replace(tzinfo=None)
        != local
    ):
        probe = local
        for _ in range(_MAX_GAP_MINUTES):
            probe += timedelta(minutes=1)
            shifted = probe.replace(tzinfo=zone)
            if (
                shifted.astimezone(ZoneInfo("UTC"))
                .astimezone(zone)
                .replace(tzinfo=None)
                == probe
            ):
                return shifted.astimezone(ZoneInfo("UTC"))
        # No valid instant within the window. Returning the original keeps the
        # schedule alive rather than dropping it; a zone with a gap longer than
        # three hours does not exist today.
        return candidate.astimezone(ZoneInfo("UTC"))

    # Fall back: this wall-clock time happens twice. `fold=0` is the earlier
    # one, which is Python's default and the one we want — fire once, early.
    return candidate.astimezone(ZoneInfo("UTC"))


def occurrences_between(
    recurrence: Recurrence, *, after: datetime, until: datetime, limit: int = 1000
) -> list[datetime]:
    """Every occurrence in (after, until], as UTC instants.

    Exclusive of `after` so a caller can pass the last fired time without
    getting it back, inclusive of `until` so an occurrence landing exactly now
    is due now rather than next tick.
    """
    zone = ZoneInfo(recurrence.timezone)

    if recurrence.rule is None:
        start = recurrence.starts_at
        return [start] if after < start <= until else []

    local_start = recurrence.starts_at.astimezone(zone).replace(tzinfo=None)
    rule = rrulestr(recurrence.rule, dtstart=local_start)

    # Widened by a day on each side before converting: an occurrence's UTC
    # instant can fall outside the window its local time suggests, by up to the
    # zone's offset. Filtering happens after conversion, in UTC, where the
    # comparison is unambiguous.
    local_after = (after.astimezone(zone) - timedelta(days=1)).replace(tzinfo=None)
    local_until = (until.astimezone(zone) + timedelta(days=1)).replace(tzinfo=None)

    found: list[datetime] = []
    for local in rule.between(local_after, local_until, inc=True):
        moment = _to_utc(local, zone)
        if after < moment <= until:
            found.append(moment)
        if len(found) >= limit:
            break

    if recurrence.ends_at:
        found = [moment for moment in found if moment <= recurrence.ends_at]
    return found


def next_occurrence(recurrence: Recurrence, *, after: datetime) -> datetime | None:
    """The first occurrence strictly after `after`, or None if there is none."""
    zone = ZoneInfo(recurrence.timezone)

    if recurrence.rule is None:
        start = recurrence.starts_at
        return start if start > after else None

    local_start = recurrence.starts_at.astimezone(zone).replace(tzinfo=None)
    rule = rrulestr(recurrence.rule, dtstart=local_start)

    # A day back, for the same offset reason as above: the occurrence whose
    # local time precedes `after` may still be a UTC instant that follows it.
    probe = (after.astimezone(zone) - timedelta(days=1)).replace(tzinfo=None)
    for local in rule.xafter(probe, count=64, inc=True):
        moment = _to_utc(local, zone)
        if moment > after:
            if recurrence.ends_at and moment > recurrence.ends_at:
                return None
            return moment
    return None


def latest_occurrence(recurrence: Recurrence, *, at: datetime) -> datetime | None:
    """The last occurrence at or before `at`, or None if there is none.

    Looked up backwards rather than taken from the end of a forward
    enumeration. That distinction is a bug this had: a forward walk has to be
    bounded, and the last element of a *bounded* walk is the oldest occurrence
    in the window, not the newest. Coalescing then fired a months-old
    occurrence and called it the current one — the exact opposite of what the
    policy promises.
    """
    zone = ZoneInfo(recurrence.timezone)

    if recurrence.rule is None:
        start = recurrence.starts_at
        return start if start <= at else None

    local_start = recurrence.starts_at.astimezone(zone).replace(tzinfo=None)
    rule = rrulestr(recurrence.rule, dtstart=local_start)

    # A day forward, because an occurrence whose local time follows `at` can
    # still be a UTC instant that precedes it. Walking back from there, the
    # first candidate that converts to <= at is the answer.
    probe = (at.astimezone(zone) + timedelta(days=1)).replace(tzinfo=None)
    for _ in range(64):
        local = rule.before(probe, inc=True)
        if local is None:
            return None
        moment = _to_utc(local, zone)
        if moment <= at:
            if recurrence.ends_at and moment > recurrence.ends_at:
                # Past its end: clamp by asking again from the boundary.
                return latest_occurrence(recurrence, at=recurrence.ends_at)
            return moment
        probe = local - timedelta(microseconds=1)
    return None


def resolve_due(
    recurrence: Recurrence,
    *,
    last_fired_at: datetime | None,
    now: datetime,
    policy: MisfirePolicy = MisfirePolicy.COALESCE,
) -> DueResolution:
    """What this schedule owes at `now`, and when it is next owed.

    The whole misfire question lives here. Everything between the last fire and
    now came due while nothing was running; the policy decides what that means.

    `COALESCE` fires the **most recent** missed occurrence and counts the rest
    as skipped — the current state is what a reminder or a check-in is about,
    and the older ones are superseded by it. `FIRE_ALL` returns them all, for
    work where each occurrence is its own artifact, bounded so an outage cannot
    turn into a thundering herd.
    """
    # A schedule that has never fired owes nothing from before it existed.
    since = last_fired_at or (recurrence.starts_at - timedelta(microseconds=1))
    upcoming = next_occurrence(recurrence, after=now)

    if policy is MisfirePolicy.COALESCE:
        # The target is looked up backwards, so it is the *most recent* owed
        # occurrence however long the outage was. Only the count is bounded.
        latest = latest_occurrence(recurrence, at=now)
        if latest is None or latest <= since:
            return DueResolution(fire_at=[], skipped=0, next_at=upcoming)
        missed = occurrences_between(
            recurrence,
            after=since,
            until=latest - timedelta(microseconds=1),
            limit=MAX_SKIPPED_COUNTED,
        )
        return DueResolution(fire_at=[latest], skipped=len(missed), next_at=upcoming)

    due = occurrences_between(
        recurrence, after=since, until=now, limit=MAX_OCCURRENCES_PER_RESOLUTION
    )
    if not due:
        return DueResolution(fire_at=[], skipped=0, next_at=upcoming)

    # Everything past the batch limit is counted, not silently dropped. The
    # count itself is bounded — see MAX_SKIPPED_COUNTED.
    skipped = 0
    if len(due) >= MAX_OCCURRENCES_PER_RESOLUTION:
        overflow = occurrences_between(
            recurrence, after=due[-1], until=now, limit=MAX_SKIPPED_COUNTED
        )
        skipped = len(overflow)
    return DueResolution(fire_at=due, skipped=skipped, next_at=upcoming)
