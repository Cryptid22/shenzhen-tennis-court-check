from __future__ import annotations

import json
import os
import socket
import ssl
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path
from typing import Any, List, Mapping, Optional, Sequence, Tuple

from .base import AuthenticationError, Slot, VenueError


BASE_URL = "https://wlhmobile.crland.com.cn"
MATRIX_PATH = "/business/client/field/area/matrix"
APP_ID = "wx020209beec4251e0"
PROJECT_UUID = "3a59e62a07f811f1bec0aeefcf2e061a"
VENUE_LABEL = "深圳湾网球"
FIELD_AREAS: Tuple[str, ...] = (
    "71abff5590af11f195a452a64e4c2bdc",  # 风雨棚 1-4 号
    "b7f8a0770a4d11f198f45a68b1262c30",  # 室外 5-12 号
)
PRIVATE_CONFIG = Path(__file__).resolve().parents[1] / ".private" / "config.json"


def load_authorization(config_path: Path = PRIVATE_CONFIG) -> str:
    value = os.environ.get("TENNIS_CHECK_WEILAIHUI_AUTHORIZATION", "").strip()
    if value:
        return value
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return ""
    except (OSError, json.JSONDecodeError) as exc:
        raise VenueError("本地凭证配置无法读取") from exc
    section = payload.get("weilaihui")
    if not isinstance(section, Mapping):
        return ""
    return str(section.get("authorization") or "").strip()


class WeilaihuiClient:
    def __init__(self, timeout: float = 10.0, authorization: Optional[str] = None) -> None:
        self.timeout = timeout
        self.authorization = authorization if authorization is not None else load_authorization()
        # This domestic endpoint is deliberately accessed without the overseas
        # Clash exit; Proxyman is only needed while initially capturing it.
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def fetch(self, query_date: date) -> List[Slot]:
        if not self.authorization:
            raise AuthenticationError("缺少登录凭证，需要重新抓包")
        slots: List[Slot] = []
        for field_area_uuid in FIELD_AREAS:
            slots.extend(self._fetch_area(field_area_uuid, query_date))
        return slots

    def _fetch_area(self, field_area_uuid: str, query_date: date) -> List[Slot]:
        body = json.dumps(
            {
                "fieldAreaUuid": field_area_uuid,
                "reserveDate": query_date.isoformat(),
                "enterpriseUuid": "",
                "discountSpecUuid": "",
                "projectUuid": PROJECT_UUID,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{BASE_URL}{MATRIX_PATH}",
            data=body,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "appId": APP_ID,
                "projectUuid": PROJECT_UUID,
                "Authorization": self.authorization,
                "User-Agent": "tennis-check/0.1 (read-only availability query)",
            },
            method="POST",
        )
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise AuthenticationError("登录已过期，需要重新抓包") from exc
            raise VenueError(f"HTTP {exc.code}") from exc
        except (urllib.error.URLError, socket.timeout, TimeoutError, ssl.SSLError) as exc:
            reason = getattr(exc, "reason", exc)
            raise VenueError(f"网络错误：{reason}") from exc
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise VenueError("接口返回了无法解析的数据") from exc
        return self.parse_payload(query_date, payload)

    @staticmethod
    def parse_payload(query_date: date, payload: Mapping[str, Any]) -> List[Slot]:
        code = payload.get("code")
        message = str(payload.get("text") or payload.get("message") or "未知错误")
        if code in (401, 403) or any(
            word in message.lower() for word in ("登录", "token", "认证", "授权", "unauthorized")
        ):
            raise AuthenticationError("登录已过期，需要重新抓包")
        if code != 200:
            raise VenueError(message)

        result = payload.get("result")
        if not isinstance(result, Mapping):
            raise VenueError("接口缺少场地矩阵")
        field_list = result.get("fieldList")
        matrices = result.get("matrix")
        if not isinstance(field_list, list) or not isinstance(matrices, list):
            raise VenueError("接口缺少场地矩阵")

        names = {
            str(item.get("fieldUuid")): str(item.get("fieldName") or "未知场地")
            for item in field_list
            if isinstance(item, Mapping) and item.get("fieldUuid")
        }
        parsed: List[Slot] = []
        for row in matrices:
            if not isinstance(row, Mapping):
                continue
            court = names.get(str(row.get("fieldUuid")), "未知场地")
            cells = row.get("matrix")
            if not isinstance(cells, list):
                continue
            for cell in cells:
                if not isinstance(cell, Mapping):
                    continue
                try:
                    start_dt = datetime.fromisoformat(str(cell["startTime"]))
                    end_dt = datetime.fromisoformat(str(cell["endTime"]))
                except (KeyError, ValueError):
                    continue
                parsed.append(
                    Slot(
                        venue_label=VENUE_LABEL,
                        court=court,
                        date=query_date,
                        start=start_dt.time(),
                        end=end_dt.time(),
                        available=cell.get("isAbleReserve") is True,
                    )
                )
        return parsed
