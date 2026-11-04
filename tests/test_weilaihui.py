import unittest
from datetime import date, time

from venues.base import AuthenticationError, VenueError
from venues.weilaihui import WeilaihuiClient


class WeilaihuiParserTests(unittest.TestCase):
    def test_parses_matrix_and_uses_explicit_availability(self):
        payload = {
            "code": 200,
            "text": "success",
            "result": {
                "fieldList": [{"fieldUuid": "court-1", "fieldName": "网球1号"}],
                "matrix": [
                    {
                        "fieldUuid": "court-1",
                        "matrix": [
                            {
                                "startTime": "2026-11-05 20:30:00",
                                "endTime": "2026-11-05 21:30:00",
                                "isAbleReserve": True,
                            },
                            {
                                "startTime": "2026-11-05 21:30:00",
                                "endTime": "2026-11-05 22:30:00",
                                "isAbleReserve": False,
                            },
                        ],
                    }
                ],
            },
        }
        slots = WeilaihuiClient.parse_payload(date(2026, 11, 5), payload)
        self.assertEqual(len(slots), 2)
        self.assertEqual((slots[0].court, slots[0].start, slots[0].end), ("网球1号", time(20, 30), time(21, 30)))
        self.assertEqual([slot.available for slot in slots], [True, False])

    def test_reports_expired_authorization(self):
        with self.assertRaises(AuthenticationError):
            WeilaihuiClient.parse_payload(date(2026, 11, 5), {"code": 403, "text": "token invalid"})

    def test_rejects_missing_matrix(self):
        with self.assertRaises(VenueError):
            WeilaihuiClient.parse_payload(date(2026, 11, 5), {"code": 200, "text": "success", "result": {}})


if __name__ == "__main__":
    unittest.main()
