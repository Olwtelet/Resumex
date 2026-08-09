from __future__ import annotations

import pytest

from resumex.models import CaptionCue, Story, StoryScore, VideoMetadata


def test_story_normalises_whitespace_in_title():
    story = Story(title="  A   spaced   title \n", body="Body text.")
    assert story.title == "A spaced title"


@pytest.mark.parametrize("field", ["title", "body"])
def test_story_rejects_empty_fields(field: str):
    kwargs = {"title": "Title", "body": "Body"}
    kwargs[field] = "   "
    with pytest.raises(ValueError):
        Story(**kwargs)


def test_story_id_is_stable_and_derived_from_text():
    a = Story(title="Same", body="Same body.")
    b = Story(title="Same", body="Same body.")
    c = Story(title="Other", body="Same body.")
    assert a.id == b.id
    assert a.id != c.id
    assert len(a.id) == 16


def test_story_id_prefers_the_source_url():
    a = Story(title="One", body="Body.", source_url="https://example.com/x")
    b = Story(title="Two", body="Different body.", source_url="https://example.com/x")
    assert a.id == b.id


def test_narration_text_puts_a_stop_after_the_title():
    story = Story(title="No stop here", body="Body.")
    assert story.narration_text.startswith("No stop here. ")

    already = Story(title="Ends already?", body="Body.")
    assert already.narration_text.startswith("Ends already? ")


def test_sentences_splits_on_terminal_punctuation():
    story = Story(title="T", body="One. Two! Three? Four")
    assert story.sentences() == ["T.", "One.", "Two!", "Three?", "Four"]


def test_story_score_clamps_to_the_scale():
    assert StoryScore(overall=99).overall == 10.0
    assert StoryScore(overall=-4).overall == 0.0


def test_story_score_renders_its_components():
    score = StoryScore(overall=7.5, components={"hook": 8, "length": 7})
    assert str(score) == "7.5/10 (hook=8, length=7)"


def test_caption_cue_validates_the_highlight_index():
    with pytest.raises(ValueError):
        CaptionCue(words=("a", "b"), highlight_index=2, start=0, end=1)


def test_caption_cue_rejects_reversed_timing():
    with pytest.raises(ValueError):
        CaptionCue(words=("a",), highlight_index=0, start=2.0, end=1.0)


def test_video_metadata_round_trips_through_a_dict():
    metadata = VideoMetadata(
        title="T", description="D", tags=("a", "b"), provider="fallback", source_url=None
    )
    assert VideoMetadata.from_dict(metadata.to_dict()) == metadata
