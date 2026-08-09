from __future__ import annotations

import json
from pathlib import Path

import pytest

from resumex.config import Config, MetadataConfig, OllamaConfig, Paths, ScoringConfig
from resumex.metadata import generate_metadata
from resumex.metadata.fallback import build_title, credit, extract_tags, generate
from resumex.models import Story
from resumex.ollama import OllamaUnavailable
from resumex.scoring import get_scorer, passes
from resumex.scoring.heuristic import HeuristicScorer
from resumex.scoring.ollama import OllamaScorer

# -- scoring -------------------------------------------------------------


def test_heuristic_scoring_is_deterministic(story: Story):
    assert HeuristicScorer().score(story) == HeuristicScorer().score(story)


def test_heuristic_score_stays_on_the_scale(story: Story):
    score = HeuristicScorer().score(story)
    assert 0.0 <= score.overall <= 10.0
    assert set(score.components) == {"length", "structure", "voice", "hook"}
    assert all(0.0 <= value <= 10.0 for value in score.components.values())


def test_a_speakable_story_outscores_a_one_liner(story: Story):
    stub = Story(title="Hi", body="Yes.")
    assert HeuristicScorer().score(story).overall > HeuristicScorer().score(stub).overall


def test_over_long_stories_lose_length_points():
    long_story = Story(title="A long one", body=" ".join(["word"] * 2000))
    assert HeuristicScorer().score(long_story).components["length"] < 5.0


def test_first_person_writing_scores_higher_on_voice():
    personal = Story(title="T", body="I went home and my dog met me at my door. I was glad.")
    detached = Story(title="T", body="The subject returned home. The animal waited by the door.")
    scorer = HeuristicScorer()
    assert scorer.score(personal).components["voice"] > scorer.score(detached).components["voice"]


def test_scoring_is_off_by_default(tmp_path: Path):
    assert get_scorer(Config(paths=Paths(workspace=tmp_path))) is None


def test_get_scorer_honours_the_configured_provider(tmp_path: Path):
    config = Config(paths=Paths(workspace=tmp_path), scoring=ScoringConfig(provider="heuristic"))
    assert isinstance(get_scorer(config), HeuristicScorer)


def test_no_score_never_filters_a_story():
    assert passes(None, minimum=9.9)


def test_ollama_scorer_falls_back_when_the_daemon_is_down(story: Story, monkeypatch):
    scorer = OllamaScorer(OllamaConfig(enabled=True))
    monkeypatch.setattr(
        scorer.client, "generate", lambda *a, **k: (_ for _ in ()).throw(OllamaUnavailable("down"))
    )
    score = scorer.score(story)
    assert score.provider == "heuristic"


def test_ollama_scorer_falls_back_on_unusable_output(story: Story, monkeypatch):
    scorer = OllamaScorer(OllamaConfig(enabled=True))
    monkeypatch.setattr(scorer.client, "generate", lambda *a, **k: "not json at all")
    assert scorer.score(story).provider == "heuristic"


def test_ollama_scores_are_used_when_they_parse(story: Story, monkeypatch):
    payload = json.dumps({"length": 8, "structure": 9, "voice": 7, "hook": 10})
    scorer = OllamaScorer(OllamaConfig(enabled=True))
    monkeypatch.setattr(scorer.client, "generate", lambda *a, **k: payload)
    score = scorer.score(story)
    assert score.provider == "ollama"
    assert score.overall == pytest.approx(8.5)


# -- metadata ------------------------------------------------------------


def test_fallback_metadata_is_deterministic(story: Story):
    assert generate(story) == generate(story)


def test_fallback_metadata_needs_no_network(story: Story):
    metadata = generate(story)
    assert metadata.provider == "fallback"
    assert metadata.title
    assert metadata.description


def test_titles_are_truncated_on_a_word_boundary():
    title = build_title("word " * 60, limit=40)
    assert len(title) <= 40
    assert title.endswith("…")


def test_short_titles_are_left_alone():
    assert build_title("A short title") == "A short title"


def test_tags_skip_stopwords_and_short_words(story: Story):
    tags = extract_tags(story)
    assert tags
    assert all(len(tag) >= 4 for tag in tags)
    assert "the" not in tags
    assert "and" not in tags


def test_credit_line_reflects_what_is_known():
    with_both = Story(title="T", body="B", author="me", source_url="https://example.com/x")
    assert "me" in credit(with_both) and "example.com" in credit(with_both)
    assert credit(Story(title="T", body="B")) == ""


def test_description_carries_attribution_when_there_is_a_source():
    story = Story(
        title="T",
        body="One sentence. Two sentence. Three sentence.",
        source_url="https://example.com/x",
    )
    assert "https://example.com/x" in generate(story).description


def test_generate_metadata_uses_the_fallback_by_default(story: Story, tmp_path: Path):
    config = Config(paths=Paths(workspace=tmp_path))
    assert generate_metadata(story, config).provider == "fallback"


def test_ollama_metadata_degrades_to_the_deterministic_one(story: Story, tmp_path: Path, monkeypatch):
    config = Config(
        paths=Paths(workspace=tmp_path),
        metadata=MetadataConfig(provider="ollama"),
        ollama=OllamaConfig(enabled=True),
    )
    monkeypatch.setattr(
        "resumex.ollama.OllamaClient.generate",
        lambda *a, **k: (_ for _ in ()).throw(OllamaUnavailable("nope")),
    )
    metadata = generate_metadata(story, config)
    assert metadata.provider == "fallback"
    assert metadata.title == generate(story).title


def test_ollama_metadata_is_cleaned_of_model_scaffolding(story: Story, tmp_path: Path, monkeypatch):
    config = Config(
        paths=Paths(workspace=tmp_path),
        metadata=MetadataConfig(provider="ollama"),
        ollama=OllamaConfig(enabled=True),
    )
    monkeypatch.setattr(
        "resumex.ollama.OllamaClient.generate",
        lambda self, prompt, **k: 'Title: **A Cleaner Title**' if "title" in prompt.lower() else "A description.",
    )
    metadata = generate_metadata(story, config)
    assert metadata.title == "A Cleaner Title"
    assert metadata.provider == "ollama"
