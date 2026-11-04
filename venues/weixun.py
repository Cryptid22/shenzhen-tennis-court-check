from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import date
from pathlib import Path
from typing import Any, List, Mapping, Sequence, Tuple

from .base import AuthenticationError, Slot, VenueError, parse_hhmm


HELPER = Path(__file__).with_name("weixun_browser.js")
VENUE_LABELS: Tuple[str, ...] = (
    "郑洁（深圳）国际网球俱乐部",
    "益田网球场",
    "皇岗公园网球中心",
    "彩田公园康体中心网球场",
    "大沙河国际网球交流中心",
    "北站中心公园体育中心",
)
NON_TENNIS_COURT = re.compile(r"足球|篮球|羽毛球|乒乓|游泳|七人|[五5]人")


class WeixunClient:
    """Query 威逊 through its own browser security layer, without changing proxies."""

    def __init__(self, timeout: float = 15.0) -> None:
        self.timeout = max(5.0, timeout)

    def fetch_all(self, query_date: date) -> Tuple[List[Slot], List[Tuple[str, str]]]:
        node = shutil.which("node")
        if not node:
            raise VenueError("本机缺少 Node.js")
        environment = os.environ.copy()
        try:
            result = subprocess.run(
                [node, str(HELPER), query_date.isoformat(), str(self.timeout)],
                check=False,
                capture_output=True,
                text=True,
                timeout=max(120.0, self.timeout * (len(VENUE_LABELS) + 2)),
                env=environment,
            )
        except subprocess.TimeoutExpired as exc:
            raise VenueError("浏览器查询超时") from exc
        except OSError as exc:
            raise VenueError("无法启动浏览器查询") from exc

        try:
            payload = json.loads(result.stdout)
        except (json.JSONDecodeError, TypeError) as exc:
            raise VenueError("浏览器查询返回了无法解析的数据") from exc
        if not isinstance(payload, Mapping):
            raise VenueError("浏览器查询返回格式异常")
        fatal = str(payload.get("fatal") or "").strip()
        if fatal:
            if "凭证" in fatal or "登录" in fatal:
                raise AuthenticationError(fatal)
            raise VenueError(fatal)
        return self.parse_payload(query_date, payload)

    @staticmethod
    def parse_payload(
        query_date: date, payload: Mapping[str, Any]
    ) -> Tuple[List[Slot], List[Tuple[str, str]]]:
        venues = payload.get("venues")
        raw_errors = payload.get("errors")
        if not isinstance(venues, list) or not isinstance(raw_errors, list):
            raise VenueError("浏览器查询缺少场馆结果")

        parsed: List[Slot] = []
        errors: List[Tuple[str, str]] = []
        for venue in venues:
            if not isinstance(venue, Mapping):
                continue
            label = str(venue.get("label") or "威逊文体")
            slots = venue.get("slots")
            if not isinstance(slots, list):
                continue
            accepted_count = 0
            for item in slots:
                if not isinstance(item, Mapping):
                    continue
                try:
                    start = parse_hhmm(str(item["start"]))
                    end = parse_hhmm(str(item["end"]))
                except (KeyError, ValueError):
                    continue
                court = str(item.get("court") or "未知场地")
                if NON_TENNIS_COURT.search(court):
                    continue
                accepted_count += 1
                parsed.append(
                    Slot(
                        venue_label=label,
                        court=court,
                        date=query_date,
                        start=start,
                        end=end,
                        available=item.get("available") is True,
                    )
                )

            if slots and accepted_count == 0:
                errors.append((label, "当前入口返回非网球场，已安全排除"))

        for item in raw_errors:
            if not isinstance(item, Mapping):
                continue
            errors.append(
                (
                    str(item.get("label") or "威逊文体"),
                    str(item.get("reason") or "查询失败"),
                )
            )
        return parsed, errors
