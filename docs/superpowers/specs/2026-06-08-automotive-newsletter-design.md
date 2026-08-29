# Automotive Newsletter Design

## Goal

Build a local Korean automotive newsletter web app that collects daily news about OEMs, Tier 1 suppliers, SDV/software-defined vehicle trends, influential institutions/people/magazines, and automotive conferences. The app stores each daily issue as history, shows it in a browser, and sends the selected issue by email when the user presses a send button.

## Approach

The app is a Python FastAPI service with SQLite storage. It uses RSS and Google News RSS feeds so it can run without paid news API keys. It stores fetched articles, Korean summaries, source links, tags, and grouped sections per issue. It supports manual collection from the web UI and optional daily collection while the server is running.

## Main User Flows

1. Open the app in a browser and see the latest newsletter issue.
2. Press refresh to collect today's automotive news and save it as a dated issue.
3. Browse previous daily issues from the history rail.
4. Press send to email the selected issue through SMTP settings.
5. See conference-related items near the end of the issue.

## Architecture

- `automotive_newsletter/config.py` reads environment settings, default paths, source lists, and SMTP configuration.
- `automotive_newsletter/sources.py` defines news buckets and RSS URLs.
- `automotive_newsletter/collector.py` fetches feeds, resolves links, deduplicates articles, ranks them, and builds issues.
- `automotive_newsletter/summarizer.py` creates deterministic Korean summaries and tags without requiring an LLM.
- `automotive_newsletter/store.py` owns SQLite schema and persistence.
- `automotive_newsletter/mailer.py` renders and sends issue email through SMTP.
- `automotive_newsletter/web.py` exposes FastAPI routes and renders the UI.
- `automotive_newsletter/cli.py` provides `serve`, `collect`, `send`, and `schedule` commands.

## Data Model

- `issues`: one row per issue date, including generated title and timestamps.
- `articles`: issue-linked rows with title, URL, source, category, published date, Korean summary, excerpt, tags, and score.

## Sections

The newsletter renders these sections in order:

1. 오늘의 큰 뉴스
2. OEM 주요 동향
3. Tier 1 / 공급망
4. SDV / 소프트웨어
5. 기관 / 인물 / 매거진
6. 컨퍼런스 / 이벤트

## Email

Email sending is an explicit side effect triggered by the send button or CLI. It requires SMTP environment variables. If configuration is missing, the UI returns a clear setup message and does not attempt to send.

## Daily Collection

The app supports two daily modes:

- A server-side background scheduler when `ENABLE_DAILY_SCHEDULER=true`.
- A CLI `schedule` command for long-running daily collection.

The collection time defaults to `08:00` local time and can be changed with `DAILY_COLLECTION_TIME`.

## Error Handling

- Feed failures are recorded as non-fatal warnings; other feeds continue.
- Duplicate URLs and near-duplicate titles are collapsed.
- Missing SMTP settings return a readable error.
- Empty collection still creates a page with status messaging instead of crashing.

## Testing

Tests cover storage/history behavior, summary/category logic, collector deduplication and issue building, mail configuration errors, CLI behavior, and web rendering for the main controls.

