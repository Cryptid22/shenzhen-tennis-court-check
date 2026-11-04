import unittest
from datetime import date, time

from venues.base import AuthenticationError, VenueError
from venues.shentie import ShentieClient, ShentieVenue


class ShentieParserTests(unittest.TestCase):
    def setUp(self):
        self.venue = ShentieVenue("测试场馆", "31", ("55",))

    def test_only_loading_status_is_available(self):
        rows = []
        for index, status in enumerate(("LOADING", "APPLY", "NOT_PAY", "SUCCESS", "FIXED", "LOCK")):
            rows.append(
                {
                    "sceneName": "1号网球场",
                    "makeTimeStart": f"{8 + index:02d}:00",
                    "makeTimeEnd": f"{9 + index:02d}:00",
                    "status": status,
                }
            )
        payload = {"code": 20000, "msg": "success", "data": {"list": rows}}
        slots = ShentieClient.parse_payload(self.venue, date(2026, 11, 5), payload)
        self.assertEqual(len(slots), 6)
        self.assertEqual((slots[0].start, slots[0].end), (time(8), time(9)))
        self.assertEqual([slot.available for slot in slots], [True, False, False, False, False, False])

    def test_reports_authentication_failure(self):
        with self.assertRaises(AuthenticationError):
            ShentieClient.parse_payload(
                self.venue, date(2026, 11, 5), {"code": 401, "msg": "token invalid"}
            )

    def test_rejects_missing_schedule(self):
        with self.assertRaises(VenueError):
            ShentieClient.parse_payload(
                self.venue, date(2026, 11, 5), {"code": 20000, "msg": "success", "data": {}}
            )


if __name__ == "__main__":
    unittest.main()
