import argparse
import json
import time
from dataclasses import dataclass, asdict
from typing import List, Optional
import re
from dateutil import parser as dateparser
from urllib.parse import urlparse, urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup


@dataclass
class Event:
    title: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    location: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    source: Optional[str] = None


HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; event-scraper/1.0)"}


def fetch(url: str, timeout: int = 15) -> Optional[str]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        return resp.text
    except Exception:
        return None


def scrape_eventbrite_list(url: str, delay: float = 1.0) -> List[Event]:
    html = fetch(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    events: List[Event] = []

    # Find event links heuristically
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/e/" in href:
            full = urljoin(url, href)
            ev = scrape_event_page(full, source="eventbrite")
            if ev:
                events.append(ev)
            time.sleep(delay)

    # Deduplicate by URL
    seen = set()
    dedup = []
    for e in events:
        if e.url and e.url in seen:
            continue
        if e.url:
            seen.add(e.url)
        dedup.append(e)
    return dedup


def scrape_meetup_list(url: str, delay: float = 1.0) -> List[Event]:
    html = fetch(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    events: List[Event] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/events/" in href:
            full = urljoin(url, href)
            ev = scrape_event_page(full, source="meetup")
            if ev:
                events.append(ev)
            time.sleep(delay)

    seen = set()
    dedup = []
    for e in events:
        if e.url and e.url in seen:
            continue
        if e.url:
            seen.add(e.url)
        dedup.append(e)
    return dedup


def scrape_event_page(url: str, source: Optional[str] = None) -> Optional[Event]:
    html = fetch(url)
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    title = None
    description = None
    date = None
    time_str = None
    location = None

    # title: try meta og:title then h1
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        title = og["content"].strip()
    if not title:
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)

    ogd = soup.find("meta", property="og:description")
    if ogd and ogd.get("content"):
        description = ogd["content"].strip()
    if not description:
        p = soup.find("p")
        if p:
            description = p.get_text(strip=True)

    # Extract date/time using multiple heuristics
    def try_parse_datetime(text: str):
        if not text or not text.strip():
            return None
        try:
            dt = dateparser.parse(text, fuzzy=True)
            return dt
        except Exception:
            return None

    date = None
    time_str = None

    # 1) JSON-LD structured data
    for s in soup.find_all("script", type=lambda v: v and "ld+json" in v):
        try:
            data = json.loads(s.string or "{}")
        except Exception:
            continue
        # data may be a list or dict
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            for key in ("startDate", "start_date", "start_time", "date"):
                if key in item and item[key]:
                    dt = try_parse_datetime(str(item[key]))
                    if dt:
                        date = dt.date().isoformat()
                        time_str = dt.time().isoformat(timespec='minutes')
                        break
            if date:
                break
        if date:
            break

    # 2) meta tags and time tags
    if not date:
        # meta tags
        for m in soup.find_all("meta"):
            for attr in ("property", "name", "itemprop"):
                val = m.get(attr, "")
                if val and any(k in val.lower() for k in ("start", "date", "event")):
                    content = m.get("content")
                    dt = try_parse_datetime(content or "")
                    if dt:
                        date = dt.date().isoformat()
                        time_str = dt.time().isoformat(timespec='minutes')
                        break
            if date:
                break

    if not date:
        ttag = soup.find("time")
        if ttag:
            dt = None
            if ttag.get("datetime"):
                dt = try_parse_datetime(ttag.get("datetime"))
            if not dt:
                dt = try_parse_datetime(ttag.get_text(" ", strip=True))
            if dt:
                date = dt.date().isoformat()
                time_str = dt.time().isoformat(timespec='minutes')

    # 3) look for common class/id names containing date/time keywords
    if not date:
        candidates = []
        for el in soup.find_all(True, class_=True):
            if re.search(r"date|time|when|dtstart|start", " ".join(el.get("class", [])), re.I):
                candidates.append(el.get_text(" ", strip=True))
        for el in soup.find_all(True, id=True):
            if re.search(r"date|time|when|dtstart|start", el.get("id", ""), re.I):
                candidates.append(el.get_text(" ", strip=True))
        for text in candidates:
            dt = try_parse_datetime(text)
            if dt:
                date = dt.date().isoformat()
                time_str = dt.time().isoformat(timespec='minutes')
                break

    # 4) fallback: try to parse first date-like substring from page text
    if not date:
        body_text = soup.get_text(" ", strip=True)
        # try to find month names or numeric dates
        # use a short sliding window of text tokens to attempt parsing
        tokens = re.split(r"\s{2,}|\n", body_text)
        for t in tokens[:200]:
            if len(t) > 300:
                continue
            dt = try_parse_datetime(t)
            if dt:
                date = dt.date().isoformat()
                time_str = dt.time().isoformat(timespec='minutes')
                break

    # location heuristics
    sel = soup.select_one("[data-venue-name], .event-details, .venue, .location")
    if sel:
        location = sel.get_text(" ", strip=True)

    return Event(title=title, date=date, time=time_str, location=location, url=url, description=description, source=source)


def scrape_urls(urls: List[str], delay: float = 1.0) -> List[Event]:
    results: List[Event] = []
    for url in urls:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if "eventbrite" in domain:
            results.extend(scrape_eventbrite_list(url, delay=delay))
        elif "meetup" in domain:
            results.extend(scrape_meetup_list(url, delay=delay))
        else:
            # Generic: try to find event-like pages on the domain
            html = fetch(url)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            # find links containing keywords
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if any(k in href.lower() for k in ("event", "meetup", "networking", "tickets", "/e/")):
                    full = urljoin(url, href)
                    ev = scrape_event_page(full, source=domain)
                    if ev:
                        results.append(ev)
                    time.sleep(delay)

    # final dedupe by (title,url)
    seen = set()
    unique = []
    for e in results:
        key = (e.title or "", e.url or "")
        if key in seen:
            continue
        seen.add(key)
        unique.append(e)
    return unique


def save_to_excel(events: List[Event], out_path: str) -> None:
    rows = [asdict(e) for e in events]
    df = pd.DataFrame(rows)
    df.to_excel(out_path, index=False)


def load_urls_file(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f.readlines() if l.strip() and not l.strip().startswith("#")]
    return lines


def main():
    parser = argparse.ArgumentParser(description="Scrape event pages and save to Excel")
    parser.add_argument("--urls-file", "-u", help="File with URLs to scrape (one per line)")
    parser.add_argument("--output", "-o", default="events.xlsx", help="Output Excel file")
    parser.add_argument("--delay", "-d", type=float, default=1.0, help="Delay between requests (seconds)")
    args = parser.parse_args()

    urls: List[str] = []
    if args.urls_file:
        urls = load_urls_file(args.urls_file)

    if not urls:
        print("No URLs provided. Create a file with event-listing URLs and pass --urls-file")
        return

    print(f"Scraping {len(urls)} seed URLs...")
    events = scrape_urls(urls, delay=args.delay)
    print(f"Found {len(events)} events; saving to {args.output}")
    save_to_excel(events, args.output)


if __name__ == "__main__":
    main()
