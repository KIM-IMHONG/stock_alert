# 🚀 한국투자증권 급등/급락 알림봇 프로젝트

한국투자증권 OpenAPI를 활용한 실시간 주식 가격 모니터링 및 급등/급락 알림 시스템입니다.

## 📋 주요 기능

- 🔌 **한국투자증권 API 연동**: REST API + WebSocket 실시간 데이터
- 📊 **실시간 모니터링**: 여러 종목 동시 감시
- 🚨 **급등/급락 알림**: 설정 가능한 임계값 기반 자동 알림
- 📱 **텔레그램 봇**: 즉시 알림 발송
- 💾 **데이터 저장**: 가격 히스토리 및 알림 로그

## 🏗️ 프로젝트 구조

```
korea-stock-alert-bot/
├── src/
│   ├── api/              # 🔌 KIS API 연동 모듈 (NEW!)
│   │   ├── kis_api/
│   │   │   ├── client.py           # REST API 클라이언트
│   │   │   ├── websocket_client.py # WebSocket 클라이언트  
│   │   │   ├── manager.py          # 통합 관리자
│   │   │   ├── config.py           # 설정 관리
│   │   │   └── exceptions.py       # 예외 처리
│   │   ├── utils/                  # 유틸리티
│   │   ├── quick_start.py          # 빠른 시작 가이드
│   │   └── test_example.py         # 테스트 코드
│   ├── bot/              # 텔레그램 봇
│   ├── alert/            # 알림 시스템
│   └── data/             # 데이터 관리
├── requirements.txt      # 의존성
├── .env.example         # 환경변수 예시
└── README.md
```

## 🚀 빠른 시작

### 1. 환경 설정

```bash
# 저장소 클론
git clone <repository_url>
cd korea-stock-alert-bot

# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정
cp .env.example .env
```

### 2. KIS API 키 설정

1. [한국투자증권 OpenAPI](https://developers.koreainvestment.com) 회원가입
2. 앱 등록 후 API 키 발급
3. `.env` 파일에 정보 입력:

```env
KIS_APP_KEY=your_app_key_here
KIS_APP_SECRET=your_app_secret_here
```

### 3. 빠른 테스트

```bash
# API 모듈 빠른 시작
cd src/api
python quick_start.py

# 전체 기능 테스트
python test_example.py
```

## 🔌 API 모듈 사용법

### 기본 사용
```python
from src.api.kis_api import KISManager

# 매니저 생성
manager = KISManager()

# 종목 정보 조회
stock_info = manager.get_stock_info("005930")  # 삼성전자
print(f"현재가: {stock_info.current_price:,}원")
```

### 급등/급락 모니터링
```python
def alert_callback(alert_type, data):
    print(f"🚨 {alert_type}: {data.stock_code} - {data.current_price:,}원")

# 모니터링 설정
manager.add_stock_to_monitor("005930", alert_callback)
manager.set_alert_thresholds(surge_threshold=5.0, plunge_threshold=-5.0)
manager.start_price_monitoring(check_interval=30)
```

### 실시간 데이터 구독
```python
def realtime_callback(data):
    print(f"실시간: {data.stock_code} - {data.current_price:,}원")

# WebSocket 구독
manager.subscribe_realtime(["005930", "000660"], realtime_callback)
```

## 📊 주요 클래스

### KISAPIClient
- ✅ 토큰 관리 (자동 발급/갱신)
- ✅ 종목 정보 조회
- ✅ 현재가 조회
- ✅ 에러 처리 및 재시도
- ✅ Rate limiting

### KISWebSocketClient  
- ✅ 실시간 데이터 수신
- ✅ 자동 재연결
- ✅ 데이터 파싱 및 정규화

### KISManager (통합 관리)
- ✅ REST + WebSocket 통합
- ✅ 다중 종목 모니터링
- ✅ 급등/급락 감지
- ✅ 콜백 기반 알림

## 🔧 환경변수

```env
# KIS API 설정
KIS_APP_KEY=your_app_key_here
KIS_APP_SECRET=your_app_secret_here

# 텔레그램 봇 (선택)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# 모니터링 설정
MONITORING_INTERVAL=30
SURGE_THRESHOLD=5.0
PLUNGE_THRESHOLD=-5.0
WATCH_LIST=005930,000660,035420
```

## 🧪 테스트

```bash
# API 모듈 테스트
cd src/api
python test_example.py

# 개별 기능 테스트
python -c "from test_example import test_basic_api; test_basic_api()"
```

## 📈 지원 기능

### ✅ 구현 완료
- 🔌 한국투자증권 API 연동 모듈
- 📊 종목 정보 조회 (REST API)
- 📡 실시간 데이터 수신 (WebSocket)
- 🚨 급등/급락 감지 알고리즘
- ⚡ 자동 재연결 및 에러 처리
- 📝 상세 로깅 및 모니터링

### 🚧 구현 예정
- 📱 텔레그램 봇 통합
- 💾 데이터베이스 연동
- 📈 차트 및 분석 기능
- 🔔 다양한 알림 채널 (이메일, 슬랙 등)

## 🔗 관련 링크

- [한국투자증권 OpenAPI](https://developers.koreainvestment.com)
- [KIS OpenAPI GitHub](https://github.com/koreainvestment/open-trading-api)

## 📄 라이선스

MIT License

## 🤝 기여

이슈 및 풀 리퀘스트를 환영합니다!

---

⭐ **Star this repo if it helps you!**