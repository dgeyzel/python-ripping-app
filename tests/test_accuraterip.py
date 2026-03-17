"""Tests for AccurateRip verification."""


def test_fetch_ar_matches_returns_empty_without_audiotools(monkeypatch):
    """When accuraterip module is missing, fetch_ar_matches returns empty dict."""
    from src import accuraterip
    monkeypatch.setattr(accuraterip, "ar_module", None)
    class MockReader:
        pass
    result = accuraterip.fetch_ar_matches(MockReader())
    assert result == {}


def test_verify_track_returns_not_verified_when_no_matches():
    """verify_track with no AR matches returns verified=False."""
    from src.accuraterip import verify_track
    result = verify_track(
        track_number=1,
        total_tracks=1,
        track_pcm_frames=1000,
        frame_lists=iter([]),
        ar_matches={},
    )
    assert result.verified is False
    assert result.confidence is None


def test_verify_track_returns_not_verified_when_ar_module_missing(monkeypatch):
    """When ar_module is None, verify_track returns VerifyResult(verified=False)."""
    from src import accuraterip
    monkeypatch.setattr(accuraterip, "ar_module", None)
    result = accuraterip.verify_track(
        track_number=1,
        total_tracks=1,
        track_pcm_frames=1000,
        frame_lists=iter([]),
        ar_matches={1: [(1, 12345, 67890)]},
    )
    assert result.verified is False
