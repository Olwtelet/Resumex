"""Configuration: one place that decides every setting and every path.

Precedence, lowest to highest: built-in defaults, then ``resumex.toml``, then
``RESUMEX_*`` environment variables, then whatever the CLI passes explicitly.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field, fields, replace
from pathlib import Path
from typing import Any

from resumex.exceptions import ConfigError

CONFIG_FILENAME = "resumex.toml"

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
BUNDLED_FONT = ASSETS_DIR / "fonts" / "NotoSans-Bold.ttf"
BUNDLED_DEMO_STORY = ASSETS_DIR / "stories" / "demo.md"
BUNDLED_SAMPLE_STORY = ASSETS_DIR / "stories" / "sample.md"


@dataclass(frozen=True, slots=True)
class Paths:
    """Every directory Resumex reads from or writes to."""

    workspace: Path

    @property
    def backgrounds(self) -> Path:
        return self.workspace / "backgrounds"

    @property
    def stories(self) -> Path:
        return self.workspace / "stories"

    @property
    def output(self) -> Path:
        return self.workspace / "output"

    @property
    def internal(self) -> Path:
        return self.workspace / ".resumex"

    @property
    def database(self) -> Path:
        return self.internal / "state.db"

    @property
    def temp(self) -> Path:
        return self.internal / "tmp"

    def user_dirs(self) -> tuple[Path, ...]:
        return (self.backgrounds, self.stories, self.output)

    def ensure(self) -> None:
        for path in (*self.user_dirs(), self.internal, self.temp):
            path.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True, slots=True)
class ToolsConfig:
    """External executables. ``None`` means "look it up on PATH"."""

    ffmpeg: str = "ffmpeg"
    ffprobe: str = "ffprobe"


@dataclass(frozen=True, slots=True)
class RenderConfig:
    width: int = 1080
    height: int = 1920
    fps: int = 30
    crf: int = 20
    preset: str = "medium"
    audio_bitrate: str = "192k"
    font_path: Path | None = None
    font_size: int = 84
    caption_max_words: int = 4
    caption_max_duration: float = 2.2
    caption_stroke_width: int = 8
    caption_text_color: str = "#FFFFFF"
    caption_highlight_color: str = "#FFC83D"
    caption_stroke_color: str = "#101014"
    caption_position: float = 0.62
    background_dim: float = 0.35

    def __post_init__(self) -> None:
        if self.width % 2 or self.height % 2:
            raise ConfigError(
                "render.width and render.height must both be even (H.264 requires it)"
            )
        if self.width <= 0 or self.height <= 0:
            raise ConfigError("render.width and render.height must be positive")
        if not 1 <= self.fps <= 120:
            raise ConfigError("render.fps must be between 1 and 120")
        if not 0 <= self.crf <= 51:
            raise ConfigError("render.crf must be between 0 and 51")
        if not 0.0 <= self.caption_position <= 1.0:
            raise ConfigError("render.caption_position must be between 0.0 and 1.0")
        if not 0.0 <= self.background_dim <= 1.0:
            raise ConfigError("render.background_dim must be between 0.0 and 1.0")
        if self.caption_max_words < 1:
            raise ConfigError("render.caption_max_words must be at least 1")

    @property
    def font(self) -> Path:
        return self.font_path or BUNDLED_FONT

    @property
    def resolution(self) -> tuple[int, int]:
        return (self.width, self.height)


@dataclass(frozen=True, slots=True)
class NarrationConfig:
    provider: str = "auto"
    voice: str = "af_heart"
    lang_code: str = "a"
    speed: float = 1.0
    words_per_minute: int = 165

    def __post_init__(self) -> None:
        allowed = {"auto", "kokoro", "silent"}
        if self.provider not in allowed:
            raise ConfigError(
                f"narration.provider must be one of {sorted(allowed)}, got {self.provider!r}"
            )
        if self.words_per_minute < 40:
            raise ConfigError("narration.words_per_minute must be at least 40")


@dataclass(frozen=True, slots=True)
class ScoringConfig:
    provider: str = "none"
    min_overall: float = 0.0

    def __post_init__(self) -> None:
        allowed = {"none", "heuristic", "ollama"}
        if self.provider not in allowed:
            raise ConfigError(
                f"scoring.provider must be one of {sorted(allowed)}, got {self.provider!r}"
            )


@dataclass(frozen=True, slots=True)
class MetadataConfig:
    provider: str = "fallback"
    max_title_length: int = 100

    def __post_init__(self) -> None:
        allowed = {"fallback", "ollama"}
        if self.provider not in allowed:
            raise ConfigError(
                f"metadata.provider must be one of {sorted(allowed)}, got {self.provider!r}"
            )


@dataclass(frozen=True, slots=True)
class OllamaConfig:
    enabled: bool = False
    url: str = "http://localhost:11434"
    model: str = "llama3.2"
    timeout: float = 120.0


@dataclass(frozen=True, slots=True)
class YouTubeConfig:
    enabled: bool = False
    client_secrets: Path | None = None
    token: Path | None = None
    privacy: str = "private"
    category_id: str = "22"
    made_for_kids: bool = False

    def __post_init__(self) -> None:
        allowed = {"private", "unlisted", "public"}
        if self.privacy not in allowed:
            raise ConfigError(
                f"youtube.privacy must be one of {sorted(allowed)}, got {self.privacy!r}"
            )


@dataclass(frozen=True, slots=True)
class RedditConfig:
    enabled: bool = False
    subreddits: tuple[str, ...] = ()
    listing: str = "top"
    time_filter: str = "month"
    limit: int = 25
    min_chars: int = 400
    max_chars: int = 4000
    user_agent: str = "resumex/0.1 (local-first short-form video tool)"

    def __post_init__(self) -> None:
        allowed = {"hot", "new", "top", "rising"}
        if self.listing not in allowed:
            raise ConfigError(
                f"reddit.listing must be one of {sorted(allowed)}, got {self.listing!r}"
            )


@dataclass(frozen=True, slots=True)
class Config:
    paths: Paths
    tools: ToolsConfig = field(default_factory=ToolsConfig)
    render: RenderConfig = field(default_factory=RenderConfig)
    narration: NarrationConfig = field(default_factory=NarrationConfig)
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    metadata: MetadataConfig = field(default_factory=MetadataConfig)
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    youtube: YouTubeConfig = field(default_factory=YouTubeConfig)
    reddit: RedditConfig = field(default_factory=RedditConfig)
    source_file: Path | None = None

    @classmethod
    def load(cls, config_file: Path | None = None, workspace: Path | None = None) -> Config:
        """Build a Config from the TOML file, if there is one, plus the environment."""
        resolved = _resolve_config_file(config_file, workspace)
        data = _read_toml(resolved) if resolved else {}

        # Always consume the key, even when an override wins, so the strict
        # unknown-section check below does not trip over it.
        raw_ws = _pop_scalar(data, "workspace")
        ws = workspace or _env_path("RESUMEX_WORKSPACE")
        if ws is None and raw_ws is not None:
            base = resolved.parent if resolved else Path.cwd()
            ws = (base / str(raw_ws)).resolve()
        if ws is None:
            ws = Path.cwd()

        config = cls(
            paths=Paths(workspace=Path(ws).resolve()),
            tools=_section(ToolsConfig, data, "tools"),
            render=_section(RenderConfig, data, "render"),
            narration=_section(NarrationConfig, data, "narration"),
            scoring=_section(ScoringConfig, data, "scoring"),
            metadata=_section(MetadataConfig, data, "metadata"),
            ollama=_section(OllamaConfig, data, "ollama"),
            youtube=_section(YouTubeConfig, data, "youtube"),
            reddit=_section(RedditConfig, data, "reddit"),
            source_file=resolved,
        )
        _reject_unknown_sections(data)
        return _apply_env(config)


EXAMPLE_CONFIG = '''\
# Resumex configuration. Every key below is optional - delete anything you do
# not want to change and Resumex uses the built-in default.
#
# Written by `resumex init`. The canonical copy lives in resumex.example.toml.

# Where Resumex reads and writes. Relative paths resolve against this file.
workspace = "."

[render]
width = 1080
height = 1920
fps = 30
crf = 20                     # 0 = lossless, 51 = worst. 18-24 is a sane range.
preset = "medium"            # x264 speed/size tradeoff: ultrafast .. veryslow
audio_bitrate = "192k"
font_size = 84
caption_max_words = 4        # words shown on screen at once
caption_max_duration = 2.2   # seconds a caption group may span
caption_position = 0.62      # 0.0 = top of frame, 1.0 = bottom
background_dim = 0.35        # 0.0 = untouched, 1.0 = black
# font_path = "/path/to/YourFont.ttf"   # defaults to the bundled Noto Sans Bold

[narration]
provider = "auto"            # "auto" | "kokoro" | "silent"
voice = "af_heart"           # Kokoro voice id
lang_code = "a"              # Kokoro language: a = American English
speed = 1.0
words_per_minute = 165       # pacing used by the silent narrator

[scoring]
provider = "none"            # "none" | "heuristic" | "ollama"
min_overall = 0.0            # skip stories scoring below this (0-10)

[metadata]
provider = "fallback"        # "fallback" = deterministic, no model | "ollama"
max_title_length = 100

# Optional. Nothing in the default pipeline needs a language model.
[ollama]
enabled = false
url = "http://localhost:11434"
model = "llama3.2"
timeout = 120.0

# Optional. Rendering works exactly the same with this switched off.
[youtube]
enabled = false
privacy = "private"          # "private" | "unlisted" | "public"
category_id = "22"
made_for_kids = false
# client_secrets = "./client_secret.json"
# token = "./.resumex/youtube-token.json"

# Optional. Reads Reddit's public JSON listings; no browser, no credentials.
[reddit]
enabled = false
subreddits = []
listing = "top"              # "hot" | "new" | "top" | "rising"
time_filter = "month"
limit = 25
min_chars = 400
max_chars = 4000

# Override these if ffmpeg is not on PATH.
[tools]
ffmpeg = "ffmpeg"
ffprobe = "ffprobe"
'''


def _resolve_config_file(config_file: Path | None, workspace: Path | None) -> Path | None:
    if config_file is not None:
        path = Path(config_file).expanduser()
        if not path.is_file():
            raise ConfigError(
                f"Configuration file not found: {path}",
                hint="Run `resumex init` to create one, or drop the --config flag.",
            )
        return path.resolve()

    from_env = _env_path("RESUMEX_CONFIG")
    if from_env is not None:
        if not from_env.is_file():
            raise ConfigError(f"RESUMEX_CONFIG points at a file that does not exist: {from_env}")
        return from_env

    candidate = (workspace or Path.cwd()) / CONFIG_FILENAME
    return candidate.resolve() if candidate.is_file() else None


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path} is not valid TOML: {exc}") from exc
    except OSError as exc:
        raise ConfigError(f"Could not read {path}: {exc}") from exc


def _pop_scalar(data: dict[str, Any], key: str) -> Any:
    value = data.get(key)
    if value is not None and not isinstance(value, dict):
        data.pop(key)
    return value


def _section(cls: type, data: dict[str, Any], name: str) -> Any:
    raw = data.pop(name, {})
    if not isinstance(raw, dict):
        raise ConfigError(f"[{name}] must be a table in {CONFIG_FILENAME}")

    known = {f.name: f for f in fields(cls)}
    unknown = sorted(set(raw) - set(known))
    if unknown:
        raise ConfigError(
            f"Unknown key(s) in [{name}]: {', '.join(unknown)}",
            hint=f"Valid keys are: {', '.join(sorted(known))}",
        )

    kwargs: dict[str, Any] = {}
    for key, value in raw.items():
        kwargs[key] = _coerce(known[key].type, value, f"{name}.{key}")
    return cls(**kwargs)


def _coerce(annotation: Any, value: Any, label: str) -> Any:
    text = annotation if isinstance(annotation, str) else getattr(annotation, "__name__", "")
    if "Path" in text:
        return Path(str(value)).expanduser()
    if "tuple" in text:
        if not isinstance(value, (list, tuple)):
            raise ConfigError(f"{label} must be a list")
        return tuple(str(v) for v in value)
    if text.startswith("bool"):
        if not isinstance(value, bool):
            raise ConfigError(f"{label} must be true or false")
        return value
    if text.startswith("int"):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigError(f"{label} must be an integer")
        return value
    if text.startswith("float"):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ConfigError(f"{label} must be a number")
        return float(value)
    return value


def _reject_unknown_sections(data: dict[str, Any]) -> None:
    if data:
        raise ConfigError(
            f"Unknown section(s) in {CONFIG_FILENAME}: {', '.join(sorted(data))}",
            hint="See resumex.example.toml for the full set of supported sections.",
        )


def _env_path(name: str) -> Path | None:
    raw = os.environ.get(name)
    return Path(raw).expanduser().resolve() if raw else None


def _apply_env(config: Config) -> Config:
    """Environment variables win over the file, for CI and container use."""
    tools = config.tools
    if ffmpeg := os.environ.get("RESUMEX_FFMPEG"):
        tools = replace(tools, ffmpeg=ffmpeg)
    if ffprobe := os.environ.get("RESUMEX_FFPROBE"):
        tools = replace(tools, ffprobe=ffprobe)

    narration = config.narration
    if voice := os.environ.get("RESUMEX_VOICE"):
        narration = replace(narration, voice=voice)
    if provider := os.environ.get("RESUMEX_NARRATION_PROVIDER"):
        narration = replace(narration, provider=provider)

    ollama = config.ollama
    if url := os.environ.get("RESUMEX_OLLAMA_URL"):
        ollama = replace(ollama, url=url, enabled=True)
    if model := os.environ.get("RESUMEX_OLLAMA_MODEL"):
        ollama = replace(ollama, model=model)

    return replace(config, tools=tools, narration=narration, ollama=ollama)
