from datetime import date
import unittest

from venues.weixun import WeixunClient


class WeixunClientTests(unittest.TestCase):
    def test_parse_payload_preserves_explicit_availability(self) -> None:
        query_date = date(2026, 11, 6)
        payload = {
            "venues": [
                {
                    "label": "益田网球场",
                    "salesId": "100242",
                    "slots": [
                        {
                            "court": "网球场1",
                            "date": "2026-11-06",
                            "start": "20:00",
                            "end": "21:00",
                            "available": True,
                        },
                        {
                            "court": "网球场1",
                            "date": "2026-11-06",
                            "start": "21:00",
                            "end": "22:00",
                            "available": False,
                        },
                    ],
                }
            ],
            "errors": [],
        }

        slots, errors = WeixunClient.parse_payload(query_date, payload)

        self.assertEqual(errors, [])
        self.assertEqual(len(slots), 2)
        self.assertTrue(slots[0].available)
        self.assertFalse(slots[1].available)
        self.assertEqual(slots[0].court, "网球场1")

    def test_parse_payload_keeps_per_venue_errors(self) -> None:
        slots, errors = WeixunClient.parse_payload(
            date(2026, 11, 6),
            {
                "venues": [],
                "errors": [{"label": "郑洁（深圳）国际网球俱乐部", "reason": "加载超时"}],
            },
        )

        self.assertEqual(slots, [])
        self.assertEqual(errors, [("郑洁（深圳）国际网球俱乐部", "加载超时")])

    def test_filters_football_courts_in_mixed_sports_center(self) -> None:
        slots, errors = WeixunClient.parse_payload(
            date(2026, 11, 6),
            {
                "venues": [
                    {
                        "label": "北站中心公园体育中心",
                        "slots": [
                            {"court": "七人场", "start": "20:00", "end": "21:00", "available": True},
                            {"court": "5人1号场", "start": "20:00", "end": "21:00", "available": True},
                        ],
                    }
                ],
                "errors": [],
            },
        )

        self.assertEqual(slots, [])
        self.assertEqual(
            errors,
            [("北站中心公园体育中心", "当前入口返回非网球场，已安全排除")],
        )


if __name__ == "__main__":
    unittest.main()
