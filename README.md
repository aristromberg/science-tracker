# Science Literature & Publication Audio Tracker

Watches PubMed and a curated list of journal RSS feeds for new articles, asks Claude to
pick out and summarize the noteworthy ones, narrates the summaries with ElevenLabs, and
publishes the result as a daily episode in a personal podcast feed (hosted on GitHub Pages).

Runs automatically Monday–Friday via GitHub Actions.

## 1. Get your API keys

- **Anthropic (Claude)**: sign up / log in at https://console.anthropic.com, go to
  **API Keys**, and create a new key. This is a *personal* key — the tracker runs on
  GitHub's servers, which can't reach an internal corporate VPN/gateway.
- **ElevenLabs**: sign up / log in at https://elevenlabs.io, go to your **Profile →
  API Keys**, and create a new key.

## 2. Where to enter the keys

**For running locally (testing on your own machine):**

1. Copy the example env file:
   ```
   cp .env.example .env
   ```
2. Open `.env` and paste your keys in:
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   ELEVENLABS_API_KEY=...
   PUBMED_EMAIL=you@example.com
   ```
   `.env` is already gitignored — it will never be committed.
3. Install dependencies and run:
   ```
   pip install -r requirements.txt
   python main.py
   ```

**For the scheduled GitHub Actions run (production):**

`.env` files are never used in CI — instead, store the keys as **GitHub Actions repo
secrets**:

1. Push this project to a new **public** GitHub repository.
2. In the repo, go to **Settings → Secrets and variables → Actions → New repository
   secret**.
3. Add each of these (name must match exactly):
   - `ANTHROPIC_API_KEY`
   - `ELEVENLABS_API_KEY`
   - `PUBMED_EMAIL`
   - `PUBMED_API_KEY` (optional — see below)

The workflow at `.github/workflows/track.yml` reads these secrets and injects them as
environment variables when it runs — they're encrypted at rest and never shown in logs.

## 3. Enable GitHub Pages

1. In the repo, go to **Settings → Pages**.
2. Under **Build and deployment → Source**, choose **Deploy from a branch**.
3. Branch: `main`, folder: `/docs`. Save.
4. Your feed will be published at `https://<your-username>.github.io/<repo-name>/episodes.xml`.

## 4. Configure what gets tracked

Edit `config.yaml`:

- `pubmed.queries` — list of PubMed search strings (keywords, MeSH terms, author names).
  Empty by default; add at least one query or journal or nothing will ever be found.
- `journals` — starter list of high-impact journal RSS feeds is pre-filled; add, remove,
  or edit entries.
- `curation.interest_profile` — free-text description of what you care about; this is
  what Claude uses to decide which articles are "of interest" versus skipped.
- `podcast.site_url` — **must be updated** to your actual GitHub Pages URL from step 3
  (e.g. `https://yourname.github.io/science-tracker`), or podcast apps won't be able to
  download episodes.
- `tts.voice_id` — ElevenLabs voice to narrate with (default is ElevenLabs' public
  "Rachel" voice).

## 5. Subscribe in a podcast app

Once at least one episode has published, subscribe to:

```
https://<your-username>.github.io/<repo-name>/episodes.xml
```

in any podcast app that supports adding a feed by URL (e.g. Overcast → "+" → "Add a URL",
Apple Podcasts → Library → "Add a Show by URL").

## Running/testing manually

- Local dry run: `python main.py` (reads `.env`).
- Manual trigger in CI: repo → **Actions** tab → **Track publications and publish
  episode** → **Run workflow**.
- The schedule is `cron: "30 11 * * 1-5"` (UTC) in `.github/workflows/track.yml` — GitHub
  Actions cron has no timezone support, so adjust the hour for your local time/DST as
  needed.

## Notes

- If a run finds no new articles (or Claude selects none as noteworthy), it exits without
  publishing an empty episode — this is expected and not an error.
- `seen_ids.json` tracks every article already evaluated so it isn't re-summarized (and
  re-billed) on the next run.
- The NCBI `PUBMED_API_KEY` is optional but recommended — it raises the PubMed rate limit
  from 3 to 10 requests/second. Get one free from your NCBI account settings.
