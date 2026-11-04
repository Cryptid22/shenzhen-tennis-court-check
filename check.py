#!/usr/bin/python3
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from typing import List, Optional, Sequence, Tuple

from venues.base import (
    VenueError,
    default_query_date,
    format_slot,
    merge_adjacent,
    parse_hhmm,
    select_available,
)
from venues.huolihui import HuolihuiClient, VENUE_LABEL as HUOLIHUI_LABEL
from venues.ing import IngClient, VENUES
from venues.ishenti import IshentiClient, VENUE_LABEL as ISHENTI_LABEL
from venues.kangdi import KangdiClient, VENUE_LABEL as KANGDI_LABEL
from venues.shangyue import SHAHE, ShangyueClient
from venues.shentie import ShentieClient, VENUES as SHENTIE_VENUES
from venues.weilaihui import WeilaihuiClient, VENUE_LABEL as WEILAIHUI_LABEL
from venues.weixun import WeixunClient, VENUE_LABELS as WEIXUN_LABELS


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("日期应为 YYYY-MM-DD") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="查询深圳网球场空场（只查询，不下单）")
    parser.add_argument("--date", type=parse_date, help="查询日期，格式 YYYY-MM-DD")
    parser.add_argument("--start", default="20:00", help="时段起点，默认 20:00")
    parser.add_argument("--end", default="22:00", help="时段终点，默认 22:00")
    parser.add_argument("--timeout", type=float, default=10.0, help="单个接口超时秒数")
    return parser


def run(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        start = parse_hhmm(args.start)
        end = parse_hhmm(args.end)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if start >= end:
        print("开始时间必须早于结束时间", file=sys.stderr)
        return 2

    query_date = args.date or default_query_date()
    all_slots = []
    errors: List[Tuple[str, str]] = []

    client = IngClient(timeout=args.timeout)
    for venue in VENUES:
        try:
            all_slots.extend(client.fetch(venue, query_date))
        except VenueError as exc:
            errors.append((venue.label, str(exc)))

    shangyue = ShangyueClient(timeout=args.timeout)
    try:
        all_slots.extend(shangyue.fetch(SHAHE, query_date))
    except VenueError as exc:
        errors.append((SHAHE.label, str(exc)))

    kangdi = KangdiClient(timeout=args.timeout)
    try:
        all_slots.extend(kangdi.fetch(query_date))
    except VenueError as exc:
        errors.append((KANGDI_LABEL, str(exc)))

    huolihui = HuolihuiClient(timeout=args.timeout)
    try:
        all_slots.extend(huolihui.fetch(query_date))
    except VenueError as exc:
        errors.append((HUOLIHUI_LABEL, str(exc)))

    weilaihui = WeilaihuiClient(timeout=args.timeout)
    try:
        all_slots.extend(weilaihui.fetch(query_date))
    except VenueError as exc:
        errors.append((WEILAIHUI_LABEL, str(exc)))

    shentie = ShentieClient(timeout=args.timeout)
    for venue in SHENTIE_VENUES:
        try:
            all_slots.extend(shentie.fetch(venue, query_date))
        except VenueError as exc:
            errors.append((venue.label, str(exc)))

    weixun = WeixunClient(timeout=max(args.timeout, 15.0))
    try:
        weixun_slots, weixun_errors = weixun.fetch_all(query_date)
        all_slots.extend(weixun_slots)
        errors.extend(weixun_errors)
    except VenueError as exc:
        errors.extend((label, str(exc)) for label in WEIXUN_LABELS)

    ishenti = IshentiClient(timeout=args.timeout)
    try:
        all_slots.extend(ishenti.fetch(query_date))
    except VenueError as exc:
        errors.append((ISHENTI_LABEL, str(exc)))

    available = merge_adjacent(select_available(all_slots, start, end))
    lines = [format_slot(slot) for slot in available]
    lines.extend(f"未能查询：{label}（{reason}）" for label, reason in errors)

    if not lines:
        print("【当前暂无合适空场】")
    else:
        print("\n".join(lines))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(run())
