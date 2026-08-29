# Automotive Newsletter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Korean automotive newsletter web app with daily history, live news collection, conference items, and SMTP email sending.

**Architecture:** Use a FastAPI web app backed by SQLite. RSS/Google News RSS feeds provide news without paid APIs, while deterministic Korean summaries keep the app usable without LLM credentials.

**Tech Stack:** Python 3.11+, FastAPI, Jinja2, SQLite, feedparser, httpx, BeautifulSoup, pytest.

---

### Task 1: Project Skeleton And Tests

**Files:**
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Create: `README.md`
- Create: `automotive_newsletter/__init__.py`
- Create: `automotive_newsletter/__main__.py`
- Create: `tests/test_store.py`
- Create: `tests/test_summarizer.py`
- Create: `tests/test_collector.py`
- Create: `tests/test_mailer.py`
- Create: `tests/test_web.py`

- [ ] Write failing tests for storage, summarizing, collection, mailer, and web rendering.
- [ ] Run `python -m pytest` and verify tests fail because production modules are missing.

### Task 2: Core Data And Collection

**Files:**
- Create: `automotive_newsletter/config.py`
- Create: `automotive_newsletter/models.py`
- Create: `automotive_newsletter/sources.py`
- Create: `automotive_newsletter/store.py`
- Create: `automotive_newsletter/summarizer.py`
- Create: `automotive_newsletter/collector.py`

- [ ] Implement schema creation, issue upsert, article persistence, latest issue lookup, and history list.
- [ ] Implement source definitions for big news, OEM, Tier 1, SDV, institutions, and conferences.
- [ ] Implement article normalization, deduplication, ranking, category inference, and Korean summary generation.
- [ ] Run focused tests and verify they pass.

### Task 3: Email, CLI, And Scheduler

**Files:**
- Create: `automotive_newsletter/mailer.py`
- Create: `automotive_newsletter/cli.py`
- Modify: `automotive_newsletter/__main__.py`

- [ ] Implement SMTP configuration validation.
- [ ] Implement issue email rendering and send behavior.
- [ ] Implement CLI commands `serve`, `collect`, `send`, and `schedule`.
- [ ] Run focused tests and verify they pass.

### Task 4: Web App And UI

**Files:**
- Create: `automotive_newsletter/web.py`
- Create: `automotive_newsletter/templates/base.html`
- Create: `automotive_newsletter/templates/index.html`
- Create: `automotive_newsletter/static/styles.css`
- Create: `automotive_newsletter/static/app.js`

- [ ] Implement FastAPI routes for dashboard, issue views, collection, sending, and health.
- [ ] Implement Korean UI with history rail, issue sections, original links, refresh and send controls.
- [ ] Run focused tests and verify they pass.

### Task 5: Verification And Local Run

**Files:**
- Modify as needed based on verification.

- [ ] Run `python -m pytest`.
- [ ] Start the dev server.
- [ ] Open the app in the in-app browser and verify the UI renders.
- [ ] Run one live collection attempt and verify an issue is stored.
- [ ] Report exact commands and local URL.

