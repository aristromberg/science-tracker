"""Article curation and summarization via the Anthropic API.

Two-stage process to keep episodes a reasonable length:
  1. Shortlist — score every candidate for how noteworthy it is (per-batch, cheap).
  2. Feature — from the merged shortlist, pick the top N for a full spoken summary;
     everything else shortlisted becomes a quick "also noteworthy" mention (title + journal only).
"""

import json
import logging

from anthropic import Anthropic

logger = logging.getLogger(__name__)

MAX_ARTICLES_PER_CALL = 60  # keep prompts a reasonable size; batch if needed

SHORTLIST_TOOL = {
    "name": "shortlist_articles",
    "description": "Shortlist articles that are noteworthy given the listener's interest profile.",
    "input_schema": {
        "type": "object",
        "properties": {
            "shortlisted": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "The id field of the source article."},
                        "significance_score": {
                            "type": "integer",
                            "description": "1-10 rating of how noteworthy/significant this article is given the interest profile. Only include articles scoring 5 or above.",
                        },
                    },
                    "required": ["id", "significance_score"],
                },
            }
        },
        "required": ["shortlisted"],
    },
}

FEATURE_TOOL = {
    "name": "select_featured_articles",
    "description": "From the shortlisted articles, pick the most significant ones for full narration.",
    "input_schema": {
        "type": "object",
        "properties": {
            "featured": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "The id field of the source article."},
                        "summary": {
                            "type": "string",
                            "description": (
                                "2-4 sentence spoken-style summary of why this article matters, "
                                "written to be read aloud by a text-to-speech voice (no markdown, "
                                "no citations, no special characters)."
                            ),
                        },
                    },
                    "required": ["id", "summary"],
                },
            }
        },
        "required": ["featured"],
    },
}


def _shortlist_batch(client: Anthropic, model: str, batch: list[dict], interest_profile: str) -> list[dict]:
    catalog = [
        {"id": a["id"], "title": a["title"], "journal": a["journal"], "abstract": a["abstract"][:2000]}
        for a in batch
    ]
    prompt = (
        "You are triaging candidate articles for a personal daily science-briefing podcast. "
        "Below is a JSON list of candidate articles pulled from PubMed searches and journal RSS "
        "feeds. Score each article's significance (1-10) against the listener's interest profile, "
        "using the shortlist_articles tool. Only include articles scoring 5 or above — omit the rest. "
        "It is fine to shortlist nothing if none qualify.\n\n"
        f"Listener's interest profile: {interest_profile.strip()}\n\n"
        f"Candidate articles (JSON):\n{json.dumps(catalog, ensure_ascii=False, indent=2)}"
    )

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        tools=[SHORTLIST_TOOL],
        tool_choice={"type": "tool", "name": "shortlist_articles"},
        messages=[{"role": "user", "content": prompt}],
    )

    tool_use = next((b for b in response.content if b.type == "tool_use"), None)
    if tool_use is None:
        logger.warning("Claude shortlist response had no tool_use block; skipping batch")
        return []
    return tool_use.input.get("shortlisted", [])


def _feature_from_shortlist(
    client: Anthropic, model: str, shortlist: list[dict], by_id: dict, featured_count: int, interest_profile: str
) -> list[dict]:
    catalog = [
        {
            "id": item["id"],
            "significance_score": item["significance_score"],
            "title": by_id[item["id"]]["title"],
            "journal": by_id[item["id"]]["journal"],
            "abstract": by_id[item["id"]]["abstract"][:2000],
        }
        for item in shortlist
    ]
    prompt = (
        f"From this shortlist of noteworthy articles, pick the {featured_count} MOST significant "
        "ones overall for full narration in today's episode, and write a spoken-style summary for "
        "each using the select_featured_articles tool. Pick exactly "
        f"{featured_count} unless the shortlist has fewer than {featured_count} entries, in which case "
        "pick all of them.\n\n"
        f"Listener's interest profile: {interest_profile.strip()}\n\n"
        f"Shortlisted articles (JSON):\n{json.dumps(catalog, ensure_ascii=False, indent=2)}"
    )

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        tools=[FEATURE_TOOL],
        tool_choice={"type": "tool", "name": "select_featured_articles"},
        messages=[{"role": "user", "content": prompt}],
    )

    tool_use = next((b for b in response.content if b.type == "tool_use"), None)
    if tool_use is None:
        logger.warning("Claude feature response had no tool_use block")
        return []
    return tool_use.input.get("featured", [])


def curate(articles: list[dict], model: str, interest_profile: str, featured_count: int) -> dict:
    """Curate articles into 'featured' (full summary) and 'mentions' (title/journal only).

    Returns {"featured": [...], "mentions": [...]}.
    """
    if not articles:
        return {"featured": [], "mentions": []}

    client = Anthropic()  # reads ANTHROPIC_API_KEY from env
    by_id = {a["id"]: a for a in articles}

    shortlist = []
    for batch_start in range(0, len(articles), MAX_ARTICLES_PER_CALL):
        batch = articles[batch_start : batch_start + MAX_ARTICLES_PER_CALL]
        for item in _shortlist_batch(client, model, batch, interest_profile):
            if item.get("id") in by_id:
                shortlist.append(item)
            else:
                logger.warning("Claude shortlisted unknown article id %r; skipping", item.get("id"))

    logger.info("Shortlisted %d article(s) across all batches", len(shortlist))
    if not shortlist:
        return {"featured": [], "mentions": []}

    featured_raw = _feature_from_shortlist(client, model, shortlist, by_id, featured_count, interest_profile)
    featured_ids = set()
    featured = []
    for item in featured_raw:
        article_id = item.get("id")
        if article_id not in by_id:
            logger.warning("Claude featured unknown article id %r; skipping", article_id)
            continue
        featured_ids.add(article_id)
        source = by_id[article_id]
        featured.append(
            {
                "id": article_id,
                "title": source["title"],
                "journal": source["journal"],
                "url": source["url"],
                "summary": item["summary"],
            }
        )

    mentions = []
    for item in shortlist:
        article_id = item["id"]
        if article_id in featured_ids:
            continue
        source = by_id[article_id]
        mentions.append({"id": article_id, "title": source["title"], "journal": source["journal"], "url": source["url"]})

    return {"featured": featured, "mentions": mentions}
