# Setup

## Requirements

- Python 3.11 or 3.12
- Poetry
- Chrome browser (for scraping)

## Install

```bash
poetry install
```

## Folder Structure

Create these folders:

```
sludge_videos/     # Put background videos here (Minecraft parkour, Subway Surfers, etc.)
data/              # Auto-created for tracking used posts
```

## YouTube Upload (Optional)

To enable YouTube uploads:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project and enable the YouTube Data API v3
3. Create OAuth 2.0 credentials (Desktop app)
4. Download the JSON and save as `src/youtube/client_secret.json`

On first upload, you'll be prompted to authenticate in browser.

## Run

```bash
poetry run python gui.py
```

## Tabs

- **Scraper**: Scrape Reddit posts from subreddits
- **Video**: Generate videos from scraped posts
- **Upload**: Upload generated videos to YouTube
