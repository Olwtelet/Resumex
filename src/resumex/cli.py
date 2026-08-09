"""The ``resumex`` command line.

Exit codes
----------
0   success                     5   optional integration not configured
1   unexpected failure          6   unusable input
2   bad command-line usage      7   narration failed
3   bad configuration           8   rendering failed
4   missing dependency          9   upload failed
                                10  content source unavailable
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

from resumex import __version__, console
from resumex.config import (
    BUNDLED_DEMO_STORY,
    BUNDLED_SAMPLE_STORY,
    CONFIG_FILENAME,
    EXAMPLE_CONFIG,
    Config,
)
from resumex.doctor import run_checks
from resumex.exceptions import ContentError, ResumexError
from resumex.logging import configure
from resumex.models import Story
from resumex.pipeline import Pipeline, PipelineResult, read_metadata
from resumex.sources import get_source, load_file
from resumex.state import StateStore

EPILOG = """\
examples:
  resumex init                       set up the current directory
  resumex doctor                     check what is and is not available
  resumex demo                       render a sample video, offline
  resumex render story.md            render your own story
  resumex render notes.json --all    render every story in a JSON file
  resumex batch ./stories --limit 5  render a directory of stories
  resumex upload output/story.mp4    publish (private by default)
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="resumex",
        description="Turn text stories into short-form videos, locally.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"resumex {__version__}")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="show debug logs and full tracebacks"
    )
    parser.add_argument(
        "-c", "--config", type=Path, metavar="FILE", help=f"path to {CONFIG_FILENAME}"
    )
    parser.add_argument(
        "-w", "--workspace", type=Path, metavar="DIR", help="directory Resumex reads and writes in"
    )

    sub = parser.add_subparsers(dest="command", metavar="<command>")

    init = sub.add_parser("init", help="create the workspace and a config file")
    init.add_argument("--force", action="store_true", help="overwrite an existing config file")
    init.set_defaults(handler=cmd_init)

    doctor = sub.add_parser("doctor", help="check the environment and report what works")
    doctor.set_defaults(handler=cmd_doctor)

    demo = sub.add_parser("demo", help="render a short sample video with no setup")
    demo.add_argument("-o", "--output", type=Path, help="where to write the demo MP4")
    demo.add_argument(
        "--tts",
        action="store_true",
        help="use real speech (needs the tts extra; downloads a model)",
    )
    demo.set_defaults(handler=cmd_demo)

    render = sub.add_parser("render", help="render one story file")
    render.add_argument("story", type=Path, help="a .txt, .md or .json file")
    render.add_argument("-o", "--output", type=Path, help="output MP4 path")
    render.add_argument("-b", "--background", type=Path, help="background video or image to use")
    render.add_argument("--all", action="store_true", help="render every story in the file")
    render.add_argument("--silent", action="store_true", help="skip speech synthesis")
    render.set_defaults(handler=cmd_render)

    batch = sub.add_parser("batch", help="render many stories")
    batch.add_argument(
        "path", type=Path, nargs="?", help="directory of story files (default: <workspace>/stories)"
    )
    batch.add_argument(
        "--source",
        default="local",
        choices=("local", "reddit"),
        help="where stories come from",
    )
    batch.add_argument("-n", "--limit", type=int, help="stop after this many videos")
    batch.add_argument("--redo", action="store_true", help="re-render stories already rendered")
    batch.set_defaults(handler=cmd_batch)

    stats = sub.add_parser("stats", help="show what this workspace has produced")
    stats.set_defaults(handler=cmd_stats)

    upload = sub.add_parser("upload", help="publish a rendered video to YouTube")
    upload.add_argument("video", type=Path, help="path to the MP4")
    upload.add_argument(
        "--privacy",
        choices=("private", "unlisted", "public"),
        help="visibility (default: whatever youtube.privacy says, normally private)",
    )
    upload.add_argument("--title", help="override the title from the metadata sidecar")
    upload.add_argument("--description", help="override the description")
    upload.add_argument("-y", "--yes", action="store_true", help="do not ask for confirmation")
    upload.set_defaults(handler=cmd_upload)

    auth = sub.add_parser("youtube-auth", help="authorise YouTube uploads in a browser")
    auth.set_defaults(handler=cmd_youtube_auth)

    return parser


# -- commands ------------------------------------------------------------


def cmd_init(args: argparse.Namespace, config: Config) -> int:
    config.paths.ensure()
    console.heading(f"Workspace ready at {config.paths.workspace}")
    for directory in config.paths.user_dirs():
        console.status("ok", directory.name + "/", _dir_purpose(directory.name))

    target = config.paths.workspace / CONFIG_FILENAME
    if target.exists() and not args.force:
        console.status("skip", CONFIG_FILENAME, "already exists - pass --force to overwrite")
    else:
        target.write_text(EXAMPLE_CONFIG, encoding="utf-8")
        console.status("ok", CONFIG_FILENAME, "written with commented defaults")

    sample = config.paths.stories / "sample.md"
    if not sample.exists():
        sample.write_text(BUNDLED_SAMPLE_STORY.read_text(encoding="utf-8"), encoding="utf-8")
        console.status("ok", "stories/sample.md", "a story to try")

    console.heading("Next")
    console.step("resumex doctor      check FFmpeg is installed")
    console.step("resumex demo        render a sample video")
    console.step("resumex render stories/sample.md")
    return 0


def _dir_purpose(name: str) -> str:
    return {
        "backgrounds": "drop your own footage or stills here",
        "stories": "put .txt, .md or .json stories here",
        "output": "rendered videos land here",
    }.get(name, "")


def cmd_doctor(args: argparse.Namespace, config: Config) -> int:
    return run_checks(config)


def cmd_demo(args: argparse.Namespace, config: Config) -> int:
    output = args.output or (config.paths.workspace / "demo_output" / "resumex-demo.mp4")
    # A demo should finish quickly; quality settings stay untouched for real renders.
    demo_config = replace(config, render=replace(config.render, preset="veryfast"))

    console.heading("Resumex demo")
    console.detail(f"story:      {BUNDLED_DEMO_STORY.name} (bundled)")
    console.detail(f"narration:  {'Kokoro speech' if args.tts else 'silent (no model download)'}")
    console.detail("background: generated locally")
    console.write()

    story = load_file(BUNDLED_DEMO_STORY)[0]
    demo_config.paths.temp.mkdir(parents=True, exist_ok=True)

    with Pipeline(demo_config, progress=console.step, force_silent=not args.tts) as pipeline:
        result = pipeline.render_story(story, output=output)

    _report(result)
    if result.render.duration > 0 and not args.tts:
        console.write()
        console.detail("The demo track is silent. Add speech with:  resumex demo --tts")
    return 0


def cmd_render(args: argparse.Namespace, config: Config) -> int:
    stories = load_file(args.story)
    if not args.all:
        stories = stories[:1]

    if args.output and len(stories) > 1:
        raise ContentError(
            "--output takes a single file but --all renders several videos.",
            hint="Drop --output and the videos go to the output/ directory.",
        )

    config.paths.ensure()
    with StateStore(config.paths.database) as store, Pipeline(
        config, store=store, progress=console.step, force_silent=args.silent
    ) as pipeline:
        for index, story in enumerate(stories, 1):
            if len(stories) > 1:
                console.heading(f"[{index}/{len(stories)}] {story.title[:60]}")
            result = pipeline.render_story(
                story, output=args.output, background=args.background
            )
            _report(result)
    return 0


def cmd_batch(args: argparse.Namespace, config: Config) -> int:
    config.paths.ensure()
    source = get_source(args.source, config, args.path)

    console.heading(f"Rendering from the {source.name} source")
    failures: list[tuple[Story, Exception]] = []

    with StateStore(config.paths.database) as store, Pipeline(
        config, store=store, progress=console.step
    ) as pipeline:
        results = pipeline.render_many(
            source.stories(),
            limit=args.limit,
            skip_seen=not args.redo,
            on_error=lambda story, exc: failures.append((story, exc)),
        )
        for result in results:
            console.success(f"{result.render.path.name}  ({result.render.duration:.1f}s)")

    console.heading(f"Rendered {len(results)} video(s)")
    for story, exc in failures:
        console.warn(f"{story.title[:50]}: {exc}")
    if not results and not failures:
        console.detail(
            "Nothing to do - every story here has already been rendered (--redo forces it)."
        )
    return 0 if results or not failures else 1


def cmd_stats(args: argparse.Namespace, config: Config) -> int:
    config.paths.internal.mkdir(parents=True, exist_ok=True)
    with StateStore(config.paths.database) as store:
        stats = store.stats()
        console.heading(f"Resumex - {config.paths.workspace}")
        console.status("ok", "stories seen", str(stats.stories))
        console.status("ok", "videos rendered", str(stats.renders))
        console.status("ok", "videos uploaded", str(stats.uploads))

        recent = store.recent_renders(5)
        if recent:
            console.heading("Recent renders")
            console.table(
                [
                    (
                        Path(row["path"]).name,
                        f"{row['duration']:.1f}s",
                        (row["title"] or "")[:44],
                    )
                    for row in recent
                ],
                headers=("file", "length", "story"),
            )
    return 0


def cmd_upload(args: argparse.Namespace, config: Config) -> int:
    from resumex.upload.youtube import YouTubeUploader

    video = args.video
    if not video.is_file():
        raise ContentError(f"No such video: {video}")

    title = args.title
    description = args.description
    if not title or not description:
        sidecar = read_metadata(video)
        title = title or str(sidecar.get("title") or video.stem)
        description = description or str(sidecar.get("description") or "")

    privacy = args.privacy or config.youtube.privacy
    uploader = YouTubeUploader(config)

    console.heading("Upload to YouTube")
    console.status("ok", "file", f"{video.name} ({video.stat().st_size / 1e6:.1f} MB)")
    console.status("ok", "title", title)
    console.status("ok" if privacy != "public" else "warn", "visibility", privacy)
    if privacy == "public":
        console.warn("This video will be visible to everyone as soon as it finishes processing.")

    if not args.yes:
        answer = input("\nUpload now? [y/N]: ").strip().lower()
        if answer != "y":
            console.write("Cancelled. Nothing was uploaded.")
            return 0

    result = uploader.upload(video, title=title, description=description, privacy=privacy)

    config.paths.internal.mkdir(parents=True, exist_ok=True)
    with StateStore(config.paths.database) as store:
        store.record_upload(video, result.video_id, result.url, privacy)

    console.write()
    console.success(f"Uploaded as {privacy}: {result.url}")
    console.detail(f"Your local file is untouched: {video}")
    return 0


def cmd_youtube_auth(args: argparse.Namespace, config: Config) -> int:
    from resumex.upload.youtube import YouTubeUploader

    console.heading("YouTube authorisation")
    console.detail("A browser window will open so you can grant upload access.")
    token = YouTubeUploader(config).authorize()
    console.success(f"Token saved to {token}")
    console.detail("This file is a credential. It is git-ignored - keep it that way.")
    return 0


# -- helpers -------------------------------------------------------------


def _report(result: PipelineResult) -> None:
    render = result.render
    console.write()
    console.success(f"{render.path}")
    console.detail(
        f"{render.width}x{render.height} | {render.duration:.1f}s | "
        f"{'audio' if render.has_audio else 'no audio'} | narrated by {result.narration_provider}"
    )
    console.detail(f"title:    {result.metadata.title}")
    console.detail(f"metadata: {result.metadata_path.name}")
    if result.score is not None:
        console.detail(f"score:    {result.score}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    configure(args.verbose)

    try:
        config = Config.load(config_file=args.config, workspace=args.workspace)
        return int(args.handler(args, config))
    except ResumexError as exc:
        console.write(stream=sys.stderr)
        console.error(exc.message)
        if exc.hint:
            console.write(f"\n{exc.hint}\n", stream=sys.stderr)
        if args.verbose:
            raise
        return exc.exit_code
    except KeyboardInterrupt:
        console.write("\nInterrupted.", stream=sys.stderr)
        return 130
    except (OSError, ValueError) as exc:
        console.error(str(exc))
        if args.verbose:
            raise
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
