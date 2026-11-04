from __future__ import annotations

import json
import socket
import ssl
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from typing import Any, Callable, List, Mapping, Optional, Sequence

from .base import AuthenticationError, Slot, VenueError


BASE_URL = "https://wxservice-stg48.pospal.cn"
SCHEDULE_PATH = "/wxapi/AppointmentVenue/LoadValidClassRoomApptSettingV2"
STORE_ID = "6076092"
VENUE_LABEL = "康堤报业网球"


class KangdiClient:
    def __init__(
        self,
        timeout: float = 10.0,
        store_id: str = STORE_ID,
        venue_label: str = VENUE_LABEL,
        project_uids: Sequence[str] = (),
        court_filter: Optional[Callable[[str], bool]] = None,
    ) -> None:
        self.timeout = timeout
        self.store_id = store_id
        self.venue_label = venue_label
        self.project_uids = tuple(project_uids)
        self.court_filter = court_filter
        # This domestic endpoint times out through the user's overseas Clash exit.
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def fetch(self, query_date: date) -> List[Slot]:
        projects: Sequence[Optional[str]] = self.project_uids or (None,)
        slots: List[Slot] = []
        for project_uid in projects:
            slots.extend(self._fetch_project(query_date, project_uid))
        return slots

    def _fetch_project(self, query_date: date, project_uid: Optional[str]) -> List[Slot]:
        payload: dict[str, str] = {"dateTime": query_date.isoformat()}
        if project_uid is not None:
            payload["projectUid"] = project_uid
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{BASE_URL}{SCHEDULE_PATH}",
            data=body,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "StoreId": self.store_id,
                "User-Agent": "tennis-check/0.1 (read-only availability query)",
            },
            method="POST",
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

        return self.parse_payload(
            query_date,
            payload,
            venue_label=self.venue_label,
            court_filter=self.court_filter,
        )

    @staticmethod
    def parse_payload(
        query_date: date,
        payload: Mapping[str, Any],
        venue_label: str = VENUE_LABEL,
        court_filter: Optional[Callable[[str], bool]] = None,
    ) -> List[Slot]:
        success = payload.get("successed")
        code = payload.get("errorCode")
        status = str(payload.get("status") or "")
        message = str(
            payload.get("errorMessage") or payload.get("message") or status or "未知错误"
        )
        if code in (401, 403) or any(
            word in message.lower() for word in ("登录", "token", "认证", "授权")
        ):
            raise AuthenticationError("登录已过期")
        if success is not True or code != 0:
            raise VenueError(message)

        result = payload.get("result")
        slots = result.get("slots") if isinstance(result, Mapping) else None
        if not isinstance(slots, list):
            raise VenueError("接口缺少场地时段列表")

        parsed: List[Slot] = []
        for item in slots:
            if not isinstance(item, Mapping):
                continue
            try:
                start_dt = datetime.fromisoformat(str(item["beginDatetime"]))
                end_dt = datetime.fromisoformat(str(item["endDatetime"]))
            except (KeyError, ValueError):
                continue

            # Pospal returns inclusive end minutes (20:00-20:29 means a
            # half-hour cell). Convert them to the exclusive Slot convention.
            end_dt += timedelta(minutes=1)
            info = item.get("apptInfo")
            info = info if isinstance(info, Mapping) else {}
            court_name = str(item.get("classRoomName") or "未知场地")
            if court_filter is not None and not court_filter(court_name):
                continue
            available = (
                info.get("canApptOrNot") is True
                and info.get("status") == 0
                and info.get("isPassTime") is not True
                and info.get("isCycleLock") is not True
            )
            parsed.append(
                Slot(
                    venue_label=venue_label,
                    court=court_name,
                    date=query_date,
                    start=start_dt.time(),
                    end=end_dt.time(),
                    available=available,
                )
            )
        return parsed
