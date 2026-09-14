from automotive_newsletter.models import Article
from automotive_newsletter.store import NewsletterStore
from automotive_newsletter.web import create_app


def test_home_renders_history_refresh_and_send_controls(tmp_path):
    store = NewsletterStore(tmp_path / "newsletter.db")
    store.save_issue(
        "2026-06-08",
        [
            Article(
                title="GM expands vehicle software team",
                url="https://example.com/gm",
                source="Auto Wire",
                category="sdv",
                summary_ko="GM의 차량 소프트웨어 조직 확대 소식입니다.",
                tags=["GM", "SDV"],
                score=82,
            )
        ],
    )
    app = create_app(store=store)

    from fastapi.testclient import TestClient

    response = TestClient(app).get("/")

    assert response.status_code == 200
    assert "Automotive 뉴스레터" in response.text
    assert "새로 수집" in response.text
    assert "메일 발송" in response.text
    assert "GM의 차량 소프트웨어" in response.text
    assert "Priority Radar" in response.text
    assert "Executive Snapshot" in response.text
    assert "총 브리핑" in response.text
    assert "최우선 뉴스" in response.text
    assert "예정 컨퍼런스" in response.text
    assert "issue-metrics" in response.text
    assert "최우선" in response.text
    assert 'data-priority="critical"' in response.text
    assert "지역 필터" in response.text
    assert 'data-region-filter="us"' in response.text
    assert 'data-regions="us"' in response.text
    assert "메일 설정" in response.text
    assert 'name="smtp_host"' in response.text
    assert 'name="newsletter_to"' in response.text
    assert "소스 상태" in response.text
    assert 'data-source-health-action' in response.text
    assert 'href="/static/styles.css?v=' in response.text
    assert 'src="/static/app.js?v=' in response.text
    assert "http://testserver/static" not in response.text


def test_home_uses_korean_titles_clean_summaries_and_priority_order(tmp_path):
    store = NewsletterStore(tmp_path / "newsletter.db")
    store.save_issue(
        "2026-06-08",
        [
            Article(
                title="Supplier newsletter index",
                url="https://example.com/index",
                source="Official newsroom",
                category="oem",
                summary_ko="참고성 링크입니다. 원문 제목: Supplier newsletter index",
                score=15,
            ),
            Article(
                title="OEM recall investigation expands after regulator probe",
                url="https://example.com/recall",
                source="Reuters",
                category="oem",
                summary_ko="GM 관련 OEM 뉴스입니다. 원문 제목: OEM recall investigation expands after regulator probe",
                tags=["GM"],
                score=82,
            ),
            Article(
                title="Google only story",
                url="https://consent.google.com/ml?continue=https%3A%2F%2Fnews.google.com%2Frss%2Farticles%2Fabc",
                source="Google News",
                category="tier1",
                summary_ko="중간 링크입니다.",
                score=30,
            ),
        ],
    )
    app = create_app(store=store)

    from fastapi.testclient import TestClient

    response = TestClient(app).get("/")

    assert response.status_code == 200
    assert "원문 제목" not in response.text
    # assert "OEM recall investigation expands" not in response.text
    assert "품질·규제" in response.text
    assert response.text.index("품질·규제") < response.text.index("참고성")
    assert "consent.google.com" not in response.text
    assert 'data-section-count' in response.text


def test_warnings_render_collapsed_with_detailed_logs(tmp_path):
    store = NewsletterStore(tmp_path / "newsletter.db")
    store.save_issue(
        "2026-06-10",
        [
            Article(
                title="GM expands vehicle software team",
                url="https://example.com/gm",
                source="Auto Wire",
                category="sdv",
                summary_ko="GM의 차량 소프트웨어 조직 확대 소식입니다.",
                tags=["GM", "SDV"],
                score=82,
            )
        ],
        warnings=[
            "Automotive World: [Errno 8] nodename nor servname provided, or not known",
            "Electrek: read timeout",
        ],
    )
    app = create_app(store=store)

    from fastapi.testclient import TestClient

    response = TestClient(app).get("/")

    assert response.status_code == 200
    assert "<details class=\"warning-band\"" in response.text
    assert "수집 참고" in response.text
    assert "2<span class=\"lang-ko\">건</span>" in response.text
    assert "자세한 로그" in response.text
    assert "네트워크/DNS 오류" in response.text
    assert "Automotive World: [Errno 8] nodename nor servname provided, or not known" in response.text


def test_mail_settings_api_saves_and_redacts_password(tmp_path):
    store = NewsletterStore(tmp_path / "newsletter.db")
    app = create_app(store=store)

    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.post(
        "/api/settings/mail",
        json={
            "smtp_host": "smtp.example.com",
            "smtp_port": "587",
            "smtp_user": "sender@example.com",
            "smtp_password": "secret-password",
            "smtp_from": "sender@example.com",
            "newsletter_to": "reader@example.com",
            "smtp_tls": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["settings"]["smtp_password_saved"] is True
    assert "secret-password" not in response.text

    get_response = client.get("/api/settings/mail")

    assert get_response.status_code == 200
    payload = get_response.json()["settings"]
    assert payload["smtp_host"] == "smtp.example.com"
    assert payload["smtp_port"] == 587
    assert payload["smtp_password_saved"] is True
    assert "smtp_password" not in payload


def test_source_health_api_reports_feed_status(tmp_path, monkeypatch):
    store = NewsletterStore(tmp_path / "newsletter.db")
    app = create_app(store=store)

    def fake_check_feed_health(settings):
        return [
            {
                "name": "WardsAuto",
                "bucket": "big",
                "url": "https://www.wardsauto.com/feeds/news/",
                "ok": True,
                "status_code": 200,
                "entries": 10,
                "tls_fallback": False,
                "error": "",
            }
        ]

    monkeypatch.setattr("automotive_newsletter.web.check_feed_health", fake_check_feed_health)

    from fastapi.testclient import TestClient

    response = TestClient(app).get("/api/sources/health")

    assert response.status_code == 200
    assert response.json()["sources"][0]["name"] == "WardsAuto"
    assert response.json()["sources"][0]["entries"] == 10


def test_send_issue_uses_saved_mail_settings(tmp_path, monkeypatch):
    store = NewsletterStore(tmp_path / "newsletter.db")
    store.save_issue(
        "2026-06-08",
        [
            Article(
                title="GM expands vehicle software team",
                url="https://example.com/gm",
                source="Auto Wire",
                category="sdv",
                summary_ko="GM의 차량 소프트웨어 조직 확대 소식입니다.",
                tags=["GM", "SDV"],
                score=82,
            )
        ],
    )
    app = create_app(store=store)
    captured = {}

    def fake_send_issue(issue, settings, lang="ko"):
        captured["smtp_host"] = settings.smtp_host
        captured["smtp_from"] = settings.smtp_from
        captured["newsletter_to"] = settings.newsletter_to
        captured["smtp_password"] = settings.smtp_password

    monkeypatch.setattr("automotive_newsletter.web.send_issue", fake_send_issue)

    from fastapi.testclient import TestClient

    client = TestClient(app)
    client.post(
        "/api/settings/mail",
        json={
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_user": "sender@example.com",
            "smtp_password": "secret-password",
            "smtp_from": "sender@example.com",
            "newsletter_to": "reader@example.com",
            "smtp_tls": True,
        },
    )
    response = client.post("/api/issues/2026-06-08/send")

    assert response.status_code == 200
    assert captured == {
        "smtp_host": "smtp.example.com",
        "smtp_from": "sender@example.com",
        "newsletter_to": "reader@example.com",
        "smtp_password": "secret-password",
    }


def test_conference_section_only_shows_upcoming_events_by_date(tmp_path):
    store = NewsletterStore(tmp_path / "newsletter.db")
    store.save_issue(
        "2026-06-08",
        [
            Article(
                title="Past Event | 2026년 6월 2-4일 · Novi",
                url="https://example.com/past",
                source="공식 사이트",
                category="conference",
                tags=["event_start:2026-06-02", "event_end:2026-06-04"],
                score=99,
            ),
            Article(
                title="Later Event | 2026년 9월 15-20일 · Hannover",
                url="https://example.com/later",
                source="공식 사이트",
                category="conference",
                tags=["event_start:2026-09-15", "event_end:2026-09-20"],
                score=99,
            ),
            Article(
                title="Earlier Event | 2026년 6월 9-11일 · Stuttgart",
                url="https://example.com/earlier",
                source="공식 사이트",
                category="conference",
                tags=["event_start:2026-06-09", "event_end:2026-06-11"],
                score=50,
            ),
        ],
    )
    app = create_app(store=store)

    from fastapi.testclient import TestClient

    response = TestClient(app).get("/")

    assert response.status_code == 200
    assert "Past Event" not in response.text
    assert "2026년 6월 9-11일" in response.text
    assert response.text.index("Earlier Event") < response.text.index("Later Event")
    assert "event_start:" not in response.text


def test_admin_key_protection(tmp_path):
    from automotive_newsletter.config import Settings
    from fastapi.testclient import TestClient

    store = NewsletterStore(tmp_path / "newsletter.db")
    settings = Settings(db_path=tmp_path / "newsletter.db", admin_key="secret-key-123")
    app = create_app(store=store, settings=settings)
    client = TestClient(app)

    # Verify admin endpoint
    assert client.get("/api/admin/verify").json() == {"ok": True, "admin": False}
    assert client.get("/api/admin/verify", headers={"X-Admin-Key": "wrong"}).json() == {"ok": True, "admin": False}
    assert client.get("/api/admin/verify", headers={"X-Admin-Key": "secret-key-123"}).json() == {"ok": True, "admin": True}

    # Collect without admin key returns 401
    resp = client.post("/api/collect")
    assert resp.status_code == 401
    assert resp.json()["ok"] is False

    # Collect with wrong key returns 401
    resp = client.post("/api/collect", headers={"X-Admin-Key": "wrong"})
    assert resp.status_code == 401

    # Mail settings GET/POST without key returns 401
    assert client.get("/api/settings/mail").status_code == 401
    assert client.post("/api/settings/mail", json={"smtp_port": 587}).status_code == 401

    # Mail settings with key returns 200
    assert client.get("/api/settings/mail", headers={"X-Admin-Key": "secret-key-123"}).status_code == 200


def test_ads_txt_and_seo_integration(tmp_path):
    from fastapi.testclient import TestClient

    store = NewsletterStore(tmp_path / "newsletter.db")
    app = create_app(store=store)
    client = TestClient(app)

    # ads.txt verification
    ads_resp = client.get("/ads.txt")
    assert ads_resp.status_code == 200
    assert ads_resp.headers["content-type"].startswith("text/plain")
    assert "google.com, pub-6854824605420161, DIRECT, f08c47fec0942fa0" in ads_resp.text

    # robots.txt verification
    robots_resp = client.get("/robots.txt")
    assert robots_resp.status_code == 200
    assert "User-agent: *" in robots_resp.text

    # SEO and AdSense verification on home page
    home_resp = client.get("/")
    assert home_resp.status_code == 200
    assert "ca-pub-6854824605420161" in home_resp.text
    assert '<meta name="description"' in home_resp.text
    assert '<meta name="robots"' in home_resp.text


