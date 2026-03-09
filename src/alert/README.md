# 급등/급락 알림 시스템

한국 주식 시장을 위한 실시간 급등/급락 감지 및 알림 시스템입니다.

## 🎯 주요 기능

- **실시간 가격 모니터링**: 종목별 가격 및 거래량 추적
- **급등/급락 감지**: 사용자 정의 임계값 기반 조건 검사
- **스마트 알림 제어**: 중복 방지, 쿨다운, 시간당 제한
- **거래시간 필터링**: 장중에만 알림 발송
- **다중 사용자 지원**: 사용자별 개별 설정
- **확장 가능한 아키텍처**: 모듈화된 설계

## 📁 구조

```
src/alert/
├── __init__.py                    # 모듈 초기화
├── alert_system.py               # 메인 시스템 클래스
├── price_monitor.py              # 가격 모니터링
├── threshold_checker.py          # 임계값 검사
├── notification_controller.py    # 알림 제어
├── example.py                    # 사용 예제
├── test_alert_system.py         # 테스트 코드
└── README.md                     # 이 파일
```

## 🚀 빠른 시작

### 1. 기본 설정

```python
import asyncio
from alert import AlertSystem

# 시스템 초기화
alert_system = AlertSystem(
    enable_trading_time_filter=True,  # 거래시간 필터링
    max_history_minutes=30           # 가격 히스토리 보관 시간
)

# 종목 추가
alert_system.add_symbol(
    symbol="005930",           # 삼성전자
    surge_threshold=5.0,       # 급등 임계값: +5%
    plunge_threshold=-3.0,     # 급락 임계값: -3%
    volume_threshold=300.0,    # 거래량 급증: 300%
    time_window=5             # 시간 창: 5분
)
```

### 2. 시스템 실행

```python
async def main():
    # 시스템 시작
    await alert_system.start()
    
    # 가격 업데이트 (실제로는 API에서 받아옴)
    alert_system.update_price("005930", 75000, 50000)
    
    try:
        # 메인 로직
        await asyncio.sleep(60)  # 1분간 모니터링
    finally:
        # 시스템 종료
        await alert_system.stop()

asyncio.run(main())
```

### 3. 알림 핸들러 추가

```python
async def telegram_notification(record):
    """텔레그램 알림 핸들러"""
    condition = record.alert_condition
    message = f"🚨 {condition.alert_type.value}: {condition.message}"
    
    # 텔레그램 봇으로 메시지 발송
    # await send_telegram_message(message)
    print(message)

# 핸들러 등록
alert_system.notification_controller.add_notification_handler(
    telegram_notification
)
```

## 📊 핵심 클래스

### AlertSystem
메인 시스템 클래스로 모든 컴포넌트를 통합합니다.

```python
# 시스템 상태 확인
status = alert_system.get_system_status()
print(f"실행 상태: {status.is_running}")
print(f"모니터링 종목: {status.monitored_symbols_count}개")

# 종목 정보 조회
info = alert_system.get_symbol_info("005930")
print(f"현재가: {info['price_stats']['current_price']:,}원")
```

### PriceMonitor
실시간 가격 데이터를 모니터링합니다.

```python
# 가격 변동률 계산
change_rate = alert_system.price_monitor.calculate_price_change_rate("005930", 5)
print(f"5분 변동률: {change_rate:+.2f}%")

# 거래량 변동률
volume_rate = alert_system.price_monitor.calculate_volume_change_rate("005930", 30)
print(f"거래량 변화: {volume_rate:.1f}%")
```

### ThresholdChecker
급등/급락 조건을 검사합니다.

```python
# 임계값 설정
alert_system.threshold_checker.set_threshold(
    symbol="005930",
    surge_threshold=7.0,     # 7% 급등
    plunge_threshold=-5.0,   # 5% 급락
    enabled=True
)

# 거래시간 확인
is_trading = alert_system.threshold_checker.is_trading_hours()
print(f"거래시간: {'예' if is_trading else '아니오'}")
```

### NotificationController
알림 발송을 제어합니다.

```python
# 사용자 설정
alert_system.notification_controller.update_user_settings(
    user_id="user123",
    enabled=True,
    max_notifications_per_hour=15,  # 시간당 최대 15개
    cooldown_minutes=10            # 동일 종목 10분 쿨다운
)

# 알림 히스토리 조회
history = alert_system.notification_controller.get_notification_history(
    symbol="005930", 
    hours=24
)
```

## ⚙️ 고급 설정

### 사용자별 알림 설정

```python
from alert.threshold_checker import AlertType

# 사용자 설정 조회
settings = alert_system.notification_controller.get_user_settings("user123")

# 알림 유형 설정 (급등만 받기)
settings.enabled_alert_types = {AlertType.SURGE}

# 우선순위 설정 (높은 우선순위만)
settings.min_priority = 1  # 1: 높음, 2: 보통, 3: 낮음
```

### 이벤트 핸들러

```python
# 가격 업데이트 이벤트
def on_price_update(symbol, price, volume):
    print(f"{symbol}: {price:,}원 (거래량: {volume:,})")

alert_system.add_price_update_handler(on_price_update)

# 알림 발생 이벤트
def on_alert(condition, record):
    if condition.alert_type == AlertType.SURGE:
        print(f"🔥 {condition.symbol} 급등!")

alert_system.add_alert_handler(on_alert)
```

### 배치 종목 추가

```python
# 여러 종목 한번에 추가
symbols = ["005930", "000660", "035420", "005380"]

for symbol in symbols:
    alert_system.add_symbol(
        symbol=symbol,
        surge_threshold=5.0,
        plunge_threshold=-3.0
    )
```

## 📈 알림 조건

### 기본 임계값
- **급등**: 5분 내 +5% 이상 상승
- **급락**: 5분 내 -3% 이상 하락
- **거래량 급증**: 30분 평균 대비 300% 이상

### 거래시간
- **정규시장**: 09:00 ~ 15:30
- **점심시간 제외**: 12:00 ~ 13:00
- **주말 제외**: 토요일, 일요일

### 쿨다운 정책
- **동일 종목**: 10분간 중복 알림 방지
- **시간당 제한**: 사용자당 20개까지
- **우선순위 기반**: 높은 우선순위 우선 발송

## 🧪 테스트

```bash
# 테스트 실행
cd src/alert
python test_alert_system.py

# 예제 실행
python example.py
```

## 📊 모니터링

### 시스템 통계

```python
# 알림 통계 (24시간)
stats = alert_system.notification_controller.get_statistics(hours=24)
print(f"총 알림: {stats['total_notifications']}건")
print(f"성공률: {stats['success_rate']:.1f}%")

# 종목별 통계
for symbol, count in stats['by_symbol'].items():
    print(f"{symbol}: {count}건")
```

### 성능 메트릭

```python
status = alert_system.get_system_status()
print(f"업타임: {status.uptime_seconds/3600:.1f}시간")
print(f"오류 수: {status.error_count}건")
print(f"마지막 업데이트: {status.last_update_time}")
```

## 🚨 알림 유형

| 유형 | 설명 | 기본 임계값 | 우선순위 |
|------|------|------------|----------|
| 급등 | 단시간 급격한 상승 | +5% (5분) | 높음 |
| 급락 | 단시간 급격한 하락 | -3% (5분) | 높음 |
| 거래량급증 | 평균 대비 거래량 증가 | 300% (30분) | 보통 |

## 🔧 문제 해결

### 일반적인 문제

1. **알림이 오지 않음**
   - 거래시간 필터 확인: `alert_system.is_trading_hours()`
   - 임계값 설정 확인: `alert_system.get_symbol_info(symbol)`
   - 쿨다운 상태 확인: `notification_controller.get_cooldown_status()`

2. **너무 많은 알림**
   - 임계값 조정: 더 높은 값으로 설정
   - 시간당 제한 설정: `max_notifications_per_hour` 낮추기
   - 쿨다운 시간 증가: `cooldown_minutes` 늘리기

3. **성능 이슈**
   - 히스토리 보관 시간 단축: `max_history_minutes` 줄이기
   - 모니터링 간격 조정: `set_monitor_interval()` 사용

### 로그 확인

```python
import logging

# 디버그 로깅 활성화
logging.getLogger('alert').setLevel(logging.DEBUG)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

## 📝 라이센스

이 프로젝트는 MIT 라이센스를 따릅니다.