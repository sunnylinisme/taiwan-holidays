import csv
import io
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from scripts.update_holidays import HEADERS, atomic_write, build_feed, parse_calendar, select_resources


def calendar_csv(year, overrides=None):
    out = io.StringIO(newline="")
    writer = csv.writer(out)
    writer.writerow(HEADERS)
    day = date(year, 1, 1)
    while day.year == year:
        off = (overrides or {}).get(day, day.weekday() >= 5)
        writer.writerow([day.strftime("%Y%m%d"), "一二三四五六日"[day.weekday()], 2 if off else 0,
                         '測試「假日」,含逗號' if off else ""])
        day += timedelta(days=1)
    return out.getvalue().encode("utf-8-sig")


class CalendarTests(unittest.TestCase):
    def test_link_selection_excludes_google_and_prefers_revision(self):
        def link(month, name, host="www.dgpa.gov.tw"):
            return f'<a href="https://{host}/FileConversion?filename=dgpa/files/{month}/x.csv&amp;name={name}">CSV</a>'
        page = link("202501", "115年辦公日曆.csv") + link("202601", "115年Google.csv")
        page += link("202506", "115年辦公日曆修正版.csv") + link("202701", "115年.csv", "example.com")
        selected = select_resources(page)
        self.assertEqual(set(selected), {2026})
        self.assertIn("/202506/", selected[2026])
        self.assertNotIn("&amp;", selected[2026])

    def test_complete_leap_year_and_quoted_csv(self):
        rows = parse_calendar(calendar_csv(2028), 2028)
        self.assertEqual(len(rows), 366)
        self.assertIn(",", rows[0]["title"])

    def test_missing_duplicate_and_wrong_schema_rejected(self):
        raw = calendar_csv(2026)
        lines = raw.decode("utf-8-sig").splitlines()
        for body in [lines[:-1], lines[:10] + [lines[9]] + lines[11:], ["Subject,Start Date"] + lines[1:]]:
            with self.subTest(body=body[:1]), self.assertRaises(ValueError):
                parse_calendar("\n".join(body).encode(), 2026)

    def test_wrong_weekday_and_flag_rejected(self):
        raw = calendar_csv(2026)
        for old, new in [(b"20260101,", b"20260102,"), (",0,".encode(), ",9,".encode())]:
            with self.assertRaises(ValueError):
                parse_calendar(raw.replace(old, new, 1), 2026)

    def test_current_missing_fails_next_missing_is_allowed(self):
        with self.assertRaises(ValueError):
            build_feed(date(2026, 1, 1), {}, lambda _: b"")
        feed = build_feed(date(2026, 1, 1), {2026: "2026"}, lambda _: calendar_csv(2026))
        self.assertEqual(feed["years"], [2026])
        self.assertEqual(len(feed["warnings"]), 1)

    def test_correction_is_retained_and_reinstatement_clears_it(self):
        today = date(2026, 10, 22)
        day = date(2026, 11, 7)  # Saturday
        resources = {2026: "2026", 2027: "2027"}
        def normal(url): return calendar_csv(int(url))
        old = build_feed(today, resources, normal)
        def changed(url): return calendar_csv(int(url), {day: False})
        corrected = build_feed(today, resources, changed, old)
        self.assertEqual([h["date_code"] for h in corrected["cancelled"]], [20261107])
        again = build_feed(today, resources, changed, corrected)
        self.assertEqual(again["cancelled"], corrected["cancelled"])
        restored = build_feed(today, resources, normal, again)
        self.assertEqual(restored["cancelled"], [])

    def test_last_valid_next_year_is_preserved_when_link_disappears(self):
        today = date(2026, 10, 22)
        loader = lambda url: calendar_csv(int(url))
        old = build_feed(today, {2026: "2026", 2027: "2027"}, loader)
        feed = build_feed(today, {2026: "2026"}, loader, old)
        self.assertEqual(feed["years"], [2026, 2027])
        self.assertEqual(feed["valid_until_code"], 20271231)
        self.assertEqual(len(feed["holidays"]), len(old["holidays"]))

    def test_exact_all_day_boundaries_and_marker(self):
        feed = build_feed(date(2026, 1, 1), {2026: "2026"}, lambda _: calendar_csv(2026))
        day = feed["holidays"][0]
        self.assertEqual(day["start"], "2026-01-03T00:00:00+08:00")
        self.assertEqual(day["end"], "2026-01-04T00:00:00+08:00")
        self.assertEqual(day["last_second"], "2026-01-03T23:59:59+08:00")
        self.assertTrue(day["notes"].startswith(day["marker"] + "\n"))

    def test_failed_build_does_not_replace_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "holidays.json"
            atomic_write(path, {"sentinel": "previous validated feed"})
            before = path.read_bytes()
            with self.assertRaises(ValueError):
                feed = build_feed(date(2026, 1, 1), {2026: "x"}, lambda _: b"bad")
                atomic_write(path, feed)
            self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
