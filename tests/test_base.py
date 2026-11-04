import unittest
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from venues.base import Slot, default_query_date, format_slot, merge_adjacent, select_available


class BaseTests(unittest.TestCase):
    def test_default_date_skips_weekend(self):
        tz = ZoneInfo("Asia/Shanghai")
        saturday = datetime(2026, 11, 7, 12, 0, tzinfo=tz)
        self.assertEqual(default_query_date(saturday), date(2026, 11, 9))

    def test_default_date_after_22_moves_forward(self):
        tz = ZoneInfo("Asia/Shanghai")
        friday_night = datetime(2026, 11, 6, 22, 0, tzinfo=tz)
        self.assertEqual(default_query_date(friday_night), date(2026, 11, 9))

    def test_filter_and_merge(self):
        day = date(2026, 11, 5)
        slots = [
            Slot("测试店", "1号场", day, time(19, 30), time(20), True),
            Slot("测试店", "1号场", day, time(20), time(20, 30), True),
            Slot("测试店", "1号场", day, time(20, 30), time(21), True),
            Slot("测试店", "1号场", day, time(21), time(21, 30), False),
        ]
        selected = select_available(slots, time(20), time(22))
        merged = merge_adjacent(selected)
        self.assertEqual(len(merged), 1)
        self.assertEqual((merged[0].start, merged[0].end), (time(20), time(21)))
        self.assertEqual(format_slot(merged[0]), "【测试店1号场】星期四(11-05)空场: 20:00-21:00")


if __name__ == "__main__":
    unittest.main()
