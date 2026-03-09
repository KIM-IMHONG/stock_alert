"""
급등/급락 알림 시스템 사용 예제

기본적인 사용법과 고급 설정 방법을 보여줍니다.
"""

import asyncio
import logging
import random
import time
from typing import List

from alert_system import AlertSystem
from threshold_checker import AlertCondition
from notification_controller import NotificationRecord


# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class TelegramNotificationHandler:
    """텔레그램 알림 핸들러 예제"""
    
    def __init__(self, bot_token: str = None, chat_id: str = None):
        self.bot_token = bot_token
        self.chat_id = chat_id
        
    async def send_alert(self, record: NotificationRecord):
        """텔레그램으로 알림 발송"""
        condition = record.alert_condition
        
        # 실제 구현에서는 telegram bot API 호출
        print(f"📱 텔레그램 알림: {condition.message}")
        
        # 가상의 발송 시뮬레이션
        await asyncio.sleep(0.1)


async def simulate_price_data(alert_system: AlertSystem, symbols: List[str]):
    """가격 데이터 시뮬레이션"""
    base_prices = {
        "005930": 75000,   # 삼성전자
        "000660": 145000,  # SK하이닉스
        "035420": 310000,  # NAVER
        "005380": 480000,  # 현대차
        "006400": 22000,   # 삼성SDI
    }
    
    print("📈 가격 데이터 시뮬레이션 시작...")
    
    for i in range(100):  # 100회 업데이트
        for symbol in symbols:
            if symbol not in base_prices:
                base_prices[symbol] = 50000
                
            # 랜덤한 가격 변동 시뮬레이션
            base_price = base_prices[symbol]
            
            # 일반적인 변동 (-1% ~ +1%)
            change_rate = random.uniform(-1, 1)
            
            # 가끔 큰 변동 발생 (급등/급락 테스트)
            if random.random() < 0.05:  # 5% 확률
                if random.random() < 0.5:
                    change_rate = random.uniform(5, 10)  # 급등
                else:
                    change_rate = random.uniform(-10, -3)  # 급락
                    
            new_price = base_price * (1 + change_rate / 100)
            volume = random.randint(1000, 100000)
            
            alert_system.update_price(symbol, new_price, volume)
            base_prices[symbol] = new_price
            
        await asyncio.sleep(1)  # 1초 대기
        
    print("📈 가격 데이터 시뮬레이션 완료")


async def main():
    """메인 함수"""
    print("🚨 급등/급락 알림 시스템 예제 시작")
    
    # 1. 알림 시스템 초기화
    alert_system = AlertSystem(
        enable_trading_time_filter=False,  # 예제에서는 거래시간 필터 비활성화
        max_history_minutes=30
    )
    
    # 2. 텔레그램 핸들러 추가 (예제)
    telegram_handler = TelegramNotificationHandler()
    alert_system.notification_controller.add_notification_handler(telegram_handler.send_alert)
    
    # 3. 커스텀 알림 핸들러 추가
    def custom_alert_handler(condition: AlertCondition, record: NotificationRecord):
        if condition.alert_type.value == "급등":
            print(f"🔥 급등 감지! {condition.symbol}: {condition.current_value:+.2f}%")
        elif condition.alert_type.value == "급락":
            print(f"💥 급락 감지! {condition.symbol}: {condition.current_value:+.2f}%")
    
    alert_system.add_alert_handler(custom_alert_handler)
    
    # 4. 모니터링할 종목 추가
    symbols = ["005930", "000660", "035420", "005380", "006400"]
    
    for symbol in symbols:
        alert_system.add_symbol(
            symbol=symbol,
            surge_threshold=5.0,    # 급등: +5%
            plunge_threshold=-3.0,  # 급락: -3%
            volume_threshold=300.0, # 거래량: 300%
            time_window=5          # 5분 기준
        )
    
    # 5. 사용자 알림 설정
    alert_system.notification_controller.update_user_settings(
        user_id="user1",
        enabled=True,
        max_notifications_per_hour=10,
        cooldown_minutes=5
    )
    
    # 6. 시스템 시작
    await alert_system.start()
    
    try:
        # 7. 가격 데이터 시뮬레이션과 모니터링
        await asyncio.gather(
            simulate_price_data(alert_system, symbols),
            show_system_status(alert_system)
        )
        
    finally:
        # 8. 시스템 종료
        await alert_system.stop()
        
    # 9. 최종 통계 출력
    await show_final_statistics(alert_system)


async def show_system_status(alert_system: AlertSystem):
    """시스템 상태 모니터링"""
    print("📊 시스템 상태 모니터링 시작...")
    
    for i in range(20):  # 20번 상태 체크 (20초간)
        await asyncio.sleep(5)  # 5초마다 체크
        
        status = alert_system.get_system_status()
        print(f"\n=== 시스템 상태 (T+{i*5:02d}초) ===")
        print(f"실행 상태: {'🟢 실행중' if status.is_running else '🔴 중지'}")
        print(f"모니터링 종목: {status.monitored_symbols_count}개")
        print(f"24시간 알림: {status.total_notifications_24h}건")
        print(f"업타임: {status.uptime_seconds:.1f}초")
        print(f"오류 수: {status.error_count}건")
        
        # 각 종목별 현황
        symbols_info = alert_system.get_all_symbols_info()
        for symbol, info in symbols_info.items():
            stats = info.get('price_stats', {})
            price = stats.get('current_price', 0)
            change_5m = stats.get('price_change_5m', 0)
            
            if price > 0 and change_5m is not None:
                emoji = "🔥" if change_5m > 5 else "💥" if change_5m < -3 else "📈" if change_5m > 0 else "📉"
                print(f"  {emoji} {symbol}: {price:,.0f}원 ({change_5m:+.2f}%)")


async def show_final_statistics(alert_system: AlertSystem):
    """최종 통계 출력"""
    print("\n" + "="*50)
    print("📊 최종 통계")
    print("="*50)
    
    # 전체 통계
    stats = alert_system.notification_controller.get_statistics(hours=1)
    print(f"총 알림 수: {stats['total_notifications']}건")
    print(f"성공률: {stats['success_rate']:.1f}%")
    
    # 상태별 통계
    print("\n상태별 알림:")
    for status, count in stats['by_status'].items():
        print(f"  {status}: {count}건")
        
    # 종목별 통계
    print("\n종목별 알림:")
    for symbol, count in stats['by_symbol'].items():
        print(f"  {symbol}: {count}건")
        
    # 알림 유형별 통계
    print("\n알림 유형별:")
    for alert_type, count in stats['by_alert_type'].items():
        print(f"  {alert_type}: {count}건")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 시스템 종료")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        logging.exception("예제 실행 중 오류")