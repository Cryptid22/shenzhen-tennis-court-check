import unittest
from datetime import date

from venues.huolihui import HuolihuiClient, TENNIS_PROJECT_UIDS, VENUE_LABEL


class HuolihuiParserTests(unittest.TestCase):
    def test_only_queries_main_tennis_project(self):
        self.assertEqual(TENNIS_PROJECT_UIDS, ("1738807846229889123",))

    def test_filters_non_tennis_courts_defensively(self):
        payload = {
            "successed": True,
            "status": "success",
            "errorCode": 0,
            "result": {
                "slots": [
                    {
                        "classRoomName": "匹克球1",
                        "beginDatetime": "2026-11-05 20:00:00",
                        "endDatetime": "2026-11-05 20:29:00",
                        "apptInfo": {"canApptOrNot": True, "status": 0},
                    },
                    {
                        "classRoomName": "网球一号场",
                        "beginDatetime": "2026-11-05 20:00:00",
                        "endDatetime": "2026-11-05 20:29:00",
                        "apptInfo": {"canApptOrNot": True, "status": 0},
                    },
                ]
            },
        }
        client = HuolihuiClient()

        slots = client.parse_payload(
            date(2026, 11, 5),
            payload,
            venue_label=client.venue_label,
            court_filter=client.court_filter,
        )

        self.assertEqual(len(slots), 1)
        self.assertEqual(slots[0].venue_label, VENUE_LABEL)
        self.assertEqual(slots[0].court, "网球一号场")


if __name__ == "__main__":
    unittest.main()
