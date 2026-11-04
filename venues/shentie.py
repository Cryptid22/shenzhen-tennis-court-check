from __future__ import annotations

import json
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date
from typing import Any, List, Mapping, Tuple

from .base import AuthenticationError, Slot, VenueError, parse_hhmm


BASE_URL = "https://wtt.huangxuansoft.cn"
MAKE_PATH = "/api/mini/venue/make"


@dataclass(frozen=True)
class ShentieVenue:
    label: str
    venue_id: str
    sport_ids: Tuple[str, ...]


VENUES: Tuple[ShentieVenue, ...] = (
    # The park exposes outdoor courts 1-8 and 12 under sport 55, and covered
    # courts 9-11 under sport 33.
    ShentieVenue("深圳地铁文体公园", "31", ("55", "33")),
    ShentieVenue("塘朗运动中心", "22", ("40",)),
)


class ShentieClient:
    def __init__(self, timeout: float = 10.0) -> None:
        self.timeout = timeout
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def fetch(self, venue: ShentieVenue, query_date: date) -> List[Slot]:
        slots: List[Slot] = []
        for sport_id in venue.sport_ids:
            slots.extend(self._fetch_sport(venue, sport_id, query_date))
        return slots

    def _fetch_sport(self, venue: ShentieVenue, sport_id: str, query_date: date) -> List[Slot]:
        query = urllib.parse.urlencode(
            {
                "venueId": venue.venue_id,
                "sportId": sport_id,
                "makeDate": query_date.isoformat(),
            }
        )
        request = urllib.request.Request(
            f"{BASE_URL}{MAKE_PATH}?{query}",
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
            if exc.code in (401, 403):
                raise AuthenticationError("登录已过期") from exc
            raise VenueError(f"HTTP {exc.code}") from exc
        except (urllib.error.URLError, socket.timeout, TimeoutError, ssl.SSLError) as exc:
            reason = getattr(exc, "reason", exc)
            raise VenueError(f"网络错误：{reason}") from exc
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise VenueError("接口返回了无法解析的数据") from exc
        return self.parse_payload(venue, query_date, payload)

    @staticmethod
    def parse_payload(
        venue: ShentieVenue, query_date: date, payload: Mapping[str, Any]
    ) -> List[Slot]:
        code = payload.get("code")
        message = str(payload.get("msg") or "未知错误")
        if code in (401, 403, 40001) or any(
            word in message.lower() for word in ("登录", "token", "认证", "授权", "unauthorized")
        ):
            raise AuthenticationError("登录已过期")
        if code != 20000:
            raise VenueError(message)

        data = payload.get("data")
        rows = data.get("list") if isinstance(data, Mapping) else None
        if not isinstance(rows, list):
            raise VenueError("接口缺少场地时段列表")

        parsed: List[Slot] = []
        for item in rows:
            if not isinstance(item, Mapping):
                continue
            # The system's own booking UI only makes LOADING cells selectable.
            # APPLY, NOT_PAY, SUCCESS, FIXED and LOCK are all unavailable.
            try:
                start = parse_hhmm(str(item["makeTimeStart"]))
                end = parse_hhmm(str(item["makeTimeEnd"]))
            except (KeyError, ValueError):
                continue
            parsed.append(
                Slot(
                    venue_label=venue.label,
                    court=str(item.get("sceneName") or "未知场地"),
                    date=query_date,
                    start=start,
                    end=end,
                    available=item.get("status") == "LOADING",
                )
            )
        return parsed
