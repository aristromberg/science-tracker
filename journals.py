"""Journal RSS/table-of-contents feed monitoring via feedparser."""

import logging

import feedparser
import requests

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 ScienceTracker/1.0"
)
REQUEST_TIMEOUT_SECONDS = 20


def fetch_journal(name: str, rss_url: str) -> list[dict]:
    """Fetch and parse one journal's RSS feed. Returns [] (and logs) on any failure."""
    try:
        response = requests.get(rss_url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        parsed = feedparser.parse(response.content)
    except Exception:
        logger.exception("Failed to fetch/parse feed for journal %r (%s)", name, rss_url)
        return []

    if parsed.bozo and not parsed.entries:
        logger.warning("Feed for %r appears malformed and had no entries: %s", name, parsed.get("bozo_exception"))
        return []

    articles = []
    for entry in parsed.entries:
        link = entry.get("link", "")
        if not link:
            continue
        articles.append(
            {
                "id": f"url:{link}",
                "source": "journal",
                "matched_query": name,
                "title": entry.get("title", "").strip(),
                "abstract": entry.get("summary", "").strip(),
                "journal": name,
                "url": link,
            }
        )
    return articles


def fetch_all(journals: list[dict]) -> list[dict]:
    """Fetch all configured journal feeds and return the merged article list (not deduped)."""
    all_articles = []
    for journal in journals:
        all_articles.extend(fetch_journal(journal["name"], journal["rss_url"]))
    return all_articles
