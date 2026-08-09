"""``resumex doctor`` — what works, what does not, and what is simply optional.

A missing optional integration is reported as "not configured", never as an
error. The only thing that can actually stop you rendering is FFmpeg.
"""

from __future__ import annotations

import os
import platform
import sys
from dataclasses import dataclass
from pathlib import Path

from resumex import console
from resumex.config import CONFIG_FILENAME, Config
from resumex.exceptions import MissingDependencyError
from resumex.narration import kokoro as kokoro_module
from resumex.rendering import ffmpeg

MIN_PYTHON = (3, 11)


@dataclass(frozen=True, slots=True)
class Check:
    state: str  # "ok" | "warn" | "fail" | "skip"
    label: str
    note: str = ""

    @property
    def blocking(self) -> bool:
        return self.state == "fail"


def run_checks(config: Config) -> int:
    """Print the report and return the exit code the CLI should use."""
    console.heading("Resumex doctor")

    core = [*_environment(config), *_workspace(config), *_assets(config)]
    for check in core:
        console.status(check.state, check.label, check.note)

    optional = [*_speech(), *_ollama(config), *_reddit(config), *_youtube(config)]
    console.heading("Optional")
    for check in optional:
        console.status(check.state, check.label, check.note)

    blockers = [check for check in core if check.blocking]
    console.write()
    if blockers:
        console.error("Not ready to render.")
        for check in blockers:
            console.write(f"    {check.label}: {check.note}")
        if any("FFmpeg" in check.label or "ffprobe" in check.label for check in blockers):
            console.write(f"\n{ffmpeg.INSTALL_HINT}")
        return MissingDependencyError.exit_code

    console.success("Ready to render.  Try:  resumex demo")
    return 0


def _environment(config: Config) -> list[Check]:
    version = platform.python_version()
    python_ok = sys.version_info >= MIN_PYTHON
    checks = [
        Check(
            "ok" if python_ok else "fail",
            f"Python {version}",
            "" if python_ok else f"Resumex needs {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer",
        ),
        Check("ok", "Platform", f"{platform.system()} {platform.machine()}"),
    ]

    has_ffmpeg, has_ffprobe = ffmpeg.available(config.tools)
    if has_ffmpeg:
        banner = ffmpeg.version(config.tools.ffmpeg) or ""
        checks.append(Check("ok", "FFmpeg", banner.replace("ffmpeg version ", "")[:48]))
    else:
        checks.append(Check("fail", "FFmpeg", "not found on PATH"))

    checks.append(
        Check("ok", "ffprobe", "available")
        if has_ffprobe
        else Check("fail", "ffprobe", "not found on PATH")
    )
    return checks


def _workspace(config: Config) -> list[Check]:
    workspace = config.paths.workspace
    checks = [Check("ok", "Workspace", str(workspace))]

    if config.source_file is not None:
        checks.append(Check("ok", "Config", str(config.source_file)))
    else:
        checks.append(Check("skip", "Config", f"no {CONFIG_FILENAME} - using defaults"))

    writable = _writable(workspace)
    checks.append(
        Check("ok", "Write access", "workspace is writable")
        if writable
        else Check("fail", "Write access", f"cannot write to {workspace}")
    )

    for directory in config.paths.user_dirs():
        if directory.is_dir():
            count = sum(1 for _ in directory.iterdir())
            checks.append(Check("ok", f"{directory.name}/", f"{count} item(s)"))
        else:
            checks.append(Check("skip", f"{directory.name}/", "not created yet - run resumex init"))

    return checks


def _assets(config: Config) -> list[Check]:
    font = config.render.font
    if font.is_file():
        return [Check("ok", "Caption font", font.name)]
    return [Check("fail", "Caption font", f"missing: {font}")]


def _speech() -> list[Check]:
    if kokoro_module.is_available():
        return [Check("ok", "Speech (Kokoro)", "installed - weights download on first use")]
    return [
        Check("skip", "Speech (Kokoro)", 'not installed - pip install "resumex[tts]"'),
        Check("ok", "Silent narration", "available, so rendering still works"),
    ]


def _ollama(config: Config) -> list[Check]:
    if not config.ollama.enabled:
        return [Check("skip", "Ollama", "disabled (optional)")]

    from resumex.ollama import OllamaClient

    client = OllamaClient(config.ollama)
    if not client.is_available():
        return [Check("warn", "Ollama", f"enabled but not answering at {client.base_url}")]

    wanted = config.ollama.model.split(":")[0]
    if any(name.split(":")[0] == wanted for name in client.list_models()):
        return [Check("ok", "Ollama", f"{client.base_url} | model {config.ollama.model}")]
    return [
        Check(
            "warn",
            "Ollama",
            f"model {config.ollama.model} not pulled - ollama pull {config.ollama.model}",
        )
    ]


def _reddit(config: Config) -> list[Check]:
    if not config.reddit.enabled:
        return [Check("skip", "Reddit source", "disabled (optional)")]
    if not config.reddit.subreddits:
        return [Check("warn", "Reddit source", "enabled but reddit.subreddits is empty")]
    return [
        Check("ok", "Reddit source", f"{len(config.reddit.subreddits)} subreddit(s) configured")
    ]


def _youtube(config: Config) -> list[Check]:
    if not config.youtube.enabled:
        return [Check("skip", "YouTube upload", "disabled (optional)")]

    try:
        from resumex.upload.youtube import default_token_path, is_available
    except ImportError:  # pragma: no cover - defensive
        return [Check("warn", "YouTube upload", "upload module could not be imported")]

    if not is_available():
        return [
            Check("warn", "YouTube upload", 'libraries missing - pip install "resumex[youtube]"')
        ]

    secrets = config.youtube.client_secrets
    if secrets is None or not Path(secrets).is_file():
        return [Check("warn", "YouTube upload", "youtube.client_secrets is not set or not found")]

    token = config.youtube.token or default_token_path(config)
    if not Path(token).is_file():
        return [Check("warn", "YouTube upload", "not authorised yet - run resumex youtube-auth")]
    return [Check("ok", "YouTube upload", f"authorised | default visibility {config.youtube.privacy}")]


def _writable(directory: Path) -> bool:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".resumex-write-test"
        probe.write_text("", encoding="utf-8")
        probe.unlink()
    except OSError:
        return False
    return os.access(directory, os.W_OK)
