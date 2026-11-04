import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

from venues.base import VenueError
from venues.ing import IngClient, IngVenue


class IngTests(unittest.TestCase):
    def test_only_unoccupied_unreserved_cell_is_available(self):
        payload = {
            "code": 200,
            "success": True,
            "msg": "操作成功",
            "data": {
                "period": 30,
                "array": [
                    {
                        "fieldName": "1号场地",
                        "daySource": [
                            {"startTime": "20:00", "endTime": "20:30", "occupy": False, "reserveId": "reservation-1"},
                            {"startTime": "20:30", "endTime": "21:00", "occupy": True, "reserveId": None},
                            {"startTime": "21:00", "endTime": "21:30", "occupy": False, "reserveId": None},
                        ],
                    }
                ],
            },
        }
        slots = IngClient.parse_payload(IngVenue("测试店", "1"), date(2026, 11, 5), payload)
        self.assertEqual([slot.available for slot in slots], [False, False, True])

    def test_rejects_date_before_release_time(self):
        shanghai = ZoneInfo("Asia/Shanghai")
        with self.assertRaisesRegex(VenueError, "今日 23:00"):
            IngClient.ensure_date_released(
                IngVenue("测试店", "1"),
                date(2026, 11, 6),
                {"reservableDay": 2, "releaseTime": "23:00:00"},
                now=datetime(2026, 11, 4, 20, 0, tzinfo=shanghai),
            )

    def test_accepts_date_after_release_time(self):
        shanghai = ZoneInfo("Asia/Shanghai")
        IngClient.ensure_date_released(
            IngVenue("测试店", "1"),
            date(2026, 11, 6),
            {"reservableDay": 2, "releaseTime": "23:00:00"},
            now=datetime(2026, 11, 4, 23, 0, tzinfo=shanghai),
        )


if __name__ == "__main__":
    unittest.main()
