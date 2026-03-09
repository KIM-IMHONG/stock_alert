# 한국투자증권 API 연동 모듈

한국투자증권 OpenAPI 및 WebSocket을 활용한 주식 정보 조회 및 실시간 모니터링 모듈입니다.

## 📋 주요 기능

### 🔌 KISAPIClient
- **인증 토큰 관리**: 자동 토큰 발급 및 갱신
- **종목 정보 조회**: get_stock_info(), get_current_price()
- **에러 처리**: 자동 재시도 및 상세 예외 처리
- **API 호출 제한**: Rate limiting 및 호출 간격 조절

### 📡 KISWebSocketClient
- **실시간 데이터 수신**: 호가/체결가 실시간 구독
- **자동 재연결**: 연결 끊김 시 자동 복구
- **데이터 정규화**: 수신 데이터 파싱 및 구조화

### 🎯 KISManager
- **통합 관리**: REST API + WebSocket 통합 인터페이스
- **급등/급락 감지**: 설정 가능한 임계값 기반 알림
- **모니터링**: 다중 종목 동시 감시

## 🚀 빠른 시작

### 1. 환경 설정

```bash
# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정 (.env 파일 생성)
cp .env.example .env
```

`.env` 파일에 KIS API 정보 입력:
```env
KIS_APP_KEY=your_app_key_here
KIS_APP_SECRET=your_app_secret_here
```

### 2. 기본 사용법

```python
from kis_api import KISAPIClient, KISConfig
from kis_api.manager import KISManager

# 기본 API 사용
client = KISAPIClient()
stock_info = client.get_stock_info("005930")  # 삼성전자
print(f"현재가: {stock_info.current_price}원")

# 매니저 사용 (권장)
manager = KISManager()

# 알림 콜백 정의
def alert_callback(alert_type, data):
    print(f"{alert_type}: {data.stock_code} - {data.current_price}원")

# 모니터링 시작
manager.add_stock_to_monitor("005930", alert_callback)
manager.start_price_monitoring(check_interval=30)
```

### 3. 실시간 구독

```python
from kis_api.websocket_client import RealtimeData

def realtime_callback(data: RealtimeData):
    print(f"실시간: {data.stock_code} - {data.current_price}원")

# 실시간 구독
manager.subscribe_realtime(["005930", "000660"], realtime_callback)
```

## 📁 프로젝트 구조

```
src/api/
├── kis_api/
│   ├── __init__.py           # 모듈 진입점
│   ├── client.py             # REST API 클라이언트
│   ├── websocket_client.py   # WebSocket 클라이언트
│   ├── manager.py            # 통합 관리자
│   ├── config.py             # 설정 관리
│   └── exceptions.py         # 예외 클래스들
├── utils/
│   ├── __init__.py
│   ├── logger.py             # 로깅 유틸리티
│   ├── validators.py         # 데이터 검증
│   └── formatters.py         # 데이터 포매팅
└── test_example.py           # 테스트 및 예시 코드
```

## 🔧 주요 클래스

### KISAPIClient
```python
class KISAPIClient:
    def get_access_token(self) -> str
    def get_stock_info(self, stock_code: str) -> StockInfo
    def get_current_price(self, stock_code: str) -> int
    def get_multiple_stocks_info(self, stock_codes: List[str]) -> List[StockInfo]
    def calculate_change_rate(self, current_price: int, previous_price: int) -> float
    def is_surge_detected(self, change_rate: float, threshold: float = 5.0) -> bool
    def is_plunge_detected(self, change_rate: float, threshold: float = -5.0) -> bool
```

### KISWebSocketClient
```python
class KISWebSocketClient:
    def connect(self)
    def subscribe_realtime(self, stock_codes: List[str], callback: Callable)
    def unsubscribe_stock(self, stock_code: str)
    def disconnect(self)
```

### KISManager
```python
class KISManager:
    def initialize_websocket(self)
    def subscribe_realtime(self, stock_codes: List[str], callback: Callable)
    def add_stock_to_monitor(self, stock_code: str, callback: Callable)
    def start_price_monitoring(self, check_interval: int = 30)
    def set_alert_thresholds(self, surge_threshold: float, plunge_threshold: float)
    def get_monitoring_status(self) -> Dict[str, Any]
```

## 📊 데이터 구조

### StockInfo
```python
@dataclass
class StockInfo:
    code: str                 # 종목코드
    name: str                 # 종목명
    current_price: int        # 현재가
    change_rate: float        # 변동률
    change_amount: int        # 변동금액
    trading_volume: int       # 거래량
    market_cap: Optional[int] # 시가총액
    timestamp: Optional[datetime] # 조회시간
```

### RealtimeData
```python
@dataclass
class RealtimeData:
    stock_code: str      # 종목코드
    current_price: int   # 현재가
    change_rate: float   # 변동률
    change_amount: int   # 변동금액
    trading_volume: int  # 거래량
    bid_price: int       # 매수호가
    ask_price: int       # 매도호가
    timestamp: datetime  # 수신시간
```

## 🛡️ 에러 처리

### 예외 클래스 계층
- `KISAPIError`: 기본 예외
  - `KISAuthError`: 인증 관련 예외
  - `KISConnectionError`: 연결 관련 예외
  - `KISRateLimitError`: API 호출 제한 예외
  - `KISDataError`: 데이터 파싱/형식 예외

### 자동 재시도
- HTTP 요청 실패시 최대 3회 재시도
- 지수 백오프 (exponential backoff) 적용
- Rate limit 감지시 자동 대기

## 🧪 테스트 실행

```bash
# 테스트 실행
python src/api/test_example.py

# 또는 개별 기능 테스트
python -c "from test_example import test_basic_api; test_basic_api()"
```

## ⚙️ 설정 옵션

### KISConfig
```python
@dataclass
class KISConfig:
    BASE_URL: str = "https://openapi.koreainvestment.com:9443"
    WEBSOCKET_URL: str = "ws://ops.koreainvestment.com:21000"
    
    app_key: str = ""         # 환경변수에서 로드
    app_secret: str = ""      # 환경변수에서 로드
    
    max_retries: int = 3      # 최대 재시도 횟수
    timeout: int = 30         # 요청 타임아웃 (초)
    rate_limit_delay: float = 0.1  # API 호출 간격 (초)
```

## 📝 사용 예시

### 급등/급락 알림 봇
```python
def create_alert_bot():
    manager = KISManager()
    
    def alert_handler(alert_type, data):
        message = f"""
🚨 {alert_type} 감지!
종목: {data.stock_code}
현재가: {data.current_price:,}원
변동률: {data.change_rate:.2f}%
시간: {data.timestamp.strftime('%H:%M:%S')}
        """
        # 텔레그램, 이메일 등으로 알림 발송
        send_notification(message)
    
    # 관심 종목 모니터링
    stocks = ["005930", "000660", "035420"]  # 삼성전자, SK하이닉스, 네이버
    
    for stock in stocks:
        manager.add_stock_to_monitor(stock, alert_handler)
    
    manager.set_alert_thresholds(surge_threshold=3.0, plunge_threshold=-3.0)
    manager.start_price_monitoring(check_interval=30)
    
    return manager
```

### 실시간 포트폴리오 모니터링
```python
def monitor_portfolio():
    manager = KISManager()
    portfolio = {}
    
    def update_portfolio(data):
        portfolio[data.stock_code] = {
            'price': data.current_price,
            'change_rate': data.change_rate,
            'timestamp': data.timestamp
        }
        print(f"포트폴리오 업데이트: {portfolio}")
    
    # 실시간 구독
    manager.subscribe_realtime(
        ["005930", "000660", "035420"], 
        update_portfolio
    )
    
    return manager, portfolio
```

## 🔗 관련 링크

- [한국투자증권 OpenAPI 문서](https://developers.koreainvestment.com)
- [KIS OpenAPI GitHub](https://github.com/koreainvestment/open-trading-api)

## ⚠️ 주의사항

1. **API 키 보안**: 환경변수 사용, 코드에 직접 입력 금지
2. **호출 제한**: API 호출 횟수 제한 준수
3. **실시간 데이터**: WebSocket 연결 안정성 확인 필요
4. **테스트**: 실제 거래 전 충분한 테스트 필요

## 📄 라이선스

이 프로젝트는 MIT 라이선스를 따릅니다.