"""Build a validated public feed from Taiwan DGPA's official CSV resources."""
from __future__ import annotations

import argparse
import calendar
import csv
import hashlib
import io
import json
import os
import re
import tempfile
import time
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

CATALOG = "https://data.gov.tw/dataset/14718"
MARKER = "TW-DGPA-GITHUB-V1:"
TAIPEI = ZoneInfo("Asia/Taipei")
HEADERS = ["西元日期", "星期", "是否放假", "備註"]


class ResourceLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            self.links.extend(v for k, v in attrs if k.lower() == "href" and v)


def select_resources(page: str) -> dict[int, str]:
    parser = ResourceLinks()
    parser.feed(page)
    choices = {}
    for order, link in enumerate(parser.links):
        u = urlsplit(link)
        if u.scheme != "https" or u.netloc.lower() != "www.dgpa.gov.tw" or u.path.lower() != "/fileconversion":
            continue
        query = parse_qs(u.query)
        name = query.get("name", [""])[0]
        filename = query.get("filename", [""])[0]
        match = re.match(r"^(\d{3})(?:年|中)", name)
        version = re.search(r"(?:^|/)files/(\d{6})/", filename)
        if not match or not version or "google" in name.lower() or not filename.lower().endswith(".csv"):
            continue
        year = int(match[1]) + 1911
        priority = (int(version[1]), order)
        if year not in choices or priority > choices[year][0]:
            choices[year] = (priority, quote(link, safe=":/?&=%+"))
    return {year: entry[1] for year, entry in choices.items()}


def fetch(url: str) -> bytes:
    for attempt in range(3):
        try:
            request = Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "*/*"})
            with urlopen(request, timeout=30) as response:
                body = response.read(4_000_001)
            if len(body) > 4_000_000:
                raise ValueError("Official resource exceeds size limit")
            return body
        except (OSError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(attempt + 1)
    raise AssertionError("Unreachable")


def parse_calendar(raw: bytes, year: int) -> list[dict]:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp950")
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if reader.fieldnames != HEADERS:
        raise ValueError(f"{year}: unexpected CSV columns {reader.fieldnames!r}")
    result = []
    for index, row in enumerate(reader):
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f"{year}: malformed CSV row {index + 2}")
        code = row["西元日期"].strip()
        if not re.fullmatch(r"\d{8}", code):
            raise ValueError(f"{year}: invalid date {code!r}")
        day = datetime.strptime(code, "%Y%m%d").date()
        expected = date(year, 1, 1) + timedelta(days=index)
        if day != expected or day.year != year:
            raise ValueError(f"{year}: duplicate, missing, or out-of-order date {code}")
        weekday = row["星期"].strip()
        if weekday != "一二三四五六日"[day.weekday()] and not (day.weekday() == 6 and weekday == "天"):
            raise ValueError(f"{year}: weekday mismatch {code}")
        flag = row["是否放假"].strip()
        if flag not in ("0", "2"):
            raise ValueError(f"{year}: unexpected holiday flag {flag!r}")
        result.append({"date": day, "holiday": flag == "2", "title": row["備註"].strip() or "例假日"})
    if len(result) != (366 if calendar.isleap(year) else 365):
        raise ValueError(f"{year}: incomplete year ({len(result)} days)")
    if not 52 <= sum(row["holiday"] for row in result) <= 200:
        raise ValueError(f"{year}: implausible holiday count")
    return result


def event_record(day: date, title: str) -> dict:
    start = datetime.combine(day, datetime.min.time(), tzinfo=TAIPEI)
    end = start + timedelta(days=1)
    code = day.strftime("%Y%m%d")
    return {
        "date_code": int(code),
        "title": title,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "last_second": (end - timedelta(seconds=1)).isoformat(),
        "marker": MARKER + code,
        "notes": f"{MARKER}{code}\n行政院人事行政總處官方休假日\n{CATALOG}",
    }


def build_feed(today: date, resources: dict[int, str], loader, previous: dict | None = None) -> dict:
    previous = previous or {}
    holidays = []
    sources = []
    workdays = {}
    warnings = []
    years = []
    for year in (today.year, today.year + 1):
        if year not in resources:
            if year == today.year:
                raise ValueError(f"No official resource for current year {year}")
            warnings.append(f"{year} 年官方資料尚未提供；保留已驗證資料或等待下次更新。")
            if year in previous.get("years", []):
                years.append(year)
                holidays.extend(h for h in previous["holidays"] if h["date_code"] // 10000 == year)
                sources.extend(s for s in previous.get("sources", []) if s["year"] == year)
            continue
        url = resources[year]
        raw = loader(url)
        rows = parse_calendar(raw, year)
        years.append(year)
        sources.append({"year": year, "url": url, "sha256": hashlib.sha256(raw).hexdigest(),
                        "days": len(rows), "holidays": sum(r["holiday"] for r in rows)})
        for row in rows:
            entry = event_record(row["date"], row["title"])
            if row["holiday"]:
                holidays.append(entry)
            else:
                workdays[entry["date_code"]] = entry
    # Keep corrections until they cease being working days. Only the phone can
    # remove its own marked events; this service has no calendar credentials.
    old_holidays = {h["date_code"] for h in previous.get("holidays", [])}
    old_cancelled = {h["date_code"] for h in previous.get("cancelled", [])}
    cancelled = [workdays[code] for code in sorted((old_holidays | old_cancelled) & workdays.keys())]
    if today.year + 1 not in resources:
        cancelled.extend(h for h in previous.get("cancelled", []) if h["date_code"] // 10000 == today.year + 1)
    feed = {
        "schema": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "catalog": CATALOG,
        "years": years,
        "valid_until_code": max(years) * 10000 + 1231,
        "sources": sources,
        "warnings": warnings,
        "holidays": sorted(holidays, key=lambda h: h["date_code"]),
        "cancelled": sorted(cancelled, key=lambda h: h["date_code"]),
    }
    if len({h["date_code"] for h in holidays}) != len(holidays):
        raise ValueError("Duplicate holidays in feed")
    return feed


def atomic_write(path: Path, feed: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=".holidays-", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as f:
            json.dump(feed, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("data/holidays.json"))
    parser.add_argument("--today", type=date.fromisoformat, help="Override date for reproducible checks")
    args = parser.parse_args()
    today = args.today or datetime.now(TAIPEI).date()
    previous = json.loads(args.output.read_text()) if args.output.exists() else None
    resources = select_resources(fetch(CATALOG).decode("utf-8"))
    feed = build_feed(today, resources, fetch, previous)
    atomic_write(args.output, feed)
    print(json.dumps({"years": feed["years"], "holidays": len(feed["holidays"]),
                      "cancelled": len(feed["cancelled"]), "warnings": feed["warnings"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
