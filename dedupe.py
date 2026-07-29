"""Persisted dedupe state — tracks article IDs already surfaced across runs."""

import json
import os

STATE_PATH = os.path.join(os.path.dirname(__file__), "seen_ids.json")


def load_seen_ids() -> set[str]:
    if not os.path.exists(STATE_PATH):
        return set()
    with open(STATE_PATH, "r", encoding="utf-8") as f:
        return set(json.load(f))


def save_seen_ids(seen_ids: set[str]) -> None:
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(seen_ids), f, indent=2)


def filter_new(articles: list[dict], seen_ids: set[str]) -> list[dict]:
    """Return articles whose id is not in seen_ids, deduped against each other too."""
    new_articles = []
    seen_in_batch = set()
    for article in articles:
        article_id = article["id"]
        if article_id in seen_ids or article_id in seen_in_batch:
            continue
        seen_in_batch.add(article_id)
        new_articles.append(article)
    return new_articles
