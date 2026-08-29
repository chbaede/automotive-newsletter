# Automotive Newsletter

한국어 자동차 뉴스레터를 매일 수집하고, 웹에서 히스토리로 확인하고, 버튼으로 메일 발송하는 로컬 앱입니다.

## 실행

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m automotive_newsletter serve
```

브라우저에서 `http://127.0.0.1:8000`을 엽니다.

## 메일 발송 설정

웹 화면의 `메일 설정` 탭에서 아래 값을 저장하면 전송 버튼이 SMTP로 뉴스레터를 발송합니다. 비밀번호는 화면에 다시 표시하지 않고 저장 여부만 보여줍니다.

`.env` 또는 환경 변수로도 설정할 수 있습니다.

```bash
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=your-account
SMTP_PASSWORD=your-password
SMTP_FROM=sender@example.com
NEWSLETTER_TO=recipient@example.com
SMTP_TLS=true
```

## 매일 수집

서버가 켜져 있을 때 자동 수집하려면:

```bash
ENABLE_DAILY_SCHEDULER=true
DAILY_COLLECTION_TIME=08:00
python -m automotive_newsletter serve
```

또는 장시간 실행 프로세스로:

```bash
python -m automotive_newsletter schedule
```

## 수집 옵션

```bash
MAX_ENTRIES_PER_FEED=12
RESOLVE_NEWS_LINKS=true
FETCH_ARTICLE_EXCERPTS=false
REQUEST_TIMEOUT_SECONDS=8
```
