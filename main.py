"""Orchestrates a single tracker run: fetch -> dedupe -> curate -> narrate -> publish feed."""

import datetime as dt
import logging
import os
import sys

import yaml
from dotenv import load_dotenv

import curate
import dedupe
import feed
import journals
import pubmed
import tts

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> int:
    load_dotenv()
    config = load_config()
    today = dt.datetime.now(dt.timezone.utc).date()

    logger.info("Fetching PubMed articles...")
    pubmed_articles = pubmed.search_all(
        queries=config["pubmed"]["queries"],
        lookback_days=config["pubmed"]["lookback_days"],
        max_results_per_query=config["pubmed"]["max_results_per_query"],
    )
    logger.info("Fetched %d PubMed candidates", len(pubmed_articles))

    logger.info("Fetching journal feeds...")
    journal_articles = journals.fetch_all(config["journals"])
    logger.info("Fetched %d journal candidates", len(journal_articles))

    all_candidates = pubmed_articles + journal_articles

    seen_ids = dedupe.load_seen_ids()
    new_candidates = dedupe.filter_new(all_candidates, seen_ids)
    logger.info("%d new candidates after dedupe", len(new_candidates))

    if not new_candidates:
        logger.info("Nothing new today — exiting without publishing an episode.")
        return 0

    logger.info("Asking Claude to curate and summarize...")
    selections = curate.curate(
        new_candidates,
        model=config["curation"]["model"],
        interest_profile=config["curation"]["interest_profile"],
    )
    logger.info("Claude selected %d article(s)", len(selections))

    # Mark every candidate seen regardless of selection, so unselected articles aren't
    # re-evaluated (and re-billed) on tomorrow's run.
    seen_ids.update(a["id"] for a in new_candidates)
    dedupe.save_seen_ids(seen_ids)

    if not selections:
        logger.info("No articles met the bar today — exiting without publishing an episode.")
        return 0

    script_text = tts.build_script(selections, today)
    audio_filename = f"{today.isoformat()}.mp3"
    audio_path = os.path.join(os.path.dirname(__file__), "docs", "audio", audio_filename)

    logger.info("Synthesizing audio via ElevenLabs...")
    tts.synthesize(
        script_text,
        voice_id=config["tts"]["voice_id"],
        model_id=config["tts"]["model_id"],
        output_path=audio_path,
    )
    audio_size_bytes = os.path.getsize(audio_path)

    site_url = config["podcast"]["site_url"].rstrip("/")
    audio_url = f"{site_url}/audio/{audio_filename}"

    episode_titles = "; ".join(s["title"] for s in selections)
    episodes = feed.load_episodes()
    episodes = feed.add_episode(
        episodes,
        title=f"Science Briefing — {today.strftime('%B %d, %Y')}",
        description=episode_titles,
        audio_url=audio_url,
        audio_size_bytes=audio_size_bytes,
        pub_date=dt.datetime.now(dt.timezone.utc),
    )
    feed.save_episodes(episodes)
    feed.render_feed(episodes, config["podcast"])

    logger.info("Published episode with %d article(s) to %s", len(selections), audio_url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
