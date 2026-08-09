from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from resumex.config import CONFIG_FILENAME, EXAMPLE_CONFIG, Config, Paths, RenderConfig
from resumex.exceptions import ConfigError

REPO_ROOT = Path(__file__).resolve().parents[2]


def write_config(directory: Path, body: str) -> Path:
    path = directory / CONFIG_FILENAME
    path.write_text(body, encoding="utf-8")
    return path


def test_defaults_apply_when_there_is_no_config_file(tmp_path: Path):
    config = Config.load(workspace=tmp_path)
    assert config.source_file is None
    assert config.render.resolution == (1080, 1920)
    assert config.narration.provider == "auto"
    assert config.scoring.provider == "none"
    assert config.youtube.privacy == "private"


def test_file_values_override_defaults(tmp_path: Path):
    write_config(tmp_path, '[render]\nfps = 24\ncrf = 26\n\n[narration]\nvoice = "am_adam"\n')
    config = Config.load(workspace=tmp_path)
    assert config.render.fps == 24
    assert config.render.crf == 26
    assert config.narration.voice == "am_adam"


def test_unknown_key_is_rejected_with_the_valid_ones_listed(tmp_path: Path):
    write_config(tmp_path, "[render]\nfpsss = 24\n")
    with pytest.raises(ConfigError) as exc:
        Config.load(workspace=tmp_path)
    assert "fpsss" in exc.value.message
    assert "fps" in (exc.value.hint or "")


def test_unknown_section_is_rejected(tmp_path: Path):
    write_config(tmp_path, "[rendering]\nfps = 24\n")
    with pytest.raises(ConfigError, match="rendering"):
        Config.load(workspace=tmp_path)


def test_workspace_key_is_not_mistaken_for_a_section(tmp_path: Path):
    write_config(tmp_path, 'workspace = "."\n[render]\nfps = 24\n')
    config = Config.load(workspace=tmp_path)
    assert config.render.fps == 24


def test_explicit_workspace_wins_over_the_file(tmp_path: Path):
    other = tmp_path / "elsewhere"
    other.mkdir()
    write_config(tmp_path, 'workspace = "./from-file"\n')
    config = Config.load(config_file=tmp_path / CONFIG_FILENAME, workspace=other)
    assert config.paths.workspace == other.resolve()


def test_relative_workspace_resolves_against_the_config_file(tmp_path: Path):
    nested = tmp_path / "conf"
    nested.mkdir()
    path = write_config(nested, 'workspace = "../data"\n')
    config = Config.load(config_file=path)
    assert config.paths.workspace == (tmp_path / "data").resolve()


def test_wrong_type_is_reported_against_the_key(tmp_path: Path):
    write_config(tmp_path, '[render]\nfps = "thirty"\n')
    with pytest.raises(ConfigError, match=r"render\.fps"):
        Config.load(workspace=tmp_path)


def test_malformed_toml_is_reported(tmp_path: Path):
    write_config(tmp_path, "[render\nfps = 30\n")
    with pytest.raises(ConfigError, match="not valid TOML"):
        Config.load(workspace=tmp_path)


def test_missing_explicit_config_file_is_an_error(tmp_path: Path):
    with pytest.raises(ConfigError, match="not found"):
        Config.load(config_file=tmp_path / "nope.toml")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"width": 1081},
        {"fps": 0},
        {"crf": 99},
        {"caption_position": 1.5},
        {"background_dim": -0.1},
        {"caption_max_words": 0},
    ],
)
def test_render_config_rejects_impossible_values(kwargs: dict):
    with pytest.raises(ConfigError):
        RenderConfig(**kwargs)


@pytest.mark.parametrize(
    ("section", "key", "value"),
    [
        ("narration", "provider", "espeak"),
        ("scoring", "provider", "magic"),
        ("metadata", "provider", "gpt"),
        ("youtube", "privacy", "everyone"),
        ("reddit", "listing", "controversial"),
    ],
)
def test_provider_names_are_validated(tmp_path: Path, section: str, key: str, value: str):
    write_config(tmp_path, f'[{section}]\n{key} = "{value}"\n')
    with pytest.raises(ConfigError):
        Config.load(workspace=tmp_path)


def test_environment_overrides_the_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    write_config(tmp_path, '[narration]\nvoice = "af_heart"\n')
    monkeypatch.setenv("RESUMEX_VOICE", "bm_george")
    monkeypatch.setenv("RESUMEX_FFMPEG", "/opt/ffmpeg")
    config = Config.load(workspace=tmp_path)
    assert config.narration.voice == "bm_george"
    assert config.tools.ffmpeg == "/opt/ffmpeg"


def test_paths_are_derived_from_one_workspace(tmp_path: Path):
    paths = Paths(workspace=tmp_path)
    assert paths.output == tmp_path / "output"
    assert paths.backgrounds == tmp_path / "backgrounds"
    assert paths.database == tmp_path / ".resumex" / "state.db"
    paths.ensure()
    assert all(directory.is_dir() for directory in paths.user_dirs())


def test_example_config_file_matches_the_one_init_writes():
    shipped = (REPO_ROOT / "resumex.example.toml").read_text(encoding="utf-8")
    assert shipped == EXAMPLE_CONFIG, "regenerate resumex.example.toml from config.EXAMPLE_CONFIG"


def test_example_config_parses_with_every_key_recognised(tmp_path: Path):
    tomllib.loads(EXAMPLE_CONFIG)  # syntactically valid
    write_config(tmp_path, EXAMPLE_CONFIG)
    config = Config.load(workspace=tmp_path)
    assert config.render.width == 1080
