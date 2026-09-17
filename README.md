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

## CLI 명령어 (CLI Usage)

```bash
# 1. 웹 서버 실행 (Forwarded proxy 및 trusted host 보안 설정 적용)
automotive-newsletter serve --host 127.0.0.1 --port 8000

# 2. 오늘자 기사 수집 및 저장 (타임존 명시 및 중복/동시성 락 방지)
automotive-newsletter collect

# 강제 재수집 (--force)
automotive-newsletter collect --force

# 특정 날짜 수집
automotive-newsletter collect --date 2026-09-17

# 3. 단독 스케줄러 프로세스 실행 (서버 재시작 대응, missed execution 자동 catch-up)
automotive-newsletter schedule --time 06:00

# 4. 발행된 뉴스레터 이메일 발송
automotive-newsletter send --date 2026-09-17

# 5. 소스 피드 헬스 체크
automotive-newsletter sources
```

## 프로덕션 스케줄링 가이드 (Production Scheduling)

FastAPI 웹 프로세스에서 긴 sleep 루프를 실행하는 대신, 웹 프로세스와 스케줄링을 분리하는 것을 권장합니다.

### 1) Cron 스케줄링 (권장)
호스트 또는 컨테이너 크론탭에 다음과 같이 등록합니다 (`crontab -e`):

```cron
# 매일 오전 06:00 (Europe/Berlin 기준) 수집 실행
NEWSLETTER_TIMEZONE=Europe/Berlin
0 6 * * * /app/.venv/bin/automotive-newsletter collect >> /var/log/newsletter-cron.log 2>&1
```

### 2) Systemd Timer (Linux 배포)
`/etc/systemd/system/automotive-newsletter-collect.service`:
```ini
[Unit]
Description=Automotive Newsletter Daily Collection
After=network.target

[Service]
Type=oneshot
User=newsletter
WorkingDirectory=/opt/automotive-newsletter
EnvironmentFile=/opt/automotive-newsletter/.env
ExecStart=/opt/automotive-newsletter/.venv/bin/automotive-newsletter collect
```

`/etc/systemd/system/automotive-newsletter-collect.timer`:
```ini
[Unit]
Description=Run Automotive Newsletter collection daily at 06:00 Europe/Berlin

[Timer]
OnCalendar=*-*-* 06:00:00 Europe/Berlin
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
systemctl daemon-reload
systemctl enable --now automotive-newsletter-collect.timer
```
`Persistent=true` 설정으로 서버가 06:00에 꺼져 있었더라도 부팅 후 누락된 수집을 즉시 자동 실행(catch-up)합니다.

### 3) Docker Compose 아키텍처
웹 서비스와 스케줄러 컨테이너를 분리하여 운영:

```yaml
version: '3.8'

services:
  web:
    image: automotive-newsletter:latest
    ports:
      - "127.0.0.1:8000:8000"
    volumes:
      - newsletter-data:/app/data
    environment:
      - NEWSLETTER_TIMEZONE=Europe/Berlin
      - TRUSTED_PROXIES=127.0.0.1,::1
      - FORWARDED_ALLOW_IPS=127.0.0.1,::1
      - ADMIN_KEY_FILE=/run/secrets/admin_key
      - SMTP_PASSWORD_FILE=/run/secrets/smtp_password
    secrets:
      - admin_key
      - smtp_password
    restart: unless-stopped

  scheduler:
    image: automotive-newsletter:latest
    command: ["automotive-newsletter", "schedule", "--time", "06:00"]
    volumes:
      - newsletter-data:/app/data
    environment:
      - NEWSLETTER_TIMEZONE=Europe/Berlin
    secrets:
      - admin_key
      - smtp_password
    restart: unless-stopped

volumes:
  newsletter-data:

secrets:
  admin_key:
    file: ./secrets/admin_key.txt
  smtp_password:
    file: ./secrets/smtp_password.txt
```

---

## 프로덕션 보안 & 모니터링 (Production Security & Observability)

### 1) 관리자 인증 보안 (Admin Security)
- 관리자 키는 URL 쿼리 파라미터(`?admin_key=...`)로 전송되지 않으며, 서버 로그 및 브라우저 히스토리에 노출되지 않습니다.
- HTTP 헤더 `X-Admin-Key` 또는 `Authorization: Bearer <key>` 헤더를 통해서만 수락됩니다.
- 상수 시간 비교(`hmac.compare_digest`)를 사용하여 타이밍 공격을 방지합니다.

### 2) 비밀번호 보안 (SMTP & Admin Secrets)
- 비밀번호는 SQLite DB에 평문 저장하지 않고 환경 변수(`SMTP_PASSWORD`) 또는 Docker Secret 파일(`/run/secrets/smtp_password`) 사용을 권장합니다.

### 3) 프록시 및 신뢰 호스트 보안 (Reverse Proxy Hardening)
- `TRUSTED_PROXIES` 및 `FORWARDED_ALLOW_IPS`는 기본적으로 루프백(`127.0.0.1,::1`)으로 제한되며, 와일드카드(`*`)는 명시적으로 설정된 경우에만 활성화됩니다.

### 4) 구조화된 로깅 (Structured JSON Logging)
- 수집 및 스케줄러 이벤트는 표준 JSON 형태로 출력되어 Datadog, CloudWatch, ELK 등 로그 수집기에 직접 연동됩니다:
  `{"timestamp": "...", "level": "INFO", "component": "collector", "source": "reuters", "event": "feed_fetch_ok", "duration": 0.45, "error": null}`

### 5) 헬스체크 (`/health`) 및 수집 메트릭
- 웹 및 DB 상태, 최신 수집 메트릭을 제공합니다:
  - `healthy`: 정상 동작 중
  - `degraded`: 웹/DB는 정상이나 최근 수집에서 피드 실패(`feeds_failed > 0`) 발생
- 메트릭 항목: `feeds_total`, `feeds_ok`, `feeds_failed`, `articles_collected`, `articles_after_dedupe`, `articles_selected`, `collection_duration`
- 민감한 인증 정보는 일체 노출되지 않습니다.

## 수집 옵션

```bash
MAX_ENTRIES_PER_FEED=12
RESOLVE_NEWS_LINKS=true
FETCH_ARTICLE_EXCERPTS=false
REQUEST_TIMEOUT_SECONDS=8
```

## 소스 및 피드 아키텍처 (Source & Feed Architecture)

피드 수집기는 체계적인 메타데이터와 신뢰도(Authority) 계층을 기반으로 고품질 자동차 소스 카탈로그를 관리합니다.

### 1. SourceFeed 메타데이터
각 소스는 단순 피드 주소를 넘어 표준화된 메타데이터를 보유합니다:
- `id` / `source_id`: 고유 식별자 슬러그 (예: `reuters`, `automotive_news`, `unece`, `heise_autos`, `bosch`)
- `name`: 소스 표시명
- `bucket`: 기본 카테고리 (`big`, `oem`, `tier1`, `sdv`, `ev_battery`, `regulation`, `software`, `supply_chain`, `institution`, `conference` 등)
- `url`: 수집 URL (RSS/Atom 피드 또는 타깃 검색 피드 주소)
- `source_type`: 소스 분류 (`media`, `official`, `institution`, `regulator`, `research`, `open_source`, `aggregator`, `press_release`, `event`)
- `authority_score`: 0~100 사이의 출처 신뢰도/원천 취재력 점수
- `region`: 관할 지역 (`global`, `us`, `europe`, `asia`, `kr`)
- `language`: 기본 언어 (`en`, `ko`, `de`)
- `paywalled`: 유료 구독 여부
- `enabled`: 활성화 여부
- `catalog_group`: 카탈로그 그룹 (`primary`, `media`, `institution`, `aggregator`)
- `discovery_method`: 수집 및 발견 방식 (`rss`, `atom`, `search`, `manual_web`)

### 2. 신뢰도(Authority) 계층
신뢰도 점수는 사실 여부 판정이 아닌 출처의 공식성과 1차 취재력을 평가하는 휴리스틱 지표입니다:
- **100**: 규제/정부/공식 표준 기구 (`regulator`: NHTSA, Euro NCAP, UNECE, European Commission, ACEA)
- **95**: 주요 독립 통신사/와이어 (`news_agency`: Reuters, Bloomberg, AP)
- **90**: 정통 자동차 B2B 전문지 (`industry_media`: Automotive News, Automotive World, WardsAuto, JustAuto, Automotive Dive, Automotive Logistics)
- **85**: 특화 기술 매체 및 오픈소스 표준 (`specialist_media` / `open_source`: Heise Autos, electrive, ATTI, Electrek, InsideEVs, The Drive, Eclipse SDV, Eclipse S-CORE, COVESA, AUTOSAR)
- **80**: 주요 분석/연구 기관 (`research` / `institution`: S&P Global Mobility, McKinsey, Gartner, SAE)
- **75**: 일반 테크/모빌리티 미디어 (`tech_media`: TechCrunch, The Verge)
- **70**: 완성차(OEM) 및 부품사(Tier 1) 공식 뉴스룸 (`official`: Mercedes, VW, BMW, Bosch, ZF, Hyundai, Kia, Mobis 등)
- **60**: 보도자료 배포망 (`press_release`: PR Newswire)
- **40**: 검색/수집 어그리게이터 (`aggregator`: Google News 검색 토픽 피드)

---

### 3. 소스 카탈로그 (Source Catalog)

카탈로그는 4가지 명확한 그룹으로 구분되어 관리됩니다:

#### 1) PRIMARY SOURCES (공식 뉴스룸, 규제 기관, 표준 기구)
| Source ID | Source Name | Type | Group | Authority | Region | Lang | Discovery Method |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| `unece` | UNECE WP.29 Vehicle Regulations | `regulator` | Primary | 100 | global | en | search |
| `nhtsa` | NHTSA | `regulator` | Primary | 100 | us | en | search |
| `euro_ncap` | Euro NCAP | `regulator` | Primary | 100 | europe | en | search |
| `autosar` | AUTOSAR Development Partnership | `open_source` | Primary | 85 | global | en | search |
| `eclipse_sdv` | Eclipse SDV | `open_source` | Primary | 85 | global | en | search |
| `eclipse_score`| Eclipse S-CORE | `open_source` | Primary | 85 | global | en | search |
| `covesa` | COVESA Alliance | `open_source` | Primary | 85 | global | en | search |
| `mercedes_benz` | Mercedes-Benz Group Media | `official` | Primary | 70 | europe | en | search |
| `volkswagen` | Volkswagen Group Newsroom | `official` | Primary | 70 | europe | en | search |
| `bmw` | BMW Group PressClub | `official` | Primary | 70 | europe | en | search |
| `stellantis` | Stellantis Media | `official` | Primary | 70 | europe | en | search |
| `renault` | Renault Group Newsroom | `official` | Primary | 70 | europe | en | search |
| `toyota` | Toyota Motor Newsroom | `official` | Primary | 70 | global | en | search |
| `hyundai` | Hyundai Motor Newsroom | `official` | Primary | 70 | kr | en | search |
| `kia` | Kia Worldwide Media | `official` | Primary | 70 | kr | en | search |
| `bosch` | Bosch Media Service | `official` | Primary | 70 | europe | en | search |
| `continental` | Continental Press | `official` | Primary | 70 | europe | en | search |
| `zf` | ZF Group Press | `official` | Primary | 70 | europe | en | search |
| `valeo` | Valeo Media | `official` | Primary | 70 | europe | en | search |
| `magna` | Magna International News | `official` | Primary | 70 | global | en | search |
| `aptiv` | Aptiv Media | `official` | Primary | 70 | global | en | search |
| `forvia` | Forvia Newsroom | `official` | Primary | 70 | europe | en | search |
| `hyundai_mobis`| Hyundai Mobis Newsroom | `official` | Primary | 70 | kr | en | search |

#### 2) MEDIA (글로벌 와이어, 전문지, 독일/유럽 매체, 공급망)
| Source ID | Source Name | Type | Group | Authority | Region | Lang | Discovery Method |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| `reuters` | Reuters Automotive | `media` | Media | 95 | global | en | search |
| `bloomberg` | Bloomberg Hyperdrive | `media` | Media | 95 | global | en | search |
| `automotive_news` | Automotive News | `media` | Media | 90 | global | en | rss |
| `automotive_news_europe` | Automotive News Europe | `media` | Media | 90 | europe | en | rss |
| `automotive_world` | Automotive World | `media` | Media | 90 | global | en | rss |
| `wardsauto` | WardsAuto | `media` | Media | 90 | us | en | rss |
| `just_auto` | JustAuto | `media` | Media | 90 | global | en | rss |
| `automotive_dive` | Automotive Dive | `media` | Media | 90 | us | en | rss |
| `heise_autos` | Heise Autos | `media` | Media | 85 | europe | de | atom |
| `electrive_en` | electrive (EN) | `media` | Media | 85 | europe | en | rss |
| `electrive_de` | electrive (DE) | `media` | Media | 85 | europe | de | rss |
| `automotive_logistics` | Automotive Logistics | `media` | Media | 90 | global | en | search |
| `insideevs` | InsideEVs | `media` | Media | 85 | global | en | rss |
| `car_and_driver` | Car and Driver News | `media` | Media | 85 | us | en | rss |
| `motor1` | Motor1 News | `media` | Media | 85 | global | en | rss |
| `the_drive` | The Drive | `media` | Media | 85 | us | en | rss |
| `electrek` | Electrek | `media` | Media | 85 | global | en | rss |
| `techcrunch_transportation` | TechCrunch Transportation | `media` | Media | 75 | global | en | rss |
| `the_verge_transportation` | The Verge Transportation | `media` | Media | 75 | global | en | rss |
| `atti` | ATTI | `media` | Media | 85 | global | en | rss |
| `pr_newswire_automotive` | PR Newswire Automotive | `press_release`| Media | 60 | global | en | rss |

#### 3) INSTITUTIONS (산업 협회, 분석 기관, 컨퍼런스)
| Source ID | Source Name | Type | Group | Authority | Region | Lang | Discovery Method |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| `acea` | ACEA (European Automobile Manufacturers’ Association) | `institution` | Institution | 100 | europe | en | search |
| `european_commission` | European Commission Automotive & Mobility | `regulator` | Institution | 100 | europe | en | search |
| `institutions_and_magazines` | Institutions and magazines | `aggregator` | Institution | 40 | global | en | search |
| `automotive_conferences` | Automotive conferences | `event` | Institution | 70 | global | en | search |

#### 4) AGGREGATORS (토픽 검색 어그리게이터)
| Source ID | Source Name | Type | Group | Authority | Region | Lang | Discovery Method |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| `global_automotive_big_news` | Global automotive big news | `aggregator` | Aggregator | 40 | global | en | search |
| `korea_auto_news` | Korea Auto News | `aggregator` | Aggregator | 40 | kr | ko | search |
| `oem_strategy` | OEM strategy | `aggregator` | Aggregator | 40 | global | en | search |
| `tier1_suppliers` | Tier 1 suppliers | `aggregator` | Aggregator | 40 | global | en | search |
| `sdv_software` | SDV software | `aggregator` | Aggregator | 40 | global | en | search |
| `regulators_and_safety` | Regulators and safety | `aggregator` | Aggregator | 40 | global | en | search |

---

### 4. 소스 헬퍼 및 무결성 검증 함수
`automotive_newsletter.sources` 모듈에서 다음과 같은 헬퍼 함수를 제공합니다:
- `get_source(source_id)`: ID, 별칭(aliases), 또는 이름으로 `SourceFeed` 조회
- `get_enabled_sources(group=None)`: 활성화된(`enabled=True`) 피드 목록 반환 (그룹 필터 지원)
- `get_primary_sources()`, `get_media_sources()`, `get_institution_sources()`, `get_aggregator_sources()`: 그룹별 소스 목록 반환
- `get_sources_by_group(group)`: 특정 카탈로그 그룹의 소스 목록 반환
- `source_metadata(source_id)`: 소스 메타데이터 딕셔너리 반환
- `source_authority(source_id)`: 소스 ID, 언론사명, 또는 소스 타입에 따른 권위 점수 반환
- `check_catalog_integrity()`: 전체 카탈로그 스키마 및 고유성 검증


