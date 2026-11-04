from __future__ import annotations

import json
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from .base import AuthenticationError, SHANGHAI, Slot, VenueError, parse_hhmm


BASE_URL = "https://gateway.gemdalesports.com"
RESERVE_PATH = "/inside-frontend/api/field/fieldReserve"
DETAIL_PATH = "/inside-frontend/api/gym/detail"


@dataclass(frozen=True)
class IngVenue:
    label: str
    gym_id: str


VENUES: Tuple[IngVenue, ...] = (
    IngVenue("深圳金海湾店", "1471031753752711169"),
    IngVenue("深圳金地花园店", "1479062575424475137"),
    IngVenue("深圳南山威新店", "1479063349546192897"),
)


class IngClient:
    def __init__(self, timeout: float = 10.0) -> None:
        self.timeout = timeout
        # This domestic API times out through the user's overseas Clash exit.
        # Deliberately bypass environment and macOS proxy settings.
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def fetch(self, venue: IngVenue, query_date: date) -> List[Slot]:
        detail = self._fetch_detail(venue)
        self.ensure_date_released(venue, query_date, detail)
        query = urllib.parse.urlencode(
            {
                "gymId": venue.gym_id,
                "sportsType": "1",
                "reserveDate": query_date.isoformat(),
            }
        )
        url = f"{BASE_URL}{RESERVE_PATH}?{query}"
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "User-Agent": "tennis-check/0.1 (read-only availability query)",
            },
            method="GET",
        )

        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise AuthenticationError("登录已过期") from exc
            raise VenueError(f"HTTP {exc.code}") from exc
        except (urllib.error.URLError, socket.timeout, TimeoutError, ssl.SSLError) as exc:
            reason = getattr(exc, "reason", exc)
            raise VenueError(f"网络错误：{reason}") from exc
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise VenueError("接口返回了无法解析的数据") from exc

        return self.parse_payload(venue, query_date, payload)

    def _fetch_detail(self, venue: IngVenue) -> Mapping[str, Any]:
        query = urllib.parse.urlencode({"gymId": venue.gym_id})
        request = urllib.request.Request(
            f"{BASE_URL}{DETAIL_PATH}?{query}",
            headers={
                "Accept": "application/json",
                "User-Agent": "tennis-check/0.1 (read-only availability query)",
            },
            method="GET",
        )
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            raise VenueError(f"HTTP {exc.code}") from exc
        except (urllib.error.URLError, socket.timeout, TimeoutError, ssl.SSLError) as exc:
            reason = getattr(exc, "reason", exc)
            raise VenueError(f"网络错误：{reason}") from exc
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise VenueError("接口返回了无法解析的数据") from exc
        if payload.get("code") != 200 or payload.get("success") is not True:
            raise VenueError(str(payload.get("msg") or "无法读取放场规则"))
        detail = payload.get("data")
        if not isinstance(detail, Mapping):
            raise VenueError("接口缺少放场规则")
        return detail

    @staticmethod
    def ensure_date_released(
        venue: IngVenue,
        query_date: date,
        detail: Mapping[str, Any],
        now: datetime | None = None,
    ) -> None:
        current = now.astimezone(SHANGHAI) if now else datetime.now(SHANGHAI)
        try:
            reservable_days = int(detail["reservableDay"])
            release_time = datetime.strptime(str(detail["releaseTime"]), "%H:%M:%S").time()
        except (KeyError, TypeError, ValueError) as exc:
            raise VenueError("接口缺少有效的放场规则") from exc

        last_open_date = current.date() + timedelta(days=max(reservable_days - 1, 0))
        if current.time() >= release_time:
            last_open_date += timedelta(days=1)
        if query_date <= last_open_date:
            return

        open_date = query_date - timedelta(days=reservable_days)
        if open_date == current.date():
            when = f"今日 {release_time:%H:%M}"
        else:
            when = f"{open_date:%m-%d} {release_time:%H:%M}"
        raise VenueError(f"该日期尚未开放预订（预计{when}开放）")

    @staticmethod
    def parse_payload(venue: IngVenue, query_date: date, payload: Mapping[str, Any]) -> List[Slot]:
        code = payload.get("code")
        success = payload.get("success")
        message = str(payload.get("msg") or "未知错误")
        if code in (401, 403) or any(word in message for word in ("登录", "token", "认证", "授权")):
            raise AuthenticationError("登录已过期")
        if code != 200 or success is not True:
            raise VenueError(message)

        data = payload.get("data")
        courts = data.get("array") if isinstance(data, Mapping) else None
        if not isinstance(courts, list):
            raise VenueError("接口缺少场地列表")

        results: List[Slot] = []
        for court in courts:
            if not isinstance(court, Mapping):
                continue
            court_name = str(court.get("fieldName") or "未知场地")
            day_source = court.get("daySource")
            if not isinstance(day_source, list):
                continue
            for item in day_source:
                if not isinstance(item, Mapping):
                    continue
                try:
                    start = parse_hhmm(str(item["startTime"]))
                    end = parse_hhmm(str(item["endTime"]))
                except (KeyError, ValueError):
                    continue

                # reserveId identifies an existing reservation, not inventory.
                # The mini-program renders a cell as selectable only when it is
                # neither occupied/closed nor associated with a reservation.
                available = item.get("occupy") is False and not item.get("reserveId")
                results.append(
                    Slot(
                        venue_label=venue.label,
                        court=court_name,
                        date=query_date,
                        start=start,
                        end=end,
                        available=available,
                    )
                )
        return results
