# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses
[semantic versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0]

First release as an installable, testable tool. Everything before this point
lived as loose scripts and is not covered by a compatibility promise.

### Added

- `resumex` console script, also runnable as `python -m resumex`, with `init`,
  `doctor`, `demo`, `render`, `batch`, `stats`, `upload` and `youtube-auth`.
- `resumex demo` renders a real 1080x1920 MP4 with no credentials, no network
  and no model download.
- `resumex doctor` reports Python, FFmpeg, ffprobe, workspace permissions and
  each optional integration separately.
- Local `.txt`, `.md` and `.json` files as a first-class content source.
- Kokoro text-to-speech behind the `tts` extra, plus a silent narrator that
  keeps the pipeline working without it.
- Word-level caption timing derived from the speech synthesiser's own segments.
- Deterministic 9:16 H.264/AAC rendering through a single FFmpeg invocation.
- Locally drawn gradient backgrounds when `backgrounds/` is empty.
- SQLite state store tracking stories, renders and uploads.
- Configuration via `resumex.toml` with strict validation, plus `RESUMEX_*`
  environment overrides.
- Optional Ollama scoring and metadata, each with a deterministic fallback.
- Optional YouTube upload: private by default, confirmed before publishing, and
  never destructive to local files.
- 164 offline unit tests plus an FFmpeg integration test, and CI across Linux,
  macOS and Windows on Python 3.11 and 3.13.

### Changed

- Rebuilt as a `src/resumex` package installed with `pip install -e .`; Poetry
  is no longer needed to run anything.
- Reddit is now one optional adapter reading public JSON listings, rather than
  the foundation of the product.
- Metadata is written as a `.metadata.json` sidecar next to each video.

### Removed

- The vendored copy of the Kokoro engine, its 54 voice tensors and 54 voice-test
  WAV files — about 39 MB of committed binaries. Kokoro is now an ordinary
  optional dependency that fetches its own weights.
- Whisper transcription. Caption timing no longer requires transcribing the
  audio the pipeline just generated.
- The YouTube background-clip downloader, and with it `yt-dlp`.
- Selenium, `undetected-chromedriver` and the browser fingerprint patching that
  went with them.
- MoviePy, OpenCV and `faster-whisper`.
- The Tkinter GUI and the always-on cron loop, which duplicated core logic.
- Automatic deletion of local videos after a successful upload.

### Security

- FFmpeg is invoked with argument lists only; no command is built by string
  interpolation or run through a shell.
- Credentials, tokens, caches, model files and rendered output are git-ignored;
  the OAuth token is written with `600` permissions where supported.
- Uploads default to `private` and require an explicit `--privacy public`.
