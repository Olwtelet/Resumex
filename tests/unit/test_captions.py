from __future__ import annotations

from itertools import pairwise
from pathlib import Path

from resumex.captions.render import band_height, render_track, y_offset
from resumex.captions.timing import cues_from_chunks, word_timings
from resumex.config import RenderConfig
from resumex.models import NarrationChunk


def test_word_timings_cover_the_whole_span():
    timings = word_timings("one two three", 0.0, 3.0)
    assert len(timings) == 3
    assert timings[0][1] == 0.0
    assert abs(timings[-1][2] - 3.0) < 1e-6


def test_word_timings_give_longer_words_more_time():
    timings = word_timings("a considerable", 0.0, 4.0)
    short = timings[0][2] - timings[0][1]
    long = timings[1][2] - timings[1][1]
    assert long > short


def test_word_timings_of_empty_text_is_empty():
    assert word_timings("   ", 0.0, 1.0) == []


def test_word_timings_survive_a_zero_length_span():
    timings = word_timings("one two", 2.0, 2.0)
    assert [t[0] for t in timings] == ["one", "two"]


def test_one_cue_per_word_each_carrying_its_group(chunks):
    cues = cues_from_chunks(chunks, max_words=3, max_duration=5.0)
    words = [cue.words[cue.highlight_index] for cue in cues]
    assert words == ["The", "pier", "is", "still", "there.", "Someone", "left", "a", "fresh", "note."]


def test_groups_respect_the_word_limit():
    chunk = NarrationChunk(text="one two three four five six seven", start=0.0, end=7.0)
    cues = cues_from_chunks([chunk], max_words=3, max_duration=99.0)
    assert max(len(cue.words) for cue in cues) == 3


def test_groups_respect_the_duration_limit():
    chunk = NarrationChunk(text="one two three four five six", start=0.0, end=6.0)
    cues = cues_from_chunks([chunk], max_words=99, max_duration=2.0)
    assert all(cue.words for cue in cues)
    assert max(len(cue.words) for cue in cues) < 6


def test_groups_never_span_two_narration_chunks(chunks):
    cues = cues_from_chunks(chunks, max_words=99, max_duration=99.0)
    groups = {cue.words for cue in cues}
    assert len(groups) == 2


def test_cues_never_overlap(chunks):
    cues = cues_from_chunks(chunks, max_words=2, max_duration=1.0)
    for earlier, later in pairwise(cues):
        assert earlier.end <= later.start + 1e-6
        assert earlier.end > earlier.start


def test_no_chunks_means_no_cues():
    assert cues_from_chunks([]) == []


def test_caption_band_sits_inside_the_frame():
    config = RenderConfig()
    assert band_height(config) < config.height
    assert y_offset(config) >= 0
    assert y_offset(config) + band_height(config) <= config.height


def test_render_track_writes_a_frame_per_cue_plus_a_concat_file(tmp_path: Path, chunks):
    config = RenderConfig(width=270, height=480, font_size=24)
    cues = cues_from_chunks(chunks, max_words=3, max_duration=2.0)
    track = render_track(cues, config, tmp_path, total_duration=6.0)

    assert track is not None
    assert track.concat_file.is_file()
    assert track.width == 270
    assert len(list(tmp_path.glob("caption-0*.png"))) == len(cues)

    text = track.concat_file.read_text(encoding="utf-8")
    assert text.count("duration ") >= len(cues)
    # The last file is repeated so its duration is honoured by the concat demuxer.
    assert text.rstrip().splitlines()[-1].startswith("file ")


def test_render_track_pads_the_tail_so_the_overlay_covers_the_video(tmp_path: Path):
    config = RenderConfig(width=270, height=480, font_size=24)
    cues = cues_from_chunks(
        [NarrationChunk(text="short", start=0.0, end=1.0)], max_words=3, max_duration=2.0
    )
    track = render_track(cues, config, tmp_path, total_duration=10.0)
    assert track is not None
    durations = [
        float(line.split()[1])
        for line in track.concat_file.read_text(encoding="utf-8").splitlines()
        if line.startswith("duration ")
    ]
    assert sum(durations) >= 9.9


def test_render_track_returns_none_without_cues(tmp_path: Path):
    assert render_track([], RenderConfig(), tmp_path, 5.0) is None


def test_concat_paths_are_posix_and_absolute(tmp_path: Path, chunks):
    config = RenderConfig(width=270, height=480, font_size=24)
    cues = cues_from_chunks(chunks, max_words=4, max_duration=2.0)
    track = render_track(cues, config, tmp_path, total_duration=5.0)
    assert track is not None
    for line in track.concat_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("file "):
            assert "\\" not in line
            assert line.startswith("file '")
