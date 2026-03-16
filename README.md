     1→# 🚀 한국투자증권 급등/급락 알림봇 프로젝트
     2→
     3→한국투자증권 OpenAPI를 활용한 실시간 주식 가격 모니터링 및 급등/급락 알림 시스템입니다.
     4→
     5→## 📋 주요 기능
     6→
     7→- 🔌 **한국투자증권 API 연동**: REST API + WebSocket 실시간 데이터
     8→- 📊 **실시간 모니터링**: 여러 종목 동시 감시
     9→- 🚨 **급등/급락 알림**: 설정 가능한 임계값 기반 자동 알림
    10→- 📱 **텔레그램 봇**: 즉시 알림 발송
    11→- 💾 **데이터 저장**: 가격 히스토리 및 알림 로그
    12→
    13→## 🏗️ 프로젝트 구조
    14→
    15→```
    16→korea-stock-alert-bot/
    17→├── src/
    18→│   ├── api/              # 🔌 KIS API 연동 모듈 (NEW!)
    19→│   │   ├── kis_api/
    20→│   │   │   ├── client.py           # REST API 클라이언트
    21→│   │   │   ├── websocket_client.py # WebSocket 클라이언트  
    22→│   │   │   ├── manager.py          # 통합 관리자
    23→│   │   │   ├── config.py           # 설정 관리
    24→│   │   │   └── exceptions.py       # 예외 처리
    25→│   │   ├── utils/                  # 유틸리티
    26→│   │   ├── quick_start.py          # 빠른 시작 가이드
    27→│   │   └── test_example.py         # 테스트 코드
    28→│   ├── bot/              # 텔레그램 봇
    29→│   ├── alert/            # 알림 시스템
    30→│   └── data/             # 데이터 관리
    31→├── requirements.txt      # 의존성
    32→├── .env.example         # 환경변수 예시
    33→└── README.md
    34→```
    35→
    36→## 🚀 빠른 시작
    37→
    38→### 1. 환경 설정
    39→
    40→```bash
    41→# 저장소 클론
    42→git clone <repository_url>
    43→cd korea-stock-alert-bot
    44→
    45→# 의존성 설치
    46→pip install -r requirements.txt
    47→
    48→# 환경변수 설정
    49→cp .env.example .env
    50→```
    51→
    52→### 2. KIS API 키 설정
    53→
    54→1. [한국투자증권 OpenAPI](https://developers.koreainvestment.com) 회원가입
    55→2. 앱 등록 후 API 키 발급
    56→3. `.env` 파일에 정보 입력:
    57→
    58→```env
    59→KIS_APP_KEY=your_app_key_here
    60→KIS_APP_SECRET=your_app_secret_here
    61→```
    62→
    63→### 3. 빠른 테스트
    64→
    65→```bash
    66→# API 모듈 빠른 시작
    67→cd src/api
    68→python quick_start.py
    69→
    70→# 전체 기능 테스트
    71→python test_example.py
    72→```
    73→
    74→## 🔌 API 모듈 사용법
    75→
    76→### 기본 사용
    77→```python
    78→from src.api.kis_api import KISManager
    79→
    80→# 매니저 생성
    81→manager = KISManager()
    82→
    83→# 종목 정보 조회
    84→stock_info = manager.get_stock_info("005930")  # 삼성전자
    85→print(f"현재가: {stock_info.current_price:,}원")
    86→```
    87→
    88→### 급등/급락 모니터링
    89→```python
    90→def alert_callback(alert_type, data):
    91→    print(f"🚨 {alert_type}: {data.stock_code} - {data.current_price:,}원")
    92→
    93→# 모니터링 설정
    94→manager.add_stock_to_monitor("005930", alert_callback)
    95→manager.set_alert_thresholds(surge_threshold=5.0, plunge_threshold=-5.0)
    96→manager.start_price_monitoring(check_interval=30)
    97→```
    98→
    99→### 실시간 데이터 구독
   100→```python
   101→def realtime_callback(data):
   102→    print(f"실시간: {data.stock_code} - {data.current_price:,}원")
   103→
   104→# WebSocket 구독
   105→manager.subscribe_realtime(["005930", "000660"], realtime_callback)
   106→```
   107→
   108→## 📊 주요 클래스
   109→
   110→### KISAPIClient
   111→- ✅ 토큰 관리 (자동 발급/갱신)
   112→- ✅ 종목 정보 조회
   113→- ✅ 현재가 조회
   114→- ✅ 에러 처리 및 재시도
   115→- ✅ Rate limiting
   116→
   117→### KISWebSocketClient  
   118→- ✅ 실시간 데이터 수신
   119→- ✅ 자동 재연결
   120→- ✅ 데이터 파싱 및 정규화
   121→
   122→### KISManager (통합 관리)
   123→- ✅ REST + WebSocket 통합
   124→- ✅ 다중 종목 모니터링
   125→- ✅ 급등/급락 감지
   126→- ✅ 콜백 기반 알림
   127→
   128→## 🔧 환경변수
   129→
   130→```env
   131→# KIS API 설정
   132→KIS_APP_KEY=your_app_key_here
   133→KIS_APP_SECRET=your_app_secret_here
   134→
   135→# 텔레그램 봇 (선택)
   136→TELEGRAM_BOT_TOKEN=your_bot_token
   137→TELEGRAM_CHAT_ID=your_chat_id
   138→
   139→# 모니터링 설정
   140→MONITORING_INTERVAL=30
   141→SURGE_THRESHOLD=5.0
   142→PLUNGE_THRESHOLD=-5.0
   143→WATCH_LIST=005930,000660,035420
   144→```
   145→
   146→## 🧪 테스트
   147→
   148→```bash
   149→# API 모듈 테스트
   150→cd src/api
   151→python test_example.py
   152→
   153→# 개별 기능 테스트
   154→python -c "from test_example import test_basic_api; test_basic_api()"
   155→```
   156→
   157→## 📈 지원 기능
   158→
   159→### ✅ 구현 완료
   160→- 🔌 한국투자증권 API 연동 모듈
   161→- 📊 종목 정보 조회 (REST API)
   162→- 📡 실시간 데이터 수신 (WebSocket)
   163→- 🚨 급등/급락 감지 알고리즘
   164→- ⚡ 자동 재연결 및 에러 처리
   165→- 📝 상세 로깅 및 모니터링
   166→
   167→### 🚧 구현 예정
   168→- 📱 텔레그램 봇 통합
   169→- 💾 데이터베이스 연동
   170→- 📈 차트 및 분석 기능
   171→- 🔔 다양한 알림 채널 (이메일, 슬랙 등)
   172→
   173→## 🔗 관련 링크
   174→
   175→- [한국투자증권 OpenAPI](https://developers.koreainvestment.com)
   176→- [KIS OpenAPI GitHub](https://github.com/koreainvestment/open-trading-api)
   177→
   178→## 📄 라이선스
   179→
   180→MIT License
   181→
   182→## 🤝 기여
   183→
   184→이슈 및 풀 리퀘스트를 환영합니다!
   185→
   186→---
   187→
   188→⭐ **Star this repo if it helps you!**