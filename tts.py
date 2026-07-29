"""Text-to-speech rendering via the ElevenLabs API."""

import datetime as dt
import logging
import os

from elevenlabs.client import ElevenLabs

logger = logging.getLogger(__name__)


def build_script(selections: list[dict], episode_date: dt.date) -> str:
    """Build the full narration script for one episode from the day's selected articles."""
    intro = (
        f"Here is your science briefing for {episode_date.strftime('%B %d, %Y')}. "
        f"{len(selections)} article{'s' if len(selections) != 1 else ''} today.\n\n"
    )
    body_parts = []
    for i, selection in enumerate(selections, start=1):
        body_parts.append(
            f"Article {i}, from {selection['journal']}: {selection['title']}.\n{selection['summary']}\n"
        )
    outro = "\nThat's all for today's briefing."
    return intro + "\n".join(body_parts) + outro


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
