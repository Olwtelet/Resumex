"""CLI smoke tests. Nothing here renders a video or touches the network."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from resumex.cli import build_parser, main
from resumex.config import CONFIG_FILENAME
from resumex.exceptions import ConfigError, ContentError, NotConfiguredError


def test_help_exits_cleanly():
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0


def test_version_reports_the_package_version(capsys: pytest.CaptureFixture):
    from resumex import __version__

    with pytest.raises(SystemExit):
        main(["--version"])
    assert __version__ in capsys.readouterr().out


def test_no_command_prints_help_and_succeeds(capsys: pytest.CaptureFixture):
    assert main([]) == 0
    assert "usage: resumex" in capsys.readouterr().out


def test_every_subcommand_has_a_handler_and_help():
    parser = build_parser()
    actions = [a for a in parser._actions if hasattr(a, "choices") and a.choices]
    subcommands = actions[0].choices
    assert set(subcommands) == {
        "init",
        "doctor",
        "demo",
        "render",
        "batch",
        "stats",
        "upload",
        "youtube-auth",
    }
    for name, sub in subcommands.items():
        assert sub.get_default("handler") is not None, f"{name} has no handler"


def test_init_creates_the_workspace_and_a_config(tmp_path: Path, capsys: pytest.CaptureFixture):
    assert main(["-w", str(tmp_path), "init"]) == 0
    assert (tmp_path / CONFIG_FILENAME).is_file()
    assert (tmp_path / "backgrounds").is_dir()
    assert (tmp_path / "output").is_dir()
    assert (tmp_path / "stories" / "sample.md").is_file()
    assert "Next" in capsys.readouterr().out


def test_init_does_not_overwrite_an_existing_config(tmp_path: Path):
    config = tmp_path / CONFIG_FILENAME
    config.write_text("# mine\n", encoding="utf-8")
    main(["-w", str(tmp_path), "init"])
    assert config.read_text(encoding="utf-8") == "# mine\n"


def test_init_force_overwrites(tmp_path: Path):
    config = tmp_path / CONFIG_FILENAME
    config.write_text("# mine\n", encoding="utf-8")
    main(["-w", str(tmp_path), "init", "--force"])
    assert "[render]" in config.read_text(encoding="utf-8")


def test_doctor_reports_optional_integrations_separately(
    tmp_path: Path, capsys: pytest.CaptureFixture
):
    main(["-w", str(tmp_path), "doctor"])
    out = capsys.readouterr().out
    assert "Resumex doctor" in out
    assert "Optional" in out
    assert "Ollama" in out and "disabled (optional)" in out


def test_doctor_exit_code_reflects_missing_ffmpeg(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
):
    monkeypatch.setenv("RESUMEX_FFMPEG", "definitely-not-here-xyz")
    monkeypatch.setenv("RESUMEX_FFPROBE", "definitely-not-here-xyz")
    code = main(["-w", str(tmp_path), "doctor"])
    assert code == 4
    assert "Not ready to render." in capsys.readouterr().err


def test_stats_works_on_an_empty_workspace(tmp_path: Path, capsys: pytest.CaptureFixture):
    assert main(["-w", str(tmp_path), "stats"]) == 0
    assert "videos rendered" in capsys.readouterr().out


def test_missing_story_file_exits_with_the_content_code(tmp_path: Path):
    assert main(["-w", str(tmp_path), "render", str(tmp_path / "nope.md")]) == ContentError.exit_code


def test_broken_config_exits_with_the_config_code(tmp_path: Path):
    (tmp_path / CONFIG_FILENAME).write_text("[render]\nfps = 'x'\n", encoding="utf-8")
    assert main(["-w", str(tmp_path), "stats"]) == ConfigError.exit_code


def test_errors_print_the_hint(tmp_path: Path, capsys: pytest.CaptureFixture):
    main(["-w", str(tmp_path), "render", str(tmp_path / "nope.md")])
    err = capsys.readouterr().err
    assert "not found" in err
    assert ".txt" in err


def test_upload_without_configuration_says_rendering_still_works(
    tmp_path: Path, capsys: pytest.CaptureFixture
):
    video = tmp_path / "v.mp4"
    video.write_bytes(b"not really a video")
    video.with_suffix(".metadata.json").write_text(
        json.dumps({"title": "T", "description": "D"}), encoding="utf-8"
    )
    code = main(["-w", str(tmp_path), "upload", str(video), "--yes"])
    assert code == NotConfiguredError.exit_code
    assert "Rendering still works normally" in capsys.readouterr().err


def test_upload_of_a_missing_file_is_a_content_error(tmp_path: Path):
    code = main(["-w", str(tmp_path), "upload", str(tmp_path / "gone.mp4"), "--yes"])
    assert code == ContentError.exit_code


def test_batch_from_an_unknown_source_is_rejected():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["batch", "--source", "twitter"])


def test_render_all_with_a_single_output_path_is_rejected(
    tmp_path: Path, capsys: pytest.CaptureFixture
):
    stories = tmp_path / "s.json"
    stories.write_text(
        json.dumps([{"title": "A", "body": "a"}, {"title": "B", "body": "b"}]), encoding="utf-8"
    )
    code = main(
        ["-w", str(tmp_path), "render", str(stories), "--all", "-o", str(tmp_path / "one.mp4")]
    )
    assert code == ContentError.exit_code
    assert "--output" in capsys.readouterr().err
