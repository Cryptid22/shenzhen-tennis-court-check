from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from typing import Iterable, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo


SHANGHAI = ZoneInfo("Asia/Shanghai")
WEEKDAYS_ZH = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")


class VenueError(RuntimeError):
    """A venue could not be queried reliably."""


class AuthenticationError(VenueError):
    """The venue credential is missing or expired."""


@dataclass(frozen=True)
class Slot:
    venue_label: str
    court: str
    date: date
    start: time
    end: time
    available: bool


def parse_hhmm(value: str) -> time:
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError as exc:
        raise ValueError(f"无效时间 {value!r}，应为 HH:MM") from exc


def default_query_date(now: Optional[datetime] = None) -> date:
    current = now.astimezone(SHANGHAI) if now else datetime.now(SHANGHAI)
    candidate = current.date()
    if current.time() >= time(22, 0):
        candidate += timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate


def overlaps(slot: Slot, start: time, end: time) -> bool:
    return slot.start < end and slot.end > start


def select_available(slots: Iterable[Slot], start: time, end: time) -> List[Slot]:
    return [slot for slot in slots if slot.available and overlaps(slot, start, end)]


def merge_adjacent(slots: Iterable[Slot]) -> List[Slot]:
    """Merge adjacent slots while preserving venue/court discovery order."""
    groups: "OrderedDict[Tuple[str, str, date], List[Slot]]" = OrderedDict()
    for slot in slots:
        groups.setdefault((slot.venue_label, slot.court, slot.date), []).append(slot)

    merged: List[Slot] = []
    for group in groups.values():
        ordered = sorted(group, key=lambda item: (item.start, item.end))
        current = ordered[0]
        for following in ordered[1:]:
            if current.available == following.available and current.end == following.start:
                current = replace(current, end=following.end)
            else:
                merged.append(current)
                current = following
        merged.append(current)
    return merged


def format_slot(slot: Slot) -> str:
    weekday = WEEKDAYS_ZH[slot.date.weekday()]
    return (
        f"【{slot.venue_label}{slot.court}】{weekday}({slot.date:%m-%d})空场: "
        f"{slot.start:%H:%M}-{slot.end:%H:%M}"
    )

