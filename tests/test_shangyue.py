import unittest
from datetime import date, time

from venues.base import AuthenticationError, VenueError
from venues.shangyue import SHAHE, ShangyueClient


class ShangyueParserTests(unittest.TestCase):
    def test_parses_available_and_booked_cells(self):
        payload = {
            "status": 200,
            "msg": "ok",
            "data": {
                "children": [
                    {
                        "time": "20:00~21:00",
                        "full_time": "20:00~21:00",
                        "children": [
                            {"name": "1号场", "active": "1", "status_text": "60.00"},
                            {"name": "2号场", "active": "0", "status_text": "已预约"},
                        ],
                    }
                ]
            },
        }

        slots = ShangyueClient.parse_payload(SHAHE, date(2026, 11, 5), payload)

        self.assertEqual(len(slots), 2)
        self.assertEqual(slots[0].start, time(20, 0))
        self.assertEqual(slots[0].end, time(21, 0))
        self.assertTrue(slots[0].available)
        self.assertFalse(slots[1].available)

    def test_accepts_non_zero_padded_times(self):
        payload = {
            "status": 200,
            "msg": "ok",
            "data": {
                "children": [
                    {
                        "time": "6:00~7:00",
                        "children": [{"name": "1号场", "active": "1"}],
                    }
                ]
            },
        }
        slot = ShangyueClient.parse_payload(SHAHE, date(2026, 11, 5), payload)[0]
        self.assertEqual((slot.start, slot.end), (time(6, 0), time(7, 0)))

    def test_reports_authentication_failure(self):
        with self.assertRaises(AuthenticationError):
            ShangyueClient.parse_payload(
                SHAHE, date(2026, 11, 5), {"status": 401, "msg": "token无效"}
            )

    def test_rejects_missing_schedule(self):
        with self.assertRaises(VenueError):
            ShangyueClient.parse_payload(
                SHAHE, date(2026, 11, 5), {"status": 200, "msg": "ok", "data": {}}
            )


if __name__ == "__main__":
    unittest.main()
