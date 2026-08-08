"""설정 로딩 테스트 — 키는 환경변수에서만 오고, 누락 시 명확히 실패해야 한다 (NFR-3)."""

import pytest

from app.config import ConfigError, Settings


def test_config_load_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """필수 환경변수가 모두 있으면 Settings가 값을 그대로 담는다."""
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-yt-key")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-service-key")

    settings = Settings.from_env()

    assert settings.youtube_api_key == "test-yt-key"
    assert settings.supabase_url == "https://example.supabase.co"
    assert settings.supabase_service_key == "test-service-key"


def test_config_missing_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """필수 환경변수가 없으면 ConfigError로 즉시 실패한다 (조용한 기본값 금지)."""
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-service-key")
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)

    with pytest.raises(ConfigError, match="YOUTUBE_API_KEY"):
        Settings.from_env()


def test_config_url_trailing_slash_removed(monkeypatch: pytest.MonkeyPatch) -> None:
    """SUPABASE_URL 끝의 슬래시는 제거한다 (REST 경로 조합 시 이중 슬래시 방지)."""
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-yt-key")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co/")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-service-key")

    assert Settings.from_env().supabase_url == "https://example.supabase.co"


def test_config_repr_hides_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    """로그·예외 출력에 키가 새지 않아야 한다 (NFR-3)."""
    monkeypatch.setenv("YOUTUBE_API_KEY", "super-secret-yt")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "super-secret-service")

    rendered = repr(Settings.from_env())

    assert "super-secret-yt" not in rendered
    assert "super-secret-service" not in rendered
    assert "example.supabase.co" in rendered
