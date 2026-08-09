# Security policy

## Supported versions

Resumex is at `0.1.x`. Fixes land on `main` and go out in the next release.

## Reporting a vulnerability

Please report privately rather than in a public issue: open a
[security advisory](https://github.com/Olwtelet/Resumex/security/advisories/new)
on this repository. Include what you did, what happened, and what you expected.
Expect a first reply within a week.

Please do not test against anyone else's accounts or infrastructure.

## What Resumex touches

Worth knowing when assessing a report:

- **It shells out to FFmpeg.** Always as an argument list, never through a
  shell, and all of it goes through `resumex.rendering.ffmpeg`. A command built
  by string interpolation would be a bug.
- **It reads files you point it at.** Story files, background media and the
  config file. Story text ends up drawn on video frames and written to a
  metadata sidecar; it is never executed.
- **It makes no network request by default.** Reddit, Ollama and YouTube are all
  opt-in and off in a fresh install.
- **It stores credentials only if you set up YouTube.** The OAuth token is
  written to `.resumex/youtube-token.json`, chmod `600` where the filesystem
  supports it. That path and `client_secret*.json` are git-ignored. Credentials
  are never logged, and `-v` does not print them.
- **It does not publish anything on its own.** Uploads need an explicit command,
  default to `private`, and never delete or modify your local files.
- **There is no telemetry.** Nothing is reported anywhere, ever.

## Out of scope

- Vulnerabilities in FFmpeg, Kokoro, or the Google client libraries — report
  those upstream.
- Anything requiring an attacker who already has write access to your config
  file or workspace.
