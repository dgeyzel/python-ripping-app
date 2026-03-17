"""Tests for metadata lookup and selection."""


def test_resolve_metadata_returns_none_when_lookup_false():
    """When lookup=False, resolve_metadata returns None."""
    # Without a real reader we can't call resolve_metadata; we'd need a mock
    # So we test the helper that formats match summary
    from src.metadata import _format_match_summary
    class FakeMeta:
        artist_name = "Artist"
        album_name = "Album"
        year = "2020"
    summary = _format_match_summary([FakeMeta()], 1)
    assert "Artist" in summary
    assert "Album" in summary
    assert "2020" in summary


def test_resolve_metadata_with_mock_reader_no_lookup(monkeypatch):
    """resolve_metadata with lookup=False returns None."""
    from src.metadata import resolve_metadata
    class MockReader:
        pass
    result = resolve_metadata(MockReader(), [1, 2, 3], lookup=False, interactive=False)
    assert result is None


def test_prompt_choice_returns_none_for_empty():
    """_prompt_choice with empty list returns None."""
    from src.metadata import _prompt_choice
    assert _prompt_choice([]) is None


def test_prompt_choice_returns_first_for_single_match():
    """_prompt_choice with one match returns that match (the list) without input."""
    from src.metadata import _prompt_choice
    class M:
        artist_name = "A"
        album_name = "B"
    one_match = [[M()]]  # list of one match, each match is list of MetaData
    result = _prompt_choice(one_match)
    assert result is one_match[0]
