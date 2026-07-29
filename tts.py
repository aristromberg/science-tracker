"""Text-to-speech rendering via the ElevenLabs API."""

import datetime as dt
import logging
import os

from elevenlabs.client import ElevenLabs

logger = logging.getLogger(__name__)


def build_script(featured: list[dict], mentions: list[dict], episode_date: dt.date) -> str:
    """Build the full narration script for one episode: full summaries plus a quick mentions list."""
    intro = (
        f"Here is your science briefing for {episode_date.strftime('%B %d, %Y')}. "
        f"{len(featured)} featured article{'s' if len(featured) != 1 else ''} today.\n\n"
    )
    body_parts = []
    for i, article in enumerate(featured, start=1):
        body_parts.append(
            f"Article {i}, from {article['journal']}: {article['title']}.\n{article['summary']}\n"
        )

    mentions_part = ""
    if mentions:
        mentions_part = "\nAlso noteworthy today:\n" + "\n".join(
            f"{m['title']}, from {m['journal']}." for m in mentions
        ) + "\n"

    outro = "\nThat's all for today's briefing."
    return intro + "\n".join(body_parts) + mentions_part + outro


def synthesize(text: str, voice_id: str, model_id: str, output_path: str) -> None:
    """Render text to an mp3 file at output_path via ElevenLabs."""
    client = ElevenLabs()  # reads ELEVENLABS_API_KEY from env

    audio = client.text_to_speech.convert(
        text=text,
        voice_id=voice_id,
        model_id=model_id,
        output_format="mp3_44100_128",
    )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as f:
        for chunk in audio:
            if chunk:
                f.write(chunk)
