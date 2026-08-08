"""환경변수 기반 설정 로딩.

키는 로컬 `.env`와 GitHub Actions Secrets에만 존재하며 (NFR-3),
누락 시 조용한 기본값 대신 ConfigError로 즉시 실패한다.
"""

from __future__ import annotations

import os
import ssl
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class ConfigError(RuntimeError):
    """필수 설정이 없거나 잘못된 경우."""


def ensure_ssl_certificates() -> None:
    """Mac python.org 배포판이 시스템 인증서를 쓰지 않는 문제를 보정한다.

    SSL_CERT_FILE이 이미 지정돼 있으면 아무것도 하지 않는다
    (GitHub Actions Ubuntu 환경은 이 보정이 필요 없다).
    """
    if os.environ.get("SSL_CERT_FILE"):
        return
    try:
        import certifi
    except ImportError:  # pragma: no cover - certifi는 requirements에 포함
        return
    os.environ["SSL_CERT_FILE"] = certifi.where()

    def _context(*args: object, **kwargs: object) -> ssl.SSLContext:
        return ssl.create_default_context(cafile=certifi.where())

    ssl._create_default_https_context = _context


def _require(name: str) -> str:
    """환경변수를 읽되 비어 있으면 ConfigError를 던진다."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(
            f"필수 환경변수 {name} 가 설정되지 않았습니다. .env 또는 Actions Secrets를 확인하세요."
        )
    return value


@dataclass(frozen=True)
class Settings:
    """파이프라인 실행에 필요한 설정값.

    Attributes:
        youtube_api_key: YouTube Data API v3 키.
        supabase_url: Supabase 프로젝트 URL (끝 슬래시 제거됨).
        supabase_service_key: RLS를 우회하는 service key — 파이프라인 전용.
    """

    youtube_api_key: str = field(repr=False)
    supabase_url: str
    supabase_service_key: str = field(repr=False)

    @classmethod
    def from_env(cls, *, load_dotenv_file: bool = False) -> Settings:
        """환경변수에서 설정을 읽는다.

        Args:
            load_dotenv_file: True면 프로젝트 루트의 `.env`를 먼저 읽어들인다.
                테스트에서는 실제 키가 섞이지 않도록 False(기본값)로 둔다.

        Returns:
            채워진 Settings 인스턴스.

        Raises:
            ConfigError: 필수 환경변수가 비어 있는 경우.
        """
        if load_dotenv_file:
            load_dotenv(PROJECT_ROOT / ".env")
        return cls(
            youtube_api_key=_require("YOUTUBE_API_KEY"),
            supabase_url=_require("SUPABASE_URL").rstrip("/"),
            supabase_service_key=_require("SUPABASE_SERVICE_KEY"),
        )
