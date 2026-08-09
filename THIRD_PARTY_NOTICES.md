# Third-party notices

Resumex itself is MIT licensed (see [LICENSE](LICENSE)). The items below are
**not** covered by that license — they keep their own copyright and terms.

## Bundled in this repository

### Noto Sans (Bold)

- File: [`src/resumex/assets/fonts/NotoSans-Bold.ttf`](src/resumex/assets/fonts/NotoSans-Bold.ttf)
- Copyright 2022 The Noto Project Authors
- License: SIL Open Font License, Version 1.1
- Full license text: [`src/resumex/assets/fonts/NotoSans-OFL.txt`](src/resumex/assets/fonts/NotoSans-OFL.txt)

Used as the default caption typeface so that rendering looks identical on every
machine. Set `render.font_path` in `resumex.toml` to use a different font.

## Required at runtime, not redistributed here

### FFmpeg

Resumex shells out to `ffmpeg` and `ffprobe`. They are not bundled; you install
them yourself. FFmpeg is licensed under the LGPL or GPL depending on the build
you install. See <https://ffmpeg.org/legal.html>.

## Installed on demand (optional extras)

These are ordinary PyPI dependencies pulled in by `pip install "resumex[...]"`.
No third-party source code is vendored into this repository.

- **Kokoro** (`resumex[tts]`) — Apache-2.0. Speech synthesis. Downloads model
  weights to the Hugging Face cache on first use.
- **Google API client libraries** (`resumex[youtube]`) — Apache-2.0. Used only
  by `resumex upload`.
