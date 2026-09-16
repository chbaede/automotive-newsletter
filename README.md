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
DAILY_COLLECTION_TIME=06:00
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

## 소스 및 피드 아키텍처 (Source & Feed Architecture)

피드 수집기는 명확한 메타데이터와 신뢰도(Authority) 계층을 기반으로 소스를 관리합니다.

### 1. SourceFeed 메타데이터
각 피드는 단순 URL을 넘어 다음 메타데이터를 보유합니다:
- `id`: 고유 식별자 슬러그 (예: `reuters`, `automotive_news`, `wardsauto`, `acea`, `unece`, `eclipse_sdv`)
- `name`: 소스 표시명
- `bucket`: 기본 카테고리 (`big`, `oem`, `tier1`, `sdv`, `institution`, `conference`)
- `url`: RSS/Atom 피드 주소
- `source_type`: 소스 분류 (`media`, `official`, `institution`, `regulator`, `research`, `open_source`, `aggregator`, `press_release`, `event`)
- `authority_score`: 0~100 사이의 출처 특성/원천 신뢰도 점수
- `region`: 관할 지역 (`global`, `us`, `europe`, `asia`, `kr`)
- `language`: 기본 언어 (`en`, `ko`)
- `paywalled`: 유료 구독 여부
- `enabled`: 활성화 여부 (`get_enabled_sources()`로 필터링)

### 2. 신뢰도(Authority) 계층
신뢰도 점수는 기사의 '진실성'이 아니라 언론사/원천 출처의 취재력과 공식성을 평가하는 휴리스틱 지표입니다:
- **100**: 규제/정부/공식 표준 기구 (`regulator`: NHTSA, Euro NCAP, UNECE, ACEA)
- **95**: 주요 독립 통신사/와이어 (`news_agency`: Reuters, Bloomberg, AP)
- **90**: 정통 자동차 B2B 전문지 (`industry_media`: Automotive News, Automotive World, WardsAuto, JustAuto, Automotive Dive)
- **85**: 특화 기술/모빌리티 매체 (`specialist_media` / `open_source`: ATTI, Electrek, InsideEVs, The Drive, Eclipse SDV)
- **80**: 주요 분석/연구 기관 (`research` / `institution`: S&P Global Mobility, McKinsey, Gartner, SAE)
- **75**: 일반 테크/모빌리티 미디어 (`tech_media`: TechCrunch, The Verge)
- **70**: 완성차 및 부품사 공식 뉴스룸 / 행사 (`official`, `event`: OEM/Tier 1 뉴스룸)
- **60**: 보도자료 배포망 (`press_release`: PR Newswire)
- **40**: 검색/수집 어그리게이터 (`aggregator`: Google News 검색 피드)

### 3. 발견 출처(Discovery)와 실제 발행사(Publisher) 분리
Google News와 같은 어그리게이터 피드에서 수집된 기사는 `Google News`가 발행처로 표기되지 않고, 피드 내 메타데이터 및 헤드라인에서 실제 취재 언론사를 자동 추출합니다:
- `discovered_via`: `"Google News"` (발견 경로)
- `publisher`: `"Reuters"` (실제 발행사)
- `source`: `"Reuters"` (기사 표시 출처)

### 4. 소스 헬퍼 함수
`automotive_newsletter.sources` 모듈에서 다음과 같은 헬퍼 함수를 제공합니다:
- `get_source(source_id)`: ID 또는 이름으로 `SourceFeed` 조회
- `get_enabled_sources()`: 활성화된(`enabled=True`) 피드 목록 반환
- `source_metadata(source_id)`: 소스 메타데이터 딕셔너리 반환
- `source_authority(source_id)`: 소스 ID, 언론사명, 또는 소스 타입에 따른 권위 점수 반환

