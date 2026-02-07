# Baltimore Networking Events Scraper

This project scrapes event listing pages (Eventbrite, Meetup, and other sites) for Baltimore networking events and writes results to an Excel file.

Usage:

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Edit `sample_urls.txt` or create your own file with one seed URL per line (event listing pages or search results).

3. Run the scraper:

```bash
python scrape.py --urls-file sample_urls.txt --output baltimore_events.xlsx
```

Notes:
- The scraper uses simple heuristics and may not extract every field on all sites. For robust scraping of heavily scripted sites you may need Selenium or site-specific parsers.
- Respect site `robots.txt` and terms of service.
