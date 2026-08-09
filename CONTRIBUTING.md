# Contributing

Thanks for looking. Small, focused pull requests are the easiest to review and
the most likely to land.

## Setting up

Requires Python 3.11+ and FFmpeg on your `PATH`.

```bash
python -m venv .venv
# source .venv/bin/activate   (.venv\Scripts\activate on Windows)
pip install -e ".[dev]"
resumex doctor
pytest
```

## Before you open a pull request

```bash
ruff check .
pytest
```

Both are what CI runs, plus a wheel build. If you touched rendering, run the
integration test too — it renders a real MP4 and probes it:

```bash
pytest -m integration
```

## What a good change looks like

- **One thing at a time.** Behaviour change, refactor and formatting in separate
  commits, ideally separate PRs.
- **Tested at the seam that could break.** New config keys need a parsing test;
  new FFmpeg arguments need a `build_command` assertion. `build_command` is a
  pure function precisely so you can test it without running anything.
- **Offline by default.** No test may touch the network. A fixture in
  `tests/conftest.py` blocks sockets, so a stray call fails loudly. Stub external
  providers at their boundary.
- **Documented where it is true.** If a change makes the README wrong, fix the
  README in the same PR. Nothing in the docs should describe a feature that does
  not exist.
- **Errors that help.** Raise a `ResumexError` subclass with a `hint` saying what
  to do next, rather than letting a traceback reach the user.

## House conventions

- `pathlib.Path` everywhere, never string paths.
- Dataclasses for anything that crosses a module boundary; no untyped dicts
  between pipeline stages.
- All FFmpeg calls go through `resumex.rendering.ffmpeg`, always as an argument
  list, never through a shell.
- Terminal output stays ASCII — a legacy Windows console mangles anything else.
- Line length 100. Ruff decides the rest.

## Adding a provider

Sources, scorers, narrators and metadata generators are all interfaces with a
local, dependency-free implementation already behind them. To add another:

1. Implement the base class in the matching package.
2. Register it in that package's `get_*` factory.
3. Add its settings to `config.py` **and** to `EXAMPLE_CONFIG` in the same file
   — a test checks that `resumex.example.toml` still matches.
4. Make sure it degrades. If your provider needs a daemon, a key or a download,
   the pipeline must keep working when it is absent, and `resumex doctor` should
   report it as optional rather than broken.

## Things that will be turned down

- Anything that scrapes or downloads third-party media as default behaviour.
- Anti-bot evasion, fingerprint spoofing or rate-limit circumvention.
- Telemetry, analytics or phoning home.
- Publishing anything without an explicit request from the user.
- Claims about how content will perform.

## Reporting bugs

Use the issue templates. The output of `resumex doctor` and the command you ran
with `-v` answer most of the questions a maintainer would otherwise have to ask.
