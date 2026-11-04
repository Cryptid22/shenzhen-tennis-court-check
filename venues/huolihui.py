from __future__ import annotations

from .kangdi import KangdiClient


STORE_ID = "5794018"
VENUE_LABEL = "活力汇体育"
TENNIS_PROJECT_UIDS = (
    "1738807846229889123",  # 网球
)


class HuolihuiClient(KangdiClient):
    def __init__(self, timeout: float = 10.0) -> None:
        super().__init__(
            timeout=timeout,
            store_id=STORE_ID,
            venue_label=VENUE_LABEL,
            project_uids=TENNIS_PROJECT_UIDS,
            court_filter=lambda name: "网球" in name,
        )
