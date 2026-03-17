"""Tests for metadata lookup and selection."""

from src.metadata_types import MetaData


def test_resolve_metadata_returns_none_when_lookup_false():
    """When lookup=False, resolve_metadata returns None."""
    from src.metadata import _format_match_summary
    meta = MetaData(artist_name="Artist", album_name="Album", year="2020")
    summary = _format_match_summary([meta], 1)
    assert "Artist" in summary
    assert "Album" in summary
    assert "2020" in summary


def test_resolve_metadata_with_no_lookup():
    """resolve_metadata with lookup=False returns None."""
    from src.metadata import resolve_metadata
    result = resolve_metadata(
        "", [1, 2, 3], cue_toc=None, cue_leadout=None, lookup=False, interactive=False
    )
    assert result is None


def test_prompt_choice_returns_none_for_empty():
    """_prompt_choice with empty list returns None."""
    from src.metadata import _prompt_choice
    assert _prompt_choice([]) is None


def test_prompt_choice_returns_first_for_single_match():
    """_prompt_choice with one match returns that match without input."""
    from src.metadata import _prompt_choice
    one_match = [[MetaData(artist_name="A", album_name="B")]]
    result = _prompt_choice(one_match)
    assert result is one_match[0]
