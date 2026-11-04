from __future__ import annotations

import hashlib
import json
import socket
import ssl
import time as time_module
import urllib.error
import urllib.request
from datetime import date, datetime, time, timedelta
from typing import Any, List, Mapping, Optional

from .base import SHANGHAI, Slot, VenueError, parse_hhmm


BASE_URL = "https://sports.sztyzx.com.cn"
ROUND_LIST_PATH = "/module-stadium/stadiumRoundInfo/list"
VENUE_LABEL = "深圳市体育中心"
ORG_ID = 1112
SPORTSCAT_ID = 1621
GROUNDTYPE_ID = 1744
APPLICATION_ID = "4"
ADVANCE_DAYS = 4
LAST_DAY_RELEASE_TIME = time(10, 0)


class IshentiClient:
    """Read-only client for i深体's Shenzhen Sports Center tennis courts."""

    def __init__(self, timeout: float = 10.0) -> None:
        self.timeout = timeout
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def fetch(self, query_date: date) -> List[Slot]:
        payload = {
            "sportscatId": SPORTSCAT_ID,
            "groundtypeId": GROUNDTYPE_ID,
            "orgId": ORG_ID,
            "useDate": query_date.isoformat(),
            "auditFlag": 3,
            "qryPriceFlag": 1,
            "isPriceEmpty": 1,
            "publicType": 2,
            "applicationId": APPLICATION_ID,
        }
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        timestamp = str(int(time_module.time()))
        signature = hashlib.md5(
            (f"Timestamp{timestamp}#&!6" + body.decode("utf-8")).encode("utf-8")
        ).hexdigest()
        request = urllib.request.Request(
            f"{BASE_URL}{ROUND_LIST_PATH}",
            data=body,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Timestamp": timestamp,
                "Sign": signature,
                "User-Agent": "tennis-check/0.1 (read-only availability query)",
            },
            method="POST",
        )
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                response_payload = json.load(response)
        except urllib.error.HTTPError as exc:
            raise VenueError(f"HTTP {exc.code}") from exc
        except (urllib.error.URLError, socket.timeout, TimeoutError, ssl.SSLError) as exc:
            reason = getattr(exc, "reason", exc)
            raise VenueError(f"网络错误：{reason}") from exc
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise VenueError("接口返回了无法解析的数据") from exc
        return self.parse_payload(query_date, response_payload)

    @staticmethod
    def parse_payload(
        query_date: date,
        payload: Mapping[str, Any],
        now: Optional[datetime] = None,
    ) -> List[Slot]:
        if str(payload.get("code")) != "0":
            raise VenueError(str(payload.get("msg") or "未知错误"))
        rows = payload.get("body")
        if not isinstance(rows, list):
            raise VenueError("接口缺少场地时段列表")

        current = now.astimezone(SHANGHAI) if now else datetime.now(SHANGHAI)
        last_bookable_day = current.date() + timedelta(days=ADVANCE_DAYS - 1)
        before_last_day_release = (
            query_date == last_bookable_day and current.time() < LAST_DAY_RELEASE_TIME
        )

        slots: List[Slot] = []
        for item in rows:
            if not isinstance(item, Mapping):
                continue
            try:
                start = parse_hhmm(str(item["startTime"])[:5])
                end_text = str(item["endTime"])
                if end_text == "00:00:00":
                    continue
                end = parse_hhmm(end_text[:5])
            except (KeyError, ValueError):
                continue

            # These are the same guards used by i深体's venue-table click handler.
            available = (
                item.get("roundStatus") == 1
                and item.get("appointFlag") == 1
                and item.get("stadiumEnableStatus") != 2
                and item.get("trainOccupyType", 0) == 0
                and not before_last_day_release
            )
            slots.append(
                Slot(
                    venue_label=VENUE_LABEL,
                    court=str(item.get("placeName") or item.get("roundName") or "未知场地"),
                    date=query_date,
                    start=start,
                    end=end,
                    available=available,
                )
            )
        return slots
