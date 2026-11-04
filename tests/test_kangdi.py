import unittest
from datetime import date, time

from venues.base import AuthenticationError, VenueError
from venues.kangdi import KangdiClient


class KangdiParserTests(unittest.TestCase):
    def test_parses_availability_and_inclusive_end_minute(self):
        payload = {
            "successed": True,
            "status": "success",
            "errorCode": 0,
            "result": {
                "slots": [
                    {
                        "classRoomName": "1号网球场",
                        "beginDatetime": "2026-11-05 20:00:00",
                        "endDatetime": "2026-11-05 20:29:00",
                        "apptInfo": {
                            "canApptOrNot": True,
                            "status": 0,
                            "isPassTime": False,
                            "isCycleLock": False,
                        },
                    },
                    {
                        "classRoomName": "2号网球场",
                        "beginDatetime": "2026-11-05 20:30:00",
                        "endDatetime": "2026-11-05 20:59:00",
                        "apptInfo": {
                            "canApptOrNot": False,
                            "status": 3,
                            "isPassTime": False,
                            "isCycleLock": False,
                        },
                    },
                ]
            },
        }

        slots = KangdiClient.parse_payload(date(2026, 11, 5), payload)

        self.assertEqual(len(slots), 2)
        self.assertEqual((slots[0].start, slots[0].end), (time(20, 0), time(20, 30)))
        self.assertTrue(slots[0].available)
        self.assertFalse(slots[1].available)

    def test_rejects_passed_or_cycle_locked_cell(self):
        base = {
            "classRoomName": "1号网球场",
            "beginDatetime": "2026-11-05 20:00:00",
            "endDatetime": "2026-11-05 20:29:00",
        }
        payload = {
            "successed": True,
            "status": "success",
            "errorCode": 0,
            "result": {
                "slots": [
                    {**base, "apptInfo": {"canApptOrNot": True, "status": 0, "isPassTime": True}},
                    {**base, "apptInfo": {"canApptOrNot": True, "status": 0, "isCycleLock": True}},
                ]
            },
        }
        slots = KangdiClient.parse_payload(date(2026, 11, 5), payload)
        self.assertEqual([slot.available for slot in slots], [False, False])

    def test_reports_authentication_failure(self):
        with self.assertRaises(AuthenticationError):
            KangdiClient.parse_payload(
                date(2026, 11, 5),
                {"successed": False, "status": "token invalid", "errorCode": 401},
            )

    def test_rejects_missing_slots(self):
        with self.assertRaises(VenueError):
            KangdiClient.parse_payload(
                date(2026, 11, 5),
                {"successed": True, "status": "success", "errorCode": 0, "result": {}},
            )


if __name__ == "__main__":
    unittest.main()
