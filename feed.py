"""Podcast RSS feed generation via feedgen.

Episode metadata is kept in docs/episodes_state.json (our own source of truth) and the
public docs/episodes.xml is fully regenerated from that state on every run. This avoids
needing to parse/round-trip an existing RSS file.
"""

import datetime as dt
import json
import os

from feedgen.feed import FeedGenerator

DOCS_DIR = os.path.join(os.path.dirname(__file__), "docs")
STATE_PATH = os.path.join(DOCS_DIR, "episodes_state.json")
FEED_PATH = os.path.join(DOCS_DIR, "episodes.xml")


def load_episodes() -> list[dict]:
    if not os.path.exists(STATE_PATH):
        return []
    with open(STATE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def add_episode(
    episodes: list[dict],
    *,
    title: str,
    description: str,
    audio_url: str,
    audio_size_bytes: int,
    pub_date: dt.datetime,
) -> list[dict]:
    episodes.append(
        {
            "title": title,
            "description": description,
            "audio_url": audio_url,
            "audio_size_bytes": audio_size_bytes,
            "pub_date": pub_date.isoformat(),
        }
    )
    return episodes


def save_episodes(episodes: list[dict]) -> None:
    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(episodes, f, indent=2)


def render_feed(episodes: list[dict], podcast_config: dict) -> None:
    fg = FeedGenerator()
    fg.load_extension("podcast")

    fg.title(podcast_config["title"])
    fg.description(podcast_config["description"])
    fg.link(href=podcast_config["site_url"], rel="alternate")
    fg.link(href=f"{podcast_config['site_url']}/episodes.xml", rel="self")
    fg.language("en")
    fg.podcast.itunes_author(podcast_config["author"])
    fg.podcast.itunes_category("Science")
    fg.podcast.itunes_explicit("no")

    # feedgen orders entries newest-first based on insertion when using fe.pubDate desc sort;
    # add newest last so it appears first after feedgen's internal handling.
    for episode in sorted(episodes, key=lambda e: e["pub_date"]):
        fe = fg.add_entry()
        fe.id(episode["audio_url"])
        fe.title(episode["title"])
        fe.description(episode["description"])
        fe.enclosure(episode["audio_url"], str(episode["audio_size_bytes"]), "audio/mpeg")
        fe.pubDate(episode["pub_date"])

    os.makedirs(DOCS_DIR, exist_ok=True)
    fg.rss_file(FEED_PATH)
