"""Article curation and summarization via the Anthropic API."""

import json
import logging
import os

from anthropic import Anthropic

logger = logging.getLogger(__name__)

MAX_ARTICLES_PER_CALL = 60  # keep prompts a reasonable size; batch if needed

SELECT_TOOL = {
    "name": "select_articles",
    "description": "Select the noteworthy articles and provide a spoken-style summary for each.",
    "input_schema": {
        "type": "object",
        "properties": {
            "selections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "The id field of the source article."},
                        "title": {"type": "string"},
                        "journal": {"type": "string"},
                        "url": {"type": "string"},
                        "summary": {
                            "type": "string",
                            "description": (
                                "2-4 sentence spoken-style summary of why this article matters, "
                                "written to be read aloud by a text-to-speech voice (no markdown, "
                                "no citations, no special characters)."
                            ),
                        },
                    },
                    "required": ["id", "title", "journal", "url", "summary"],
                },
            }
        },
        "required": ["selections"],
    },
}


def _build_prompt(articles: list[dict], interest_profile: str) -> str:
    catalog = [
        {
            "id": a["id"],
            "title": a["title"],
            "journal": a["journal"],
            "abstract": a["abstract"][:2000],
            "url": a["url"],
        }
        for a in articles
    ]
    return (
        "You are curating a personal daily science-briefing podcast. Below is a JSON list of "
        "candidate articles pulled from PubMed searches and journal RSS feeds. Select ONLY the "
        "articles that are genuinely noteworthy given this listener's interests, and write a "
        "concise spoken-style summary for each selected article using the select_articles tool. "
        "It is fine to select zero articles if none qualify.\n\n"
        f"Listener's interest profile: {interest_profile.strip()}\n\n"
        f"Candidate articles (JSON):\n{json.dumps(catalog, ensure_ascii=False, indent=2)}"
    )


def curate(articles: list[dict], model: str, interest_profile: str) -> list[dict]:
    """Ask Claude to select and summarize noteworthy articles. Returns a list of selection dicts."""
    if not articles:
        return []

    client = Anthropic()  # reads ANTHROPIC_API_KEY from env
    by_id = {a["id"]: a for a in articles}

    all_selections = []
    for batch_start in range(0, len(articles), MAX_ARTICLES_PER_CALL):
        batch = articles[batch_start : batch_start + MAX_ARTICLES_PER_CALL]
        prompt = _build_prompt(batch, interest_profile)

        response = client.messages.create(
            model=model,
            max_tokens=4096,
            tools=[SELECT_TOOL],
            tool_choice={"type": "tool", "name": "select_articles"},
            messages=[{"role": "user", "content": prompt}],
        )

        tool_use = next((b for b in response.content if b.type == "tool_use"), None)
        if tool_use is None:
            logger.warning("Claude response had no tool_use block; skipping batch")
            continue

        for selection in tool_use.input.get("selections", []):
            if selection.get("id") not in by_id:
                logger.warning("Claude selected unknown article id %r; skipping", selection.get("id"))
                continue
            all_selections.append(selection)

    return all_selections
