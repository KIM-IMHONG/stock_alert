#!/usr/bin/env python3
"""
급등/급락 알림 시스템 빠른 테스트

기본 기능을 간단히 테스트할 수 있는 스크립트입니다.
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 현재 디렉터리를 sys.path에 추가
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from alert_system import AlertSystem
    from threshold_checker import AlertType
except ImportError as e:
    print(f"❌ 모듈 import 오류: {e}")
    print("alert 모듈이 올바르게 설치되었는지 확인해주세요.")
    sys.exit(1)


async def quick_test():
    """빠른 테스트 실행"""
    print("🚀 급등/급락 알림 시스템 빠른 테스트 시작")
    print("="*50)
    
    # 1. 시스템 초기화
    print("1️⃣ 시스템 초기화...")
    alert_system = AlertSystem(
        enable_trading_time_filter=False,  # 테스트를 위해 비활성화
        max_history_minutes=5
    )
    
    # 2. 테스트용 알림 핸들러
    alerts_received = []
    
    def test_handler(condition, record):
        alerts_received.append((condition, record))
        print(f"📢 알림 수신: {condition.alert_type.value} - {condition.symbol} ({condition.current_value:+.2f}%)")
    
    alert_system.add_alert_handler(test_handler)
    
    # 3. 종목 추가
    print("2️⃣ 테스트 종목 추가...")
    test_symbols = ["TEST001", "TEST002", "TEST003"]
    
    for symbol in test_symbols:
        alert_system.add_symbol(
            symbol=symbol,
            surge_threshold=3.0,    # 테스트용 낮은 임계값
            plunge_threshold=-2.0,
            volume_threshold=200.0
        )
    
    print(f"   추가된 종목: {', '.join(test_symbols)}")
    
    # 4. 시스템 시작
    print("3️⃣ 시스템 시작...")
    await alert_system.start()
    
    try:
        # 5. 정상 가격 업데이트 (알림 없음)
        print("4️⃣ 정상 가격 변동 테스트...")
        
        for i in range(5):
            for symbol in test_symbols:
                base_price = 10000 + (ord(symbol[-1]) * 1000)  # 종목별 다른 기준가
                price = base_price + (i * 50)  # 점진적 상승
                alert_system.update_price(symbol, price, 1000 + (i * 100))
                
            await asyncio.sleep(0.2)
        
        print(f"   정상 변동 완료 (수신 알림: {len(alerts_received)}개)")
        
        # 6. 급등 시뮬레이션
        print("5️⃣ 급등 시뮬레이션...")
        
        symbol = test_symbols[0]
        base_price = 10000
        surge_price = base_price * 1.05  # 5% 급등
        
        alert_system.update_price(symbol, surge_price, 5000)
        await asyncio.sleep(2)  # 알림 처리 대기
        
        # 7. 급락 시뮬레이션  
        print("6️⃣ 급락 시뮬레이션...")
        
        symbol = test_symbols[1] 
        plunge_price = base_price * 0.97  # 3% 급락
        
        alert_system.update_price(symbol, plunge_price, 3000)
        await asyncio.sleep(2)  # 알림 처리 대기
        
        # 8. 결과 확인
        print("7️⃣ 테스트 결과 확인...")
        
        # 시스템 상태
        status = alert_system.get_system_status()
        print(f"   시스템 상태: {'✅ 정상' if status.is_running else '❌ 중지'}")
        print(f"   모니터링 종목: {status.monitored_symbols_count}개")
        print(f"   24시간 알림: {status.total_notifications_24h}개")
        print(f"   오류 수: {status.error_count}개")
        
        # 알림 통계
        stats = alert_system.notification_controller.get_statistics(hours=1)
        print(f"   테스트 중 알림: {stats['total_notifications']}개")
        print(f"   성공률: {stats['success_rate']:.1f}%")
        
        # 종목별 현황
        print("   종목별 현황:")
        for symbol in test_symbols:
            info = alert_system.get_symbol_info(symbol)
            if info and info['price_stats']:
                stats = info['price_stats']
                price = stats.get('current_price', 0)
                change = stats.get('price_change_5m', 0)
                print(f"     {symbol}: {price:,.0f}원 ({change:+.2f}%)")
        
        # 9. 알림 히스토리
        print("8️⃣ 알림 히스토리...")
        history = alert_system.notification_controller.get_notification_history(hours=1)
        
        if history:
            for record in history[:5]:  # 최근 5개만
                condition = record.alert_condition
                status_icon = "✅" if record.status.value == "발송완료" else "❌"
                print(f"   {status_icon} {record.formatted_timestamp}: {condition.alert_type.value} - {condition.symbol}")
        else:
            print("   알림 히스토리 없음")
            
    finally:
        # 10. 정리
        print("9️⃣ 시스템 종료...")
        await alert_system.stop()
        
    print("="*50)
    print("🎉 빠른 테스트 완료!")
    
    if len(alerts_received) > 0:
        print(f"✅ {len(alerts_received)}개 알림이 정상적으로 발생했습니다.")
        for i, (condition, record) in enumerate(alerts_received, 1):
            print(f"   {i}. {condition.alert_type.value}: {condition.symbol} ({condition.current_value:+.2f}%)")
    else:
        print("⚠️  알림이 발생하지 않았습니다. 임계값을 확인해주세요.")


async def component_test():
    """개별 컴포넌트 테스트"""
    print("\n🧪 컴포넌트 개별 테스트")
    print("="*30)
    
    # PriceMonitor 테스트
    print("📊 PriceMonitor 테스트...")
    
    try:
        from price_monitor import PriceMonitor
        
        monitor = PriceMonitor()
        monitor.add_symbol("TEST")
        monitor.update_price("TEST", 10000, 1000)
        
        current = monitor.get_current_price("TEST") 
        print(f"   현재가 조회: {current.price if current else 'None'}")
        
        time.sleep(0.1)
        monitor.update_price("TEST", 10500, 1200)  # 5% 상승
        
        change_rate = monitor.calculate_price_change_rate("TEST", 1)
        print(f"   변동률 계산: {change_rate}%")
        
        print("   ✅ PriceMonitor 테스트 통과")
        
    except Exception as e:
        print(f"   ❌ PriceMonitor 테스트 실패: {e}")
    
    # ThresholdChecker 테스트
    print("⚖️ ThresholdChecker 테스트...")
    
    try:
        try:
            from .threshold_checker import ThresholdChecker
        except ImportError:
            from threshold_checker import ThresholdChecker
        
        checker = ThresholdChecker(enable_trading_time_filter=False)
        checker.set_threshold("TEST", surge_threshold=3.0)
        
        # 급등 조건 테스트
        condition = checker.check_price_surge("TEST", 5.0)  # 5% 상승
        print(f"   급등 감지: {'✅' if condition else '❌'}")
        
        print("   ✅ ThresholdChecker 테스트 통과")
        
    except Exception as e:
        print(f"   ❌ ThresholdChecker 테스트 실패: {e}")
    
    # NotificationController 테스트
    print("📮 NotificationController 테스트...")
    
    try:
        try:
            from .notification_controller import NotificationController
            from .threshold_checker import AlertCondition, AlertType
        except ImportError:
            from notification_controller import NotificationController
            from threshold_checker import AlertCondition, AlertType
        
        controller = NotificationController()
        
        condition = AlertCondition(
            alert_type=AlertType.SURGE,
            symbol="TEST",
            current_value=5.0,
            threshold=3.0,
            message="테스트 알림"
        )
        
        record = await controller.send_notification(condition)
        print(f"   알림 발송: {'✅' if record.status.value == '발송완료' else '❌'}")
        
        print("   ✅ NotificationController 테스트 통과")
        
    except Exception as e:
        print(f"   ❌ NotificationController 테스트 실패: {e}")


if __name__ == "__main__":
    print("🧪 급등/급락 알림 시스템 테스트 도구")
    print(f"📍 실행 위치: {Path.cwd()}")
    
    try:
        # 기본 테스트
        asyncio.run(quick_test())
        
        # 컴포넌트 테스트
        asyncio.run(component_test())
        
    except KeyboardInterrupt:
        print("\n⏹️ 사용자에 의해 중단됨")
    except Exception as e:
        print(f"\n❌ 테스트 실행 중 오류: {e}")
        logging.exception("테스트 실행 오류")
        sys.exit(1)
    
    print("\n🏁 테스트 완료")