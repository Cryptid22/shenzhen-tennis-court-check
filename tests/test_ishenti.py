from datetime import date, datetime
import unittest
from zoneinfo import ZoneInfo

from venues.base import VenueError
from venues.ishenti import IshentiClient


SHANGHAI = ZoneInfo("Asia/Shanghai")


class IshentiClientTests(unittest.TestCase):
    def test_parse_payload_matches_booking_page_status_rules(self) -> None:
        payload = {
            "code": "0",
            "body": [
                {"placeName": "1号场", "startTime": "20:00:00", "endTime": "21:00:00", "roundStatus": 1, "appointFlag": 1, "stadiumEnableStatus": 1, "trainOccupyType": 0},
                {"placeName": "2号场", "startTime": "20:00:00", "endTime": "21:00:00", "roundStatus": 2, "appointFlag": 2, "stadiumEnableStatus": 1, "trainOccupyType": 0},
                {"placeName": "3号场", "startTime": "20:00:00", "endTime": "21:00:00", "roundStatus": 1, "appointFlag": 1, "stadiumEnableStatus": 2, "trainOccupyType": 0},
                {"placeName": "4号场", "startTime": "20:00:00", "endTime": "21:00:00", "roundStatus": 4, "appointFlag": 1, "stadiumEnableStatus": 1, "trainOccupyType": 0},
            ],
        }

        slots = IshentiClient.parse_payload(
            date(2026, 11, 6), payload,
            now=datetime(2026, 11, 5, 12, 0, tzinfo=SHANGHAI),
        )

        self.assertEqual([slot.available for slot in slots], [True, False, False, False])
        self.assertEqual(slots[0].court, "1号场")

    def test_last_advance_day_is_unavailable_before_release_time(self) -> None:
        payload = {
            "code": "0",
            "body": [
                {"placeName": "1号场", "startTime": "20:00:00", "endTime": "21:00:00", "roundStatus": 1, "appointFlag": 1, "stadiumEnableStatus": 1, "trainOccupyType": 0}
            ],
        }

        slots = IshentiClient.parse_payload(
            date(2026, 11, 8), payload,
            now=datetime(2026, 11, 5, 9, 0, tzinfo=SHANGHAI),
        )

        self.assertFalse(slots[0].available)

    def test_api_error_is_not_reported_as_no_availability(self) -> None:
        with self.assertRaisesRegex(VenueError, "签名错误"):
            IshentiClient.parse_payload(
                date(2026, 11, 6),
                {"code": "100001", "msg": "签名错误", "body": None},
            )


if __name__ == "__main__":
    unittest.main()
