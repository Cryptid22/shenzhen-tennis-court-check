from __future__ import annotations

import json
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date
from typing import Any, List, Mapping

from .base import AuthenticationError, Slot, VenueError, parse_hhmm


BASE_URL = "https://sysh.tennis168.vip"
DATE_LIST_PATH = "/api/sports/space/date_list"


@dataclass(frozen=True)
class ShangyueVenue:
    label: str
    store_id: str


SHAHE = ShangyueVenue("上越网球中心-沙河店", "117")


class ShangyueClient:
    def __init__(self, timeout: float = 10.0) -> None:
        self.timeout = timeout
        # This domestic API is unreliable through the user's overseas Clash exit.
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def fetch(self, venue: ShangyueVenue, query_date: date) -> List[Slot]:
        query = urllib.parse.urlencode(
            {"date": query_date.isoformat(), "store_id": venue.store_id}
        )
        request = urllib.request.Request(
            f"{BASE_URL}{DATE_LIST_PATH}?{query}",
            headers={
                "Accept": "application/json",
                "Form-type": "routine",
                "store-id": venue.store_id,
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
        venue: ShangyueVenue, query_date: date, payload: Mapping[str, Any]
    ) -> List[Slot]:
        status = payload.get("status")
        message = str(payload.get("msg") or "未知错误")
        if status in (401, 403) or any(
            word in message.lower() for word in ("登录", "token", "认证", "授权")
        ):
            raise AuthenticationError("登录已过期")
        if status != 200:
            raise VenueError(message)

        data = payload.get("data")
        rows = data.get("children") if isinstance(data, Mapping) else None
        if not isinstance(rows, list):
            raise VenueError("接口缺少场地时段列表")

        results: List[Slot] = []
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            time_range = str(row.get("full_time") or row.get("time") or "")
            parts = time_range.replace("-", "~").split("~", 1)
            if len(parts) != 2:
                continue
            try:
                start = parse_hhmm(parts[0])
                end = parse_hhmm(parts[1])
            except ValueError:
                continue

            courts = row.get("children")
            if not isinstance(courts, list):
                continue
            for court in courts:
                if not isinstance(court, Mapping):
                    continue
                court_name = str(court.get("name") or "未知场地")
                # The mini program marks bookable cells with active="1".
                # Booked cells use active="0" and status_text="已预约".
                available = str(court.get("active")) == "1"
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
