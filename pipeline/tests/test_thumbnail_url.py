"""썸네일 URL 검증 테스트 (보안 리뷰 2026-08-08).

썸네일은 브라우저의 `<img src>` 로 그대로 들어간다. 저장 단계에서 호스트를 검증하지 않으면,
DB에 쓸 수 있게 된 공격자가 임의 호스트를 넣어 방문자 IP·Referer를 수집할 수 있다.
"""

from app.thumbnail import safe_thumbnail_url


class TestAllowedHosts:
    def test_accepts_youtube_image_cdn(self) -> None:
        url = "https://i.ytimg.com/vi/abc123/mqdefault.jpg"

        assert safe_thumbnail_url(url) == url

    def test_accepts_channel_avatar_host(self) -> None:
        url = "https://yt3.ggpht.com/ytc/AIdro_abc=s88-c-k-c0x00ffffff-no-rj"

        assert safe_thumbnail_url(url) == url

    def test_accepts_googleusercontent_avatars(self) -> None:
        url = "https://yt3.googleusercontent.com/ytc/xyz=s88"

        assert safe_thumbnail_url(url) == url


class TestRejectedUrls:
    def test_rejects_other_hosts(self) -> None:
        """임의 호스트는 방문자 IP·Referer 수집 경로가 된다."""
        assert safe_thumbnail_url("https://evil.example.com/pixel.gif") is None

    def test_rejects_lookalike_host(self) -> None:
        """호스트 접미사만 맞춰 속이는 시도를 막는다."""
        assert safe_thumbnail_url("https://ytimg.com.evil.example/x.jpg") is None

    def test_rejects_non_https_scheme(self) -> None:
        assert safe_thumbnail_url("http://i.ytimg.com/vi/abc/mq.jpg") is None
        assert safe_thumbnail_url("javascript:alert(1)") is None
        assert safe_thumbnail_url("data:image/svg+xml;base64,PHN2Zz4=") is None

    def test_rejects_empty_or_malformed(self) -> None:
        assert safe_thumbnail_url("") is None
        assert safe_thumbnail_url(None) is None
        assert safe_thumbnail_url("not a url") is None

    def test_rejects_userinfo_disguise(self) -> None:
        """`@` 앞부분은 사용자 정보라 실제 호스트가 뒤에 온다."""
        assert safe_thumbnail_url("https://i.ytimg.com@evil.example/x.jpg") is None
