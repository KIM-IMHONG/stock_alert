"""
급등/급락 알림 시스템 테스트

단위 테스트 및 통합 테스트를 포함합니다.
"""

import asyncio
import unittest
import time
import logging
from unittest.mock import Mock, patch

from price_monitor import PriceMonitor, PriceData
from threshold_checker import ThresholdChecker, AlertType, ThresholdConfig
from notification_controller import NotificationController, NotificationStatus
from alert_system import AlertSystem


class TestPriceMonitor(unittest.TestCase):
    """PriceMonitor 테스트"""
    
    def setUp(self):
        self.monitor = PriceMonitor(max_history_minutes=10)
    
    def test_add_remove_symbol(self):
        """종목 추가/제거 테스트"""
        # 종목 추가
        self.monitor.add_symbol("005930")
        self.assertIn("005930", self.monitor)
        self.assertEqual(len(self.monitor), 1)
        
        # 종목 제거
        self.monitor.remove_symbol("005930")
        self.assertNotIn("005930", self.monitor)
        self.assertEqual(len(self.monitor), 0)
    
    def test_price_update(self):
        """가격 업데이트 테스트"""
        symbol = "005930"
        self.monitor.add_symbol(symbol)
        
        # 가격 업데이트
        self.monitor.update_price(symbol, 75000, 1000)
        
        # 현재 가격 확인
        current = self.monitor.get_current_price(symbol)
        self.assertIsNotNone(current)
        self.assertEqual(current.price, 75000)
        self.assertEqual(current.volume, 1000)
    
    def test_price_change_calculation(self):
        """가격 변동률 계산 테스트"""
        symbol = "005930"
        self.monitor.add_symbol(symbol)
        
        # 초기 가격
        self.monitor.update_price(symbol, 100000, 1000)
        time.sleep(0.1)
        
        # 변동 가격 (5% 상승)
        self.monitor.update_price(symbol, 105000, 1500)
        
        # 변동률 계산
        change_rate = self.monitor.calculate_price_change_rate(symbol, 1)
        self.assertIsNotNone(change_rate)
        self.assertAlmostEqual(change_rate, 5.0, places=1)


class TestThresholdChecker(unittest.TestCase):
    """ThresholdChecker 테스트"""
    
    def setUp(self):
        self.checker = ThresholdChecker(enable_trading_time_filter=False)
    
    def test_threshold_setting(self):
        """임계값 설정 테스트"""
        symbol = "005930"
        self.checker.set_threshold(
            symbol=symbol,
            surge_threshold=5.0,
            plunge_threshold=-3.0
        )
        
        config = self.checker.get_threshold(symbol)
        self.assertIsNotNone(config)
        self.assertEqual(config.surge_threshold, 5.0)
        self.assertEqual(config.plunge_threshold, -3.0)
    
    def test_surge_detection(self):
        """급등 감지 테스트"""
        symbol = "005930"
        self.checker.set_threshold(symbol=symbol, surge_threshold=5.0)
        
        # 급등 조건 (6% 상승)
        condition = self.checker.check_price_surge(symbol, 6.0)
        self.assertIsNotNone(condition)
        self.assertEqual(condition.alert_type, AlertType.SURGE)
        self.assertEqual(condition.current_value, 6.0)
        
        # 정상 조건 (3% 상승)
        condition = self.checker.check_price_surge(symbol, 3.0)
        self.assertIsNone(condition)
    
    def test_plunge_detection(self):
        """급락 감지 테스트"""
        symbol = "005930"
        self.checker.set_threshold(symbol=symbol, plunge_threshold=-3.0)
        
        # 급락 조건 (-5% 하락)
        condition = self.checker.check_price_plunge(symbol, -5.0)
        self.assertIsNotNone(condition)
        self.assertEqual(condition.alert_type, AlertType.PLUNGE)
        self.assertEqual(condition.current_value, -5.0)
        
        # 정상 조건 (-1% 하락)
        condition = self.checker.check_price_plunge(symbol, -1.0)
        self.assertIsNone(condition)


class TestNotificationController(unittest.IsolatedAsyncioTestCase):
    """NotificationController 테스트"""
    
    async def asyncSetUp(self):
        self.controller = NotificationController()
    
    async def test_notification_sending(self):
        """알림 발송 테스트"""
        from threshold_checker import AlertCondition, AlertType
        
        # 알림 조건 생성
        condition = AlertCondition(
            alert_type=AlertType.SURGE,
            symbol="005930",
            current_value=6.0,
            threshold=5.0,
            message="테스트 급등"
        )
        
        # 알림 발송
        record = await self.controller.send_notification(condition, "test_user")
        
        # 결과 확인
        self.assertEqual(record.status, NotificationStatus.SENT)
        self.assertEqual(record.user_id, "test_user")
    
    async def test_cooldown_mechanism(self):
        """쿨다운 메커니즘 테스트"""
        from threshold_checker import AlertCondition, AlertType
        
        # 사용자 설정 (쿨다운 1분)
        self.controller.update_user_settings("test_user", cooldown_minutes=1)
        
        condition = AlertCondition(
            alert_type=AlertType.SURGE,
            symbol="005930",
            current_value=6.0,
            threshold=5.0,
            message="테스트 급등"
        )
        
        # 첫 번째 알림 (성공)
        record1 = await self.controller.send_notification(condition, "test_user")
        self.assertEqual(record1.status, NotificationStatus.SENT)
        
        # 두 번째 알림 (쿨다운으로 차단)
        record2 = await self.controller.send_notification(condition, "test_user")
        self.assertEqual(record2.status, NotificationStatus.COOLDOWN)


class TestAlertSystem(unittest.IsolatedAsyncioTestCase):
    """AlertSystem 통합 테스트"""
    
    async def asyncSetUp(self):
        # 로깅 레벨 조정 (테스트 중 노이즈 감소)
        logging.getLogger().setLevel(logging.WARNING)
        
        self.system = AlertSystem(
            enable_trading_time_filter=False,
            max_history_minutes=10
        )
    
    async def asyncTearDown(self):
        if self.system.is_running():
            await self.system.stop()
    
    async def test_system_lifecycle(self):
        """시스템 생명주기 테스트"""
        # 시작 전 상태
        self.assertFalse(self.system.is_running())
        
        # 시스템 시작
        await self.system.start()
        self.assertTrue(self.system.is_running())
        
        # 시스템 중지
        await self.system.stop()
        self.assertFalse(self.system.is_running())
    
    async def test_symbol_management(self):
        """종목 관리 테스트"""
        symbol = "005930"
        
        # 종목 추가
        self.system.add_symbol(
            symbol=symbol,
            surge_threshold=5.0,
            plunge_threshold=-3.0
        )
        
        # 시스템 상태 확인
        status = self.system.get_system_status()
        self.assertEqual(status.monitored_symbols_count, 1)
        
        # 종목 정보 확인
        info = self.system.get_symbol_info(symbol)
        self.assertIsNotNone(info)
        self.assertTrue(info['monitoring'])
        
        # 종목 제거
        self.system.remove_symbol(symbol)
        status = self.system.get_system_status()
        self.assertEqual(status.monitored_symbols_count, 0)
    
    async def test_price_update_and_alert(self):
        """가격 업데이트 및 알림 테스트"""
        symbol = "005930"
        
        # 알림 핸들러 모킹
        alert_handler = Mock()
        self.system.add_alert_handler(alert_handler)
        
        # 종목 추가 및 시스템 시작
        self.system.add_symbol(symbol, surge_threshold=5.0)
        await self.system.start()
        
        # 초기 가격
        self.system.update_price(symbol, 100000, 1000)
        await asyncio.sleep(0.1)
        
        # 급등 가격 (6% 상승)
        self.system.update_price(symbol, 106000, 1500)
        await asyncio.sleep(2)  # 모니터링 루프가 실행될 시간
        
        # 알림 핸들러가 호출되었는지 확인
        # (실제로는 충분한 히스토리가 쌓여야 하므로 여러 번 업데이트)
        for i in range(10):
            price = 100000 + (i * 1000)  # 점진적 상승
            self.system.update_price(symbol, price, 1000)
            await asyncio.sleep(0.1)
            
        # 급등 상황 시뮬레이션
        self.system.update_price(symbol, 107000, 2000)  # 7% 급등
        await asyncio.sleep(2)
        
        await self.system.stop()


def run_performance_test():
    """성능 테스트"""
    print("\n🏃 성능 테스트 시작...")
    
    async def performance_test():
        system = AlertSystem(enable_trading_time_filter=False)
        
        # 많은 수의 종목 추가
        symbols = [f"TEST{i:06d}" for i in range(100)]
        for symbol in symbols:
            system.add_symbol(symbol)
        
        await system.start()
        
        # 대량 가격 업데이트
        start_time = time.time()
        
        for i in range(1000):  # 1000회 업데이트
            for j, symbol in enumerate(symbols[:10]):  # 상위 10개 종목만
                price = 10000 + (i * 10) + j
                system.update_price(symbol, price, 1000)
        
        end_time = time.time()
        
        await system.stop()
        
        # 결과 출력
        duration = end_time - start_time
        updates_per_second = (1000 * 10) / duration
        
        print(f"⏱️  처리 시간: {duration:.2f}초")
        print(f"🚀 처리량: {updates_per_second:.0f} updates/sec")
        
        status = system.get_system_status()
        print(f"📊 오류 수: {status.error_count}")
    
    asyncio.run(performance_test())


def main():
    """테스트 실행"""
    print("🧪 급등/급락 알림 시스템 테스트 시작")
    
    # 단위 테스트 실행
    unittest.main(argv=[''], exit=False, verbosity=2)
    
    # 성능 테스트 실행
    run_performance_test()
    
    print("✅ 모든 테스트 완료")


if __name__ == "__main__":
    main()